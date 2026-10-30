"""Test-only accepted construction; invoked solely inside the disposable handoff project."""

import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.colony.models import ConstructionOrder
from app.colony.rules import load_ruleset
from app.colony.service import configure_universe, enqueue, initialize_colony
from app.core.config import Settings
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import Colony, Empire, Planet, StellarSystem
from app.simulation.clock import SystemClock
from app.simulation.service import TimeEngine


def main(universe_id):
    settings = Settings()
    assert settings.postgres_db == "echosphere_handoff_game_test"
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    rules = load_ruleset()
    at = datetime.now(UTC) - timedelta(days=1)
    universe_id = UUID(universe_id)
    with factory.begin() as session:
        configure_universe(session, universe_id, rules)
        empire = Empire(
            universe_id=universe_id, name="C09 test only", controller_type="human"
        )
        system = StellarSystem(universe_id=universe_id, name="C09 test only")
        session.add_all([empire, system])
        session.flush()
        planet = Planet(
            universe_id=universe_id,
            system_id=system.id,
            name="C09 test only",
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
        initialize_colony(session, universe_id, empire.id, colony.id, at)
        order = enqueue(
            session,
            TimeEngine(factory, SystemClock()),
            universe_id,
            empire.id,
            colony.id,
            key="c09-outage",
            kind="extraction_complex",
            sector=rules.colony.sectors,
            target_level=1,
            at=at,
        )
        identifier = order.id
    for _ in range(30):
        with factory() as session:
            complete = session.get(ConstructionOrder, identifier).status == "completed"
        if complete:
            break
        time.sleep(1)
    assert complete, (
        "The live Game worker must finish an accepted action while Portal is offline"
    )
    engine.dispose()
    print("C09 Game worker completed an accepted construction while Portal was stopped")
