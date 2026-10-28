from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.colony.models import (
    ColonyEconomy,
    ColonyInfrastructure,
    ConstructionOrder,
    UniverseEconomy,
)
from app.colony.rules import Ruleset, load_ruleset
from app.colony.service import (
    ColonyError,
    cancel,
    complete_construction,
    configure_universe,
    enqueue,
    initialize_colony,
)
from app.persistence.database import create_session_factory
from app.persistence.models import Colony, Empire, Planet, StellarSystem, Universe
from app.simulation.models import ColonyTimeline, EventStream, ResourceBalance, ScheduledEvent
from app.simulation.production import MICRO_UNITS
from app.simulation.scheduler import IdempotencyConflict
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration
START = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class Clock:
    value: datetime = START

    def now(self):
        return self.value


@dataclass(frozen=True)
class Scope:
    universe: object
    empire: object
    colony: object


@pytest.fixture
def economy(database_engine):
    factory, clock, created = create_session_factory(database_engine), Clock(), []
    rules = load_ruleset()

    def make(override=None):
        config = override or rules
        with factory.begin() as session:
            universe = Universe(name="Economy test", seed="economy")
            session.add(universe)
            session.flush()
            created.append(universe.id)
            configure_universe(session, universe.id, config)
            empire = Empire(universe_id=universe.id, name="Human", controller_type="human")
            system = StellarSystem(universe_id=universe.id, name="Home")
            session.add_all([empire, system])
            session.flush()
            planet = Planet(
                universe_id=universe.id,
                system_id=system.id,
                name="Reference",
                sector_capacity=config.colony.sectors,
                orbital_capacity=config.colony.orbital_slots,
            )
            session.add(planet)
            session.flush()
            colony = Colony(universe_id=universe.id, empire_id=empire.id, planet_id=planet.id)
            session.add(colony)
            session.flush()
            initialize_colony(session, universe.id, empire.id, colony.id, START)
            return Scope(universe.id, empire.id, colony.id)

    yield factory, clock, TimeEngine(factory, clock), make
    with factory.begin() as session:
        for universe in created:
            colonies = select(Colony.id).where(Colony.universe_id == universe)
            for model in [ConstructionOrder, ColonyInfrastructure, ColonyEconomy]:
                session.execute(delete(model).where(model.universe_id == universe))
            session.execute(delete(ScheduledEvent).where(ScheduledEvent.universe_id == universe))
            session.execute(delete(ResourceBalance).where(ResourceBalance.colony_id.in_(colonies)))
            session.execute(delete(ColonyTimeline).where(ColonyTimeline.universe_id == universe))
            session.execute(delete(EventStream).where(EventStream.universe_id == universe))
            for model in [Colony, Planet, StellarSystem, Empire, UniverseEconomy]:
                session.execute(delete(model).where(model.universe_id == universe))
            session.execute(delete(Universe).where(Universe.id == universe))


def add(
    factory, engine, scope, key="build", *, kind="extraction_complex", sector=5, level=1, at=START
):
    with factory.begin() as session:
        return enqueue(
            session,
            engine,
            scope.universe,
            scope.empire,
            scope.colony,
            key=key,
            kind=kind,
            sector=sector,
            target_level=level,
            at=at,
        )


def stop(factory, engine, scope, order, at=START):
    with factory.begin() as session:
        return cancel(session, engine, scope.universe, scope.empire, scope.colony, order, at=at)


def balances(factory, scope):
    with factory() as session:
        return {
            row.resource: row.stock
            for row in session.scalars(
                select(ResourceBalance).where(ResourceBalance.colony_id == scope.colony)
            )
        }


