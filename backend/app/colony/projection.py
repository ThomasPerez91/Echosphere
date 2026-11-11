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
    construction_quote,
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
    quote = construction_quote(rules, state, kind, level)
    if action == "repair":
        # DEF-01: a repair costs its share of the module, as `plan_order` will charge it.
        from app.defense.service import repair_quote

        quote = repair_quote(rules.defense, quote)
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
        # COL-11: what unlocks a locked building, shown greyed with its prerequisites.
        "requires": [
            {"infrastructure_type": k, "level": v}
            for k, v in sorted(rules.catalogue.infrastructures[kind].requires.items())
        ],
    }


def options(rules: Ruleset, state: ColonyState, permissions: list[str]) -> list[dict]:
    projected = {
        row.sector_index: (row.infrastructure_type, row.level) for row in state.infrastructures
    }
    for order in state.queue:
        projected[order.sector_index] = (order.infrastructure_type, order.target_level)
    from app.defense.service import module_of, slots

    bonus = construction_bonus(rules, state.infrastructures)
    result = []
    for kind in rules.catalogue.infrastructures:
        # DEF-01: an ORBITAL module takes the first free orbital slot, everything else a sector.
        free = [index for index in slots(rules, state.planet, kind) if index not in projected]
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
        if module_of(rules, kind) is not None:
            # A module never levels up; a DAMAGED one is repaired at its level.
            for row in sorted(state.infrastructures, key=lambda r: r.sector_index):
                if row.infrastructure_type == kind and row.condition == "damaged":
                    result.append(
                        option(
                            rules,
                            state,
                            permissions,
                            bonus,
                            action="repair",
                            kind=kind,
                            sector=row.sector_index,
                            level=row.level,
                        )
                    )
            continue
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
    surface = range(1, planet.sector_capacity + 1)
    built = {row.sector_index for row in state.infrastructures if row.sector_index in surface}
    reserved = {order.sector_index for order in state.queue if order.sector_index in surface}
    reserved -= built
    return {
        "server_time": at.isoformat(),
        "settled_at": iso(timeline.settled_at),
        "ruleset_version": rules.version,
        "permissions": sorted(permissions),
        "colony": {
            "id": str(colony.id),
            "name": colony.display_name(planet),
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
                **({"condition": row.condition} if row.condition is not None else {}),
            }
            for row in sorted(state.infrastructures, key=lambda r: r.sector_index)
        ],
        **defense_view(rules, state),
        "queue": queue_view(state, permissions),
        "queue_limit": rules.colony.queue_limit,
        "options": options(rules, state, permissions),
        "incoming": incoming(session, rules, colony, permissions),
    }


def incoming(session, rules, colony, permissions):
    """Hostile force announced on this Colony's planet: battle instant and state only."""
    if rules.combat is None or "combat.read" not in permissions:
        return None
    from app.combat.service import alerts_for

    planet = str(colony.planet_id)
    return [
        {k: a[k] for k in ("id", "battle_at", "state")}
        for a in alerts_for(session, colony.universe_id, colony.empire_id)
        if a["planet_id"] == planet
    ]


def defense_view(rules, state):
    """DEF-01 (v0.13): the colony's defense network as it is (capacity, slots, modules and their
    state, upkeep) and the catalogue of its modules; absent before v0.13."""
    d = rules.defense
    if d is None:
        return {}
    from app.defense.rules import ORBITAL_BASE

    planet = state.planet
    center = max(
        (r.level for r in state.infrastructures if r.infrastructure_type == d.center), default=0
    )
    modules = [r for r in state.infrastructures if r.infrastructure_type in d.modules]
    queued = [o for o in state.queue if o.infrastructure_type in d.modules]
    taken = {r.sector_index for r in state.infrastructures} | {o.sector_index for o in state.queue}
    orbit = range(ORBITAL_BASE + 1, ORBITAL_BASE + planet.orbital_capacity + 1)
    combat = rules.combat
    return {
        "defense": {
            "center": d.center,
            "center_level": center,
            "capacity": d.capacity(center),
            "capacity_per_level": d.capacity_per_level,
            "used": len({r.sector_index for r in modules} | {o.sector_index for o in queued}),
            "orbital": {
                "capacity": planet.orbital_capacity,
                "base": ORBITAL_BASE,
                "free_indices": [i for i in orbit if i not in taken],
            },
            "upkeep_flux_per_hour": str(
                sum(
                    d.modules[r.infrastructure_type].upkeep_flux * 1_000_000
                    for r in modules
                    if r.condition == "operational"
                )
            ),
            "modules": [
                {
                    "sector_index": r.sector_index,
                    "infrastructure_type": r.infrastructure_type,
                    "condition": r.condition,
                }
                for r in sorted(modules, key=lambda r: r.sector_index)
            ],
            "catalogue": {
                kind: {
                    "family": m.family,
                    "placement": m.placement,
                    "upkeep_flux": m.upkeep_flux,
                    "hull": combat.modules[m.combat_class].hull,
                    "attack": combat.modules[m.combat_class].attack,
                    "matchups_bps": {
                        c: combat.matchups_bps[m.combat_class][c] for c in combat.classes
                    },
                }
                for kind, m in d.modules.items()
            },
            "repair_cost_bps": d.repair_cost_bps,
            "repair_duration_bps": d.repair_duration_bps,
        }
    }
