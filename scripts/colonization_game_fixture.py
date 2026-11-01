"""Test-only v0.5 graph for the disposable Colonization recipe; refused outside its *_test DB.

The universe is provisioned by Portal through the private control plane. This fixture only adds
what no product flow creates yet: explicit galaxy generation, the human Empire with its colony,
and, for the two-Empire contest only, a test-only rival Empire plus test-placed colonizer fleets
in one system. Durations are shortened for the recipe; every other rule is the real v0.5 data.
Contest missions go through the real Fleet service launch at one frozen instant (same due_at).
"""

import json
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.colony.rules import Ruleset, load_ruleset
from app.colony.service import configure_universe, initialize_colony
from app.core.config import Settings
from app.fleet import service as fleet_service
from app.fleet.models import Fleet, FleetCargo, FleetMission, FleetReport, FleetStack
from app.galaxy import service as galaxy
from app.galaxy.models import PlanetKnowledge, SystemKnowledge
from app.galaxy.world import generate_world
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import Colony, Empire, Planet, Universe
from app.simulation.clock import SystemClock
from app.simulation.models import ResourceBalance
from app.simulation.service import TimeEngine
from sqlalchemy import select, text

DATABASE = "echosphere_colonization_game_test"
M = 1_000_000
PACKAGE = {"alloys": 600, "flux": 300, "data": 100}


def factory():
    settings = Settings()
    assert settings.postgres_db == DATABASE, "Colonization fixture is restricted to its test DB"
    engine = create_database_engine(settings)
    return engine, create_session_factory(engine)


def empire_with_colony(session, sessions, universe_id, site_index, name, now):
    site = session.execute(
        text(
            "SELECT planet_id FROM galaxy_starting_sites WHERE universe_id = :u "
            "ORDER BY planet_id OFFSET :i LIMIT 1"
        ),
        {"u": universe_id, "i": site_index},
    ).scalar_one()
    empire = Empire(universe_id=universe_id, name=name, controller_type="human")
    session.add(empire)
    session.flush()
    colony = Colony(universe_id=universe_id, empire_id=empire.id, planet_id=site)
    session.add(colony)
    session.flush()
    initialize_colony(session, universe_id, empire.id, colony.id, now)
    galaxy.initialize_empire(
        session, TimeEngine(sessions, SystemClock()), universe_id, empire.id, colony.id, now
    )
    return empire, colony


def setup(universe_id):
    engine, sessions = factory()
    universe_id = UUID(universe_id)
    for _ in range(60):
        with sessions() as session:
            if session.get(Universe, universe_id) is not None:
                break
        time.sleep(0.5)
    else:
        raise RuntimeError("Universe was not provisioned through the control plane")
    data = load_ruleset("v0.5").model_dump()
    for ship in data["fleets"]["classes"].values():
        ship["build_seconds"], ship["hop_seconds"] = 2, 20
    data["fleets"]["survey_seconds"] = 30
    rules = Ruleset.model_validate(data)
    now = datetime.now(UTC)
    with sessions.begin() as session:
        configure_universe(session, universe_id, rules)
        generate_world(session, universe_id)
        empire, colony = empire_with_colony(
            session, sessions, universe_id, 0, "Empire de recette", now
        )
        planet = session.get(Planet, colony.planet_id)
        result = {
            "empire_id": str(empire.id),
            "colony_id": str(colony.id),
            "system_id": str(planet.system_id),
        }
    engine.dispose()
    print(json.dumps(result))


def station(session, universe_id, empire_id, colony_id, system_id, at):
    known = session.get(SystemKnowledge, (empire_id, system_id))
    if known is None or known.state == "DETECTED":
        galaxy.map_system(session, universe_id, empire_id, system_id, at)
    fleet = Fleet(
        empire_id=empire_id,
        universe_id=universe_id,
        home_colony_id=colony_id,
        kind="TASK",
        status="STATIONED",
        system_id=system_id,
        name="Colonisateur de recette",
    )
    session.add(fleet)
    session.flush()
    session.add(FleetStack(fleet_id=fleet.id, ship_class="colonizer", count=1))
    for resource, value in PACKAGE.items():
        session.add(FleetCargo(fleet_id=fleet.id, resource=resource, amount=value * M))
    session.flush()
    return fleet.id