def test_reference_colony_initialization_and_atomic_reservation(economy):
    factory, clock, engine, make = economy
    scope = make()
    assert balances(factory, scope) == {
        "alloys": 2000 * MICRO_UNITS,
        "flux": 1500 * MICRO_UNITS,
        "data": 750 * MICRO_UNITS,
    }
    with factory() as session:
        rows = session.scalars(
            select(ColonyInfrastructure)
            .where(ColonyInfrastructure.colony_id == scope.colony)
            .order_by(ColonyInfrastructure.sector_index)
        ).all()
        assert len(rows) == 4 and [r.sector_index for r in rows] == [1, 2, 3, 4]
        assert [r.level for r in rows] == [1] * 4
        for resource, rate in [("alloys", 120), ("flux", 100), ("data", 60)]:
            row = session.get(ResourceBalance, (scope.colony, resource))
            assert row.rate_per_hour == rate * MICRO_UNITS
            assert row.capacity == 10000 * MICRO_UNITS
    first = add(factory, engine, scope)
    assert first.status == "active"
    assert first.due_at == START + timedelta(microseconds=109090910)
    assert balances(factory, scope)["alloys"] == 1750 * MICRO_UNITS
    second = add(factory, engine, scope, "two", sector=6)
    assert second.status == "queued" and second.started_at is None
    assert balances(factory, scope)["alloys"] == 1500 * MICRO_UNITS


def test_queue_limit_and_repeated_buildings(economy):
    factory, _, engine, make = economy
    scope = make()
    for sector in [5, 6, 7]:
        add(factory, engine, scope, str(sector), sector=sector)
    before = balances(factory, scope)
    with pytest.raises(ColonyError, match="queue full"):
        add(factory, engine, scope, "four", sector=8)
    assert balances(factory, scope) == before


@pytest.mark.parametrize(
    "kind,sector,level,error",
    [
        ("extraction_complex", 0, 1, "capacity"),
        ("extraction_complex", 13, 1, "capacity"),
        ("flux_reactor", 1, 1, "Occupied"),
        ("extraction_complex", 1, 3, "upgrade"),
        ("industrial_complex", 5, 1, "uniqueness"),
    ],
)
def test_invalid_sector_upgrade_or_unique_building_refused(economy, kind, sector, level, error):
    factory, _, engine, make = economy
    scope = make()
    before = balances(factory, scope)
    with pytest.raises(ColonyError, match=error):
        add(factory, engine, scope, kind=kind, sector=sector, level=level)
    assert balances(factory, scope) == before


def test_logistics_unique_in_completed_and_reserved_sectors(economy):
    factory, _, engine, make = economy
    scope = make()
    add(factory, engine, scope, kind="logistics_center")
    with pytest.raises(ColonyError, match="uniqueness"):
        add(factory, engine, scope, "other", kind="logistics_center", sector=6)


def test_insufficient_resources_rolls_back_even_if_caller_catches_error(economy):
    factory, _, engine, make = economy
    scope = make()
    with factory.begin() as session:
        session.get(ResourceBalance, (scope.colony, "flux")).stock = 0
    before = balances(factory, scope)
    with factory.begin() as session:
        with pytest.raises(ColonyError, match="Insufficient"):
            enqueue(
                session,
                engine,
                scope.universe,
                scope.empire,
                scope.colony,
                key="no",
                kind="extraction_complex",
                sector=5,
                target_level=1,
                at=START,
            )
    assert balances(factory, scope) == before
    with factory() as session:
        assert not session.scalars(select(ConstructionOrder)).all()


def test_concurrent_commands_cannot_spend_same_resources(economy):
    factory, _, engine, make = economy
    scope = make()
    with factory.begin() as session:
        for resource, value in [("alloys", 250), ("flux", 120), ("data", 0)]:
            session.get(ResourceBalance, (scope.colony, resource)).stock = value * MICRO_UNITS
    barrier = Barrier(2)

    def build(sector):
        barrier.wait(timeout=5)
        try:
            return add(factory, engine, scope, str(sector), sector=sector).status
        except ColonyError:
            return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(build, [5, 6]))
    assert sorted(result) == ["active", "refused"]
    assert balances(factory, scope)["alloys"] == 0


