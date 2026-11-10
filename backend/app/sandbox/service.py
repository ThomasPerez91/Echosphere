"""Test game (sandbox, recette 10/11/2026): an almost finished world and tools to test fast.

Only a universe created as a test game (`Universe.sandbox`) accepts these commands. They use the
usual locks and handlers (Operations → Research → Colony), never another stream's lock order:
- `sandbox_rules` (bootstrap): fleets 20 times faster, attacks 10 minutes after launch.
- `prepare` (bootstrap): every key building at a high level, every technology acquired, every
  system of the galaxy mapped with its routes, a garrison with every ship class. No contact is
  created: other Empires stay unknown to Relations.
- `grant_resources`: sets the stocks of a colony (bounded by its storage capacity).
- `grant_ships`: adds ships to a colony garrison.
- `finish`: completes now every construction, research and ship order of the Empire.
"""

from sqlalchemy import select

from app.colony.models import ColonyInfrastructure, ConstructionOrder
from app.colony.service import (
    ColonyError,
    catch_up_owned,
    infrastructure_rows,
    owned_colony,
    refresh_effects,
    rules_for,
)
from app.galaxy import service as galaxy
from app.galaxy.models import GalaxySystem
from app.persistence.models import Colony, Planet, Universe
from app.research import service as research
from app.research.models import AcquiredTechnology, ResearchOrder
from app.simulation.clock import utc
from app.simulation.models import ColonyTimeline, ResourceBalance, ScheduledEvent
from app.simulation.production import MICRO_UNITS, RESOURCES, amount
from app.simulation.service import settle

LEVEL = 10  # buildings of the test colony (within every planet level cap)
STOCK = 250_000  # starting stock per resource, in units
SHIPS = {
    "probe": 10,
    "freighter": 6,
    "extractor": 6,
    "colonizer": 3,
    "interceptor": 20,
    "frigate": 10,
    "cruiser": 4,
}
FINISH_LIMIT = 200  # orders completed by one `finish` call, every queue included


FLEET_SPEED = 20  # fleets travel 20 times faster in a test game
WARNING_SECONDS = 600  # an attack can strike 10 minutes after its launch (24 h normally)


def sandbox_rules(rules):
    """Pinned rules of a test game: same ruleset, instance speeds of the test game.

    Only the per-instance fleet speed and the attack warning change; the AI policy, its digest
    and every other rule stay those of the chosen ruleset."""
    data = rules.model_dump()
    data["colony"]["speeds"]["fleet"] = {"numerator": FLEET_SPEED, "denominator": 1}
    if data.get("combat"):
        data["combat"]["min_warning_seconds"] = min(
            data["combat"]["min_warning_seconds"], WARNING_SECONDS
        )
    return type(rules).model_validate(data)


class SandboxError(ColonyError):
    pass


def require(session, universe_id):
    universe = session.get(Universe, universe_id)
    if universe is None or not universe.sandbox:
        raise SandboxError("Not a test game", "sandbox_unavailable")
    return universe


def prepare(session, universe_id, empire_id, colony_id, at):
    """Bootstrap of a test game, in the bootstrap transaction (nothing scheduled yet)."""
    from app.fleet.service import add_units, garrison_for

    rules = rules_for(session, universe_id)
    colony = owned_colony(session, universe_id, empire_id, colony_id)
    rows = {row.infrastructure_type: row for row in infrastructure_rows(session, colony_id)}
    sector = max((row.sector_index for row in rows.values()), default=0)
    cap = rules.colony.level_cap.cap(rules.colony.sectors) if rules.colony.level_cap else LEVEL
    level = min(LEVEL, cap)
    for kind in rules.catalogue.infrastructures:
        row = rows.get(kind)
        if row is None:
            sector += 1
            if sector > rules.colony.sectors:
                break
            row = ColonyInfrastructure(
                colony_id=colony_id,
                universe_id=universe_id,
                sector_index=sector,
                infrastructure_type=kind,
                level=level,
            )
            session.add(row)
        row.level = level
    session.flush()
    # Same instant as the colony initialisation: rates and capacity follow the buildings.
    refresh_effects(session, colony_id, rules)
    for resource in RESOURCES:
        balance = session.get(ResourceBalance, (colony_id, resource))
        balance.stock = min(amount(STOCK * MICRO_UNITS), balance.capacity)
    if rules.research is not None:
        for technology_id, technology in rules.research.technologies.items():
            session.add(
                AcquiredTechnology(
                    empire_id=empire_id,
                    universe_id=universe_id,
                    technology_id=technology_id,
                    acquired_at=utc(at),
                    effect=technology.effect,
                    reduction_bps=technology.reduction_bps,
                )
            )
    for system_id in session.scalars(
        select(GalaxySystem.system_id)
        .where(GalaxySystem.universe_id == universe_id)
        .order_by(GalaxySystem.ordinal)
    ):
        galaxy.map_system(session, universe_id, empire_id, system_id, at)
    galaxy.refresh_monitoring(session, universe_id, empire_id, at)
    if rules.fleets is not None:
        ships = {k: n for k, n in SHIPS.items() if k in rules.fleets.classes}
        add_units(session, garrison_for(session, colony).id, ships)
    session.flush()


def grant_resources(session, engine, universe_id, empire_id, colony_id, wanted, at):
    """Sets the stocks of an own colony; a value above its storage capacity is capped."""
    require(session, universe_id)
    if not wanted or set(wanted) - RESOURCES:
        raise SandboxError("Invalid resources", "invalid_request")
    catch_up_owned(session, engine, universe_id, empire_id, colony_id, at)
    timeline = session.get(ColonyTimeline, colony_id)
    settle(session, timeline, at)
    for resource, value in wanted.items():
        if type(value) is not int or value < 0:
            raise SandboxError("Invalid resources", "invalid_request")
        balance = session.get(ResourceBalance, (colony_id, resource))
        balance.stock = min(amount(value * MICRO_UNITS), balance.capacity)
        balance.remainder = 0
    session.flush()


