"""Empire-local knowledge/expeditions: principal → Exploration → Research → Colony.

Explicit initialization precedes player traffic. Completion never locks a second stream,
spends resources, calls Portal or requires a human session. Caller owns every transaction.
"""

from collections import deque
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.colony.service import ColonyError, catch_up_owned, owned_colony, rules_for
from app.galaxy.models import (
    EmpireExploration,
    ExplorationMission,
    ExplorationReport,
    GalaxyPlanet,
    GalaxyRoute,
    GalaxySystem,
    MissionLeg,
    PlanetKnowledge,
    RouteKnowledge,
    SystemKnowledge,
)
from app.persistence.models import Colony, Empire, Planet, StellarSystem
from app.research import service as research
from app.simulation.clock import utc
from app.simulation.models import ResourceBalance
from app.simulation.scheduler import (
    IdempotencyConflict,
    TimelineError,
    create_stream,
    lock_stream,
    schedule,
)


class GalaxyError(ColonyError):
    pass


def state_for(session, universe_id, empire_id):
    state = session.get(EmpireExploration, empire_id)
    if state is None or state.universe_id != universe_id:
        raise GalaxyError("Galaxy not initialized", "galaxy_unavailable")
    return state


def catch_up(session, engine, universe_id, empire_id, at):
    state = state_for(session, universe_id, empire_id)
    lock_stream(session, state.stream_id, universe_id)
    if not engine.catch_up_stream(session, state.stream_id, universe_id, utc(at)).complete:
        raise GalaxyError("Exploration needs retry/operator", "exploration_busy")
    return state


