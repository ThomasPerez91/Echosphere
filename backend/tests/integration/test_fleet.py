"""Real PostgreSQL + GameSession tests for Fleets (ruleset v0.4): worker-only progression."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
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
from test_game_sessions import enter

from app.access.http import cookie_name
from app.colony.rules import load_ruleset
from app.colony.service import configure_universe, enqueue, initialize_colony
from app.fleet import service as fleet_service
from app.fleet.models import Fleet, FleetMission, FleetStack, ShipOrder
from app.galaxy import service as g
from app.galaxy.models import GalaxyPlanet, StartingSite, SystemKnowledge
from app.galaxy.world import generate_world
from app.main import create_app
from app.persistence.models import Colony, Empire, Planet, Universe
from app.research import service as research
from app.simulation.models import ResourceBalance, ScheduledEvent
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
    assert post(w, f"/orders/{last}/cancel", {}).status_code == 200
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
    cancelled = post(w, f"/orders/{active}/cancel", {}).json()
    assert cancelled["result"]["refunded"]["alloys"] == str(500 * M)
    assert stocks(w)["alloys"] == 10_000 * M
    assert post(w, f"/orders/{active}/cancel", {}).json()["result"]["refunded"]["alloys"] == str(
        500 * M
    )
    with w.game.factory() as s:
        event = s.scalar(
            select(ScheduledEvent).where(ScheduledEvent.idempotency_key == f"ship-order:{active}")
        )
        assert (event.status, event.error_code) == ("completed", "cancelled")
        assert s.get(ShipOrder, UUID(queued)).status == "active"  # promoted at the same instant
    flux = stocks(w)["flux"]
    assert post(w, f"/orders/{queued}/cancel", {}).status_code == 200
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
    set_access(
        w.game,
        w.user,
        w.universe,
        w.membership,
        [{"empire_id": str(w.empire), "permissions": rights}],
        revision=2,
        epoch=2,
    )
    from test_game_sessions import ticket

    encoded, pre, _ = ticket(w.game, (w.user, w.universe, w.membership), revision=2, access_epoch=2)
    raw, _ = w.game.exchange(encoded, pre, None, w.universe)
    w.raw = raw
    w.client.cookies.set(cookie_name(w.universe), raw)
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