def test_command_replay_before_after_completion_and_conflict(economy):
    factory, clock, engine, make = economy
    scope = make()
    order = add(factory, engine, scope)
    assert add(factory, engine, scope).id == order.id
    with pytest.raises(IdempotencyConflict):
        add(factory, engine, scope, sector=6)
    clock.value = START + timedelta(hours=1)
    assert TimeEngine(factory, clock).process_next().status == "completed"
    assert add(factory, engine, scope).id == order.id
    assert TimeEngine(factory, clock).process_next() is None
    with factory() as session:
        assert (
            session.scalar(
                select(ColonyInfrastructure).where(
                    ColonyInfrastructure.colony_id == scope.colony,
                    ColonyInfrastructure.sector_index == 5,
                )
            ).level
            == 1
        )


def test_cancel_queued_full_refund_active_eighty_and_idempotence(economy):
    factory, _, engine, make = economy
    scope = make()
    first = add(factory, engine, scope)
    second = add(factory, engine, scope, "two", sector=6)
    assert stop(factory, engine, scope, second.id).refunded["alloys"] == 250 * MICRO_UNITS
    assert balances(factory, scope)["alloys"] == 1750 * MICRO_UNITS
    assert stop(factory, engine, scope, first.id).refunded["alloys"] == 200 * MICRO_UNITS
    assert balances(factory, scope)["alloys"] == 1950 * MICRO_UNITS
    assert stop(factory, engine, scope, first.id).status == "cancelled"
    assert balances(factory, scope)["alloys"] == 1950 * MICRO_UNITS
    assert engine.process_next() is None


def test_active_cancel_starts_next_at_logical_cancellation_time(economy):
    factory, clock, engine, make = economy
    scope = make()
    first = add(factory, engine, scope)
    second = add(factory, engine, scope, "two", sector=6)
    clock.value = START + timedelta(seconds=30)
    stop(factory, engine, scope, first.id, at=clock.value)
    with factory() as session:
        assert session.get(ConstructionOrder, second.id).started_at == clock.value
        assert (
            session.scalar(
                select(ScheduledEvent).where(
                    ScheduledEvent.idempotency_key == f"construction:{first.id}"
                )
            ).error_code
            == "cancelled"
        )
    clock.value = START + timedelta(hours=1)
    assert TimeEngine(factory, clock).process_next().status == "completed"
    assert TimeEngine(factory, clock).process_next() is None


def test_cancel_dependency_chain_releases_reserved_sector(economy):
    factory, _, engine, make = economy
    scope = make()
    first = add(factory, engine, scope)
    second = add(factory, engine, scope, "upgrade", sector=5, level=2)
    stop(factory, engine, scope, first.id)
    with factory() as session:
        assert session.get(ConstructionOrder, second.id).status == "cancelled"
        assert session.get(ConstructionOrder, second.id).refunded["alloys"] == 800 * MICRO_UNITS
    assert (
        add(factory, engine, scope, "replacement", kind="flux_reactor", sector=5).status == "active"
    )


def test_industrial_completion_changes_next_duration_at_activation(economy):
    factory, clock, engine, make = economy
    scope = make()
    first = add(factory, engine, scope, "industry", kind="industrial_complex", sector=4, level=2)
    second = add(factory, engine, scope, "extraction", sector=1, level=2)
    clock.value = START + timedelta(hours=1)
    assert TimeEngine(factory, clock).process_next().status == "completed"
    with factory() as session:
        row = session.get(ConstructionOrder, second.id)
        assert row.started_at == first.due_at and row.applied_bonus_bps == 2000
        assert row.due_at - row.started_at == timedelta(seconds=750)
    assert TimeEngine(factory, clock).process_next().status == "completed"
    with factory.begin() as session:
        assert engine.catch_up(session, scope.colony, clock.value).complete
        assert (
            session.get(ResourceBalance, (scope.colony, "alloys")).rate_per_hour
            == 210 * MICRO_UNITS
        )


