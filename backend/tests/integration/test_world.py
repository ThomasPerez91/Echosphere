from datetime import timedelta

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.exc import DataError, IntegrityError

from app.persistence.database import create_session_factory
from app.persistence.models import Colony, Empire, Planet, StellarSystem, Universe

pytestmark = pytest.mark.integration


def world(session, label="A"):
    universe = Universe(name=f"Universe {label}", seed=f"seed-{label}")
    session.add(universe)
    session.flush()
    empire = Empire(universe_id=universe.id, name="Empire", controller_type="human")
    system = StellarSystem(universe_id=universe.id, name="System")
    session.add_all([empire, system])
    session.flush()
    planet = Planet(
        universe_id=universe.id,
        system_id=system.id,
        name="Planet",
        sector_capacity=12,
        orbital_capacity=2,
    )
    session.add(planet)
    session.flush()
    return universe, empire, system, planet


def test_migrations_roundtrip_and_no_model_drift(database_engine, migration_config):
    command.check(migration_config)
    command.downgrade(migration_config, "base")
    assert set(inspect(database_engine).get_table_names()) == {"alembic_version"}
    command.upgrade(migration_config, "head")
    command.check(migration_config)
    assert set(inspect(database_engine).get_table_names()) == {
        "universe_economies",
        "colony_economies",
        "colony_infrastructures",
        "construction_orders",
        "event_streams",
        "colony_timelines",
        "resource_balances",
        "scheduled_events",
        "alembic_version",
        "universes",
        "empires",
        "stellar_systems",
        "planets",
        "colonies",
    }


def test_world_roundtrip_utc_and_colony(session):
    universe, empire, system, planet = world(session)
    colony = Colony(universe_id=universe.id, empire_id=empire.id, planet_id=planet.id)
    session.add(colony)
    session.flush()
    assert colony.id is not None
    assert colony.created_at.utcoffset() == timedelta(0)
    session.expire_all()
    assert session.get(Colony, colony.id).planet_id == planet.id
    assert session.get(Planet, planet.id).system_id == system.id


def test_planet_cannot_reference_another_universe_system(session):
    universe, _, _, _ = world(session)
    _, _, foreign_system, _ = world(session, "B")
    session.add(
        Planet(
            universe_id=universe.id,
            system_id=foreign_system.id,
            name="Invalid",
            sector_capacity=12,
            orbital_capacity=2,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("foreign", ["empire", "planet"])
def test_colony_cannot_cross_universes(session, foreign):
    universe, empire, _, planet = world(session)
    _, other_empire, _, other_planet = world(session, "B")
    session.add(
        Colony(
            universe_id=universe.id,
            empire_id=other_empire.id if foreign == "empire" else empire.id,
            planet_id=other_planet.id if foreign == "planet" else planet.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_planet_cannot_have_two_colonies(session):
    universe, empire, _, planet = world(session)
    session.add(Colony(universe_id=universe.id, empire_id=empire.id, planet_id=planet.id))
    session.flush()
    session.add(Colony(universe_id=universe.id, empire_id=empire.id, planet_id=planet.id))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize(
    "field,value", [("sector_capacity", 0), ("sector_capacity", -1), ("orbital_capacity", -1)]
)
def test_invalid_capacity_rejected(session, field, value):
    _, _, _, planet = world(session)
    setattr(planet, field, value)
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("value,error_type", [("bot", IntegrityError), ("cheating_bot", DataError)])
def test_controller_type_rejected(session, value, error_type):
    _, empire, _, _ = world(session)
    empire.controller_type = value
    with pytest.raises(error_type) as error:
        session.flush()
    if error_type is IntegrityError:
        assert error.value.orig.diag.constraint_name == "ck_empires_controller_type"


def test_invalid_write_rolls_back_whole_service_transaction(database_engine):
    factory = create_session_factory(database_engine)
    universe_id = None
    with pytest.raises(IntegrityError), factory.begin() as session:
        universe = Universe(name="Rollback candidate", seed="rollback")
        session.add(universe)
        session.flush()
        universe_id = universe.id
        session.add(Empire(universe_id=universe.id, name="Invalid", controller_type="invalid"))
        session.flush()
    with factory() as session:
        assert session.scalar(select(Universe).where(Universe.id == universe_id)) is None
