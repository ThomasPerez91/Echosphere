"""Real PostgreSQL + GameSession tests for generated worlds, fog and expeditions."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_colony_api import Clock, World, game, set_access, world  # noqa: F401
from test_game_sessions import enter

from app.access.http import cookie_name
from app.colony.rules import load_ruleset
from app.colony.service import configure_universe, enqueue, initialize_colony
from app.colony.service import read_snapshot as read_order
from app.galaxy import service as g
from app.galaxy.models import (
    ExplorationMission,
    ExplorationReport,
    GalaxyRoute,
    GalaxySystem,
    MissionLeg,
    PlanetKnowledge,
    StartingSite,
    SystemKnowledge,
    UniverseGalaxy,
)
from app.galaxy.world import generate_world
from app.main import create_app
from app.persistence.models import Colony, Empire, Planet, StellarSystem, Universe
from app.research import service as research
from app.simulation.models import ResourceBalance
from app.simulation.scheduler import IdempotencyConflict
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration
ALL = ["colony.read", "galaxy.read", "exploration.read", "exploration.start"]


@pytest.fixture
def galaxy(game):
    def make(permissions=ALL, universe=None, other=False):
        universe = universe or uuid4()
        user, membership = uuid4(), uuid4()
        with game.factory.begin() as s:
            if s.get(Universe, universe) is None:
                s.add(Universe(id=universe, name="Galaxy test", seed="test-galaxy"))
                s.flush()
                configure_universe(s, universe, load_ruleset("v0.3"))
                generate_world(s, universe)
            sites = list(
                s.scalars(
                    select(StartingSite)
                    .where(StartingSite.universe_id == universe)
                    .order_by(StartingSite.planet_id)
                )
            )
            site = sites[1 if other else 0]
            empire = Empire(universe_id=universe, name="Explorer", controller_type="human")
            s.add(empire)
            s.flush()
            colony = Colony(universe_id=universe, empire_id=empire.id, planet_id=site.planet_id)
            s.add(colony)
            s.flush()
            initialize_colony(s, universe, empire.id, colony.id, game.clock())
            engine = TimeEngine(game.factory, Clock(game))
            g.initialize_empire(s, engine, universe, empire.id, colony.id, game.clock())
            empire_id, colony_id = empire.id, colony.id
        set_access(
            game,
            user,
            universe,
            membership,
            [{"empire_id": str(empire_id), "permissions": list(permissions)}],
        )
        raw, _, _ = enter(game, (user, universe, membership))
        app = create_app(game.settings)
        app.state.session_factory, app.state.clock = game.factory, Clock(game)
        client = TestClient(app, base_url=game.settings.game_public_origin)
        client.cookies.set(cookie_name(universe), raw)
        return World(game, app, client, raw, user, universe, membership, empire_id, colony_id)

    return make


def read(w, system=None):
    suffix = f"/systems/{system}" if system else ""
    return w.client.get(
        f"/game/{w.universe}/galaxy/{w.empire}{suffix}", headers={"X-Game-Request": "bootstrap"}
    )


def send(w, destination, key=None, **extra):
    return w.client.post(
        f"/game/{w.universe}/exploration/{w.empire}/missions",
        headers=w.headers(),
        json={
            "colony_id": str(w.colony),
            "destination_id": str(destination),
            "idempotency_key": key or uuid4().hex,
            **extra,
        },
    )


def detected(w):
    return next(s["id"] for s in read(w).json()["systems"] if s["state"] == "DETECTED")


def test_generation_manifest_replay_and_reject_replacement(galaxy):
    w = galaxy()
    with w.game.factory.begin() as s:
        manifest = s.get(UniverseGalaxy, w.universe)
        assert generate_world(s, w.universe).digest == manifest.digest
        with pytest.raises(IdempotencyConflict):
            generate_world(s, w.universe, system_count=30)
        assert s.scalar(select(func.count()).select_from(GalaxySystem)) == 40
        assert s.scalar(select(func.count()).select_from(StartingSite)) == 4
    # No automatic adoption, even with a seed and a historical ruleset.
    with w.game.factory.begin() as s:
        old = Universe(name="Old", seed="old")
        s.add(old)
        s.flush()
        configure_universe(s, old.id, load_ruleset("v0.2"))
        with pytest.raises(g.GalaxyError.__bases__[0]):
            generate_world(s, old.id)
        assert s.get(UniverseGalaxy, old.id) is None


def test_unknown_absent_detected_minimal_and_local_monitoring_does_not_expire(galaxy):
    w = galaxy()
    body = read(w).json()
    assert len(body["systems"]) == 4  # one real origin and three adjacent detections
    assert len(body["routes"]) == 3
    assert (
        not {"seed", "inputs", "generator_version", "starting_sites", "system_count"} & body.keys()
    )
    ids = {s["id"] for s in body["systems"]}
    for system in body["systems"]:
        if system["state"] == "DETECTED":
            assert not {"name", "planets", "last_seen_at", "observation"} & system.keys()
            assert system["x"] % 100 == 50 and system["y"] % 100 == 50
    with w.game.factory() as s:
        unknown = next(
            row.system_id
            for row in s.scalars(select(GalaxySystem))
            if str(row.system_id) not in ids
        )
    assert read(w, unknown).status_code == read(w, uuid4()).status_code == 404
    assert read(w, unknown).json() == read(w, uuid4()).json()
    assert send(w, unknown).status_code == 404
    w.advance(hours=1)
    origin = next(s for s in read(w).json()["systems"] if s["state"] == "MONITORED")
    assert origin["observation"]["own_colony_ids"] == [str(w.colony)]


def test_expedition_paid_once_worker_without_session_and_immutable_report(galaxy):
    w = galaxy()
    target = detected(w)
    key = uuid4().hex
    before = {r: w.stock(r) for r in ["alloys", "flux", "data"]}
    first = send(w, target, key)
    assert first.status_code == 200, first.text
    mission = first.json()["mission_id"]
    assert send(w, target, key).json()["mission_id"] == mission
    assert {r: before[r] - w.stock(r) for r in before} == {
        "alloys": 50_000_000,
        "flux": 60_000_000,
        "data": 25_000_000,
    }
    assert send(w, target).status_code == 409
    with w.game.factory() as s:
        row = s.get(ExplorationMission, mission)
        assert row.due_at - row.started_at == timedelta(minutes=45)
    w.advance(minutes=60)
    engine = TimeEngine(w.game.factory, w.app.state.clock)
    assert engine.process_next().status == "completed"  # no browser or session call
    assert engine.process_next() is None
    with w.game.factory() as s:
        report = s.get(ExplorationReport, mission)
        snapshot = report.discoveries
        assert report.observed_at + timedelta(minutes=15) == report.processed_at
        assert snapshot["system"]["state"] == "MAPPED"
        assert snapshot["system"]["planets"]
        assert s.scalar(select(func.count()).select_from(ExplorationReport)) == 1
    assert send(w, target, key).json()["mission_id"] == mission
    assert send(w, target).status_code == 409
    assert read(w, target).json()["state"] == "MAPPED"
    with w.game.factory.begin() as s:
        # Changing physical data cannot enrich an old structural observation or report.
        s.get(Planet, snapshot["system"]["planets"][0]["id"]).sector_capacity = 99
    assert read(w, target).json()["planets"] == snapshot["system"]["planets"]
    with w.game.factory() as s:
        assert s.get(ExplorationReport, mission).discoveries == snapshot


def test_two_empires_keep_independent_knowledge_and_foreign_scope(galaxy):
    w = galaxy()
    other = galaxy(universe=w.universe, other=True)
    a, b = read(w).json(), read(other).json()
    assert not {s["id"] for s in a["systems"]} & {s["id"] for s in b["systems"]}
    foreign = next(s["id"] for s in b["systems"])
    assert read(w, foreign).status_code == 404
    target = detected(w)
    assert send(w, target).status_code == 200
    assert send(other, detected(other)).status_code == 200
    w.advance(minutes=50)
    engine = TimeEngine(w.game.factory, w.app.state.clock)
    assert engine.process_next() and engine.process_next()
    assert read(other, target).status_code == 404


@pytest.mark.parametrize(
    "permissions,status",
    [
        (["colony.read"], 404),
        (["galaxy.read"], 403),
        (["galaxy.read", "exploration.read", "exploration.start"], 403),
        (["colony.read", "galaxy.read", "exploration.read"], 403),
    ],
)
def test_explicit_permissions_no_construct_required(galaxy, permissions, status):
    w = galaxy(permissions=permissions)
    with w.game.factory() as s:
        target = s.scalar(
            select(SystemKnowledge.system_id).where(
                SystemKnowledge.empire_id == w.empire, SystemKnowledge.state == "DETECTED"
            )
        )
    assert send(w, target).status_code == status


def test_corruption_rolls_back_discovery_and_report_then_retries(galaxy):
    w = galaxy()
    target = detected(w)
    mission = send(w, target).json()["mission_id"]
    with w.game.factory.begin() as s:
        row = s.get(ExplorationMission, mission)
        original = row.snapshot
        row.snapshot = {**original, "duration_us": 1}
    w.advance(minutes=50)
    engine = TimeEngine(w.game.factory, w.app.state.clock)
    assert engine.process_next().status == "pending"
    with w.game.factory() as s:
        assert s.get(ExplorationReport, mission) is None
        assert s.get(SystemKnowledge, (w.empire, target)).state == "DETECTED"
    with w.game.factory.begin() as s:
        s.get(ExplorationMission, mission).snapshot = original
    w.advance(seconds=31)
    assert engine.process_next().status == "completed"


def test_same_intent_concurrent_one_debit_and_worker_once(galaxy):
    w = galaxy()
    target = detected(w)
    key = uuid4().hex
    barrier = Barrier(2)

    def launch():
        barrier.wait()
        with w.game.factory.begin() as s:
            return g.start(
                s,
                TimeEngine(w.game.factory, w.app.state.clock),
                w.universe,
                w.empire,
                w.colony,
                UUID(target),
                key=key,
                at=w.game.clock(),
            ).id

    before = w.stock("alloys")
    with ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(lambda _: launch(), range(2)))
    assert rows[0] == rows[1] and before - w.stock("alloys") == 50_000_000
    w.advance(minutes=50)

    def process(_):
        return TimeEngine(w.game.factory, w.app.state.clock).process_next()

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(process, range(2)))
    assert sum(o is not None for o in outcomes) == 1


def test_scoped_fk_and_populated_downgrade_refusal(galaxy, migration_config):
    w = galaxy()
    with w.game.factory.begin() as s:
        other = Universe(name="Foreign", seed="foreign")
        s.add(other)
        s.flush()
        route = s.scalar(select(GalaxyRoute).where(GalaxyRoute.universe_id == w.universe))
        with pytest.raises(IntegrityError), s.begin_nested():
            s.add(GalaxyRoute(universe_id=other.id, a_id=route.a_id, b_id=route.b_id))
            s.flush()
    with pytest.raises(RuntimeError, match="populated"):
        command.downgrade(migration_config, "0007_empire_research")


def test_lost_monitoring_preserves_structure_and_last_seen(galaxy):
    w = galaxy()
    target = UUID(detected(w))
    with w.game.factory.begin() as s:
        g.catch_up(
            s, TimeEngine(w.game.factory, w.app.state.clock), w.universe, w.empire, w.game.clock()
        )
        g.map_system(s, w.universe, w.empire, target, w.game.clock())
        known = s.get(SystemKnowledge, (w.empire, target))
        known.state, known.last_seen_at = "MONITORED", w.game.clock()
        known.observation = {"own_colony_ids": []}
        previous, name = known.last_seen_at, known.known_name
        g.refresh_monitoring(s, w.universe, w.empire, w.game.clock())
        assert known.state == "MAPPED" and known.last_seen_at == previous
        assert known.known_name == name


def hidden_texts(w):
    """Ids/names of every system and planet this Empire does not legitimately know."""
    with w.game.factory() as s:
        known = {
            row.system_id: row.state
            for row in s.scalars(
                select(SystemKnowledge).where(SystemKnowledge.empire_id == w.empire)
            )
        }
        hidden = set()
        for row in s.scalars(select(GalaxySystem).where(GalaxySystem.universe_id == w.universe)):
            system = s.get(StellarSystem, row.system_id)
            if row.system_id not in known:
                hidden.add(str(row.system_id))
            if known.get(row.system_id, "DETECTED") == "DETECTED":
                hidden.add(system.name)
                for planet in s.scalars(select(Planet).where(Planet.system_id == row.system_id)):
                    hidden |= {str(planet.id), planet.name}
        # Generated planet names are generic ("World 1"): only values not legitimately known.
        legit = set(
            s.scalars(
                select(PlanetKnowledge.known_name).where(PlanetKnowledge.empire_id == w.empire)
            )
        )
        return hidden - legit


def test_no_unknown_or_unmapped_detail_in_any_payload_before_and_after_discovery(galaxy):
    w = galaxy()
    for phase in range(2):
        hidden = hidden_texts(w)
        assert hidden
        payloads = [
            read(w).text,
            w.client.get(
                f"/game/{w.universe}/galaxy", headers={"X-Game-Request": "bootstrap"}
            ).text,
            w.client.get(
                f"/game/{w.universe}/exploration/{w.empire}/missions",
                headers={"X-Game-Request": "bootstrap"},
            ).text,
        ]
        payloads += [read(w, s["id"]).text for s in read(w).json()["systems"]]
        for text in payloads:
            assert not [value for value in hidden if value in text]
        if phase == 0:
            assert send(w, detected(w)).status_code == 200
            w.advance(minutes=46)
            assert TimeEngine(w.game.factory, w.app.state.clock).process_next().status == (
                "completed"
            )


def test_refusals_leave_stocks_capacity_and_knowledge_unchanged(galaxy):
    w = galaxy()
    other = galaxy(universe=w.universe, other=True)
    target = detected(w)
    with w.game.factory() as s:
        origin = next(
            row.system_id
            for row in s.scalars(
                select(SystemKnowledge).where(SystemKnowledge.empire_id == w.empire)
            )
            if row.state == "MONITORED"
        )
        isolated = next(
            row.system_id
            for row in s.scalars(select(GalaxySystem).where(GalaxySystem.universe_id == w.universe))
            if s.get(SystemKnowledge, (w.empire, row.system_id)) is None
        )
    with w.game.factory.begin() as s:
        # A DETECTED system without any known route: no omniscient path may be used.
        s.add(
            SystemKnowledge(
                empire_id=w.empire,
                universe_id=w.universe,
                system_id=isolated,
                state="DETECTED",
                approximate_x=50,
                approximate_y=50,
                discovered_at=w.game.clock(),
            )
        )
    before = {r: w.stock(r) for r in ["alloys", "flux", "data"]}
    codes = {
        "mapped": send(w, origin),
        "unreachable": send(w, isolated),
        "foreign_colony": send(w, target, colony_id=str(other.colony)),
        "unknown_colony": send(w, target, colony_id=str(uuid4())),
        "foreign_empire": w.client.post(
            f"/game/{w.universe}/exploration/{other.empire}/missions",
            headers=w.headers(),
            json={
                "colony_id": str(w.colony),
                "destination_id": target,
                "idempotency_key": uuid4().hex,
            },
        ),
        "extra_field": send(w, target, extra=True),
    }
    assert {k: v.status_code for k, v in codes.items()} == {
        "mapped": 409,
        "unreachable": 409,
        "foreign_colony": 404,
        "unknown_colony": 404,
        "foreign_empire": 404,
        "extra_field": 422,
    }
    assert codes["mapped"].json()["error"]["code"] == "destination_mapped"
    assert codes["unreachable"].json()["error"]["code"] == "destination_unreachable"
    with w.game.factory.begin() as s:
        for resource in ["alloys", "flux", "data"]:
            s.get(ResourceBalance, (w.colony, resource)).stock = 0
    poor = send(w, target)
    assert poor.status_code == 409 and poor.json()["error"]["code"] == "insufficient_resources"
    with w.game.factory.begin() as s:
        for resource, value in before.items():
            s.get(ResourceBalance, (w.colony, resource)).stock = value
    key = uuid4().hex
    assert send(w, target, key).status_code == 200
    conflict = send(w, isolated, key)
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == (
        "idempotency_conflict"
    )
    with w.game.factory() as s:
        assert s.scalar(select(func.count()).select_from(ExplorationMission)) == 1
        assert s.get(SystemKnowledge, (w.empire, UUID(target))).state == "DETECTED"


def test_other_universe_cookie_and_expired_session_never_stop_accepted_mission(galaxy):
    w = galaxy()
    elsewhere = galaxy()
    target = detected(w)
    # A session cookie is bound to its Universe: another Universe's routes do not accept it.
    foreign = w.client.get(
        f"/game/{elsewhere.universe}/galaxy/{elsewhere.empire}",
        headers={"X-Game-Request": "bootstrap"},
    )
    assert foreign.status_code == 401
    mission = send(w, target).json()["mission_id"]
    w.advance(hours=3)  # beyond the 2 h idle limit of the GameSession
    assert send(w, target).status_code == 401
    assert read(w).status_code == 401
    engine = TimeEngine(w.game.factory, w.app.state.clock)
    assert engine.process_next().status == "completed"
    with w.game.factory() as s:
        assert s.get(ExplorationMission, UUID(mission)).status == "completed"
        assert s.get(SystemKnowledge, (w.empire, UUID(target))).state == "MAPPED"


def test_two_participants_share_one_capacity_with_separate_intention_keys(galaxy):
    w = galaxy()
    participant, membership = uuid4(), uuid4()
    set_access(
        w.game,
        participant,
        w.universe,
        membership,
        [{"empire_id": str(w.empire), "permissions": ALL}],
    )
    raw, _, _ = enter(w.game, (participant, w.universe, membership))
    target = detected(w)
    assert send(w, target, "shared_intention_0001").status_code == 200
    w.client.cookies.set(cookie_name(w.universe), raw)
    w.raw = raw
    assert [m["status"] for m in read(w).json()["missions"]] == ["active"]
    # Same raw key, other participant: not a replay of the first one, and capacity is shared.
    again = send(w, target, "shared_intention_0001")
    assert again.status_code == 409 and again.json()["error"]["code"] == "exploration_active"


def test_concurrent_exploration_research_and_colony_spending_never_deadlock(galaxy):
    w = galaxy()
    target = UUID(detected(w))
    before = {r: w.stock(r) for r in ["alloys", "flux", "data"]}
    barrier = Barrier(3)

    def submit(kind):
        barrier.wait()
        engine = TimeEngine(w.game.factory, w.app.state.clock)
        with w.game.factory.begin() as s:
            if kind == "exploration":
                row = g.start(
                    s,
                    engine,
                    w.universe,
                    w.empire,
                    w.colony,
                    target,
                    key="race-exp",
                    at=w.game.clock(),
                )
                return {k: v for k, v in row.snapshot["cost"].items()}
            if kind == "research":
                row = research.start(
                    s,
                    engine,
                    w.universe,
                    w.empire,
                    w.colony,
                    key="race-research",
                    technology_id="engineering_1",
                    at=w.game.clock(),
                )
                return research.read_snapshot(s, row).cost
            row = enqueue(
                s,
                engine,
                w.universe,
                w.empire,
                w.colony,
                key="race-colony",
                kind="data_node",
                sector=5,
                target_level=1,
                at=w.game.clock(),
            )
            return read_order(row).quote.cost

    with ThreadPoolExecutor(3) as pool:
        costs = list(pool.map(submit, ["exploration", "research", "colony"], timeout=60))
    assert {r: before[r] - w.stock(r) for r in before} == {
        r: sum(cost[r] for cost in costs) for r in before
    }


def test_concurrent_generation_publishes_one_manifest(game):
    universe = uuid4()
    with game.factory.begin() as s:
        s.add(Universe(id=universe, name="Race", seed="race-seed"))
        s.flush()
        configure_universe(s, universe, load_ruleset("v0.3"))
    barrier = Barrier(2)

    def run(_):
        barrier.wait()
        with game.factory.begin() as s:
            return generate_world(s, universe).digest

    with ThreadPoolExecutor(2) as pool:
        digests = list(pool.map(run, range(2)))
    assert digests[0] == digests[1]
    with game.factory() as s:
        assert s.scalar(select(func.count()).select_from(UniverseGalaxy)) == 1
        assert (
            s.scalar(
                select(func.count())
                .select_from(GalaxySystem)
                .where(GalaxySystem.universe_id == universe)
            )
            == 40
        )


def test_corrupted_path_retries_without_discovery(galaxy):
    w = galaxy()
    target = detected(w)
    mission = send(w, target).json()["mission_id"]
    with w.game.factory() as s:
        foreign = s.scalar(
            select(GalaxyRoute.id).where(
                GalaxyRoute.universe_id == w.universe,
                GalaxyRoute.a_id != UUID(target),
                GalaxyRoute.b_id != UUID(target),
            )
        )
    with w.game.factory.begin() as s:
        leg = s.scalar(select(MissionLeg).where(MissionLeg.mission_id == UUID(mission)))
        original, leg.route_id = leg.route_id, foreign
        row = s.get(ExplorationMission, UUID(mission))
        row.snapshot = {**row.snapshot, "path": [str(foreign)]}
    w.advance(minutes=46)
    engine = TimeEngine(w.game.factory, w.app.state.clock)
    assert engine.process_next().status == "pending"
    with w.game.factory() as s:
        assert s.get(ExplorationReport, UUID(mission)) is None
        assert s.get(ExplorationMission, UUID(mission)).status == "active"
    with w.game.factory.begin() as s:
        s.scalar(
            select(MissionLeg).where(MissionLeg.mission_id == UUID(mission))
        ).route_id = original
        row = s.get(ExplorationMission, UUID(mission))
        row.snapshot = {**row.snapshot, "path": [str(original)]}
    w.advance(seconds=31)
    assert engine.process_next().status == "completed"
    with w.game.factory() as s:
        report = s.get(ExplorationReport, UUID(mission)).discoveries
        assert report["path"] == [str(original)]
        assert str(original) in {route["id"] for route in report["routes"]}


def test_downgrade_refuses_galaxy_grants_even_without_domain_rows(world, migration_config):
    world(permissions=["colony.read", "galaxy.read"])
    with pytest.raises(RuntimeError, match="live Galaxy/Exploration grants"):
        command.downgrade(migration_config, "0007_empire_research")
    command.upgrade(migration_config, "head")