def grant_ships(session, engine, universe_id, empire_id, colony_id, ships, at):
    from app.fleet.service import add_units, garrison_for, operations

    require(session, universe_id)
    rules = rules_for(session, universe_id)
    if (
        rules.fleets is None
        or not ships
        or any(c not in rules.fleets.classes for c in ships)
        or any(type(n) is not int or not 0 < n <= 1000 for n in ships.values())
    ):
        raise SandboxError("Invalid ships", "invalid_request")
    operations(session, engine, universe_id, empire_id, at)
    colony = owned_colony(session, universe_id, empire_id, colony_id)
    add_units(session, garrison_for(session, colony).id, ships)
    session.flush()


def advance(event, at):
    """Moves a pending event to `at`: its own handler then completes it on the next catch-up."""
    event.due_at = event.next_attempt_at = utc(at)


def pending_event(session, stream_id, key):
    return session.scalar(
        select(ScheduledEvent).where(
            ScheduledEvent.stream_id == stream_id,
            ScheduledEvent.idempotency_key == key,
            ScheduledEvent.status == "pending",
        )
    )


def finish(session, engine, universe_id, empire_id, at):
    """Completes now every construction, research and ship order of the Empire, queues
    included (each completion starts the next order, completed in turn)."""
    from app.fleet.models import ShipOrder
    from app.fleet.service import activate_next as next_ship
    from app.fleet.service import add_units, garrison_for, operations

    require(session, universe_id)
    at = utc(at)
    rules = rules_for(session, universe_id)
    done = {"constructions": 0, "research": 0, "ships": 0}
    budget = FINISH_LIMIT
    # Global lock order: Operations → Research → Colony.
    state = operations(session, engine, universe_id, empire_id, at) if rules.fleets else None
    if rules.research is not None:
        row = research.catch_up(session, engine, universe_id, empire_id, at)
        while budget > 0:
            order = session.scalar(
                select(ResearchOrder).where(
                    ResearchOrder.empire_id == empire_id, ResearchOrder.status == "active"
                )
            )
            event = order and pending_event(session, row.stream_id, f"research:{order.id}")
            if event is None:
                break
            order.due_at = at
            advance(event, at)
            session.flush()
            if not engine.catch_up_stream(session, row.stream_id, universe_id, at).complete:
                raise SandboxError("Research is busy", "research_busy")
            done["research"] += 1
            budget -= 1
    colonies = list(
        session.scalars(
            select(Colony.id)
            .where(Colony.universe_id == universe_id, Colony.empire_id == empire_id)
            .order_by(Colony.id)
        )
    )
    for colony_id in colonies:
        catch_up_owned(session, engine, universe_id, empire_id, colony_id, at)
        stream_id = session.get(ColonyTimeline, colony_id).stream_id
        while budget > 0:
            order = session.scalar(
                select(ConstructionOrder).where(
                    ConstructionOrder.colony_id == colony_id, ConstructionOrder.status == "active"
                )
            )
            event = order and pending_event(session, stream_id, f"construction:{order.id}")
            if event is None:
                break
            order.due_at = at
            advance(event, at)
            session.flush()
            if not engine.catch_up(session, colony_id, at).complete:
                raise SandboxError("Colony is busy", "colony_busy")
            done["constructions"] += 1
            budget -= 1
    if state is not None:
        for colony_id in colonies:
            colony = session.get(Colony, colony_id)
            while budget > 0:
                order = session.scalar(
                    select(ShipOrder).where(
                        ShipOrder.colony_id == colony_id, ShipOrder.status == "active"
                    )
                )
                if order is None:
                    break
                base = f"ship-order:{order.id}"
                for event in session.scalars(
                    select(ScheduledEvent).where(
                        ScheduledEvent.stream_id == state.stream_id,
                        ScheduledEvent.idempotency_key.in_(
                            [base, f"{base}:{(order.delivered or 0) + 1}"]
                        ),
                        ScheduledEvent.status == "pending",
                    )
                ):
                    event.status, event.completed_at = "completed", at
                remaining = order.quantity - (order.delivered or 0)
                add_units(session, garrison_for(session, colony).id, {order.ship_class: remaining})
                order.delivered = order.quantity
                order.status, order.completed_at = "completed", at
                session.flush()
                next_ship(session, state, colony_id, at)
                done["ships"] += 1
                budget -= 1
    return done


def status(session, universe_id, empire_id, at):
    """Sandbox panel: the own colonies with their stocks and capacity."""
    require(session, universe_id)
    rows = []
    for colony in session.scalars(
        select(Colony)
        .where(Colony.universe_id == universe_id, Colony.empire_id == empire_id)
        .order_by(Colony.id)
    ):
        planet = session.get(Planet, colony.planet_id)
        balances = {r: session.get(ResourceBalance, (colony.id, r)) for r in sorted(RESOURCES)}
        rows.append(
            {
                "id": str(colony.id),
                "name": colony.display_name(planet),
                "capacity": str((balances["alloys"].capacity or 0) // MICRO_UNITS),
            }
        )
    rules = rules_for(session, universe_id)
    return {
        "sandbox": True,
        "colonies": rows,
        "ship_classes": list(rules.fleets.classes) if rules.fleets else [],
        "server_time": utc(at).isoformat(),
    }