def detect(session, universe_id, empire_id, system_id, at, cell):
    known = session.get(SystemKnowledge, (empire_id, system_id))
    if known is None:
        physical = session.get(GalaxySystem, system_id)
        if physical is None or physical.universe_id != universe_id:
            raise TimelineError("Discovery outside generated universe")
        known = SystemKnowledge(
            empire_id=empire_id,
            universe_id=universe_id,
            system_id=system_id,
            state="DETECTED",
            approximate_x=(physical.x // cell) * cell + cell // 2,
            approximate_y=(physical.y // cell) * cell + cell // 2,
            discovered_at=utc(at),
        )
        session.add(known)
        session.flush()
    return known


def map_system(session, universe_id, empire_id, system_id, at):
    rules = rules_for(session, universe_id).galaxy
    if rules is None:
        raise TimelineError("Missing pinned Galaxy data")
    known = detect(session, universe_id, empire_id, system_id, at, rules.detected_cell_size)
    if known.state == "DETECTED":
        # Read the structure first: state and structure become visible in one flush.
        physical = session.get(GalaxySystem, system_id)
        name = session.get(StellarSystem, system_id).name
        known.state, known.mapped_at = "MAPPED", utc(at)
        known.known_name, known.known_x, known.known_y = name, physical.x, physical.y
        for gp in session.scalars(
            select(GalaxyPlanet).where(
                GalaxyPlanet.universe_id == universe_id, GalaxyPlanet.system_id == system_id
            )
        ):
            planet = session.get(Planet, gp.planet_id)
            session.add(
                PlanetKnowledge(
                    empire_id=empire_id,
                    planet_id=gp.planet_id,
                    universe_id=universe_id,
                    system_id=system_id,
                    discovered_at=utc(at),
                    known_name=planet.name,
                    sector_capacity=planet.sector_capacity,
                    orbital_capacity=planet.orbital_capacity,
                )
            )
        session.flush()
    neighbors, routes = [], []
    for route in session.scalars(
        select(GalaxyRoute)
        .where(
            GalaxyRoute.universe_id == universe_id,
            (GalaxyRoute.a_id == system_id) | (GalaxyRoute.b_id == system_id),
        )
        .order_by(GalaxyRoute.id)
    ):
        other = route.b_id if route.a_id == system_id else route.a_id
        new = session.get(SystemKnowledge, (empire_id, other)) is None
        row = detect(session, universe_id, empire_id, other, at, rules.detected_cell_size)
        # Only the approximate snapshot: the report never carries a neighbor's structure.
        neighbors.append(
            {"id": str(other), "x": row.approximate_x, "y": row.approximate_y, "new": new}
        )
        routes.append({"id": str(route.id), "a_id": str(route.a_id), "b_id": str(route.b_id)})
        if session.get(RouteKnowledge, (empire_id, route.id)) is None:
            session.add(
                RouteKnowledge(
                    empire_id=empire_id,
                    universe_id=universe_id,
                    route_id=route.id,
                    a_id=route.a_id,
                    b_id=route.b_id,
                    discovered_at=utc(at),
                )
            )
    session.flush()
    return {"system": project_system(session, known), "neighbors": neighbors, "routes": routes}


def initialize_empire(session, engine, universe_id, empire_id, colony_id, at):
    """Explicit provisioning only. No implicit Empire/colony creation or reserved worlds."""
    with session.begin_nested():
        colony = owned_colony(session, universe_id, empire_id, colony_id)
        empire = session.scalar(
            select(Empire)
            .where(Empire.id == empire_id, Empire.universe_id == universe_id)
            .with_for_update()
        )
        if empire is None:
            raise GalaxyError("Empire not found", "empire_not_found")
        rules = rules_for(session, universe_id)
        if rules.galaxy is None or rules.exploration is None:
            raise GalaxyError("Pinned ruleset unavailable", "galaxy_unavailable")
        planet = session.get(Planet, colony.planet_id)
        physical = session.get(GalaxySystem, planet.system_id)
        if physical is None or physical.universe_id != universe_id:
            raise GalaxyError("Source outside generated world", "galaxy_unavailable")
        existing = session.get(EmpireExploration, empire_id)
        if existing is not None:
            return existing
        # Establish Research before any Exploration stream can be acquired by player commands.
        research.catch_up(session, engine, universe_id, empire_id, at)
        stream = create_stream(session, universe_id, utc(at))
        state = EmpireExploration(empire_id=empire_id, universe_id=universe_id, stream_id=stream.id)
        session.add(state)
        session.flush()
        lock_stream(session, stream.id, universe_id)
        map_system(session, universe_id, empire_id, planet.system_id, at)
        refresh_monitoring(session, universe_id, empire_id, at)
        return state


def refresh_monitoring(session, universe_id, empire_id, at):
    # Only the Empire's OWN legitimate Colony presence grants observation; no remote sensors.
    owned = session.execute(
        select(Planet.system_id, Colony.id)
        .join(Colony, Colony.planet_id == Planet.id)
        .where(Colony.universe_id == universe_id, Colony.empire_id == empire_id)
    ).all()
    by_system = {}
    for system_id, colony_id in owned:
        by_system.setdefault(system_id, []).append(str(colony_id))
    for known in session.scalars(
        select(SystemKnowledge).where(
            SystemKnowledge.universe_id == universe_id, SystemKnowledge.empire_id == empire_id
        )
    ):
        if known.system_id in by_system and known.state != "DETECTED":
            known.state, known.last_seen_at = "MONITORED", utc(at)
            known.observation = {"own_colony_ids": sorted(by_system[known.system_id])}
        elif known.state == "MONITORED":
            known.state = "MAPPED"  # preserve structure and the dated observation


def project_system(session, known):
    result = {
        "id": str(known.system_id),
        "state": known.state,
        "discovered_at": known.discovered_at.isoformat(),
        "x": known.approximate_x,
        "y": known.approximate_y,
    }
    if known.state != "DETECTED":
        result.update(
            name=known.known_name,
            x=known.known_x,
            y=known.known_y,
            mapped_at=known.mapped_at.isoformat(),
            last_seen_at=known.last_seen_at.isoformat() if known.last_seen_at else None,
            observation=known.observation,
            planets=[
                {
                    "id": str(p.planet_id),
                    "name": p.known_name,
                    "sector_capacity": p.sector_capacity,
                    "orbital_capacity": p.orbital_capacity,
                }
                for p in session.scalars(
                    select(PlanetKnowledge)
                    .where(
                        PlanetKnowledge.empire_id == known.empire_id,
                        PlanetKnowledge.universe_id == known.universe_id,
                        PlanetKnowledge.system_id == known.system_id,
                    )
                    .order_by(PlanetKnowledge.planet_id)
                )
            ],
        )
    return result


def known_path(session, universe_id, empire_id, origin_id, destination_id):
    knowledge = {
        r.system_id: r
        for r in session.scalars(
            select(SystemKnowledge).where(
                SystemKnowledge.universe_id == universe_id, SystemKnowledge.empire_id == empire_id
            )
        )
    }
    target = knowledge.get(destination_id)
    if target is None:
        raise GalaxyError("System not found", "system_not_found")
    if target.state != "DETECTED":
        raise GalaxyError("System already mapped", "destination_mapped")
    if origin_id not in knowledge or knowledge[origin_id].state == "DETECTED":
        raise GalaxyError("Source inaccessible", "destination_unreachable")
    graph = {node: [] for node in knowledge}
    for route in session.scalars(
        select(RouteKnowledge).where(
            RouteKnowledge.universe_id == universe_id, RouteKnowledge.empire_id == empire_id
        )
    ):
        graph[route.a_id].append((route.b_id, route.route_id))
        graph[route.b_id].append((route.a_id, route.route_id))
    parents = {origin_id: None}
    queue = deque([origin_id])
    while queue:
        node = queue.popleft()
        if node == destination_id:
            result = []
            while parents[node] is not None:
                node, route_id = parents[node]
                result.append(route_id)
            return list(reversed(result))
        if knowledge[node].state == "DETECTED":
            continue
        for other, route_id in sorted(graph[node]):
            if other not in parents:
                parents[other] = (node, route_id)
                queue.append(other)
    raise GalaxyError("No known route", "destination_unreachable")


def start(session, engine, universe_id, empire_id, colony_id, destination_id, *, key, at):
    with session.begin_nested():
        colony = owned_colony(session, universe_id, empire_id, colony_id)
        state = catch_up(session, engine, universe_id, empire_id, at)
        existing = session.scalar(
            select(ExplorationMission).where(
                ExplorationMission.empire_id == empire_id, ExplorationMission.idempotency_key == key
            )
        )
        if existing is not None:
            if (existing.colony_id, existing.destination_id) != (colony_id, destination_id):
                raise IdempotencyConflict("Exploration intention reused")
            return existing
        if not key or len(key) > 160:
            raise GalaxyError("Invalid intent", "invalid_request")
        path = known_path(
            session,
            universe_id,
            empire_id,
            session.get(Planet, colony.planet_id).system_id,
            destination_id,
        )
        if (
            session.scalar(
                select(ExplorationMission.id).where(
                    ExplorationMission.empire_id == empire_id, ExplorationMission.status == "active"
                )
            )
            is not None
        ):
            raise GalaxyError("Expedition capacity engaged", "exploration_active")
        # Preserve the existing Research-before-Colony order even though no bonus is applied.
        research.catch_up(session, engine, universe_id, empire_id, at)
        catch_up_owned(session, engine, universe_id, empire_id, colony_id, at)
        rules = rules_for(session, universe_id)
        cost, duration = rules.exploration.quote(len(path))
        balances = {r: session.get(ResourceBalance, (colony_id, r)) for r in cost}
        if any(balances[r].stock < value for r, value in cost.items()):
            raise GalaxyError("Insufficient source resources", "insufficient_resources")
        try:
            due_at = utc(at) + timedelta(microseconds=duration)
        except OverflowError:
            raise GalaxyError("Deadline overflow", "invalid_request") from None
        snapshot = {
            "version": rules.version,
            "rules": rules.exploration.model_dump(),
            "cost": cost,
            "duration_us": duration,
            "path": list(map(str, path)),
            "colony_id": str(colony_id),
            "destination_id": str(destination_id),
        }
        for r, value in cost.items():
            balances[r].stock -= value
        row = ExplorationMission(
            universe_id=universe_id,
            empire_id=empire_id,
            colony_id=colony_id,
            destination_id=destination_id,
            idempotency_key=key,
            snapshot=snapshot,
            status="active",
            started_at=utc(at),
            due_at=due_at,
        )
        session.add(row)
        session.flush()
        for ordinal, route_id in enumerate(path):
            session.add(
                MissionLeg(
                    mission_id=row.id,
                    ordinal=ordinal,
                    empire_id=empire_id,
                    universe_id=universe_id,
                    route_id=route_id,
                )
            )
        schedule(
            session,
            state.stream_id,
            universe_id,
            key=f"exploration:{row.id}",
            kind="EXPLORATION_COMPLETE",
            due_at=due_at,
            payload={"mission_id": str(row.id)},
        )
        session.flush()
        return row


def complete_exploration(session, event, processed_at):
    if set(event.payload) != {"mission_id"}:
        raise TimelineError("Invalid exploration payload")
    row = session.get(ExplorationMission, UUID(event.payload["mission_id"]))
    if row is None or row.universe_id != event.universe_id:
        raise TimelineError("Mission outside event universe")
    state = state_for(session, row.universe_id, row.empire_id)
    if state.stream_id != event.stream_id or event.idempotency_key != f"exploration:{row.id}":
        raise TimelineError("Mission outside event stream")
    if row.status == "completed":
        if session.get(ExplorationReport, row.id) is None:
            raise TimelineError("Completed mission missing report")
        return
    rules = rules_for(session, row.universe_id)
    legs = list(
        session.scalars(
            select(MissionLeg).where(MissionLeg.mission_id == row.id).order_by(MissionLeg.ordinal)
        )
    )
    snap = row.snapshot
    if rules.exploration is None:
        raise TimelineError("Exploration rules missing")
    cost, duration = rules.exploration.quote(len(legs))
    expected = {
        "version": rules.version,
        "rules": rules.exploration.model_dump(),
        "cost": cost,
        "duration_us": duration,
        "path": [str(leg.route_id) for leg in legs],
        "colony_id": str(row.colony_id),
        "destination_id": str(row.destination_id),
    }
    if (
        not legs
        or snap != expected
        or row.status != "active"
        or row.due_at != event.due_at
        or row.due_at - row.started_at != timedelta(microseconds=duration)
    ):
        raise TimelineError("Inconsistent mission snapshot/deadline")
    # The persisted legs must still chain the source system to the destination.
    colony = session.get(Colony, row.colony_id)
    node = session.get(Planet, colony.planet_id).system_id if colony is not None else None
    for leg in legs:
        route = session.get(GalaxyRoute, leg.route_id)
        if (
            route is None
            or route.universe_id != row.universe_id
            or node
            not in (
                route.a_id,
                route.b_id,
            )
        ):
            raise TimelineError("Inconsistent mission path")
        node = route.b_id if route.a_id == node else route.a_id
    if node != row.destination_id:
        raise TimelineError("Inconsistent mission path")
    discoveries = map_system(
        session, row.universe_id, row.empire_id, row.destination_id, event.due_at
    )
    discoveries["path"] = snap["path"]
    session.add(
        ExplorationReport(
            mission_id=row.id,
            empire_id=row.empire_id,
            universe_id=row.universe_id,
            observed_at=event.due_at,
            processed_at=utc(processed_at),
            discoveries=discoveries,
        )
    )
    row.status, row.completed_at = "completed", event.due_at
    session.flush()
