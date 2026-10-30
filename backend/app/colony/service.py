"""Scoped internal commands. Caller owns the transaction and supplies trusted empire identity.

Every command locks the colony stream and uses a SAVEPOINT so refusal cannot partially spend.
No HTTP endpoints, implicit user, commits, timers or external effects here.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.colony.models import (
    ColonyEconomy,
    ColonyInfrastructure,
    ConstructionOrder,
    UniverseEconomy,
)
from app.colony.rules import Positive, Quote, Ratio, Ruleset, StrictModel
from app.persistence.models import Colony, Planet, Universe
from app.simulation.clock import utc
from app.simulation.models import ColonyTimeline, ResourceBalance, ScheduledEvent
from app.simulation.production import MICRO_UNITS, RESOURCES, ProductionState, amount
from app.simulation.scheduler import IdempotencyConflict, TimelineError
from app.simulation.service import TimeEngine, initialize, lock_timeline, schedule, settle


class ColonyError(ValueError):
    """Refusal with a stable public code; the message remains the internal explanation."""

    def __init__(self, message: str, code: str = "colony_unavailable"):
        super().__init__(message)
        self.code = code


class OrderSnapshot(StrictModel):
    ruleset_version: str
    infrastructure_type: str
    sector_index: Positive
    target_level: Positive
    quote: Quote
    construction_speed: Ratio
    refund_queued_bps: int = Field(strict=True, ge=0, le=10000)
    refund_active_bps: int = Field(strict=True, ge=0, le=10000)


def configure_universe(session: Session, universe_id: UUID, rules: Ruleset) -> None:
    """Pin a validated immutable ruleset snapshot (including per-instance speeds) once."""
    rules = Ruleset.model_validate(rules.model_dump())
    universe = session.scalar(select(Universe).where(Universe.id == universe_id).with_for_update())
    if universe is None:
        raise ColonyError("Unknown universe")
    if session.get(UniverseEconomy, universe_id) is not None:
        raise ColonyError("Universe economics already configured")
    session.add(
        UniverseEconomy(
            universe_id=universe_id, ruleset_version=rules.version, ruleset_data=rules.model_dump()
        )
    )
    session.flush()


def rules_for(session: Session, universe_id: UUID) -> Ruleset:
    row = session.get(UniverseEconomy, universe_id)
    if row is None:
        raise ColonyError("Universe has no economic ruleset")
    rules = Ruleset.model_validate(row.ruleset_data)
    if rules.version != row.ruleset_version:
        raise ColonyError("Ruleset version mismatch")
    return rules


def owned_colony(session: Session, universe_id: UUID, empire_id: UUID, colony_id: UUID) -> Colony:
    colony = session.scalar(
        select(Colony)
        .where(
            Colony.id == colony_id, Colony.universe_id == universe_id, Colony.empire_id == empire_id
        )
        .execution_options(populate_existing=True)
    )
    if colony is None:
        raise ColonyError("Colony unavailable in requested empire/universe", "colony_not_found")
    return colony


def infrastructure_rows(session: Session, colony_id: UUID) -> list[ColonyInfrastructure]:
    return list(
        session.scalars(
            select(ColonyInfrastructure)
            .where(ColonyInfrastructure.colony_id == colony_id)
            .execution_options(populate_existing=True)
        )
    )


def queue_rows(session: Session, colony_id: UUID) -> list[ConstructionOrder]:
    return list(
        session.scalars(
            select(ConstructionOrder)
            .where(
                ConstructionOrder.colony_id == colony_id,
                ConstructionOrder.status.in_(["active", "queued"]),
            )
            .order_by(ConstructionOrder.sequence)
            .execution_options(populate_existing=True)
        )
    )


def refresh_effects(session: Session, colony_id: UUID, rules: Ruleset) -> int:
    production = dict.fromkeys(RESOURCES, 0)
    capacity, bonus = rules.colony.base_capacity * MICRO_UNITS, 0
    for row in infrastructure_rows(session, colony_id):
        quote = rules.quote(row.infrastructure_type, row.level)
        for resource, rate in quote.production.items():
            production[resource] = amount(production[resource] + rate)
        capacity = max(capacity, quote.capacity or 0)
        bonus = amount(bonus + quote.construction_bonus_bps)
    for resource in RESOURCES:
        balance = session.get(ResourceBalance, (colony_id, resource))
        if balance is None:
            raise ColonyError("Missing resource balance")
        balance.rate_per_hour = rules.colony.speeds["economy"].apply(production[resource])
        balance.capacity = amount(capacity)
        if balance.stock > capacity:
            raise ColonyError("Effect would reduce capacity below stored resources")
    session.flush()
    return bonus


def construction_bonus(rules: Ruleset, rows: list[ColonyInfrastructure]) -> int:
    """Bonus a construction would receive if it started now (read-only counterpart)."""
    bonus = 0
    for row in rows:
        bonus = amount(
            bonus + rules.quote(row.infrastructure_type, row.level).construction_bonus_bps
        )
    return bonus


def effective_duration_us(base_duration_us: int, speed: Ratio, bonus_bps: int) -> int:
    numerator = base_duration_us * speed.denominator * 10000
    denominator = speed.numerator * (10000 + bonus_bps)
    return amount(max(1, (numerator + denominator - 1) // denominator))


@dataclass(frozen=True)
class ColonyState:
    """Rows loaded once under the caller's lock; validation never mutates them."""

    planet: Planet | None
    infrastructures: list[ColonyInfrastructure]
    queue: list[ConstructionOrder]
    balances: dict[str, ResourceBalance]


