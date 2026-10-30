"""Test-only Colony graph for the disposable 5D recipe; refused outside its dedicated *_test DB.

The universe itself is provisioned by Portal through the private control plane. This fixture only
adds what no product flow creates yet (Q19–Q29/Q55): reference economy, Empire, planet and colony.
The instance pins a faster construction speed (per-universe ratio, a validated ruleset field) so
the recipe completes orders in seconds; production rules are otherwise the real v0.1 ruleset.
"""

import json
import time
from datetime import UTC, datetime
from uuid import UUID

from app.colony.rules import Ruleset, load_ruleset
from app.colony.service import configure_universe, initialize_colony
from app.core.config import Settings
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import Colony, Empire, Planet, StellarSystem, Universe
from sqlalchemy import text

DATABASE = "echosphere_colony_game_test"


def factory():
    settings = Settings()
    assert settings.postgres_db == DATABASE, (
        "Colony fixture is restricted to its disposable DB"
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
    data = load_ruleset().model_dump()
    data["colony"]["speeds"]["construction"] = {"numerator": 60, "denominator": 1}
    rules = Ruleset.model_validate(data)
    with sessions.begin() as session:
        configure_universe(session, universe_id, rules)
        empire = Empire(
            universe_id=universe_id, name="Empire de recette", controller_type="human"
        )
        system = StellarSystem(universe_id=universe_id, name="Système de recette")
        session.add_all([empire, system])
        session.flush()
        planet = Planet(
            universe_id=universe_id,
            system_id=system.id,
            name="Nouvelle Aube",
            sector_capacity=rules.colony.sectors,
            orbital_capacity=rules.colony.orbital_slots,
        )
        session.add(planet)
        session.flush()
        colony = Colony(
            universe_id=universe_id, empire_id=empire.id, planet_id=planet.id
        )
        session.add(colony)
        session.flush()
        initialize_colony(session, universe_id, empire.id, colony.id, datetime.now(UTC))
        result = {"empire_id": str(empire.id), "colony_id": str(colony.id)}
    engine.dispose()
    print(json.dumps(result))


def orders(colony_id):
    engine, sessions = factory()
    with sessions() as session:
        rows = session.execute(
            text(
                "SELECT infrastructure_type, target_level, status FROM construction_orders "
                "WHERE colony_id = :colony ORDER BY sequence"
            ),
            {"colony": colony_id},
        ).all()
    engine.dispose()
    print(json.dumps([list(row) for row in rows]))


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
