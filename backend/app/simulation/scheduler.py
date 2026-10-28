"""Universe-scoped generic event streams; no dependency on colony economics or ownership types.

Handlers are trusted in-transaction code: no commit, external side effect or other stream lock.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, true
from sqlalchemy.orm import Session, sessionmaker

from app.simulation.clock import Clock, utc
from app.simulation.models import EventStream, ScheduledEvent


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


def create_stream(session: Session, universe_id: UUID, at: datetime) -> EventStream:
    stream = EventStream(universe_id=universe_id, cursor_at=utc(at), next_sequence=1)
    session.add(stream)
    session.flush()
    return stream


def lock_stream(session: Session, stream_id: UUID, universe_id: UUID) -> EventStream:
    stream = session.scalar(
        select(EventStream)
        .where(
            EventStream.id == stream_id,
            EventStream.universe_id == universe_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if stream is None:
        raise TimelineError("Stream missing from requested universe")
    return stream


def advance_cursor(session: Session, stream: EventStream, until: datetime) -> None:
    target = utc(until)
    if target < stream.cursor_at:
        raise TimelineError("Cannot advance stream backwards")
    stream.cursor_at = target
    session.flush()


def schedule(
    session: Session,
    stream_id: UUID,
    universe_id: UUID,
    *,
    key: str,
    kind: str,
    due_at: datetime,
    payload: dict,
) -> ScheduledEvent:
    stream = lock_stream(session, stream_id, universe_id)
    target = utc(due_at)
    if not key or len(key) > 160 or not kind or len(kind) > 64:
        raise TimelineError("Invalid event key or kind")
    # Reject non-JSON and non-finite values before persistence; snapshot caller-owned dictionaries.
    snapshot = json.loads(json.dumps(payload, allow_nan=False))
    if not isinstance(snapshot, dict):
        raise TimelineError("Event payload must be an object")
    existing = session.scalar(
        select(ScheduledEvent).where(
            ScheduledEvent.stream_id == stream_id,
            ScheduledEvent.universe_id == universe_id,
            ScheduledEvent.idempotency_key == key,
        )
    )
    if existing is not None:
        if (existing.event_type, existing.due_at, existing.payload) != (kind, target, snapshot):
            raise IdempotencyConflict("Idempotency key already has a different command")
        return existing
    if target < stream.cursor_at:
        raise TimelineError("Cannot schedule before the settled timeline")
    event = ScheduledEvent(
        stream_id=stream_id,
        universe_id=universe_id,
        sequence=stream.next_sequence,
        idempotency_key=key,
        event_type=kind,
        payload=snapshot,
        due_at=target,
        next_attempt_at=target,
        status="pending",
        attempts=0,
    )
    stream.next_sequence += 1
    session.add(event)
    session.flush()
    return event


def first_pending(session: Session, stream_id: UUID, universe_id: UUID) -> ScheduledEvent | None:
    return session.scalar(
        select(ScheduledEvent)
        .where(
            ScheduledEvent.stream_id == stream_id,
            ScheduledEvent.universe_id == universe_id,
            ScheduledEvent.status != "completed",
        )
        .order_by(ScheduledEvent.due_at, ScheduledEvent.sequence)
        .limit(1)
        .execution_options(populate_existing=True)
    )


class Scheduler:
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
        self.handlers = dict(handlers) if handlers is not None else {}
        self.max_attempts, self.retry_delay = max_attempts, retry_delay

    def _apply(
        self, session: Session, stream: EventStream, event: ScheduledEvent, now: datetime
    ) -> Outcome:
        event.attempts += 1
        session.flush()
        try:
            # A failed handler rolls back its resource changes and follow-ups together.
            with session.begin_nested():
                handler = self.handlers.get(event.event_type)
                if handler is None:
                    raise UnknownEvent("Unregistered event kind")
                advance_cursor(session, stream, event.due_at)
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
                ScheduledEvent.stream_id == EventStream.id,
                ScheduledEvent.universe_id == EventStream.universe_id,
                ScheduledEvent.status != "completed",
            )
            .order_by(ScheduledEvent.due_at, ScheduledEvent.sequence)
            .limit(1)
        )
        first = first.correlate(EventStream).lateral()
        query = (
            select(EventStream)
            .join(first, true())
            .where(
                first.c.status == "pending",
                first.c.due_at <= now,
                first.c.next_attempt_at <= now,
            )
            .order_by(first.c.due_at, first.c.sequence, EventStream.id)
            .limit(1)
        )
        query = query.with_for_update(of=EventStream, skip_locked=True)
        with self.factory.begin() as session:
            stream = session.scalar(query)
            if stream is None:
                return None
            # READ COMMITTED: re-read after taking the lock, never trust a stale candidate.
            event = first_pending(session, stream.id, stream.universe_id)
            if event is None or event.status != "pending" or event.due_at > now:
                return None
            if event.next_attempt_at > now:
                return None
            return self._apply(session, stream, event, now)

    def catch_up_stream(
        self,
        session: Session,
        stream_id: UUID,
        universe_id: UUID,
        until: datetime,
        *,
        limit: int = 100,
    ) -> CatchUp:
        if not 1 <= limit <= 1000:
            raise ValueError("Catch-up limit must be between 1 and 1000")
        target, now = utc(until), utc(self.clock.now())
        if target > now:
            raise TimelineError("Cannot advance a stream into the future")
        stream = lock_stream(session, stream_id, universe_id)
        for count in range(limit):
            event = first_pending(session, stream_id, universe_id)
            if event is None or event.due_at > target:
                advance_cursor(session, stream, target)
                return CatchUp(count, True)
            if event.status == "blocked" or event.next_attempt_at > now:
                return CatchUp(count, False)
            result = self._apply(session, stream, event, now)
            if result.status != "completed":
                return CatchUp(count + 1, False)
        event = first_pending(session, stream_id, universe_id)
        complete = event is None or event.due_at > target
        if complete:
            advance_cursor(session, stream, target)
        return CatchUp(limit, complete)


def retry_blocked(session: Session, event_id: UUID, now: datetime) -> None:
    event = session.get(ScheduledEvent, event_id)
    if event is None:
        raise TimelineError("Event missing")
    lock_stream(session, event.stream_id, event.universe_id)
    session.refresh(event)
    if event.status != "blocked":
        raise TimelineError("Only blocked events can be explicitly retried")
    event.status, event.attempts, event.error_code = "pending", 0, None
    event.next_attempt_at = utc(now)
    session.flush()