def colony_state(session: Session, colony: Colony) -> ColonyState:
    balances = {r: session.get(ResourceBalance, (colony.id, r)) for r in sorted(RESOURCES)}
    if any(row is None for row in balances.values()):
        raise ColonyError("Missing resource balance")
    return ColonyState(
        session.get(Planet, colony.planet_id),
        infrastructure_rows(session, colony.id),
        queue_rows(session, colony.id),
        balances,
    )


def plan_order(
    rules: Ruleset, state: ColonyState, kind: str, sector: int, target_level: int
) -> Quote:
    """Validate a construction against completed and reserved state; shared by commands/reads."""
    try:
        quote = rules.quote(kind, target_level)
    except ValueError as error:
        raise ColonyError(str(error), "invalid_request") from None
    planet = state.planet
    if type(sector) is not int or planet is None or not 1 <= sector <= planet.sector_capacity:
        raise ColonyError("Sector outside planetary capacity", "sector_unavailable")
    if len(state.queue) >= rules.colony.queue_limit:
        raise ColonyError("Construction queue full", "queue_full")
    projected = {
        row.sector_index: (row.infrastructure_type, row.level) for row in state.infrastructures
    }
    for order in state.queue:
        projected[order.sector_index] = (order.infrastructure_type, order.target_level)
    current = projected.get(sector)
    if (current and current[0] != kind) or target_level != (current[1] + 1 if current else 1):
        raise ColonyError("Occupied sector or non-contiguous upgrade", "sector_unavailable")
    rule = rules.catalogue.infrastructures[kind]
    if current is None and rule.max_per_colony is not None:
        if sum(k == kind for k, _ in projected.values()) >= rule.max_per_colony:
            raise ColonyError("Infrastructure uniqueness limit reached", "unique_limit")
    for required, level in rule.requires.items():
        # Prerequisites must be completed, not speculative queued capacity.
        if not any(
            r.infrastructure_type == required and r.level >= level for r in state.infrastructures
        ):
            raise ColonyError("Infrastructure prerequisites unmet", "prerequisites_unmet")
    for resource, cost in quote.cost.items():
        if state.balances[resource].stock < cost:
            raise ColonyError("Insufficient resources", "insufficient_resources")
    return quote


def cancellation_plan(
    queue: list[ConstructionOrder], order: ConstructionOrder
) -> tuple[list[ConstructionOrder], dict[str, dict[str, int]], dict[str, int]]:
    """Orders removed by cancelling `order`, per-order refunds and their totals; no mutation."""
    # Removing an upgrade also cancels later dependent upgrades in that sector.
    affected = [
        row
        for row in queue
        if row.id == order.id
        or (row.sector_index == order.sector_index and row.sequence > order.sequence)
    ]
    per_order, totals = {}, dict.fromkeys(RESOURCES, 0)
    for row in affected:
        snapshot = read_snapshot(row)
        bps = snapshot.refund_active_bps if row.status == "active" else snapshot.refund_queued_bps
        per_order[str(row.id)] = {
            r: value * bps // 10000 for r, value in snapshot.quote.cost.items()
        }
        for resource, value in per_order[str(row.id)].items():
            totals[resource] = amount(totals[resource] + value)
    return affected, per_order, totals


def refund_fits(balances: dict[str, ResourceBalance], refunds: dict[str, int]) -> bool:
    return all(
        balances[r].capacity is not None and balances[r].stock + value <= balances[r].capacity
        for r, value in refunds.items()
    )