def test_storage_completion_and_saturation_preserve_lazy_exactness(economy):
    factory, clock, engine, make = economy
    scope = make()
    order = add(factory, engine, scope, kind="logistics_center")
    clock.value = START + timedelta(days=10)
    assert TimeEngine(factory, clock).process_next().status == "completed"
    with factory.begin() as session:
        assert engine.catch_up(session, scope.colony, clock.value).complete
        for resource in ["alloys", "flux", "data"]:
            row = session.get(ResourceBalance, (scope.colony, resource))
            assert row.capacity == 20000 * MICRO_UNITS and row.stock == row.capacity
            assert row.remainder == 0
        assert session.get(ConstructionOrder, order.id).completed_at == order.due_at


def test_saturated_production_without_logistics_has_no_hidden_overflow(economy):
    factory, clock, engine, make = economy
    scope = make()
    clock.value = START + timedelta(days=20)
    with factory.begin() as session:
        assert engine.catch_up(session, scope.colony, clock.value).complete
    assert set(balances(factory, scope).values()) == {10000 * MICRO_UNITS}
    # Free storage after saturation; elapsed excess production must not be recovered.
    with factory.begin() as session:
        session.get(ResourceBalance, (scope.colony, "alloys")).stock -= 100 * MICRO_UNITS
    clock.value += timedelta(minutes=1)
    with factory.begin() as session:
        engine.catch_up(session, scope.colony, clock.value)
    assert balances(factory, scope)["alloys"] == 9902 * MICRO_UNITS


def test_instance_speeds_and_pinned_rules_snapshot(economy):
    factory, _, engine, make = economy
    rules = load_ruleset().model_dump()
    rules["colony"]["speeds"]["economy"] = {"numerator": 3, "denominator": 2}
    rules["colony"]["speeds"]["construction"] = {"numerator": 2, "denominator": 1}
    faster = make(Ruleset.model_validate(rules))
    normal = make()
    order = add(factory, engine, faster)
    assert order.due_at == START + timedelta(microseconds=54545455)
    with factory() as session:
        assert (
            session.get(ResourceBalance, (faster.colony, "alloys")).rate_per_hour
            == 180 * MICRO_UNITS
        )
        assert (
            session.get(ResourceBalance, (normal.colony, "alloys")).rate_per_hour
            == 120 * MICRO_UNITS
        )
        assert (
            session.get(ConstructionOrder, order.id).snapshot["quote"]["cost"]["alloys"]
            == 250 * MICRO_UNITS
        )
    rules["catalogue"]["infrastructures"]["extraction_complex"]["explicit_levels"][0]["cost"][
        "alloys"
    ] = 999
    assert add(factory, engine, faster).snapshot["quote"]["cost"]["alloys"] == 250 * MICRO_UNITS


def test_worker_crash_rolls_back_building_and_followup_then_restart(economy):
    factory, clock, engine, make = economy
    scope = make()
    order = add(factory, engine, scope)
    next_order = add(factory, engine, scope, "two", sector=6)

    class Crash(BaseException):
        pass

    def crash(session, event):
        complete_construction(session, event)
        raise Crash()

    clock.value = START + timedelta(hours=1)
    with pytest.raises(Crash):
        TimeEngine(factory, clock, handlers={"CONSTRUCTION_COMPLETE": crash}).process_next()
    with factory() as session:
        assert session.get(ConstructionOrder, order.id).status == "active"
        assert session.get(ConstructionOrder, next_order.id).status == "queued"
        assert len(session.scalars(select(ColonyInfrastructure)).all()) == 4
    assert TimeEngine(factory, clock).process_next().status == "completed"
    assert TimeEngine(factory, clock).process_next().status == "completed"
    assert TimeEngine(factory, clock).process_next() is None


def test_cross_universe_commands_and_database_fk_rejected(economy):
    factory, _, engine, make = economy
    a, b = make(), make()
    with pytest.raises(ColonyError):
        add(factory, engine, Scope(b.universe, b.empire, a.colony))
    with pytest.raises(ColonyError):
        add(factory, engine, Scope(a.universe, b.empire, a.colony))
    with factory.begin() as session, pytest.raises(IntegrityError):
        session.add(
            ColonyInfrastructure(
                colony_id=a.colony,
                universe_id=b.universe,
                infrastructure_type="flux_reactor",
                sector_index=5,
                level=1,
            )
        )
        session.flush()
    with pytest.raises(ColonyError):
        stop(factory, engine, a, uuid4())


