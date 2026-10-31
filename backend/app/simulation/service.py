"""Colony economic adapter around the generic, universe-scoped scheduler.

Internal helpers only; future HTTP commands must authenticate and verify membership/permissions.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictInt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import Colony
from app.simulation.clock import utc
from app.simulation.models import ColonyTimeline, ResourceBalance, ScheduledEvent
from app.simulation.production import RESOURCES, ProductionState, amount, produce
from app.simulation.scheduler import (
    CatchUp,
    IdempotencyConflict,
    Scheduler,
    TimelineError,
    create_stream,
    lock_stream,
    retry_blocked,
)
from app.simulation.scheduler import (
    schedule as schedule_event,
)

__all__ = [
    "IdempotencyConflict",
    "TimeEngine",
    "TimelineError",
    "change_rate",
    "initialize",
    "retry_blocked",
    "schedule",
    "settle",
]


def lock_timeline(session: Session, colony_id: UUID) -> ColonyTimeline:
    timeline = session.get(ColonyTimeline, colony_id)
    if timeline is None:
        raise TimelineError("Colony timeline is not initialized")
    lock_stream(session, timeline.stream_id, timeline.universe_id)
    session.refresh(timeline)
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
    at = times.pop()
    stream = create_stream(session, colony.universe_id, at)
    session.add(
        ColonyTimeline(
            colony_id=colony_id, universe_id=colony.universe_id, stream_id=stream.id, settled_at=at
        )
    )
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
    return schedule_event(
        session,
        timeline.stream_id,
        timeline.universe_id,
        key=key,
        kind=kind,
        due_at=due_at,
        payload=payload,
    )


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
    timeline = session.scalar(
        select(ColonyTimeline).where(
            ColonyTimeline.stream_id == event.stream_id,
            ColonyTimeline.universe_id == event.universe_id,
        )
    )
    if timeline is None:
        raise TimelineError("Rate event has no colony adapter in its universe")
    settle(session, timeline, event.due_at)
    row = session.get(ResourceBalance, (timeline.colony_id, payload.resource))
    if row is None:
        raise TimelineError("Resource balance missing")
    row.rate_per_hour = value


class TimeEngine(Scheduler):
    """Production composition: generic scheduler plus the existing colony rate handler."""

    def __init__(self, *args, handlers=None, **kwargs):
        from app.colony.service import complete_construction
        from app.research.service import complete_research

        super().__init__(
            *args,
            handlers=handlers
            if handlers is not None
            else {
                "RESOURCE_RATE_CHANGE": change_rate,
                "CONSTRUCTION_COMPLETE": complete_construction,
                "RESEARCH_COMPLETE": complete_research,
            },
            **kwargs,
        )

    def catch_up(
        self, session: Session, colony_id: UUID, until: datetime, *, limit: int = 100
    ) -> CatchUp:
        timeline = lock_timeline(session, colony_id)
        result = self.catch_up_stream(
            session, timeline.stream_id, timeline.universe_id, until, limit=limit
        )
        if result.complete:
            settle(session, timeline, until)
        return result