def initialize_colony(
    session: Session, universe_id: UUID, empire_id: UUID, colony_id: UUID, at: datetime
) -> None:
    """Initialize the reference colony; no implicit creation/generation of worlds or users."""
    with session.begin_nested():
        colony = owned_colony(session, universe_id, empire_id, colony_id)
        # Same initialization lock order as the original economic adapter.
        session.scalar(select(Colony).where(Colony.id == colony_id).with_for_update())
        rules = rules_for(session, universe_id)
        planet = session.get(Planet, colony.planet_id)
        if planet is None or (planet.sector_capacity, planet.orbital_capacity) != (
            rules.colony.sectors,
            rules.colony.orbital_slots,
        ):
            raise ColonyError("Reference planet capacities must match its ruleset")
        initialize(
            session,
            colony_id,
            {
                r: ProductionState(
                    rules.colony.initial_stocks[r] * MICRO_UNITS,
                    0,
                    utc(at),
                    capacity=rules.colony.base_capacity * MICRO_UNITS,
                )
                for r in RESOURCES
            },
        )
        session.add(
            ColonyEconomy(colony_id=colony_id, universe_id=universe_id, next_order_sequence=1)
        )
        session.flush()
        for index, kind in enumerate(rules.colony.initial_infrastructures, start=1):
            session.add(
                ColonyInfrastructure(
                    colony_id=colony_id,
                    universe_id=universe_id,
                    sector_index=index,
                    infrastructure_type=kind,
                    level=1,
                )
            )
        session.flush()
        refresh_effects(session, colony_id, rules)


def read_snapshot(order: ConstructionOrder) -> OrderSnapshot:
    snapshot = OrderSnapshot.model_validate(order.snapshot)
    if (snapshot.infrastructure_type, snapshot.sector_index, snapshot.target_level) != (
        order.infrastructure_type,
        order.sector_index,
        order.target_level,
    ):
        raise ColonyError("Order snapshot identity mismatch")
    return snapshot


def activate_next(session: Session, colony_id: UUID, at: datetime, rules: Ruleset) -> None:
    queue = queue_rows(session, colony_id)
    if not queue or queue[0].status == "active":
        return
    order = queue[0]
    snapshot = read_snapshot(order)
    bonus = refresh_effects(session, colony_id, rules)
    duration = effective_duration_us(
        snapshot.quote.base_duration_us, snapshot.construction_speed, bonus
    )
    try:
        due = utc(at) + timedelta(microseconds=duration)
    except OverflowError as error:
        raise ColonyError("Construction deadline exceeds datetime representation") from error
    order.status, order.started_at, order.due_at = "active", utc(at), due
    order.applied_bonus_bps = bonus
    session.flush()
    schedule(
        session,
        colony_id,
        key=f"construction:{order.id}",
        kind="CONSTRUCTION_COMPLETE",
        due_at=due,
        payload={"order_id": str(order.id)},
    )


def catch_up_owned(
    session: Session,
    engine: TimeEngine,
    universe_id: UUID,
    empire_id: UUID,
    colony_id: UUID,
    at: datetime,
) -> Ruleset:
    owned_colony(session, universe_id, empire_id, colony_id)
    timeline = lock_timeline(session, colony_id)
    # Ownership may have changed while waiting for the lock; re-read under the stream lock.
    owned_colony(session, universe_id, empire_id, colony_id)
    if timeline.universe_id != universe_id or session.get(ColonyEconomy, colony_id) is None:
        raise ColonyError("Colony economics missing from requested universe", "colony_not_found")
    if not engine.catch_up(session, colony_id, at).complete:
        raise ColonyError("Colony timeline is blocked or catch-up budget exhausted", "colony_busy")
    return rules_for(session, universe_id)


def enqueue(
    session: Session,
    engine: TimeEngine,
    universe_id: UUID,
    empire_id: UUID,
    colony_id: UUID,
    *,
    key: str,
    kind: str,
    sector: int,
    target_level: int,
    at: datetime,
) -> ConstructionOrder:
    with session.begin_nested():
        # Scope is checked before looking up/replaying a key, even for completed orders.
        owned_colony(session, universe_id, empire_id, colony_id)
        lock_timeline(session, colony_id)
        owned_colony(session, universe_id, empire_id, colony_id)
        if not key or len(key) > 160:
            raise ColonyError("Invalid command key", "invalid_request")
        existing = session.scalar(
            select(ConstructionOrder)
            .where(
                ConstructionOrder.colony_id == colony_id, ConstructionOrder.idempotency_key == key
            )
            .execution_options(populate_existing=True)
        )
        if existing is not None:
            if (existing.infrastructure_type, existing.sector_index, existing.target_level) != (
                kind,
                sector,
                target_level,
            ):
                raise IdempotencyConflict("Construction key reused with another command")
            return existing
        rules = catch_up_owned(session, engine, universe_id, empire_id, colony_id, utc(at))
        state = colony_state(session, owned_colony(session, universe_id, empire_id, colony_id))
        quote = plan_order(rules, state, kind, sector, target_level)
        for resource, cost in quote.cost.items():
            state.balances[resource].stock -= cost
        economy = session.get(ColonyEconomy, colony_id)
        snapshot = OrderSnapshot(
            ruleset_version=rules.version,
            infrastructure_type=kind,
            sector_index=sector,
            target_level=target_level,
            quote=quote,
            construction_speed=rules.colony.speeds["construction"],
            refund_queued_bps=rules.colony.refund_queued_bps,
            refund_active_bps=rules.colony.refund_active_bps,
        )
        order = ConstructionOrder(
            colony_id=colony_id,
            universe_id=universe_id,
            sequence=economy.next_order_sequence,
            idempotency_key=key,
            infrastructure_type=kind,
            sector_index=sector,
            target_level=target_level,
            status="queued",
            snapshot=snapshot.model_dump(),
        )
        economy.next_order_sequence += 1
        session.add(order)
        session.flush()
        activate_next(session, colony_id, utc(at), rules)
        return order


