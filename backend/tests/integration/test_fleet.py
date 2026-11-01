"""Real PostgreSQL + GameSession tests for Fleets (ruleset v0.4): worker-only progression."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_colony_api import Clock, World, game, set_access  # noqa: F401
from test_galaxy import galaxy, read  # noqa: F401
from test_galaxy import send as explore
from test_game_sessions import enter, ticket

from app.access.http import cookie_name
from app.colony.rules import load_ruleset
from app.colony.service import configure_universe, enqueue, initialize_colony
from app.fleet import service as fleet_service
from app.fleet.models import (
    Fleet,
    FleetCargo,
    FleetMission,
    FleetReport,
    FleetStack,
    ShipOrder,
)
from app.galaxy import service as g
from app.galaxy.models import GalaxyPlanet, StartingSite, SystemKnowledge
from app.galaxy.world import generate_world
from app.main import create_app
from app.persistence.models import Colony, Empire, Planet, Universe
from app.research import service as research
from app.simulation.models import ResourceBalance, ScheduledEvent
from app.simulation.scheduler import lock_stream
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration
M = 1_000_000
FULL = [
    "colony.read",
    "galaxy.read",
    "fleet.read",
    "fleet.build",
    "fleet.command",
    "research.read",
    "research.start",
    "colony.construct",
]


@pytest.fixture
def fleets(game):
    def make(permissions=FULL, universe=None, ruleset="v0.4", other=False):
        universe = universe or uuid4()
        user, membership = uuid4(), uuid4()
        with game.factory.begin() as s:
            if s.get(Universe, universe) is None:
                s.add(Universe(id=universe, name="Fleet test", seed="test-galaxy"))
                s.flush()
                configure_universe(s, universe, load_ruleset(ruleset))
                generate_world(s, universe)
            site = list(
                s.scalars(
                    select(StartingSite)
                    .where(StartingSite.universe_id == universe)
                    .order_by(StartingSite.planet_id)
                )
            )[1 if other else 0]
            empire = Empire(universe_id=universe, name="Admiral", controller_type="human")
            s.add(empire)
            s.flush()
            colony = Colony(universe_id=universe, empire_id=empire.id, planet_id=site.planet_id)
            s.add(colony)
            s.flush()
            initialize_colony(s, universe, empire.id, colony.id, game.clock())
            g.initialize_empire(
                s,
                TimeEngine(game.factory, Clock(game)),
                universe,
                empire.id,
                colony.id,
                game.clock(),
            )
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


def view(w):
    return w.client.get(
        f"/game/{w.universe}/fleets/{w.empire}", headers={"X-Game-Request": "bootstrap"}
    )


def post(w, path, body):
    return w.client.post(
        f"/game/{w.universe}/fleets/{w.empire}{path}", headers=w.headers(), json=body
    )


def order(w, ship="probe", quantity=1, key=None):
    body = {"idempotency_key": key or uuid4().hex, "colony_id": str(w.colony)}
    return post(w, "/orders", body | {"ship_class": ship, "quantity": quantity})


def launch(w, fleet, kind, destination=None, units=None, key=None, cargo=None):
    body = {"idempotency_key": key or uuid4().hex, "fleet_id": str(fleet), "kind": kind}
    body["units"] = units or {"probe": 1}
    if destination:
        body["destination_id"] = str(destination)
    if cargo:
        body["cargo"] = cargo
    return post(w, "/missions", body)


def cancel(w, order_id, key=None):
    """Same body as the real client (useFleets.run): always an intention key."""
    return post(w, f"/orders/{order_id}/cancel", {"idempotency_key": key or uuid4().hex})


def worker(w, limit=20):
    """Drain due events like the real worker; returns how many were processed."""
    engine, count = TimeEngine(w.game.factory, Clock(w.game)), 0
    while count < limit and engine.process_next() is not None:
        count += 1
    return count


def garrison(w):
    return next((f for f in view(w).json()["fleets"] if f["kind"] == "GARRISON"), None)


def detected(w):
    return next(s["id"] for s in view(w).json()["systems"] if s["state"] == "DETECTED")


def stocks(w, colony=None):
    with w.game.factory() as s:
        return {
            r: s.get(ResourceBalance, (colony or w.colony, r)).stock
            for r in ("alloys", "flux", "data")
        }


def built(w, ship="probe", quantity=1):
    assert order(w, ship, quantity).status_code == 200
    w.advance(minutes=(20 if ship == "probe" else 40) * quantity + 1)
    assert worker(w) >= 1
    return garrison(w)


def surveyed(w):
    """One probe surveys a neighbour; returns (task fleet id, mapped system id)."""
    home = built(w)
    target = detected(w)
    body = launch(w, home["id"], "SURVEY", target).json()
    w.advance(minutes=26)
    worker(w)
    return body["result"]["fleet_id"], target


def test_historical_rulesets_have_no_fleets_and_v04_has_no_abstract_expedition(fleets, galaxy):
    old = galaxy()  # v0.3 fixture, abstract expedition intact
    response = old.client.get(
        f"/game/{old.universe}/fleets/{old.empire}", headers={"X-Game-Request": "bootstrap"}
    )
    assert response.status_code == 404  # no fleet.read granted, indistinguishable
    w = fleets(permissions=[*FULL, "exploration.read", "exploration.start"])
    body = view(w).json()
    assert (
        body["available"] is True
        and body["fleets"] == []
        and set(body["catalogue"])
        == {
            "probe",
            "freighter",
        }
    )
    refused = explore(w, detected(w))
    assert (
        refused.status_code == 409 and refused.json()["error"]["code"] == "exploration_unavailable"
    )
    assert read(w).json()["options"] == []
    v03 = fleets(ruleset="v0.3")
    assert view(v03).json() == view(v03).json() | {"available": False}
    assert order(v03).json()["error"]["code"] == "fleet_unavailable"


def test_batch_production_reaches_garrison_by_worker_only_and_activates_next(fleets):
    w = fleets()
    before = stocks(w)
    assert order(w, "probe", 3).status_code == 200
    assert order(w, "freighter", 1).status_code == 200
    assert order(w, "probe", 1).status_code == 200
    assert order(w, "probe", 1).json()["error"]["code"] == "queue_full"
    spent = {r: before[r] - stocks(w)[r] for r in before}
    assert spent == {"alloys": (240 + 200 + 80) * M, "flux": (120 + 60 + 40) * M, "data": 180 * M}
    with w.game.factory() as s:
        first = s.scalar(select(ShipOrder).where(ShipOrder.status == "active"))
        due = first.due_at
        assert due - first.started_at == timedelta(minutes=60)  # 3 × 20 min, no speed applied
    w.advance(minutes=61)
    # A projection never progresses the Empire Operations timeline.
    for _ in range(2):
        assert view(w).json()["fleets"] == []
        assert read(w).status_code == 200
    with w.game.factory() as s:
        assert s.scalar(select(ShipOrder.status).where(ShipOrder.id == first.id)) == "active"
    assert worker(w) == 1
    assert worker(w) == 0  # exactly once
    home = garrison(w)
    assert home["stacks"] == {"probe": 3} and home["status"] == "STATIONED"
    with w.game.factory() as s:
        following = s.scalar(select(ShipOrder).where(ShipOrder.status == "active"))
        assert following.ship_class == "freighter" and following.started_at == due


def test_cancellation_queued_100_active_80_capped_and_no_partial_ship(fleets):
    w = fleets()
    active = order(w, "freighter", 5).json()["result"]["order_id"]
    queued = order(w, "probe", 2).json()["result"]["order_id"]
    last = order(w, "probe", 1).json()["result"]["order_id"]
    flux = stocks(w)["flux"]
    assert cancel(w, last).status_code == 200
    assert stocks(w)["flux"] - flux == 40 * M  # still queued: 100 %
    with w.game.factory.begin() as s:
        s.get(ResourceBalance, (w.colony, "alloys")).stock = 9_500 * M  # 500 free
    preview = next(
        o["cancel"] for o in view(w).json()["colonies"][0]["orders"] if o["id"] == active
    )
    assert preview["theoretical"]["alloys"] == str(800 * M)  # 80 % of 1000
    assert preview["recoverable"]["alloys"] == str(500 * M) and preview["lost"]["alloys"] == str(
        300 * M
    )
    cancelled = cancel(w, active).json()
    assert cancelled["result"]["refunded"]["alloys"] == str(500 * M)
    assert stocks(w)["alloys"] == 10_000 * M
    assert cancel(w, active).json()["result"]["refunded"]["alloys"] == str(500 * M)
    with w.game.factory() as s:
        event = s.scalar(
            select(ScheduledEvent).where(ScheduledEvent.idempotency_key == f"ship-order:{active}")
        )
        assert (event.status, event.error_code) == ("completed", "cancelled")
        assert s.get(ShipOrder, UUID(queued)).status == "active"  # promoted at the same instant
    flux = stocks(w)["flux"]
    assert cancel(w, queued).status_code == 200
    assert stocks(w)["flux"] - flux == 64 * M  # promoted to active: 80 %
    w.advance(hours=10)
    worker(w)
    with w.game.factory() as s:  # no partial ship ever (checked in DB: the session went idle)
        assert s.scalar(select(func.count()).select_from(FleetStack)) == 0


def test_survey_travel_then_analysis_recall_window_and_worker_mapping(fleets):
    w = fleets()
    home = built(w)
    target = detected(w)
    assert w.read().status_code == 200  # settle the colony at this instant first
    before = stocks(w)
    body = launch(w, home["id"], "SURVEY", target).json()
    mission_id, probe_fleet = body["result"]["mission_id"], body["result"]["fleet_id"]
    assert {r: before[r] - stocks(w)[r] for r in before} == {
        "alloys": 0,
        "flux": 4 * M,
        "data": 20 * M,
    }
    with w.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        assert mission.travel_arrival_at - mission.started_at == timedelta(minutes=10)
        assert mission.due_at - mission.travel_arrival_at == timedelta(minutes=15)
    w.advance(minutes=11)  # analysis under way: recall refused
    refused = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert refused.json()["error"]["code"] == "recall_too_late"
    w.advance(minutes=15)  # due passed: GETs still cannot map anything
    assert read(w, target).json()["state"] == "DETECTED"
    assert next(m for m in view(w).json()["missions"])["status"] == "active"
    assert worker(w) == 1 and worker(w) == 0
    assert read(w, target).json()["state"] == "MAPPED"
    probe = next(f for f in view(w).json()["fleets"] if f["id"] == probe_fleet)
    assert probe["system"]["id"] == target and probe["status"] == "STATIONED"
    report = view(w).json()["missions"][0]["report"]
    assert report["observed_at"] == view(w).json()["missions"][0]["due_at"]
    assert report["result"]["discoveries"]["system"]["state"] == "MAPPED"


def test_deploy_recall_is_time_symmetric_idempotent_and_returns_once(fleets):
    w = fleets()
    probe, mapped = surveyed(w)
    origin = next(s["id"] for s in view(w).json()["systems"] if s["state"] == "MONITORED")
    body = launch(w, probe, "DEPLOY", origin).json()
    mission_id = body["result"]["mission_id"]
    assert body["result"]["fleet_id"] == probe  # a whole task fleet moves itself
    w.advance(minutes=4)
    key = uuid4().hex
    first = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": key}).json()
    again = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": key}).json()
    other = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex}).json()
    assert first["result"] == again["result"] == other["result"]
    with w.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        assert mission.return_at - mission.recalled_at == mission.recalled_at - mission.started_at
        events = s.scalars(
            select(ScheduledEvent).where(ScheduledEvent.idempotency_key.like(f"%{mission_id}"))
        ).all()
        assert sorted((e.event_type, e.status, e.error_code) for e in events) == [
            ("FLEET_ARRIVAL", "completed", "cancelled"),
            ("FLEET_RETURN", "pending", None),
        ]
    w.advance(minutes=5)
    assert worker(w) == 1 and worker(w) == 0
    back = next(f for f in view(w).json()["fleets"] if f["id"] == probe)
    assert back["system"]["id"] == mapped and back["status"] == "STATIONED"
    refused = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert refused.status_code == 409
    home = launch(w, probe, "RETURN").json()["result"]["mission_id"]
    no = post(w, f"/missions/{home}/recall", {"idempotency_key": uuid4().hex}).json()
    assert no["error"]["code"] == "recall_refused"
    w.advance(minutes=11)
    worker(w)
    assert next(f for f in view(w).json()["fleets"] if f["id"] == probe)["system"]["id"] == origin


def test_split_merge_keep_cargo_within_each_capacity(fleets):
    w = fleets()
    home = built(w, "freighter", 2)
    loaded = post(
        w,
        f"/{home['id']}/load",
        {"idempotency_key": uuid4().hex, "colony_id": str(w.colony), "cargo": {"alloys": 900}},
    )
    assert loaded.status_code == 200 and stocks(w)["alloys"] < 2000 * M
    too_much = post(
        w,
        f"/{home['id']}/split",
        {"idempotency_key": uuid4().hex, "units": {"freighter": 1}, "cargo": {"alloys": 100}},
    )
    assert too_much.json()["error"]["code"] == "cargo_capacity"  # 800 left for 500 capacity
    key = uuid4().hex
    split = {"idempotency_key": key, "units": {"freighter": 1}, "cargo": {"alloys": 450}}
    first = post(w, f"/{home['id']}/split", split).json()
    assert post(w, f"/{home['id']}/split", split).json()["result"] == first["result"]
    task = first["result"]["fleet_id"]
    by_id = {f["id"]: f for f in view(w).json()["fleets"]}
    assert by_id[task]["cargo"]["alloys"] == str(450 * M)
    assert by_id[home["id"]]["cargo"]["alloys"] == str(450 * M)
    merged = post(w, f"/{task}/merge", {"idempotency_key": uuid4().hex, "target_id": home["id"]})
    assert merged.status_code == 200
    by_id = {f["id"]: f for f in view(w).json()["fleets"]}
    assert task not in by_id and by_id[home["id"]]["cargo"]["alloys"] == str(900 * M)
    assert by_id[home["id"]]["stacks"] == {"freighter": 2}


def test_transport_unloads_up_to_storage_and_keeps_surplus_aboard(fleets):
    w = fleets()
    probe, mapped = surveyed(w)
    with w.game.factory.begin() as s:
        # Test-only second colony: no product flow creates one before step 10.
        planet = s.scalar(
            select(GalaxyPlanet.planet_id).where(GalaxyPlanet.system_id == UUID(mapped)).limit(1)
        )
        second = Colony(universe_id=w.universe, empire_id=w.empire, planet_id=planet)
        s.add(second)
        s.flush()
        # The reference initializer accepts only the v0.4 starting capacities (test-only colony).
        s.get(Planet, planet).sector_capacity = 12
        s.get(Planet, planet).orbital_capacity = 2
        s.flush()
        initialize_colony(s, w.universe, w.empire, second.id, w.game.clock())
        alloys = s.get(ResourceBalance, (second.id, "alloys"))
        alloys.stock, alloys.rate_per_hour = 9_900 * M, 0  # deterministic free storage: 100
        second_id = second.id
    home = built(w, "freighter", 1)
    post(
        w,
        f"/{home['id']}/load",
        {"idempotency_key": uuid4().hex, "colony_id": str(w.colony), "cargo": {"alloys": 300}},
    )
    convoy = launch(w, home["id"], "DEPLOY", mapped, units={"freighter": 1}, cargo={"alloys": 300})
    task = convoy.json()["result"]["fleet_id"]
    w.advance(minutes=21)
    worker(w)
    with w.game.factory.begin() as s:
        s.get(ResourceBalance, (second_id, "alloys")).stock = 9_900 * M  # production may refill
    preview = next(f for f in view(w).json()["fleets"] if f["id"] == task)["unload"]
    assert preview["credited"]["alloys"] == str(100 * M) and preview["kept"]["alloys"] == str(
        200 * M
    )
    key = uuid4().hex
    body = {"idempotency_key": key, "colony_id": str(second_id)}
    result = post(w, f"/{task}/unload", body).json()["result"]
    assert result["credited"]["alloys"] == str(100 * M) and result["kept"]["alloys"] == str(200 * M)
    assert post(w, f"/{task}/unload", body).json()["result"] == result  # replay credits nothing
    assert stocks(w, second_id)["alloys"] == 10_000 * M
    assert next(f for f in view(w).json()["fleets"] if f["id"] == task)["cargo"]["alloys"] == str(
        200 * M
    )


def rebind(w, rights, revision=2):
    """New binding revision and a fresh GameSession carrying exactly these rights."""
    set_access(
        w.game,
        w.user,
        w.universe,
        w.membership,
        [{"empire_id": str(w.empire), "permissions": rights}],
        revision=revision,
        epoch=revision,
    )
    encoded, pre, _ = ticket(
        w.game, (w.user, w.universe, w.membership), revision=revision, access_epoch=revision
    )
    raw, _ = w.game.exchange(encoded, pre, None, w.universe)
    w.raw = raw
    w.client.cookies.set(cookie_name(w.universe), raw)


@pytest.mark.parametrize(
    "rights,call,code",
    [
        (["colony.read", "galaxy.read"], "read", 404),
        (["fleet.read", "colony.read"], "order", 403),
        (["fleet.read", "fleet.build"], "order", 403),
        (["fleet.read", "fleet.command", "colony.read"], "survey", 403),
        (["fleet.read", "fleet.command"], "load", 403),
    ],
)
def test_permissions_are_explicit(fleets, rights, call, code):
    w = fleets()
    fleet_id = uuid4()
    if call != "read" and call != "order":
        fleet_id = built(w)["id"]
    rebind(w, rights)
    response = {
        "read": lambda: view(w),
        "order": lambda: order(w),
        "survey": lambda: launch(w, fleet_id, "SURVEY", uuid4()),
        "load": lambda: post(
            w,
            f"/{fleet_id}/load",
            {"idempotency_key": uuid4().hex, "colony_id": str(w.colony), "cargo": {"flux": 1}},
        ),
    }[call]()
    assert response.status_code == code


def test_foreign_unknown_and_cross_universe_fleets_are_indistinguishable(fleets):
    w = fleets()
    other = fleets(universe=w.universe, other=True)
    foreign = built(other)["id"]
    mine = built(w)["id"]
    absent = launch(w, uuid4(), "DEPLOY", uuid4())
    for fleet_id in [foreign]:
        response = launch(w, fleet_id, "DEPLOY", uuid4())
        assert response.status_code == absent.status_code == 404
        assert response.json() == absent.json()
    hidden = launch(w, mine, "SURVEY", uuid4()).json()
    assert hidden["error"]["code"] == "system_not_found"
    assert all(f["id"] != foreign for f in view(w).json()["fleets"])
    elsewhere = fleets()
    response = elsewhere.client.post(
        f"/game/{elsewhere.universe}/fleets/{elsewhere.empire}/{mine}/split",
        headers=elsewhere.headers(),
        json={"idempotency_key": uuid4().hex, "units": {"probe": 1}},
    )
    assert response.status_code == 404
    reader = fleets(permissions=["fleet.read", "fleet.command"])
    assert all(s["state"] != "DETECTED" for s in view(reader).json()["systems"])


def test_database_enforces_engagement_and_known_location(fleets):
    w = fleets()
    home = built(w)
    with w.game.factory() as s:
        known = s.get(Fleet, UUID(home["id"]))
        unknown = s.scalar(
            select(GalaxyPlanet.system_id).where(
                GalaxyPlanet.universe_id == w.universe,
                GalaxyPlanet.system_id.not_in(
                    select(SystemKnowledge.system_id).where(SystemKnowledge.empire_id == w.empire)
                ),
            )
        )
        cases = [
            dict(kind="TASK", status="MOVING", system_id=None),  # moving without a mission
            dict(kind="TASK", status="STATIONED", system_id=unknown),  # beyond its knowledge
            dict(kind="GARRISON", status="STATIONED", system_id=known.system_id),  # 2nd garrison
        ]
    for case in cases:
        with w.game.factory.begin() as s, pytest.raises(IntegrityError):
            s.add(
                Fleet(
                    empire_id=w.empire,
                    universe_id=w.universe,
                    home_colony_id=w.colony,
                    name="Invalid",
                    **case,
                )
            )
            s.flush()
    with w.game.factory.begin() as s, pytest.raises(IntegrityError):
        s.add(FleetStack(fleet_id=UUID(home["id"]), ship_class="probe", count=0))
        s.flush()


def test_concurrent_launches_of_one_fleet_engage_units_once(fleets):
    w = fleets()
    home = built(w, "probe", 1)
    target = detected(w)
    barrier = Barrier(2)

    def attempt(key):
        barrier.wait()
        return launch(w, home["id"], "SURVEY", target, key=key)

    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(attempt, [uuid4().hex, uuid4().hex]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    with w.game.factory() as s:
        assert s.scalar(select(func.count()).select_from(FleetMission)) == 1
        assert s.scalar(select(func.sum(FleetStack.count))) == 1  # conservation of units
    key = uuid4().hex
    with ThreadPoolExecutor(2) as pool:
        same = list(pool.map(lambda _: order(w, "probe", 1, key=key), range(2)))
    assert {r.status_code for r in same} == {200}
    assert len({r.json()["result"]["order_id"] for r in same}) == 1


def test_split_during_mission_and_recall_versus_worker_arrival(fleets):
    w = fleets()
    home = built(w, "probe", 2)
    target = detected(w)
    moving = launch(w, home["id"], "SURVEY", target).json()["result"]
    refused = post(
        w,
        f"/{moving['fleet_id']}/split",
        {"idempotency_key": uuid4().hex, "units": {"probe": 1}},
    )
    assert refused.json()["error"]["code"] == "fleet_moving"
    w.advance(minutes=10, seconds=-1)
    other = launch(w, home["id"], "SURVEY", target).json()["result"]["mission_id"]
    w.advance(minutes=30)  # past the second survey due_at: the recall races its arrival
    barrier = Barrier(2)

    def recall(_):
        barrier.wait()
        return post(w, f"/missions/{other}/recall", {"idempotency_key": uuid4().hex})

    def process(_):
        barrier.wait()
        return TimeEngine(w.game.factory, Clock(w.game)).process_next()

    with ThreadPoolExecutor(2) as pool:
        recall_result, _ = pool.map(lambda f: f(None), [recall, process])
    assert recall_result.status_code == 409
    worker(w)
    with w.game.factory() as s:
        assert s.get(FleetMission, UUID(other)).status == "completed"
        assert (
            s.scalar(
                select(func.count())
                .select_from(FleetMission)
                .where(FleetMission.status != "completed")
            )
            == 0
        )


def test_concurrent_fleet_research_and_colony_spending_never_deadlock(fleets):
    w = fleets()
    engine = TimeEngine(w.game.factory, Clock(w.game))
    barrier = Barrier(3)

    def production(_):
        barrier.wait()
        with w.game.factory.begin() as s:
            return fleet_service.order_ships(
                s,
                engine,
                w.universe,
                w.empire,
                w.colony,
                "probe",
                1,
                key=uuid4().hex,
                at=w.game.clock(),
            ).status

    def lab(_):
        barrier.wait()
        with w.game.factory.begin() as s:
            return research.start(
                s,
                engine,
                w.universe,
                w.empire,
                w.colony,
                key=uuid4().hex,
                technology_id="energy_1",
                at=w.game.clock(),
            ).status

    def build(_):
        barrier.wait()
        with w.game.factory.begin() as s:
            return enqueue(
                s,
                engine,
                w.universe,
                w.empire,
                w.colony,
                key=uuid4().hex,
                kind="extraction_complex",
                sector=5,
                target_level=1,
                at=w.game.clock(),
            ).status

    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(lambda f: f(None), [production, lab, build]))
    assert len(results) == 3 and all(results)


def test_expired_session_refuses_commands_but_accepted_fleet_work_completes(fleets):
    w = fleets()
    assert order(w).status_code == 200
    w.advance(hours=9)
    assert order(w).status_code == 401
    assert view(w).status_code == 401
    worker(w)
    with w.game.factory() as s:
        assert s.scalar(select(func.sum(FleetStack.count))) == 1


def test_galaxy_get_never_completes_an_overdue_v03_expedition(galaxy):
    w = galaxy()
    target = next(s["id"] for s in read(w).json()["systems"] if s["state"] == "DETECTED")
    assert explore(w, target).status_code == 200
    w.advance(minutes=50)  # past the 45 min expedition, within the 2 h idle limit
    for path in ["", f"/systems/{target}"]:
        read(w, target if path else None)
    assert next(s for s in read(w).json()["systems"] if s["id"] == target)["state"] == "DETECTED"
    assert read(w).json()["missions"][0]["status"] == "active"
    assert worker(w) == 1
    assert next(s for s in read(w).json()["systems"] if s["id"] == target)["state"] == "MAPPED"


def test_fleets_never_create_colonies(fleets):
    """Guard: Fleet code never touches Planet ownership or creates colonies."""
    w = fleets()
    built(w)
    with w.game.factory() as s:
        assert s.scalar(select(func.count()).select_from(Colony)) == 1
        assert s.get(Planet, s.get(Colony, w.colony).planet_id) is not None


def test_concurrent_orders_on_one_colony_keep_queue_and_sequences_consistent(fleets):
    w = fleets()
    barrier = Barrier(4)

    def attempt(_):
        barrier.wait()
        return order(w, "probe", 1)

    with ThreadPoolExecutor(4) as pool:
        responses = list(pool.map(attempt, range(4)))
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 409]
    with w.game.factory() as s:
        rows = s.scalars(select(ShipOrder).order_by(ShipOrder.sequence)).all()
        assert [r.sequence for r in rows] == [1, 2, 3]
        assert [r.status for r in rows].count("active") == 1


def test_mission_racing_a_load_never_moves_unloaded_cargo_or_duplicates_units(fleets):
    w = fleets()
    home = built(w, "freighter", 1)
    probe, mapped = surveyed(w)
    barrier = Barrier(2)

    def load(_):
        barrier.wait()
        return post(
            w,
            f"/{home['id']}/load",
            {"idempotency_key": uuid4().hex, "colony_id": str(w.colony), "cargo": {"flux": 100}},
        )

    def leave(_):
        barrier.wait()
        return launch(w, home["id"], "DEPLOY", mapped, units={"freighter": 1})

    with ThreadPoolExecutor(2) as pool:
        loaded, left = pool.map(lambda f: f(None), [load, leave])
    # Serialized on the Operations stream: whichever runs second would strand cargo in a fleet
    # without capacity, so it is refused atomically; units are never duplicated.
    responses = sorted([loaded, left], key=lambda r: r.status_code)
    assert [r.status_code for r in responses] == [200, 409]
    assert responses[1].json()["error"]["code"] == "cargo_capacity"
    with w.game.factory() as s:
        freighters = select(func.sum(FleetStack.count)).where(FleetStack.ship_class == "freighter")
        assert s.scalar(freighters) == 1


def test_two_participants_of_one_empire_share_fleets_with_separate_intentions(fleets):
    w = fleets()
    user, membership = uuid4(), uuid4()
    set_access(
        w.game, user, w.universe, membership, [{"empire_id": str(w.empire), "permissions": FULL}]
    )
    raw, _, _ = enter(w.game, (user, w.universe, membership))
    other = TestClient(w.app, base_url=w.game.settings.game_public_origin)
    other.cookies.set(cookie_name(w.universe), raw)
    key = uuid4().hex
    mine = order(w, key=key).json()["result"]["order_id"]
    theirs = other.post(
        f"/game/{w.universe}/fleets/{w.empire}/orders",
        headers=w.headers(raw),
        json={
            "idempotency_key": key,
            "colony_id": str(w.colony),
            "ship_class": "probe",
            "quantity": 1,
        },
    ).json()["result"]["order_id"]
    assert mine != theirs  # same client key, different membership namespaces
    assert len(view(w).json()["colonies"][0]["orders"]) == 2


def test_concurrent_workers_apply_an_arrival_exactly_once(fleets):
    w = fleets()
    home = built(w)
    launch(w, home["id"], "SURVEY", detected(w))
    w.advance(minutes=26)

    def process(_):
        return TimeEngine(w.game.factory, Clock(w.game)).process_next()

    with ThreadPoolExecutor(3) as pool:
        outcomes = list(pool.map(process, range(3)))
    assert sum(1 for o in outcomes if o is not None) == 1
    with w.game.factory() as s:
        assert s.scalar(select(func.count()).select_from(FleetMission)) == 1
        assert s.scalar(select(FleetMission.status)) == "completed"


def known_rows(w):
    with w.game.factory() as s:
        rows = s.scalars(select(SystemKnowledge).where(SystemKnowledge.empire_id == w.empire))
        return sorted(
            (str(r.system_id), {c.key: getattr(r, c.key) for c in r.__mapper__.column_attrs})
            for r in rows
        )


def drift(*path, value):
    """Rewrites one nested snapshot field after acceptance (JSONB replaced as a whole)."""

    def apply(s, mission, fleet, other):
        snapshot = deepcopy(mission.snapshot)
        node = snapshot
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value(node[path[-1]], mission, other)
        mission.snapshot = snapshot

    return apply


def set_column(name, value):
    def apply(s, mission, fleet, other):
        setattr(mission, name, value(mission, other))

    return apply


def add_stack(s, mission, fleet, other):
    s.add(FleetStack(fleet_id=fleet.id, ship_class="freighter", count=1))


def add_cargo(s, mission, fleet, other):
    s.add(FleetCargo(fleet_id=fleet.id, resource="alloys", amount=M))


def deploy_from_survey(w):
    """A probe on a MAPPED neighbour deploys back home: (mission id, fleet id, other system)."""
    probe, mapped = surveyed(w)
    systems = view(w).json()["systems"]
    home = next(s["id"] for s in systems if s["state"] == "MONITORED")
    other = next(s["id"] for s in systems if s["id"] not in (home, mapped))
    body = launch(w, probe, "DEPLOY", home).json()
    return body["result"]["mission_id"], probe, UUID(other)


def assert_refused_untouched(w, mission_id, fleet_id, status, knowledge, kind):
    """A drifted mission blocks: no effect, no teleport, no report, no Knowledge change."""
    blocked = TimeEngine(w.game.factory, Clock(w.game), max_attempts=1).process_next()
    assert blocked is not None and blocked.status == "blocked"
    with w.game.factory() as s:
        event = s.get(ScheduledEvent, blocked.event_id)
        assert (event.event_type, event.error_code) == (kind, "handler_failed")
        mission = s.get(FleetMission, UUID(mission_id))
        fleet = s.get(Fleet, UUID(fleet_id))
        assert mission.status == status and mission.completed_at is None
        assert (fleet.status, fleet.system_id, fleet.active_mission_id) == (
            "MOVING",
            None,
            mission.id,
        )
        assert s.get(FleetReport, mission.id) is None
    assert known_rows(w) == knowledge
    assert worker(w) == 0  # blocked head waits for an explicit operator repair


DRIFTS = {
    "origin": set_column("origin_id", lambda m, other: other),
    "destination": set_column("destination_id", lambda m, other: other),
    "path": drift("path", value=lambda v, m, other: [str(uuid4())]),
    "travel_us": drift("travel_us", value=lambda v, m, other: v + 1),
    "kind": drift("kind", value=lambda v, m, other: "SURVEY"),
    "class": drift("classes", "probe", "hop_seconds", value=lambda v, m, other: v * 2),
    "started_at": set_column("started_at", lambda m, other: m.started_at - timedelta(seconds=1)),
    "stacks": add_stack,
    "cargo": add_cargo,
}


@pytest.mark.parametrize("name", sorted(DRIFTS))
def test_worker_refuses_an_arrival_whose_accepted_mission_drifted(fleets, name):
    w = fleets()
    mission_id, probe, other = deploy_from_survey(w)
    with w.game.factory.begin() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        DRIFTS[name](s, mission, s.get(Fleet, UUID(probe)), other)
    knowledge = known_rows(w)
    w.advance(minutes=11)
    assert_refused_untouched(w, mission_id, probe, "active", knowledge, "FLEET_ARRIVAL")


def test_worker_refuses_a_survey_whose_snapshot_drifted_without_mapping(fleets):
    w = fleets()
    home = built(w)
    target = detected(w)
    body = launch(w, home["id"], "SURVEY", target).json()
    mission_id, probe = body["result"]["mission_id"], body["result"]["fleet_id"]
    with w.game.factory.begin() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        drift("survey_us", value=lambda v, m, other: v - 1)(s, mission, None, None)
    knowledge = known_rows(w)
    w.advance(minutes=26)
    assert_refused_untouched(w, mission_id, probe, "active", knowledge, "FLEET_ARRIVAL")
    assert read(w, target).json()["state"] == "DETECTED"


RETURN_DRIFTS = {
    "origin": set_column("origin_id", lambda m, other: other),
    "snapshot_origin": drift("origin_id", value=lambda v, m, other: str(m.destination_id)),
    "speed": drift("speed", "numerator", value=lambda v, m, other: v + 1),
    "stacks": add_stack,
}


@pytest.mark.parametrize("name", sorted(RETURN_DRIFTS))
def test_worker_refuses_a_return_whose_accepted_mission_drifted(fleets, name):
    w = fleets()
    mission_id, probe, other = deploy_from_survey(w)
    w.advance(minutes=4)
    recall = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert recall.status_code == 200
    with w.game.factory.begin() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        RETURN_DRIFTS[name](s, mission, s.get(Fleet, UUID(probe)), other)
    knowledge = known_rows(w)
    w.advance(minutes=5)
    assert_refused_untouched(w, mission_id, probe, "returning", knowledge, "FLEET_RETURN")


def test_recall_of_a_drifted_mission_schedules_no_return(fleets):
    w = fleets()
    mission_id, probe, other = deploy_from_survey(w)
    with w.game.factory.begin() as s:
        set_column("origin_id", lambda m, other: other)(
            s, s.get(FleetMission, UUID(mission_id)), None, other
        )
    w.advance(minutes=4)
    refused = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert refused.status_code == 503
    with w.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        assert mission.status == "active" and mission.recalled_at is None
        events = s.scalars(
            select(ScheduledEvent).where(ScheduledEvent.idempotency_key.like(f"%{mission_id}"))
        ).all()
        assert [(e.event_type, e.status) for e in events] == [("FLEET_ARRIVAL", "pending")]


def test_cancel_takes_the_client_intention_key_and_never_refunds_twice(fleets):
    w = fleets()
    order(w, "freighter", 1)
    queued = order(w, "probe", 1).json()["result"]["order_id"]
    assert w.read().status_code == 200  # settle the colony at this instant first
    flux, key = stocks(w)["flux"], uuid4().hex
    first = cancel(w, queued, key)
    assert first.status_code == 200
    assert first.json()["result"] == {
        "order_id": queued,
        "refunded": {"alloys": str(80 * M), "data": str(40 * M), "flux": str(40 * M)},
    }
    assert cancel(w, queued, key).json()["result"] == first.json()["result"]
    assert cancel(w, queued).json()["result"] == first.json()["result"]
    assert stocks(w)["flux"] - flux == 40 * M  # refunded exactly once
    assert post(w, f"/orders/{queued}/cancel", {}).status_code == 422  # the key is the contract
    with w.game.factory() as s:
        assert s.get(ShipOrder, UUID(queued)).status == "cancelled"


def test_mission_preview_hides_the_paying_colony_without_colony_read(fleets):
    w = fleets()
    probe, mapped = surveyed(w)
    home = next(s["id"] for s in view(w).json()["systems"] if s["state"] == "MONITORED")
    plan = {"fleet_id": probe, "kind": "DEPLOY", "destination_id": home, "units": {"probe": 1}}
    shown = post(w, "/missions/preview", plan)
    assert shown.status_code == 200 and shown.json()["payer_colony_id"] == str(w.colony)
    rebind(w, ["fleet.read", "fleet.command"])
    for body in (plan, {"fleet_id": probe, "kind": "RETURN", "units": {"probe": 1}}):
        hidden = post(w, "/missions/preview", body)
        assert hidden.status_code == 200 and hidden.json()["payer_colony_id"] is None
        assert hidden.json()["hops"] == 1  # the command itself stays allowed
    assert str(w.colony) not in view(w).text


def test_open_missions_are_never_hidden_by_the_history_limit(fleets):
    w = fleets()
    home = built(w, "probe", 2)
    target = detected(w)
    active = launch(w, home["id"], "SURVEY", target).json()["result"]["mission_id"]
    w.advance(minutes=1)
    recalled = launch(w, home["id"], "SURVEY", target).json()["result"]["mission_id"]
    w.advance(minutes=1)
    assert (
        post(w, f"/missions/{recalled}/recall", {"idempotency_key": uuid4().hex}).status_code == 200
    )
    with w.game.factory.begin() as s:
        old = s.get(FleetMission, UUID(active))
        for i in range(31):  # newer history: 31 completed missions started after both
            start = old.started_at + timedelta(minutes=5, seconds=i)
            s.add(
                FleetMission(
                    empire_id=w.empire,
                    universe_id=w.universe,
                    fleet_id=UUID(home["id"]),
                    kind="DEPLOY",
                    status="completed",
                    origin_id=old.origin_id,
                    destination_id=old.destination_id,
                    payer_colony_id=w.colony,
                    idempotency_key=uuid4().hex,
                    snapshot=old.snapshot,
                    started_at=start,
                    travel_arrival_at=start + timedelta(seconds=1),
                    due_at=start + timedelta(seconds=1),
                    completed_at=start + timedelta(seconds=1),
                )
            )
    missions = view(w).json()["missions"]
    statuses = {m["id"]: m["status"] for m in missions}
    assert statuses[active] == "active" and statuses[recalled] == "returning"
    assert sum(1 for m in missions if m["status"] == "completed") == 30
    assert len(missions) == 32
    starts = [(m["started_at"], m["id"]) for m in missions]
    assert [s for s, _ in starts] == sorted((s for s, _ in starts), reverse=True)
    assert [m["id"] for m in missions[-2:]] == [recalled, active]  # oldest, still listed
    assert (
        post(w, f"/missions/{active}/recall", {"idempotency_key": uuid4().hex}).status_code == 200
    )


def test_fleet_read_waits_for_the_worker_holding_the_operations_stream(fleets):
    """A GET never interleaves with an event being applied: it waits for the stream lock."""
    w = fleets()
    home = built(w)
    launch(w, home["id"], "SURVEY", detected(w))
    w.advance(minutes=26)
    with w.game.factory() as s:
        stream = g.state_for(s, w.universe, w.empire).stream_id
    holder = w.game.factory()
    holder.begin()
    lock_stream(holder, stream, w.universe)  # what the worker holds while applying the arrival
    with ThreadPoolExecutor(1) as pool:
        reading = pool.submit(view, w)
        try:
            with pytest.raises(FuturesTimeout):
                reading.result(timeout=1)
        finally:
            holder.rollback()
            holder.close()
        assert reading.result(timeout=10).status_code == 200
    assert worker(w) == 1
    body = view(w).json()
    moving = [f for f in body["fleets"] if f["status"] == "MOVING"]
    open_missions = [m for m in body["missions"] if m["status"] != "completed"]
    assert moving == open_missions == []  # one consistent state after the arrival