def contest(universe_id, empire_id, colony_id, system_id):
    """Test-only rival Empire; both Empires launch COLONIZE on one free world at one instant."""
    engine, sessions = factory()
    universe_id, empire_id = UUID(universe_id), UUID(empire_id)
    colony_id, system_id = UUID(colony_id), UUID(system_id)
    now = datetime.now(UTC)
    with sessions.begin() as session:
        rival, rival_colony = empire_with_colony(
            session, sessions, universe_id, 1, "Empire rival de recette", now
        )
        planet = session.scalar(
            select(PlanetKnowledge.planet_id)
            .outerjoin(Colony, Colony.planet_id == PlanetKnowledge.planet_id)
            .where(
                PlanetKnowledge.empire_id == empire_id,
                PlanetKnowledge.system_id == system_id,
                Colony.id.is_(None),
            )
            .order_by(PlanetKnowledge.planet_id)
            .limit(1)
        )
        ours = station(session, universe_id, empire_id, colony_id, system_id, now)
        theirs = station(session, universe_id, rival.id, rival_colony.id, system_id, now)
        rival_id = rival.id
    engine_ = TimeEngine(sessions, SystemClock())
    missions = {}
    for empire, fleet in [(empire_id, ours), (rival_id, theirs)]:
        with sessions.begin() as session:
            mission = fleet_service.launch(
                session,
                engine_,
                universe_id,
                empire,
                fleet,
                "COLONIZE",
                None,
                {"colonizer": 1},
                None,
                key=f"recipe-contest-{uuid4().hex}",
                at=now,  # one frozen instant: equal due_at, the persisted rank decides
                target_planet_id=planet,
            )
            missions[str(empire)] = str(mission.id)
    engine.dispose()
    print(json.dumps({"planet": str(planet), "rival": str(rival_id), "missions": missions}))


def outcome(planet_id, missions):
    engine, sessions = factory()
    with sessions() as session:
        owners = [
            str(c.empire_id)
            for c in session.scalars(select(Colony).where(Colony.planet_id == UUID(planet_id)))
        ]
        rows = {
            empire: session.get(FleetMission, UUID(mission)) for empire, mission in missions.items()
        }
        result = {
            "owners": owners,
            "statuses": {e: m.status for e, m in rows.items()},
            "ranks": {
                e: [m.due_at.isoformat(), m.started_at.isoformat(), str(m.id)]
                for e, m in rows.items()
            },
            "reports": {
                e: (r.result if (r := session.get(FleetReport, m.id)) else None)
                for e, m in rows.items()
            },
            "fleets": {
                e: [
                    session.get(Fleet, m.fleet_id).status,
                    session.get(Fleet, m.fleet_id).system_id is not None,
                ]
                for e, m in rows.items()
            },
        }
    engine.dispose()
    print(json.dumps(result))


def founded(empire_id):
    """Durable proof read directly in Game DB, never through a GET."""
    engine, sessions = factory()
    with sessions() as session:
        rows = []
        for c in session.scalars(
            select(Colony).where(
                Colony.empire_id == UUID(empire_id), Colony.founding_mission_id.isnot(None)
            )
        ):
            planet = session.get(Planet, c.planet_id)
            rows.append(
                {
                    "colony_id": str(c.id),
                    "planet": planet.name,
                    "sectors": planet.sector_capacity,
                    "stocks": {
                        r: session.get(ResourceBalance, (c.id, r)).stock
                        for r in ("alloys", "flux", "data")
                    },
                    "rates": [
                        session.get(ResourceBalance, (c.id, r)).rate_per_hour
                        for r in ("alloys", "flux", "data")
                    ],
                }
            )
    engine.dispose()
    print(json.dumps(rows))


def expire(universe_id):
    """Simulates reaching the absolute deadline: moves it just after the last activity."""
    engine, sessions = factory()
    with sessions.begin() as session:
        count = session.execute(
            text(
                "UPDATE game_sessions SET expires_at = last_activity_at + interval '1 millisecond' "
                "WHERE universe_id = :universe AND revoked_at IS NULL"
            ),
            {"universe": universe_id},
        ).rowcount
    engine.dispose()
    assert count == 1, "Exactly one live recipe session expected"
    print(json.dumps({"expired": count}))
