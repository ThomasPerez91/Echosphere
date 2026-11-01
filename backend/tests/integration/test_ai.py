"""AI runs against real PostgreSQL; identities, stocks and units are never faked for policy."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from app.ai.bootstrap import bootstrap
from app.ai.controller import AIDenied, activate, change_state
from app.ai.models import AIBootstrap, AIController
from app.colony.models import ColonyInfrastructure, UniverseEconomy
from app.colony.rules import load_ruleset
from app.control.models import EmpireBinding, GamePrincipal
from app.persistence.database import create_session_factory
from app.persistence.models import Empire, Universe
from app.simulation.models import ResourceBalance
from app.simulation.scheduler import IdempotencyConflict
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration


class Clock:
    def __init__(self):
        self.at = datetime(2099, 1, 1, tzinfo=UTC)

    def now(self):
        return self.at


@pytest.fixture
def ai_world(database_engine):
    factory = create_session_factory(database_engine)
    clock = Clock()
    engine = TimeEngine(factory, clock)
    universe = uuid4()
    with factory.begin() as session:
        result = bootstrap(session, engine, universe, "AI test", "test-galaxy",
                           ["economic_cautious", "expansionist"], clock.now())
    try:
        yield factory, clock, engine, result
    finally:
        with factory.begin() as session:
            session.execute(text("TRUNCATE universes, game_principals, control_operations CASCADE"))


def test_bootstrap_equal_real_starts_no_fake_users_or_units_and_replay(ai_world):
    factory, clock, engine, result = ai_world
    u = UUID(result["universe_id"])
    with factory.begin() as s:
        assert bootstrap(s, engine, u, "AI test", "test-galaxy",
                         ["economic_cautious", "expansionist"], clock.now()) == result
        assert s.scalar(select(func.count()).select_from(GamePrincipal)) == 0
        assert s.scalar(select(func.count()).select_from(AIController)) == 2
        stocks, builds = [], []
        for actor in result["actors"]:
            colony = UUID(actor["colony_id"])
            stocks.append([(b.resource, b.stock, b.rate_per_hour) for b in s.scalars(
                select(ResourceBalance).where(ResourceBalance.colony_id == colony)
                .order_by(ResourceBalance.resource))])
            builds.append([(b.infrastructure_type, b.level) for b in s.scalars(
                select(ColonyInfrastructure).where(ColonyInfrastructure.colony_id == colony)
                .order_by(ColonyInfrastructure.sector_index))])
        assert stocks[0] == stocks[1] == stocks[2]
        assert builds[0] == builds[1] == builds[2]
        assert s.scalar(text("SELECT count(*) FROM fleets")) == 0
        assert s.scalar(text("SELECT count(*) FROM ship_orders")) == 0
        assert s.scalar(select(func.count()).select_from(EmpireBinding)) == 0
    with pytest.raises(IdempotencyConflict), factory.begin() as s:
        bootstrap(s, engine, u, "AI test", "different", [], clock.now())


def test_bootstrap_insufficient_sites_is_atomic(ai_world):
    factory, clock, engine, _ = ai_world
    data = load_ruleset("v0.6").model_dump()
    data["galaxy"]["starting_site_count"] = 1
    from app.colony.rules import Ruleset
    rules = Ruleset.model_validate(data)
    u = uuid4()
    with pytest.raises(AIDenied, match="insufficient_starting_sites"), factory.begin() as s:
        bootstrap(s, engine, u, "Not enough", "test-galaxy", ["expansionist"], clock.now(),
                  rules=rules)
    with factory() as s:
        assert s.get(Universe, u) is None and s.get(AIBootstrap, u) is None


def test_v06_data_alone_never_creates_a_controller(ai_world):
    factory, clock, engine, _ = ai_world
    u = uuid4()
    with factory.begin() as s:
        result = bootstrap(s, engine, u, "Human only", "test-galaxy", [], clock.now())
        assert len(result["actors"]) == 1
        s.add(Empire(universe_id=u, name="Descriptive only", controller_type="ai"))
    with factory() as s:
        assert list(s.scalars(select(AIController).where(AIController.universe_id == u))) == []


def test_pause_resume_uses_future_grid_and_detects_pinned_policy_drift(ai_world):
    factory, clock, _, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    with factory.begin() as s:
        change_state(s, cid, "paused", clock.now())
    clock.at += timedelta(hours=3, seconds=17)
    with factory.begin() as s:
        c = change_state(s, cid, "enabled", clock.now())
        assert c.next_decision_at == datetime(2099, 1, 1, 3, 10, tzinfo=UTC)
        change_state(s, cid, "paused", clock.now())
        row = s.get(UniverseEconomy, c.universe_id)
        row.ruleset_data = row.ruleset_data | {"ai": row.ruleset_data["ai"] | {
            "research_queued_utility": 301}}
    with pytest.raises(AIDenied, match="policy_mismatch"), factory.begin() as s:
        change_state(s, cid, "enabled", clock.now())


def test_controller_exclusion_and_control_plane_grant_race(ai_world, database_engine):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from test_control import access

    from app.control.service import SERVICE, Control, ControlError

    factory, clock, _, result = ai_world
    u = UUID(result["universe_id"])
    target = UUID(result["actors"][0]["empire_id"])
    control = Control(factory, clock.now)
    with factory.begin() as s:
        s.get(Empire, target).controller_type = "ai"
    request = access(control, universe=u, bindings=[{
        "empire_id": str(target), "permissions": ["colony.read"]}])
    barrier = Barrier(2)

    def enable():
        barrier.wait()
        try:
            with factory.begin() as s:
                activate(s, u, target, "expansionist", clock.now())
            return "ai"
        except AIDenied:
            return "refused"

    def grant():
        barrier.wait()
        try:
            control.apply(SERVICE, request)
            return "human"
        except ControlError as error:
            assert error.code == "empire_ai_controlled"
            return "refused"

    with ThreadPoolExecutor(2) as pool:
        a, b = pool.submit(enable), pool.submit(grant)
        outcomes = [a.result(timeout=10), b.result(timeout=10)]
    assert outcomes.count("refused") == 1
    with factory() as s:
        controllers = list(s.scalars(select(AIController).where(AIController.empire_id == target)))
        bindings = list(s.scalars(select(EmpireBinding).where(EmpireBinding.empire_id == target)))
        assert bool(controllers) != bool(bindings)
    if bindings:
        with pytest.raises(AIDenied, match="human_binding_present"), factory.begin() as s:
            activate(s, u, target, "expansionist", clock.now())
    else:
        # Pause does not become an implicit handover to a human.
        with factory.begin() as s:
            change_state(s, controllers[0].id, "paused", clock.now())
        with pytest.raises(ControlError, match="empire_ai_controlled"):
            control.apply(SERVICE, request)


def test_ai_migration_matches_metadata_and_populated_downgrade_is_refused(
    ai_world, migration_config, database_engine,
):
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.persistence.models import Base

    with database_engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    with pytest.raises(RuntimeError, match="live AI data"):
        command.downgrade(migration_config, "0010_colonization")
