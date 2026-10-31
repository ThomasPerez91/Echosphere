"""Caller-owned transactions: Research stream → sorted financing Colony streams.

Completion touches only its Empire stream. Costs, durations and effects are immutable snapshots.
No Portal, implicit identity, cross-stream handler, second debit or retrospective repricing.
"""

from datetime import timedelta
from uuid import UUID

from pydantic import Field
from sqlalchemy import select

from app.colony.rules import Nonnegative, Positive, Ratio, ResearchRules, StrictModel, Technology
from app.colony.service import (
    ColonyError,
    catch_up_owned,
    owned_colony,
    recoverable_refunds,
    rules_for,
)
from app.persistence.models import Empire
from app.research.models import AcquiredTechnology, EmpireResearch, ResearchOrder
from app.simulation.clock import utc
from app.simulation.models import ResourceBalance, ScheduledEvent
from app.simulation.production import MICRO_UNITS, RESOURCES, amount
from app.simulation.scheduler import (
    IdempotencyConflict,
    TimelineError,
    create_stream,
    lock_stream,
    schedule,
)


class ResearchError(ColonyError):
    pass


class Snapshot(StrictModel):
    ruleset_version: str
    technology_id: str
    technology: Technology
    colony_id: str
    cost: dict[str, Nonnegative]
    base_duration_us: Positive
    duration_us: Positive
    research_speed: Ratio
    bonuses: dict[str, Nonnegative]
    refund_queued_bps: int = Field(strict=True, ge=0, le=10000)
    refund_active_bps: int = Field(strict=True, ge=0, le=10000)


def catalogue(session, universe_id) -> ResearchRules:
    rules = rules_for(session, universe_id)
    if rules.research is None:
        raise ResearchError("Research not enabled by this pinned ruleset", "research_unavailable")
    return rules.research


def lock_research(session, universe_id, empire_id, at):
    catalogue(session, universe_id)
    row = session.get(EmpireResearch, empire_id)
    if row is None:
        # Serialize only initialization; commands subsequently serialize on the stream.
        empire = session.scalar(
            select(Empire)
            .where(Empire.id == empire_id, Empire.universe_id == universe_id)
            .with_for_update()
        )
        if empire is None:
            raise ResearchError("Unknown empire", "empire_not_found")
        row = session.get(EmpireResearch, empire_id, populate_existing=True)
        if row is None:
            stream = create_stream(session, universe_id, utc(at))
            row = EmpireResearch(
                empire_id=empire_id, universe_id=universe_id, stream_id=stream.id, next_sequence=1
            )
            session.add(row)
            session.flush()
    if row.universe_id != universe_id:
        raise ResearchError("Unknown empire", "empire_not_found")
    lock_stream(session, row.stream_id, universe_id)
    session.refresh(row)
    return row


def catch_up(session, engine, universe_id, empire_id, at):
    row = lock_research(session, universe_id, empire_id, at)
    if not engine.catch_up_stream(session, row.stream_id, universe_id, utc(at)).complete:
        raise ResearchError("Research event retry/operator required", "research_busy")
    return row


def coordinate_colony(session, engine, universe_id, empire_id, at):
    """Must run before ANY Colony stream lock (including direct internal commands)."""
    if rules_for(session, universe_id).research is not None:
        catch_up(session, engine, universe_id, empire_id, at)


def acquired(session, empire_id):
    return list(
        session.scalars(
            select(AcquiredTechnology)
            .where(AcquiredTechnology.empire_id == empire_id)
            .execution_options(populate_existing=True)
        )
    )


def bonuses(session, empire_id):
    result = {}
    for row in acquired(session, empire_id):
        result[row.effect] = max(result.get(row.effect, 0), row.reduction_bps)
    return result


