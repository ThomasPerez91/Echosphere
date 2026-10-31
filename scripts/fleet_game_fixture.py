"""Test-only v0.4 graph for the disposable Fleet recipe; refused outside its dedicated *_test DB.

The universe is provisioned by Portal through the private control plane. This fixture only adds
what no product flow creates yet: explicit galaxy generation, one Empire with its colony on ONE
candidate site, its initial knowledge and, for the cargo proof only, a strictly test-only second
colony. The instance pins shorter Fleet durations so the recipe runs in minutes; costs, cargo,
fuel and every other rule stay the real v0.4 values.
"""

import json
import time
from datetime import UTC, datetime
from uuid import UUID

from app.colony.rules import Ruleset, load_ruleset
from app.colony.service import configure_universe, initialize_colony
from app.core.config import Settings
from app.fleet.models import Fleet, FleetCargo, FleetMission, FleetReport, FleetStack
from app.galaxy import service as galaxy
from app.galaxy.models import GalaxyPlanet, SystemKnowledge
from app.galaxy.world import generate_world
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import Colony, Empire, Planet, Universe
from app.simulation.clock import SystemClock
from app.simulation.models import ResourceBalance, ScheduledEvent
from app.simulation.service import TimeEngine
from sqlalchemy import select, text

DATABASE = "echosphere_fleet_game_test"
M = 1_000_000


def factory():
    settings = Settings()
    assert settings.postgres_db == DATABASE, "Fleet fixture is restricted to its disposable DB"
    engine = create_database_engine(settings)
    return engine, create_session_factory(engine)


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
    data = load_ruleset("v0.4").model_dump()
    for ship in data["fleets"]["classes"].values():
        ship["build_seconds"], ship["hop_seconds"] = 2, 20
    data["fleets"]["survey_seconds"] = 30
    rules = Ruleset.model_validate(data)
    now = datetime.now(UTC)
    with sessions.begin() as session:
        configure_universe(session, universe_id, rules)
        generate_world(session, universe_id)
        site = session.execute(
            text(
                "SELECT planet_id FROM galaxy_starting_sites WHERE universe_id = :u "
                "ORDER BY planet_id LIMIT 1"
            ),
            {"u": universe_id},
        ).scalar_one()
        empire = Empire(universe_id=universe_id, name="Empire de recette", controller_type="human")
        session.add(empire)
        session.flush()
        colony = Colony(universe_id=universe_id, empire_id=empire.id, planet_id=site)
        session.add(colony)
        session.flush()
        initialize_colony(session, universe_id, empire.id, colony.id, now)
        galaxy.initialize_empire(
            session, TimeEngine(sessions, SystemClock()), universe_id, empire.id, colony.id, now
        )
        result = {"empire_id": str(empire.id), "colony_id": str(colony.id)}
    engine.dispose()
    print(json.dumps(result))


def second_colony(universe_id, empire_id, system_id):
    """Test-only destination for the transport proof, with exactly 100 Alliages of free storage."""
    engine, sessions = factory()
    now = datetime.now(UTC)
    with sessions.begin() as session:
        known = session.get(SystemKnowledge, (UUID(empire_id), UUID(system_id)))
        assert known is not None and known.state != "DETECTED", "Destination must be mapped"
        planet_id = session.scalar(
            select(GalaxyPlanet.planet_id)
            .where(GalaxyPlanet.system_id == UUID(system_id))
            .order_by(GalaxyPlanet.planet_id)
            .limit(1)
        )
        planet = session.get(Planet, planet_id)
        planet.sector_capacity, planet.orbital_capacity = 12, 2  # reference initializer only
        colony = Colony(
            universe_id=UUID(universe_id), empire_id=UUID(empire_id), planet_id=planet_id
        )
        session.add(colony)
        session.flush()
        initialize_colony(session, UUID(universe_id), UUID(empire_id), colony.id, now)
        alloys = session.get(ResourceBalance, (colony.id, "alloys"))
        alloys.stock, alloys.rate_per_hour = 9_900 * M, 0
        result = {"colony_id": str(colony.id)}
    engine.dispose()
    print(json.dumps(result))


def state(empire_id):
    """Durable proof read directly in Game DB, never through a GET."""
    engine, sessions = factory()
    empire = UUID(empire_id)
    with sessions() as session:
        fleets = [
            {
                "id": str(f.id),
                "kind": f.kind,
                "status": f.status,
                "system_id": str(f.system_id) if f.system_id else None,
                "stacks": {
                    s.ship_class: s.count
                    for s in session.scalars(select(FleetStack).where(FleetStack.fleet_id == f.id))
                },
                "cargo": {
                    c.resource: c.amount
                    for c in session.scalars(select(FleetCargo).where(FleetCargo.fleet_id == f.id))
                },
            }
            for f in session.scalars(select(Fleet).where(Fleet.empire_id == empire))
        ]
        missions = []
        for m in session.scalars(
            select(FleetMission)
            .where(FleetMission.empire_id == empire)
            .order_by(FleetMission.started_at)
        ):
            known = session.get(SystemKnowledge, (empire, m.destination_id))
            events = sorted(
                [e.event_type, e.status, e.error_code]
                for e in session.scalars(
                    select(ScheduledEvent).where(ScheduledEvent.idempotency_key.like(f"%:{m.id}"))
                )
            )
            missions.append(
                {
                    "id": str(m.id),
                    "kind": m.kind,
                    "status": m.status,
                    "destination_state": known.state,
                    "report": session.get(FleetReport, m.id) is not None,
                    "events": events,
                }
            )
    engine.dispose()
    print(json.dumps({"fleets": fleets, "missions": missions}))


def stock(colony_id, resource):
    engine, sessions = factory()
    with sessions() as session:
        value = session.get(ResourceBalance, (UUID(colony_id), resource)).stock
    engine.dispose()
    print(json.dumps({"stock": value}))


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
