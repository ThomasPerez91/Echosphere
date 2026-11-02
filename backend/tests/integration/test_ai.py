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
from app.persistence.models import Colony, Empire, Universe
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
        result = bootstrap(
            session,
            engine,
            universe,
            "AI test",
            "test-galaxy",
            ["economic_cautious", "expansionist"],
            clock.now(),
        )
    try:
        yield factory, clock, engine, result
    finally:
        with factory.begin() as session:
            session.execute(text("TRUNCATE universes, game_principals, control_operations CASCADE"))


def test_bootstrap_equal_real_starts_no_fake_users_or_units_and_replay(ai_world):
    factory, clock, engine, result = ai_world
    u = UUID(result["universe_id"])
    with factory.begin() as s:
        assert (
            bootstrap(
                s,
                engine,
                u,
                "AI test",
                "test-galaxy",
                ["economic_cautious", "expansionist"],
                clock.now(),
            )
            == result
        )
        assert s.scalar(select(func.count()).select_from(GamePrincipal)) == 0
        assert s.scalar(select(func.count()).select_from(AIController)) == 2
        stocks, builds = [], []
        for actor in result["actors"]:
            colony = UUID(actor["colony_id"])
            stocks.append(
                [
                    (b.resource, b.stock, b.rate_per_hour)
                    for b in s.scalars(
                        select(ResourceBalance)
                        .where(ResourceBalance.colony_id == colony)
                        .order_by(ResourceBalance.resource)
                    )
                ]
            )
            builds.append(
                [
                    (b.infrastructure_type, b.level)
                    for b in s.scalars(
                        select(ColonyInfrastructure)
                        .where(ColonyInfrastructure.colony_id == colony)
                        .order_by(ColonyInfrastructure.sector_index)
                    )
                ]
            )
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
        bootstrap(
            s, engine, u, "Not enough", "test-galaxy", ["expansionist"], clock.now(), rules=rules
        )
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
        row.ruleset_data = row.ruleset_data | {
            "ai": row.ruleset_data["ai"] | {"research_queued_utility": 301}
        }
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
    request = access(
        control, universe=u, bindings=[{"empire_id": str(target), "permissions": ["colony.read"]}]
    )
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
    ai_world,
    migration_config,
    database_engine,
):
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.persistence.models import Base

    with database_engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    with pytest.raises(RuntimeError, match="live AI data"):
        command.downgrade(migration_config, "0010_colonization")


def test_turn_atomic_trace_common_command_and_pure_replay(ai_world):
    from app.ai.models import AIDecision
    from app.ai.orchestrator import Orchestrator
    from app.ai.policy import choose

    factory, clock, _, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    clock.at += timedelta(minutes=10)
    runner = Orchestrator(factory, clock)
    assert runner.process_next(controller_id=cid, raise_errors=True)["outcome"] == "accepted"
    assert runner.process_next(controller_id=cid) is None
    with factory() as s:
        c = s.get(AIController, cid)
        trace = s.get(AIDecision, (cid, 1))
        assert c.sequence == 2 and trace.outcome == "accepted"
        cfg = s.get(UniverseEconomy, c.universe_id).ruleset_data["ai"]
        from app.ai.rules import AIRules

        replay = choose(
            trace.observation,
            trace.trace["memory_evaluated"],
            c.profile,
            AIRules.model_validate(cfg),
        )
        assert replay["choice"] == trace.trace["choice"]
        assert trace.trace["intent_key"].startswith(f"ai:{cid}:1:")
        assert len(trace.observation["candidates"]) <= 128
        assert len(trace.observation["fleets"]) <= 64
        assert (
            not {"seed", "starting_sites", "manifest", "foreign_colonies"}
            & trace.observation.keys()
        )


