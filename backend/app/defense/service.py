"""Planetary defense (DEF-01, ruleset v0.13): placement, network capacity, repair quotes, Flux
upkeep and the modules fighting in a battle. Pure functions over rows loaded by the caller (its
colony lock), except `fighting` and `damage`, which read or change rows the caller has locked."""

from sqlalchemy import select

from app.colony.models import ColonyInfrastructure, ConstructionOrder
from app.defense.rules import ORBITAL_BASE
from app.simulation.production import MICRO_UNITS


def module_of(rules, kind):
    return rules.defense.modules.get(kind) if rules.defense is not None else None


def slots(rules, planet, kind):
    """Sector indexes a construction of `kind` may use on `planet`: an ORBITAL module uses the
    real orbital slots (ORBITAL_BASE + k), everything else the real sectors."""
    if planet is None:
        return range(0)
    module = module_of(rules, kind)
    if module is not None and module.placement == "orbital":
        return range(ORBITAL_BASE + 1, ORBITAL_BASE + planet.orbital_capacity + 1)
    return range(1, planet.sector_capacity + 1)


def check_module(rules, state, kind, current, projected):
    """A module is built once at level 1 (no upgrade) within the network capacity: the Défense
    center's completed level times `capacity_per_level`, queued modules included."""
    from app.colony.service import ColonyError

    if module_of(rules, kind) is None:
        return
    if current is not None:
        if current[0] == kind:
            raise ColonyError("A defense module has a single level", "module_level_fixed")
        return
    d = rules.defense
    center = max(
        (r.level for r in state.infrastructures if r.infrastructure_type == d.center), default=0
    )
    built = sum(k in d.modules for k, _ in projected.values())
    if built >= d.capacity(center):
        raise ColonyError("Defense network capacity reached", "defense_capacity_full")


def repair_quote(defense, quote):
    cost = {r: -(-v * defense.repair_cost_bps // 10000) for r, v in quote.cost.items()}
    duration = max(1, quote.base_duration_us * defense.repair_duration_bps // 10000)
    return quote.model_copy(update={"cost": cost, "base_duration_us": duration})


def ordered(defense, rows):
    rank = {kind: i for i, kind in enumerate(defense.disable_order)}
    return sorted(
        (r for r in rows if r.infrastructure_type in defense.modules),
        key=lambda r: (rank[r.infrastructure_type], r.sector_index),
    )


def power(defense, rows, flux_production):
    """Net Flux production after module upkeep, never below zero: modules not damaged start
    operational, then are DISABLED in `disable_order` (by sector) while the net production is
    negative; they come back on their own when it no longer is. Sets `condition` in place."""
    modules = [r for r in ordered(defense, rows) if r.condition != "damaged"]
    net = flux_production - sum(
        defense.modules[r.infrastructure_type].upkeep_flux * MICRO_UNITS for r in modules
    )
    for row in modules:
        row.condition = "operational"
    for row in modules:
        if net >= 0:
            break
        row.condition = "disabled"
        net += defense.modules[row.infrastructure_type].upkeep_flux * MICRO_UNITS
    return net


def fighting(session, rules, colony_id, at):
    """Operational modules of a colony at battle time `at`, by combat class, in a deterministic
    order (disable order, then sector): a module finished or repaired after `at` did not fight;
    disabled and damaged ones never fight."""
    d = rules.defense
    if d is None:
        return []
    rows = list(
        session.scalars(
            select(ColonyInfrastructure)
            .where(ColonyInfrastructure.colony_id == colony_id)
            .execution_options(populate_existing=True)
        )
    )
    late = set(
        session.scalars(
            select(ConstructionOrder.sector_index).where(
                ConstructionOrder.colony_id == colony_id,
                ConstructionOrder.status == "completed",
                ConstructionOrder.completed_at > at,
                ConstructionOrder.infrastructure_type.in_(sorted(d.modules)),
            )
        )
    )
    return [
        r for r in ordered(d, rows) if r.condition == "operational" and r.sector_index not in late
    ]


def units(rules, modules):
    out = {}
    for row in modules:
        cls = rules.defense.modules[row.infrastructure_type].combat_class
        out[cls] = out.get(cls, 0) + 1
    return out


def damage(rules, modules, losses):
    """Marks the lost modules of each combat class DAMAGED, in the same deterministic order;
    returns their sector indexes."""
    left = {c: n for c, n in losses.items() if n}
    hit = []
    for row in modules:
        cls = rules.defense.modules[row.infrastructure_type].combat_class
        if left.get(cls, 0) > 0:
            row.condition = "damaged"
            left[cls] -= 1
            hit.append(row.sector_index)
    return hit