def complete_construction(session: Session, event: ScheduledEvent) -> None:
    if set(event.payload) != {"order_id"}:
        raise ColonyError("Invalid construction event payload")
    order = session.get(ConstructionOrder, UUID(event.payload["order_id"]))
    if order is None or order.universe_id != event.universe_id:
        raise ColonyError("Order missing from event universe")
    timeline = session.get(ColonyTimeline, order.colony_id)
    if timeline is None or timeline.stream_id != event.stream_id:
        raise ColonyError("Order missing from event colony stream")
    if event.idempotency_key != f"construction:{order.id}":
        raise ColonyError("Invalid construction event identity")
    if order.status in {"completed", "cancelled"}:
        return
    if order.status != "active" or order.due_at != event.due_at:
        raise ColonyError("Construction not active at this deadline")
    snapshot = read_snapshot(order)
    settle(session, timeline, event.due_at)
    rows = {row.sector_index: row for row in infrastructure_rows(session, order.colony_id)}
    building = rows.get(order.sector_index)
    if building is None:
        if snapshot.target_level != 1:
            raise ColonyError("Missing predecessor infrastructure")
        building = ColonyInfrastructure(
            colony_id=order.colony_id,
            universe_id=event.universe_id,
            sector_index=order.sector_index,
            infrastructure_type=order.infrastructure_type,
            level=1,
        )
        session.add(building)
    elif building.infrastructure_type != order.infrastructure_type or (
        building.level + 1 != order.target_level
    ):
        raise ColonyError("Infrastructure changed before completion")
    else:
        building.level = order.target_level
    order.status, order.completed_at = "completed", event.due_at
    session.flush()
    rules = rules_for(session, event.universe_id)
    refresh_effects(session, order.colony_id, rules)
    activate_next(session, order.colony_id, event.due_at, rules)


def cancel(
    session: Session,
    engine: TimeEngine,
    universe_id: UUID,
    empire_id: UUID,
    colony_id: UUID,
    order_id: UUID,
    *,
    at: datetime,
) -> ConstructionOrder:
    with session.begin_nested():
        owned_colony(session, universe_id, empire_id, colony_id)
        lock_timeline(session, colony_id)
        owned_colony(session, universe_id, empire_id, colony_id)
        order = session.scalar(
            select(ConstructionOrder)
            .where(
                ConstructionOrder.id == order_id,
                ConstructionOrder.colony_id == colony_id,
                ConstructionOrder.universe_id == universe_id,
            )
            .execution_options(populate_existing=True)
        )
        if order is None:
            raise ColonyError("Order unavailable in requested colony", "order_not_found")
        if order.status == "cancelled":
            return order
        rules = catch_up_owned(session, engine, universe_id, empire_id, colony_id, utc(at))
        if order.status == "completed":
            raise ColonyError("Completed construction cannot be cancelled", "order_completed")
        affected, per_order, refunds = cancellation_plan(queue_rows(session, colony_id), order)
        balances = {r: session.get(ResourceBalance, (colony_id, r)) for r in RESOURCES}
        if not refund_fits(balances, refunds):
            raise ColonyError(
                "Refund exceeds storage capacity; spend resources before cancelling",
                "refund_exceeds_capacity",
            )
        for row in affected:
            row.refunded = per_order[str(row.id)]
        for resource, value in refunds.items():
            balance = balances[resource]
            balance.stock = amount(balance.stock + value)
            if balance.stock == balance.capacity:
                balance.remainder = 0
        for row in affected:
            if row.status == "active":
                timeline = session.get(ColonyTimeline, colony_id)
                event = session.scalar(
                    select(ScheduledEvent).where(
                        ScheduledEvent.stream_id == timeline.stream_id,
                        ScheduledEvent.idempotency_key == f"construction:{row.id}",
                    )
                )
                if event is None or event.status != "pending":
                    raise TimelineError("Active construction event missing or blocked")
                # Acknowledge the cancelled deadline; never leave an obsolete blocking event.
                event.status, event.completed_at, event.error_code = (
                    "completed",
                    utc(at),
                    "cancelled",
                )
            row.status, row.cancelled_at = "cancelled", utc(at)
        session.flush()
        activate_next(session, colony_id, utc(at), rules)
        return order