def test_two_orchestrators_and_crash_boundaries_never_duplicate_a_turn(ai_world):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.ai.models import AIDecision
    from app.ai.orchestrator import Orchestrator
    from app.colony.models import ConstructionOrder

    factory, clock, _, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    empire = UUID(result["actors"][1]["empire_id"])
    clock.at += timedelta(minutes=10)
    runner = Orchestrator(factory, clock)

    def crash(_):
        raise RuntimeError("Crash after common service, before turn commit")

    assert runner.process_next(controller_id=cid, after_command=crash)["outcome"] == "retry"
    with factory() as s:
        assert s.get(AIController, cid).sequence == 1
        assert s.get(AIDecision, (cid, 1)) is None
        assert s.scalar(select(func.count()).select_from(ConstructionOrder)) == 0
    clock.at += timedelta(seconds=30)
    entered, release = Event(), Event()

    def hold(_):
        entered.set()
        assert release.wait(10)

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(runner.process_next, controller_id=cid, after_command=hold)
        assert entered.wait(10)
        try:
            assert runner.process_next(controller_id=cid) is None
        finally:
            release.set()
        assert first.result(timeout=10)["outcome"] == "accepted"
    # Lost response / process crash AFTER commit: durable sequence prevents another command.
    assert runner.process_next(controller_id=cid) is None
    with factory() as s:
        rows = list(
            s.scalars(
                select(ConstructionOrder)
                .join(Colony, ConstructionOrder.colony_id == Colony.id)
                .where(Colony.empire_id == empire)
            )
        )
        assert len(rows) == 1
        assert rows[0].idempotency_key == f"ai:{cid}:1:build"
        assert s.get(AIController, cid).next_decision_at == datetime(2099, 1, 1, 0, 20, tzinfo=UTC)


def test_business_refusal_is_one_durable_decision_not_a_second_attempt(ai_world, monkeypatch):
    from app.ai import orchestrator
    from app.ai.models import AIDecision
    from app.colony.service import ColonyError

    factory, clock, _, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    attempts = []

    def refuse(*args):
        attempts.append(args[-2])
        raise ColonyError("Resources changed", "insufficient_resources")

    monkeypatch.setattr(orchestrator, "dispatch", refuse)
    clock.at += timedelta(minutes=10)
    runner = orchestrator.Orchestrator(factory, clock)
    assert runner.process_next(controller_id=cid, raise_errors=True)["outcome"] == "refusal"
    assert len(attempts) == 1 and runner.process_next(controller_id=cid) is None
    with factory() as s:
        c = s.get(AIController, cid)
        assert c.attempts == 0 and c.state == "enabled" and c.sequence == 2
        assert s.get(AIDecision, (cid, 1)).trace["result"] == {"reason": "insufficient_resources"}


def test_long_outage_coalesces_and_pause_does_not_stop_accepted_events(ai_world):
    from app.ai.orchestrator import Orchestrator
    from app.colony.models import ConstructionOrder

    factory, clock, engine, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    clock.at += timedelta(hours=3, seconds=7)
    runner = Orchestrator(factory, clock)
    assert runner.process_next(controller_id=cid, raise_errors=True)["sequence"] == 1
    assert runner.process_next(controller_id=cid) is None
    with factory.begin() as s:
        c = change_state(s, cid, "paused", clock.now())
        assert c.next_decision_at == datetime(2099, 1, 1, 3, 10, tzinfo=UTC)
    clock.at += timedelta(hours=1)
    while engine.process_next() is not None:
        pass
    assert runner.process_next(controller_id=cid) is None
    with factory() as s:
        assert s.scalar(select(ConstructionOrder.status)) == "completed"


