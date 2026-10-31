"""Test-only v0.3 graph for the disposable Galaxy recipe; refused outside its dedicated *_test DB.

The universe itself is provisioned by Portal through the private control plane. This fixture only
adds what no product flow creates yet (Q19–Q29/Q55): explicit galaxy generation, one Empire with
its colony on ONE candidate site, and its initial knowledge. The instance pins shorter Exploration
legs so the recipe completes in seconds; costs and every other rule stay the real v0.3 values.
"""

import json
import time
from datetime import UTC, datetime
from uuid import UUID

from app.colony.rules import Ruleset, load_ruleset
from app.colony.service import configure_universe, initialize_colony
from app.core.config import Settings
from app.galaxy import service as galaxy
from app.galaxy.world import generate_world
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import Colony, Empire, Universe
from app.simulation.clock import SystemClock
from app.simulation.service import TimeEngine
from sqlalchemy import text

DATABASE = "echosphere_galaxy_game_test"


def factory():
    settings = Settings()
    assert settings.postgres_db == DATABASE, (
        "Galaxy fixture is restricted to its disposable DB"
    )
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
    data = load_ruleset("v0.3").model_dump()
    data["exploration"]["leg_seconds"] = 2
    data["exploration"]["survey_seconds"] = 2
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
        empire = Empire(
            universe_id=universe_id, name="Empire de recette", controller_type="human"
        )
        session.add(empire)
        session.flush()
        colony = Colony(universe_id=universe_id, empire_id=empire.id, planet_id=site)
        session.add(colony)
        session.flush()
        initialize_colony(session, universe_id, empire.id, colony.id, now)
        galaxy.initialize_empire(
            session,
            TimeEngine(sessions, SystemClock()),
            universe_id,
            empire.id,
            colony.id,
            now,
        )
        result = {"empire_id": str(empire.id), "colony_id": str(colony.id)}
    engine.dispose()
    print(json.dumps(result))


def missions(empire_id):
    """Durable proof read directly in Game DB, never through a GET that could catch up lazily."""
    engine, sessions = factory()
    with sessions() as session:
        rows = session.execute(
            text(
                "SELECT m.status, k.state, r.mission_id IS NOT NULL, r.observed_at = m.due_at, "
                "r.processed_at >= r.observed_at, m.destination_id "
                "FROM exploration_missions m "
                "JOIN system_knowledge k ON k.empire_id = m.empire_id "
                "AND k.system_id = m.destination_id "
                "LEFT JOIN exploration_reports r ON r.mission_id = m.id "
                "WHERE m.empire_id = :empire ORDER BY m.started_at"
            ),
            {"empire": empire_id},
        ).all()
    engine.dispose()
    print(json.dumps([[*row[:5], str(row[5])] for row in rows]))


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