def discounted(value, bps):
    # Ceiling: never undercharge a fractional micro-unit; all arithmetic is integer.
    return amount((value * (10000 - bps) + 9999) // 10000)


def quote(session, universe_id, empire_id, technology_id, colony_id):
    rules = rules_for(session, universe_id)
    cat = catalogue(session, universe_id)
    tech = cat.technologies.get(technology_id)
    if tech is None:
        raise ResearchError("Unknown technology", "technology_not_found")
    bonus = bonuses(session, empire_id)
    cost = {r: amount(v * MICRO_UNITS) for r, v in tech.cost.items()}
    cost["data"] = discounted(cost["data"], bonus.get("research_data", 0))
    base = tech.duration_seconds * MICRO_UNITS
    speed = rules.colony.speeds["research"]
    duration = max(
        1,
        (
            base * speed.denominator * (10000 - bonus.get("research_duration", 0))
            + speed.numerator * 10000
            - 1
        )
        // (speed.numerator * 10000),
    )
    return Snapshot(
        ruleset_version=rules.version,
        technology_id=technology_id,
        technology=tech,
        colony_id=str(colony_id),
        cost=cost,
        base_duration_us=base,
        duration_us=duration,
        bonuses=bonus,
        research_speed=speed,
        refund_queued_bps=cat.refund_queued_bps,
        refund_active_bps=cat.refund_active_bps,
    )


def pending(session, empire_id):
    return list(
        session.scalars(
            select(ResearchOrder)
            .where(
                ResearchOrder.empire_id == empire_id,
                ResearchOrder.status.in_(["active", "queued", "blocked"]),
            )
            .order_by(ResearchOrder.sequence)
            .execution_options(populate_existing=True)
        )
    )


def read_snapshot(session, order):
    snap = Snapshot.model_validate(order.snapshot)
    if snap.technology_id != order.technology_id or snap.colony_id != str(order.colony_id):
        raise TimelineError("Research snapshot identity mismatch")
    rules = rules_for(session, order.universe_id)
    if (
        rules.research is None
        or snap.ruleset_version != rules.version
        or rules.research.technologies.get(order.technology_id) != snap.technology
        or snap.research_speed != rules.colony.speeds["research"]
    ):
        raise TimelineError("Research snapshot differs from its pinned definition")
    if set(snap.cost) != RESOURCES or any(type(v) is not int or v < 0 for v in snap.cost.values()):
        raise TimelineError("Invalid snapshotted costs")
    return snap


def validate_start(session, empire_id, technology_id, snap):
    queue = pending(session, empire_id)
    known = {r.technology_id for r in acquired(session, empire_id)}
    if technology_id in known or any(r.technology_id == technology_id for r in queue):
        raise ResearchError("Technology already acquired or reserved", "technology_duplicate")
    if len(queue) >= 2 or any(r.status == "blocked" for r in queue):
        raise ResearchError("Research queue is full or blocked", "queue_full")
    missing = set(snap.technology.requires) - known
    active = next((r for r in queue if r.status == "active"), None)
    if missing and (active is None or missing != {active.technology_id}):
        raise ResearchError("Research prerequisites unmet", "prerequisites_unmet")


def activation_block_reason(session, order, snapshot):
    """Recoverable gameplay validity only. Technical inconsistencies must raise to retry."""
    known = {r.technology_id for r in acquired(session, order.empire_id)}
    if order.technology_id in known:
        raise TimelineError("Reserved technology is already acquired")
    if set(snapshot.technology.requires) - known:
        return "prerequisites_changed"
    return None


def activate_next(session, state, at):
    queue = pending(session, state.empire_id)
    if not queue or queue[0].status in {"active", "blocked"}:
        return
    row = queue[0]
    # Corruption raises to scheduler retry; never gameplay blocked.
    snap = read_snapshot(session, row)
    reason = activation_block_reason(session, row, snap)
    if reason:
        row.status, row.blocked_reason = "blocked", reason
        session.flush()
        return
    row.status, row.started_at = "active", utc(at)
    row.due_at = utc(at) + timedelta(microseconds=snap.duration_us)
    session.flush()
    schedule(
        session,
        state.stream_id,
        state.universe_id,
        key=f"research:{row.id}",
        kind="RESEARCH_COMPLETE",
        due_at=row.due_at,
        payload={"order_id": str(row.id)},
    )


def start(session, engine, universe_id, empire_id, colony_id, *, key, technology_id, at):
    with session.begin_nested():
        owned_colony(session, universe_id, empire_id, colony_id)
        state = catch_up(session, engine, universe_id, empire_id, at)
        if not key or len(key) > 160:
            raise ResearchError("Invalid key", "invalid_request")
        existing = session.scalar(
            select(ResearchOrder)
            .where(ResearchOrder.empire_id == empire_id, ResearchOrder.idempotency_key == key)
            .execution_options(populate_existing=True)
        )
        if existing is not None:
            if (existing.technology_id, existing.colony_id) != (technology_id, colony_id):
                raise IdempotencyConflict("Research key reused with another command")
            return existing
        catch_up_owned(session, engine, universe_id, empire_id, colony_id, at)
        snap = quote(session, universe_id, empire_id, technology_id, colony_id)
        validate_start(session, empire_id, technology_id, snap)
        balances = {r: session.get(ResourceBalance, (colony_id, r)) for r in RESOURCES}
        if any(balances[r].stock < snap.cost[r] for r in RESOURCES):
            raise ResearchError("Insufficient financing resources", "insufficient_resources")
        # Bound due dates before accepting any reservation.
        try:
            utc(at) + timedelta(
                microseconds=sum(
                    read_snapshot(session, r).duration_us for r in pending(session, empire_id)
                )
                + snap.duration_us
            )
        except OverflowError:
            raise ResearchError("Research deadline exceeds datetime representation") from None
        for resource, value in snap.cost.items():
            balances[resource].stock -= value
        row = ResearchOrder(
            empire_id=empire_id,
            universe_id=universe_id,
            colony_id=colony_id,
            sequence=state.next_sequence,
            idempotency_key=key,
            technology_id=technology_id,
            status="queued",
            snapshot=snap.model_dump(),
        )
        state.next_sequence += 1
        session.add(row)
        session.flush()
        activate_next(session, state, at)
        return row


def complete_research(session, event):
    if set(event.payload) != {"order_id"}:
        raise TimelineError("Invalid Research event payload")
    row = session.get(ResearchOrder, UUID(event.payload["order_id"]))
    if row is None or row.universe_id != event.universe_id:
        raise TimelineError("Research order missing from event universe")
    state = session.get(EmpireResearch, row.empire_id)
    if state is None or state.stream_id != event.stream_id:
        raise TimelineError("Research order missing from event stream")
    if event.idempotency_key != f"research:{row.id}":
        raise TimelineError("Invalid Research event identity")
    if row.status in {"completed", "cancelled"}:
        return
    if row.status != "active" or row.due_at != event.due_at:
        raise TimelineError("Research not active at this deadline")
    snap = read_snapshot(session, row)
    session.add(
        AcquiredTechnology(
            empire_id=row.empire_id,
            universe_id=row.universe_id,
            technology_id=row.technology_id,
            acquired_at=event.due_at,
            effect=snap.technology.effect,
            reduction_bps=snap.technology.reduction_bps,
        )
    )
    row.status, row.completed_at = "completed", event.due_at
    session.flush()
    activate_next(session, state, event.due_at)


def cancellation_plan(session, empire_id, order):
    queue = pending(session, empire_id)
    return [
        r
        for r in queue
        if r.id == order.id
        or (
            order.status == "active"
            and order.technology_id in read_snapshot(session, r).technology.requires
        )
    ]


def refund_plan(session, affected):
    result = []
    for colony_id in sorted({r.colony_id for r in affected}, key=str):
        rows = [r for r in affected if r.colony_id == colony_id]
        theoretical = {}
        for row in rows:
            snap = read_snapshot(session, row)
            bps = snap.refund_active_bps if row.status == "active" else snap.refund_queued_bps
            theoretical[str(row.id)] = {r: v * bps // 10000 for r, v in snap.cost.items()}
        balances = {r: session.get(ResourceBalance, (colony_id, r)) for r in RESOURCES}
        actual, recovered, lost = recoverable_refunds(balances, theoretical)
        result.append((colony_id, theoretical, actual, recovered, lost))
    return result


def cancel(session, engine, universe_id, empire_id, order_id, *, at):
    with session.begin_nested():
        state = catch_up(session, engine, universe_id, empire_id, at)
        row = session.scalar(
            select(ResearchOrder)
            .where(
                ResearchOrder.id == order_id,
                ResearchOrder.empire_id == empire_id,
                ResearchOrder.universe_id == universe_id,
            )
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise ResearchError("Unknown order", "order_not_found")
        if row.status == "cancelled":
            return row
        if row.status == "completed":
            raise ResearchError("Completed research cannot be cancelled", "order_completed")
        affected = cancellation_plan(session, empire_id, row)
        for colony_id in sorted({r.colony_id for r in affected}, key=str):
            catch_up_owned(session, engine, universe_id, empire_id, colony_id, at)
        plans = refund_plan(session, affected)
        for colony_id, _, actual, recovered, _ in plans:
            for order in affected:
                if order.colony_id == colony_id:
                    order.refunded = actual[str(order.id)]
            for resource, value in recovered.items():
                balance = session.get(ResourceBalance, (colony_id, resource))
                balance.stock = amount(balance.stock + value)
                if balance.stock == balance.capacity:
                    balance.remainder = 0
        for order in affected:
            if order.status == "active":
                event = session.scalar(
                    select(ScheduledEvent).where(
                        ScheduledEvent.stream_id == state.stream_id,
                        ScheduledEvent.idempotency_key == f"research:{order.id}",
                    )
                )
                if event is None or event.status != "pending":
                    raise TimelineError("Research active event missing or blocked")
                event.status, event.completed_at, event.error_code = (
                    "completed",
                    utc(at),
                    "cancelled",
                )
            order.status, order.cancelled_at = "cancelled", utc(at)
            order.blocked_reason = None
        session.flush()
        activate_next(session, state, at)
        return row