def test_hidden_world_changes_never_change_authorized_observation_or_decision(ai_world):
    from app.ai.controller import authorize
    from app.ai.observation import collect
    from app.ai.policy import choose
    from app.ai.rules import canonical
    from app.colony.service import initialize_colony
    from app.fleet.models import Fleet, FleetStack
    from app.galaxy.models import StartingSite, SystemKnowledge
    from app.galaxy.service import initialize_empire
    from app.persistence.models import Planet, StellarSystem

    factory, clock, engine, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    u = UUID(result["universe_id"])

    def perceive():
        with factory() as s:
            c = s.get(AIController, cid)
            rules = authorize(s, c)
            obs, memory = collect(s, c, rules, clock.now())
            return canonical(obs), choose(obs, memory, c.profile, rules.ai)

    before = perceive()
    with factory.begin() as s:
        occupied = set(s.scalars(select(Colony.planet_id).where(Colony.universe_id == u)))
        site = next(
            p
            for p in s.scalars(select(StartingSite).where(StartingSite.universe_id == u))
            if p.planet_id not in occupied
        )
        other = Empire(universe_id=u, name="Hidden opponent", controller_type="human")
        s.add(other)
        s.flush()
        colony = Colony(universe_id=u, empire_id=other.id, planet_id=site.planet_id)
        s.add(colony)
        s.flush()
        initialize_colony(s, u, other.id, colony.id, clock.now())
        initialize_empire(s, engine, u, other.id, colony.id, clock.now())
        fleet = Fleet(
            universe_id=u,
            empire_id=other.id,
            home_colony_id=colony.id,
            kind="GARRISON",
            status="STATIONED",
            system_id=site.system_id,
            name="Hidden fleet",
        )
        s.add(fleet)
        s.flush()
        s.add(FleetStack(fleet_id=fleet.id, ship_class="probe", count=19))
        s.get(ResourceBalance, (colony.id, "alloys")).stock = 9999999999
        p = s.get(Planet, site.planet_id)
        p.name, p.sector_capacity = "Hidden changed world", 17
        # A system without any Knowledge row of this Empire is UNKNOWN: it never reaches the DTO.
        known = set(
            s.scalars(
                select(SystemKnowledge.system_id).where(
                    SystemKnowledge.empire_id == UUID(result["actors"][1]["empire_id"])
                )
            )
        )
        unknown = next(
            x
            for x in s.scalars(
                select(StellarSystem)
                .where(StellarSystem.universe_id == u)
                .order_by(StellarSystem.id)
            )
            if x.id not in known
        )
        unknown.name = "Hidden renamed system"
    assert perceive() == before


def test_budget_exceeded_before_dispatch_retries_then_blocks_without_aid(ai_world):
    from app.ai.orchestrator import Orchestrator
    from app.ai.rules import fingerprint
    from app.colony.rules import Ruleset

    factory, clock, _, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    with factory.begin() as s:
        c = s.get(AIController, cid)
        row = s.get(UniverseEconomy, c.universe_id)
        data = row.ruleset_data | {"ai": row.ruleset_data["ai"] | {"observation_bytes": 1}}
        row.ruleset_data = Ruleset.model_validate(data).model_dump()
        c.policy_digest = fingerprint(data["ai"])
    clock.at += timedelta(minutes=10)
    runner = Orchestrator(factory, clock, max_attempts=2)
    assert runner.process_next(controller_id=cid)["outcome"] == "retry"
    clock.at += timedelta(seconds=30)
    assert runner.process_next(controller_id=cid)["outcome"] == "blocked"
    with factory() as s:
        assert s.get(AIController, cid).sequence == 1
        assert s.scalar(text("SELECT count(*) FROM construction_orders")) == 0
        assert s.scalar(text("SELECT count(*) FROM ai_decisions")) == 0


def test_profiles_diverge_on_one_real_observation_by_weights_only(ai_world):
    from app.ai.controller import authorize
    from app.ai.observation import collect
    from app.ai.orchestrator import Orchestrator
    from app.ai.policy import choose

    factory, clock, engine, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    runner = Orchestrator(factory, clock)
    for _ in range(36):
        clock.at += timedelta(minutes=10)
        while engine.process_next() is not None:
            pass
        with factory() as s:
            c = s.get(AIController, cid)
            rules = authorize(s, c)
            observation, memory = collect(s, c, rules, clock.now())
        cautious, expansionist = (
            choose(observation, memory, p, rules.ai) for p in ("economic_cautious", "expansionist")
        )
        if cautious["choice"] != expansionist["choice"]:
            # Same candidates, utilities and reasons: only weight x utility changed the choice.
            def features(trace):
                return [(r["key"], r["utility"], r["reason"]) for r in trace["evaluated"]]

            assert features(cautious) == features(expansionist)
            assert cautious["choice"] and expansionist["choice"]
            return
        runner.process_next(controller_id=cid, raise_errors=True)
    pytest.fail("No reachable state where profile weights change the decision")


