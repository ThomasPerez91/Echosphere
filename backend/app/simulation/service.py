"""Authoritative timeline operations. Call inside an explicit outer transaction.

Handlers may mutate this colony and schedule its follow-ups. They must never commit,
perform external effects or acquire another colony's lock.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictInt
from sqlalchemy import select, true
from sqlalchemy.orm import Session, sessionmaker

from app.persistence.models import Colony
from app.simulation.clock import Clock, utc
from app.simulation.models import ColonyTimeline, ResourceBalance, ScheduledEvent
from app.simulation.production import RESOURCES, ProductionState, amount, produce


class TimelineError(ValueError):
    pass


class IdempotencyConflict(TimelineError):
    pass


class UnknownEvent(TimelineError):
    pass


@dataclass(frozen=True)
class Outcome:
    event_id: UUID
    status: str


@dataclass(frozen=True)
class CatchUp:
    processed: int
    complete: bool


Handler = Callable[[Session, ScheduledEvent], None]


def lock_timeline(session: Session, colony_id: UUID) -> ColonyTimeline:
    timeline = session.scalar(
        select(ColonyTimeline)
        .where(ColonyTimeline.colony_id == colony_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if timeline is None:
        raise TimelineError("Colony timeline is not initialized")
    return timeline


def initialize(session: Session, colony_id: UUID, balances: Mapping[str, ProductionState]) -> None:
    # Lock the parent before creating its lock row, so simultaneous initializations serialize.
    colony = session.scalar(select(Colony).where(Colony.id == colony_id).with_for_update())
    if colony is None or session.get(ColonyTimeline, colony_id) is not None:
        raise TimelineError("Colony missing or already initialized")
    if set(balances) != RESOURCES:
        raise TimelineError("Exactly alloys, flux and data must be supplied explicitly")
    times = {utc(balance.at) for balance in balances.values()}
    if len(times) != 1:
        raise TimelineError("Resource anchors must share one UTC instant")
    session.add(ColonyTimeline(colony_id=colony_id, settled_at=times.pop(), next_sequence=1))
    session.flush()
    for resource, balance in balances.items():
        session.add(
            ResourceBalance(
                colony_id=colony_id,
                resource=resource,
                stock=balance.stock,
                rate_per_hour=balance.rate_per_hour,
                remainder=balance.remainder,
                capacity=balance.capacity,
                updated_at=utc(balance.at),
            )
        )
    session.flush()


def schedule(
    session: Session, colony_id: UUID, *, key: str, kind: str, due_at: datetime, payload: dict
) -> ScheduledEvent:
    timeline = lock_timeline(session, colony_id)
    target = utc(due_at)
    if not key or len(key) > 160 or not kind or len(kind) > 64:
        raise TimelineError("Invalid event key or kind")
    # Reject non-JSON and non-finite values before persistence; snapshot caller-owned dictionaries.
    snapshot = json.loads(json.dumps(payload, allow_nan=False))
    if not isinstance(snapshot, dict):
        raise TimelineError("Event payload must be an object")
    existing = session.scalar(
        select(ScheduledEvent).where(
            ScheduledEvent.colony_id == colony_id,
            ScheduledEvent.idempotency_key == key,
        )
    )
    if existing is not None:
        if (existing.event_type, existing.due_at, existing.payload) != (kind, target, snapshot):
            raise IdempotencyConflict("Idempotency key already has a different command")
        return existing
    if target < timeline.settled_at:
        raise TimelineError("Cannot schedule before the settled timeline")
    event = ScheduledEvent(
        colony_id=colony_id,
        sequence=timeline.next_sequence,
        idempotency_key=key,
        event_type=kind,
        payload=snapshot,
        due_at=target,
        next_attempt_at=target,
        status="pending",
        attempts=0,
    )
    timeline.next_sequence += 1
    session.add(event)
    session.flush()
    return event


def settle(session: Session, timeline: ColonyTimeline, until: datetime) -> None:
    target = utc(until)
    if target < timeline.settled_at:
        raise TimelineError("Cannot settle a timeline backwards")
    rows = session.scalars(
        select(ResourceBalance).where(
            ResourceBalance.colony_id == timeline.colony_id,
        )
    ).all()
    if {row.resource for row in rows} != RESOURCES:
        raise TimelineError("Incomplete resource state")
    for row in rows:
        if row.updated_at != timeline.settled_at:
            raise TimelineError("Inconsistent resource anchor")
        result = produce(
            ProductionState(
                row.stock,
                row.rate_per_hour,
                row.updated_at,
                row.remainder,
                row.capacity,
            ),
            target,
        )
        row.stock, row.remainder, row.updated_at = result.stock, result.remainder, target
    timeline.settled_at = target
    session.flush()


class RateChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource: Literal["alloys", "flux", "data"]
    rate_per_hour: StrictInt


def change_rate(session: Session, event: ScheduledEvent) -> None:
    payload = RateChange.model_validate(event.payload)
    value = amount(payload.rate_per_hour)
    row = session.get(ResourceBalance, (event.colony_id, payload.resource))
    if row is None:
        raise TimelineError("Resource balance missing")
    row.rate_per_hour = value


def first_pending(session: Session, colony_id: UUID) -> ScheduledEvent | None:
    return session.scalar(
        select(ScheduledEvent)
        .where(
            ScheduledEvent.colony_id == colony_id,
            ScheduledEvent.status != "completed",
        )
        .order_by(ScheduledEvent.due_at, ScheduledEvent.sequence)
        .limit(1)
        .execution_options(populate_existing=True)
    )


class TimeEngine:
    def __init__(
        self,
        factory: sessionmaker[Session],
        clock: Clock,
        *,
        handlers: Mapping[str, Handler] | None = None,
        max_attempts: int = 3,
        retry_delay: timedelta = timedelta(seconds=30),
    ):
        if max_attempts < 1 or retry_delay < timedelta(0):
            raise ValueError("Invalid retry policy")
        self.factory, self.clock = factory, clock
        self.handlers = (
            dict(handlers) if handlers is not None else {"RESOURCE_RATE_CHANGE": change_rate}
        )
        self.max_attempts, self.retry_delay = max_attempts, retry_delay

    def _apply(
        self, session: Session, timeline: ColonyTimeline, event: ScheduledEvent, now: datetime
    ) -> Outcome:
        event.attempts += 1
        session.flush()
        try:
            # A failed handler rolls back its resource changes and follow-ups together.
            with session.begin_nested():
                handler = self.handlers.get(event.event_type)
                if handler is None:
                    raise UnknownEvent("Unregistered event kind")
                settle(session, timeline, event.due_at)
                handler(session, event)
                event.status, event.completed_at, event.error_code = "completed", now, None
                session.flush()
        except Exception as error:
            event.error_code = (
                "unknown_event" if isinstance(error, UnknownEvent) else "handler_failed"
            )
            event.next_attempt_at = now + self.retry_delay
            if event.attempts >= self.max_attempts:
                event.status = "blocked"
            session.flush()
        return Outcome(event.id, event.status)

    def process_next(self) -> Outcome | None:
        now = utc(self.clock.now())
        # Only the first outstanding event is eligible; blocked/backoff gates its successors.
        first = (
            select(ScheduledEvent)
            .where(
                ScheduledEvent.colony_id == ColonyTimeline.colony_id,
                ScheduledEvent.status != "completed",
            )
            .order_by(ScheduledEvent.due_at, ScheduledEvent.sequence)
            .limit(1)
        )
        first = first.correlate(ColonyTimeline).lateral()
        query = (
            select(ColonyTimeline)
            .join(first, true())
            .where(
                first.c.status == "pending",
                first.c.due_at <= now,
                first.c.next_attempt_at <= now,
            )
            .order_by(first.c.due_at, first.c.sequence, ColonyTimeline.colony_id)
            .limit(1)
        )
        query = query.with_for_update(of=ColonyTimeline, skip_locked=True)
        with self.factory.begin() as session:
            timeline = session.scalar(query)
            if timeline is None:
                return None
            # READ COMMITTED: re-read after taking the lock, never trust a stale candidate.
            event = first_pending(session, timeline.colony_id)
            if event is None or event.status != "pending" or event.due_at > now:
                return None
            if event.next_attempt_at > now:
                return None
            return self._apply(session, timeline, event, now)

    def catch_up(
        self, session: Session, colony_id: UUID, until: datetime, *, limit: int = 100
    ) -> CatchUp:
        if not 1 <= limit <= 1000:
            raise ValueError("Catch-up limit must be between 1 and 1000")
        target, now = utc(until), utc(self.clock.now())
        if target > now:
            raise TimelineError("Cannot advance a colony into the future")
        timeline = lock_timeline(session, colony_id)
        for count in range(limit):
            event = first_pending(session, colony_id)
            if event is None or event.due_at > target:
                settle(session, timeline, target)
                return CatchUp(count, True)
            if event.status == "blocked" or event.next_attempt_at > now:
                return CatchUp(count, False)
            result = self._apply(session, timeline, event, now)
            if result.status != "completed":
                return CatchUp(count + 1, False)
        event = first_pending(session, colony_id)
        complete = event is None or event.due_at > target
        if complete:
            settle(session, timeline, target)
        return CatchUp(limit, complete)


def retry_blocked(session: Session, event_id: UUID, now: datetime) -> None:
    event = session.get(ScheduledEvent, event_id)
    if event is None:
        raise TimelineError("Event missing")
    lock_timeline(session, event.colony_id)
    session.refresh(event)
    if event.status != "blocked":
        raise TimelineError("Only blocked events can be explicitly retried")
    event.status, event.attempts, event.error_code = "pending", 0, None
    event.next_attempt_at = utc(now)
    session.flush()