def test_database_rejects_duplicate_sector_and_invalid_level(economy):
    factory, _, _, make = economy
    scope = make()
    for sector, level in [(1, 1), (5, 0), (0, 1)]:
        with factory.begin() as session, pytest.raises(IntegrityError):
            session.add(
                ColonyInfrastructure(
                    colony_id=scope.colony,
                    universe_id=scope.universe,
                    infrastructure_type="extraction_complex",
                    sector_index=sector,
                    level=level,
                )
            )
            session.flush()


def test_refund_capacity_refusal_is_atomic_and_preserves_full_entitlement(economy):
    factory, clock, engine, make = economy
    scope = make()
    first = add(factory, engine, scope)
    with factory.begin() as session:
        session.get(ResourceBalance, (scope.colony, "alloys")).stock = 10000 * MICRO_UNITS
    with pytest.raises(ColonyError, match="Refund exceeds"):
        stop(factory, engine, scope, first.id)
    with factory() as session:
        assert session.get(ConstructionOrder, first.id).status == "active"
    assert balances(factory, scope)["alloys"] == 10000 * MICRO_UNITS


def test_completed_order_cannot_be_cancelled(economy):
    factory, clock, engine, make = economy
    scope = make()
    first = add(factory, engine, scope)
    clock.value = START + timedelta(hours=1)
    with pytest.raises(ColonyError, match="Completed"):
        stop(factory, engine, scope, first.id, at=clock.value)


def test_populated_economy_downgrade_refuses_before_ddl(economy, migration_config):
    factory, _, _, make = economy
    scope = make()
    with pytest.raises(RuntimeError, match="Cannot downgrade populated"):
        command.downgrade(migration_config, "0003_generic_event_streams")
    with factory() as session:
        assert session.get(UniverseEconomy, scope.universe).ruleset_version == "v0.1"


def test_level_six_completion_and_additive_production(economy):
    from app.colony.service import refresh_effects

    factory, clock, engine, make = economy
    scope = make()
    with factory.begin() as session:
        building = session.scalar(
            select(ColonyInfrastructure).where(
                ColonyInfrastructure.colony_id == scope.colony,
                ColonyInfrastructure.sector_index == 1,
            )
        )
        building.level = 5
        session.add(
            ColonyInfrastructure(
                colony_id=scope.colony,
                universe_id=scope.universe,
                sector_index=5,
                infrastructure_type="logistics_center",
                level=3,
            )
        )
        session.add(
            ColonyInfrastructure(
                colony_id=scope.colony,
                universe_id=scope.universe,
                sector_index=6,
                infrastructure_type="extraction_complex",
                level=2,
            )
        )
        session.flush()
        refresh_effects(session, scope.colony, load_ruleset())
        for resource in ["alloys", "flux", "data"]:
            session.get(ResourceBalance, (scope.colony, resource)).stock = 60000 * MICRO_UNITS
    order = add(factory, engine, scope, sector=1, level=6)
    clock.value = START + timedelta(days=2)
    assert engine.process_next().status == "completed"
    with factory() as session:
        assert session.get(ConstructionOrder, order.id).status == "completed"
        assert session.get(ResourceBalance, (scope.colony, "alloys")).rate_per_hour == (
            1_075_200_000 + 210 * MICRO_UNITS
        )


def test_concurrent_cancellation_refunds_once(economy):
    factory, _, engine, make = economy
    scope = make()
    order = add(factory, engine, scope)
    barrier = Barrier(2)

    def cancel_once(_):
        barrier.wait(timeout=5)
        return stop(factory, engine, scope, order.id).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(cancel_once, [1, 2])) == ["cancelled", "cancelled"]
    assert balances(factory, scope)["alloys"] == 1950 * MICRO_UNITS