def test_circular_cursor_examines_research_beyond_the_first_page(ai_world):
    from app.ai.controller import authorize
    from app.ai.observation import collect
    from app.ai.rules import fingerprint
    from app.colony.rules import Ruleset

    factory, clock, _, result = ai_world
    cid = UUID(result["actors"][1]["controller_id"])
    with factory.begin() as s:
        c = s.get(AIController, cid)
        row = s.get(UniverseEconomy, c.universe_id)
        ai = row.ruleset_data["ai"]
        data = row.ruleset_data | {
            "ai": ai | {"family_pages": ai["family_pages"] | {"research": 1}}
        }
        row.ruleset_data = Ruleset.model_validate(data).model_dump()
        c.policy_digest = fingerprint(data["ai"])
        technologies = sorted(row.ruleset_data["research"]["technologies"])
    assert len(technologies) > 1
    visits = []
    for _ in range(len(technologies) + 1):
        with factory.begin() as s:
            c = s.get(AIController, cid)
            observation, memory = collect(s, c, authorize(s, c), clock.now())
            c.memory = memory  # the cursor persists exactly as a committed turn stores it
            visits.append(
                [
                    x["body"]["technology"]
                    for x in observation["candidates"]
                    if x["goal"] == "research"
                ]
            )
    # One reference per visit, canonical order, full cover in ceil(M/P) visits, then wrap-around.
    assert visits == [[t] for t in technologies] + [[technologies[0]]]


