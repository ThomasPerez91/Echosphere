"""Authorized read model of one colony. Rules come from the pinned ruleset and 5A helpers only.

Amounts are exact micro-unit integers serialized as decimal strings (JSON numbers would lose
precision in browsers); durations are microsecond strings; dates are UTC ISO-8601 with offset.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.colony.rules import Quote, Ruleset
from app.colony.service import (
    ColonyError,
    ColonyState,
    cancellation_plan,
    colony_state,
    construction_bonus,
    effective_duration_us,
    plan_order,
    read_snapshot,
    recoverable_refunds,
)
from app.persistence.models import Colony, Empire, StellarSystem, Universe
from app.simulation.models import ColonyTimeline

RESOURCE_ORDER = ("alloys", "flux", "data")


def amounts(values: dict[str, int]) -> dict[str, str]:
    return {resource: str(values.get(resource, 0)) for resource in RESOURCE_ORDER}


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def quote_view(quote: Quote) -> dict:
    return {
        "cost": amounts(quote.cost),
        "base_duration_us": str(quote.base_duration_us),
        "production_per_hour": amounts(quote.production),
        "construction_bonus_bps": quote.construction_bonus_bps,
        "capacity": str(quote.capacity) if quote.capacity else None,
    }


def option(rules, state, permissions, bonus, *, action, kind, sector, level) -> dict:
    quote = rules.quote(kind, level)
    try:
        if sector is None:
            raise ColonyError("No free sector", "sector_unavailable")
        plan_order(rules, state, kind, sector, level)
        reason = None if "colony.construct" in permissions else "permission_denied"
    except ColonyError as error:
        reason = error.code
    return {
        "action": action,
        "infrastructure_type": kind,
        "sector_index": sector,
        "target_level": level,
        **quote_view(quote),
        # Only an immediate start has a known bonus; later starts are fixed at activation.
        "estimated_duration_us": (
            str(
                effective_duration_us(
                    quote.base_duration_us, rules.colony.speeds["construction"], bonus
                )
            )
            if not state.queue
            else None
        ),
        "available": reason is None,
        "reason": reason,
    }


def options(rules: Ruleset, state: ColonyState, permissions: list[str]) -> list[dict]:
    projected = {
        row.sector_index: (row.infrastructure_type, row.level) for row in state.infrastructures
    }
    for order in state.queue:
        projected[order.sector_index] = (order.infrastructure_type, order.target_level)
    capacity = state.planet.sector_capacity if state.planet else 0
    free = [index for index in range(1, capacity + 1) if index not in projected]
    bonus = construction_bonus(rules, state.infrastructures)
    result = []
    for kind in rules.catalogue.infrastructures:
        first_free = free[0] if free else None
        result.append(
            option(
                rules,
                state,
                permissions,
                bonus,
                action="build",
                kind=kind,
                sector=first_free,
                level=1,
            )
        )
        for sector, (existing, level) in sorted(projected.items()):
            if existing == kind:
                result.append(
                    option(
                        rules,
                        state,
                        permissions,
                        bonus,
                        action="upgrade",
                        kind=kind,
                        sector=sector,
                        level=level + 1,
                    )
                )
    return result


def queue_view(state: ColonyState, permissions: list[str]) -> list[dict]:
    result = []
    for order in state.queue:
        snapshot = read_snapshot(order)
        affected, per_order, refunds = cancellation_plan(state.queue, order)
        _, recovered, lost = recoverable_refunds(state.balances, per_order)
        reason = None if "colony.cancel" in permissions else "permission_denied"
        result.append(
            {
                "id": str(order.id),
                "sequence": order.sequence,
                "status": order.status,
                "infrastructure_type": order.infrastructure_type,
                "sector_index": order.sector_index,
                "target_level": order.target_level,
                "cost": amounts(snapshot.quote.cost),
                "base_duration_us": str(snapshot.quote.base_duration_us),
                "applied_bonus_bps": order.applied_bonus_bps,
                "started_at": iso(order.started_at),
                "due_at": iso(order.due_at),
                "cancel": {
                    "available": reason is None,
                    "reason": reason,
                    "refund": amounts(refunds),
                    "recoverable": amounts(recovered),
                    "lost": amounts(lost),
                    "also_cancels": [str(row.id) for row in affected if row.id != order.id],
                },
            }
        )
    return result


def project(
    session: Session, rules: Ruleset, colony: Colony, permissions: list[str], at: datetime
) -> dict:
    """Projection after the caller's catch-up; never exposes another empire or universe."""
    state = colony_state(session, colony)
    planet = state.planet
    system = session.get(StellarSystem, planet.system_id)
    empire = session.get(Empire, colony.empire_id)
    universe = session.get(Universe, colony.universe_id)
    timeline = session.get(ColonyTimeline, colony.id)
    built = {row.sector_index for row in state.infrastructures}
    reserved = {order.sector_index for order in state.queue} - built
    return {
        "server_time": at.isoformat(),
        "settled_at": iso(timeline.settled_at),
        "ruleset_version": rules.version,
        "permissions": sorted(permissions),
        "colony": {
            "id": str(colony.id),
            "name": planet.name,
            "planet": {
                "name": planet.name,
                "sector_capacity": planet.sector_capacity,
                "orbital_capacity": planet.orbital_capacity,
            },
            "system": {"name": system.name},
            "empire": {"id": str(empire.id), "name": empire.name},
            "universe": {"id": str(universe.id), "name": universe.name},
        },
        "sectors": {
            "capacity": planet.sector_capacity,
            "built": len(built),
            "reserved": len(reserved),
            "free": planet.sector_capacity - len(built) - len(reserved),
            "free_indices": [
                index
                for index in range(1, planet.sector_capacity + 1)
                if index not in built and index not in reserved
            ],
        },
        "resources": [
            {
                "resource": resource,
                "stock": str(state.balances[resource].stock),
                "capacity": str(state.balances[resource].capacity)
                if state.balances[resource].capacity is not None
                else None,
                "rate_per_hour": str(state.balances[resource].rate_per_hour),
            }
            for resource in RESOURCE_ORDER
        ],
        "infrastructures": [
            {
                "sector_index": row.sector_index,
                "infrastructure_type": row.infrastructure_type,
                "level": row.level,
                **quote_view(rules.quote(row.infrastructure_type, row.level)),
            }
            for row in sorted(state.infrastructures, key=lambda r: r.sector_index)
        ],
        "queue": queue_view(state, permissions),
        "queue_limit": rules.colony.queue_limit,
        "options": options(rules, state, permissions),
    }