def test_autonomous_profiles_pay_build_research_survey_colonize_and_bootstrap(ai_world):
    """72 h of injected clock; only common services act, nothing is credited, placed or revealed."""
    from app.ai.models import AIDecision
    from app.ai.orchestrator import Orchestrator
    from app.colony.models import ConstructionOrder
    from app.fleet.models import FleetMission, ShipOrder
    from app.research.models import AcquiredTechnology, ResearchOrder
    from app.simulation.production import MICRO_UNITS

    factory, clock, engine, result = ai_world
    u = UUID(result["universe_id"])
    actors = result["actors"][1:]
    rules = load_ruleset("v0.6")
    package = rules.colonization.package_minimum()
    producers = [rules.ai.producers[r] for r in ("alloys", "flux", "data")]
    runner = Orchestrator(factory, clock)
    founded, loads, milestones = set(), [], {}
    for _ in range(432):
        clock.at += timedelta(minutes=10)
        while engine.process_next() is not None:
            pass
        with factory() as s:
            # Founded by the worker, observed before any AI turn: exactly the package, nothing more.
            for c in s.scalars(
                select(Colony).where(
                    Colony.universe_id == u, Colony.founding_mission_id.is_not(None)
                )
            ):
                if c.id in founded:
                    continue
                founded.add(c.id)
                assert s.get(FleetMission, c.founding_mission_id).snapshot["cargo"] == package
                balances = s.scalars(
                    select(ResourceBalance).where(ResourceBalance.colony_id == c.id)
                )
                assert {b.resource: (b.stock, b.rate_per_hour) for b in balances} == {
                    r: (v, 0) for r, v in package.items()
                }
                assert not s.scalar(
                    select(func.count()).where(ColonyInfrastructure.colony_id == c.id)
                )
        for actor in actors:
            cid = UUID(actor["controller_id"])
            out = runner.process_next(controller_id=cid, raise_errors=True)
            if out and out["outcome"] == "accepted":
                with factory() as s:
                    d = s.get(AIDecision, (cid, out["sequence"]))
                    chosen = next(
                        x for x in d.observation["candidates"] if x["key"] == d.trace["choice"]
                    )
                    if chosen["operation"] == "load" and chosen["goal"] == "expansion":
                        loads.append(chosen["body"]["cargo"])
        with factory() as s:
            for actor in actors:
                e = UUID(actor["empire_id"])
                ships = set(s.scalars(select(ShipOrder.ship_class).where(ShipOrder.empire_id == e)))
                surveyed = s.scalar(
                    select(FleetMission.id)
                    .where(
                        FleetMission.empire_id == e,
                        FleetMission.kind == "SURVEY",
                        FleetMission.status == "completed",
                    )
                    .limit(1)
                )
                research = s.scalar(
                    select(AcquiredTechnology.technology_id)
                    .where(AcquiredTechnology.empire_id == e)
                    .limit(1)
                )
                developing = False
                for c in s.scalars(
                    select(Colony).where(
                        Colony.empire_id == e, Colony.founding_mission_id.is_not(None)
                    )
                ):
                    kinds = s.scalars(
                        select(ConstructionOrder.infrastructure_type)
                        .where(ConstructionOrder.colony_id == c.id)
                        .order_by(ConstructionOrder.sequence)
                        .limit(3)
                    ).all()
                    built = s.scalar(
                        select(func.count()).where(ColonyInfrastructure.colony_id == c.id)
                    )
                    # Founded colony bootstrap: Alloys, then Flux, then Data producers, all paid.
                    developing = developing or (kinds == producers and built >= 3)
                if {"probe", "colonizer"} <= ships and surveyed and research and developing:
                    milestones.setdefault(actor["profile"], clock.now())
        if len(milestones) == 2:
            break
    assert len(milestones) == 2, milestones
    # Whole units for LOAD, micro-units everywhere else: no 10^6 factor in either direction.
    assert loads and all(
        cargo == {r: v // MICRO_UNITS for r, v in package.items()} for cargo in loads
    )
    with factory() as s:
        for actor in actors:
            e = UUID(actor["empire_id"])
            keys = [
                *s.scalars(select(ShipOrder.idempotency_key).where(ShipOrder.empire_id == e)),
                *s.scalars(select(FleetMission.idempotency_key).where(FleetMission.empire_id == e)),
                *s.scalars(
                    select(ResearchOrder.idempotency_key).where(ResearchOrder.empire_id == e)
                ),
                *s.scalars(
                    select(ConstructionOrder.idempotency_key)
                    .join(Colony, Colony.id == ConstructionOrder.colony_id)
                    .where(Colony.empire_id == e)
                ),
            ]
            # Every strategic effect came through the AI dispatcher's common service calls.
            assert keys and all(k.startswith(f"ai:{actor['controller_id']}:") for k in keys)


@pytest.fixture
def ai_world_v07(database_engine):
    factory = create_session_factory(database_engine)
    clock = Clock()
    engine = TimeEngine(factory, clock)
    universe = uuid4()
    with factory.begin() as session:
        result = bootstrap(
            session,
            engine,
            universe,
            "AI v0.7 test",
            "test-galaxy",
            ["economic_cautious", "expansionist"],
            clock.now(),
            rules=load_ruleset("v0.7"),
        )
    try:
        yield factory, clock, engine, result
    finally:
        with factory.begin() as session:
            session.execute(text("TRUNCATE universes, game_principals, control_operations CASCADE"))


def test_v07_defensive_military_goal_alert_and_no_offensive_capability(ai_world_v07):
    from app.ai.controller import authorize
    from app.ai.dispatcher import dispatch
    from app.ai.observation import collect
    from app.combat.models import CombatEngagement
    from app.fleet.models import Fleet, FleetMission

    factory, clock, engine, result = ai_world_v07
    actor = result["actors"][1]
    cid = UUID(actor["controller_id"])

    def observe():
        with factory() as s:
            c = s.get(AIController, cid)
            rules = authorize(s, c)
            assert rules.ai.policy_version == "utility-goals-v2" and "military" in rules.ai.goals
            return collect(s, c, rules, clock.now())[0]

    calm = observe()
    military = [c for c in calm["candidates"] if c["goal"] == "military"]
    assert military and {c["utility"] for c in military} == {500}
    assert all(c["body"]["ship"] == "interceptor" for c in military)
    assert calm["alerts"] == []
    assert not any(
        c["operation"] == "launch" and c["body"].get("kind") == "ATTACK" for c in calm["candidates"]
    )
    # A hostile force announced on the AI colony (test-placed engagement row): urgent defence.
    with factory.begin() as s:
        human = UUID(result["actors"][0]["empire_id"])
        colony = s.get(Colony, UUID(actor["colony_id"]))
        from app.persistence.models import Planet

        planet = s.get(Planet, colony.planet_id)
        home = s.get(Colony, UUID(result["actors"][0]["colony_id"]))
        fleet = Fleet(
            empire_id=human,
            universe_id=colony.universe_id,
            home_colony_id=home.id,
            kind="TASK",
            status="STATIONED",
            system_id=s.get(Planet, home.planet_id).system_id,
            name="Test-only",
        )
        s.add(fleet)
        s.flush()
        from app.galaxy.service import map_system

        map_system(s, colony.universe_id, human, planet.system_id, clock.now())
        mission = FleetMission(
            empire_id=human,
            universe_id=colony.universe_id,
            fleet_id=fleet.id,
            kind="ATTACK",
            status="completed",
            origin_id=fleet.system_id,
            destination_id=planet.system_id,
            payer_colony_id=home.id,
            target_planet_id=planet.id,
            idempotency_key="test-only-alert",
            snapshot={},
            started_at=clock.now(),
            travel_arrival_at=clock.now() + timedelta(hours=1),
            due_at=clock.now() + timedelta(hours=24),
            completed_at=clock.now(),
        )
        s.add(mission)
        s.flush()
        s.add(
            CombatEngagement(
                universe_id=colony.universe_id,
                mission_id=mission.id,
                attacker_empire_id=human,
                defender_empire_id=colony.empire_id,
                target_planet_id=planet.id,
                target_system_id=planet.system_id,
                started_at=mission.started_at,
                travel_arrival_at=mission.travel_arrival_at,
                battle_at=mission.due_at,
                state="pending",
                attempts=0,
            )
        )
    alerted = observe()
    assert {a["planet_id"] for a in alerted["alerts"]} == {str(planet.id)}
    assert str(human) not in str(alerted["alerts"])  # never the attacker's identity
    urgent = [c for c in alerted["candidates"] if c["goal"] == "military"]
    assert {c["utility"] for c in urgent} == {1000}
    # Even a forged offensive candidate is refused by the dispatcher's fixed capabilities.
    with pytest.raises(AIDenied, match="ai_mission_denied"), factory.begin() as s:
        c = s.get(AIController, cid)
        forged = {
            "operation": "launch",
            "body": {"fleet_id": str(fleet.id), "kind": "ATTACK", "units": {"interceptor": 1}},
        }
        dispatch(s, engine, c, forged, "ai:forged", clock.now())


def test_v07_ai_builds_defence_through_common_production_and_never_attacks(ai_world_v07):
    from app.ai.orchestrator import Orchestrator
    from app.fleet.models import FleetMission, ShipOrder

    factory, clock, engine, result = ai_world_v07
    runner = Orchestrator(factory, clock)
    actors = result["actors"][1:]
    for _ in range(288):  # 48 h of injected clock
        clock.at += timedelta(minutes=10)
        while engine.process_next() is not None:
            pass
        for actor in actors:
            runner.process_next(controller_id=UUID(actor["controller_id"]), raise_errors=True)
    with factory() as s:
        for actor in actors:
            e = UUID(actor["empire_id"])
            ordered = s.scalars(
                select(ShipOrder.idempotency_key).where(
                    ShipOrder.empire_id == e, ShipOrder.ship_class == "interceptor"
                )
            ).all()
            assert ordered and all(k.startswith(f"ai:{actor['controller_id']}:") for k in ordered)
            attacks = select(func.count()).where(
                FleetMission.empire_id == e, FleetMission.kind == "ATTACK"
            )
            assert s.scalar(attacks) == 0
