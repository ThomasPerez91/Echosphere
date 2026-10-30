"""5D public Colony API: authorization chain, commands, idempotence, concurrency and time."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_game_sessions import apply, enter, game  # noqa: F401  (shared C07 fixture)

from app.access.http import cookie_name
from app.access.models import GameSession
from app.access.service import AccessError, csrf
from app.colony.api import Colonies, Construction
from app.colony.models import ConstructionOrder
from app.colony.rules import load_ruleset
from app.colony.service import ColonyError, configure_universe, initialize_colony
from app.main import create_app
from app.persistence.models import Colony, Empire, Planet, StellarSystem
from app.persistence.models import Universe as UniverseRow
from app.simulation.models import ResourceBalance
from app.simulation.production import MICRO_UNITS
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration
ALL = ["colony.cancel", "colony.construct", "colony.read"]


class Clock:
    """Shares the C07 fixture's controllable instant with the HTTP app and the worker."""

    def __init__(self, source):
        self.source = source

    def now(self):
        return self.source.test_clock[0]


@dataclass
class World:
    game: object
    app: object
    client: TestClient
    raw: str
    user: object
    universe: object
    membership: object
    empire: object
    colony: object

    @property
    def root(self):
        return f"/game/{self.universe}/colonies"

    def headers(self, raw=None):
        return {
            "Origin": self.game.settings.game_public_origin,
            "X-CSRF-Token": csrf(raw or self.raw),
        }

    def read(self, colony=None, client=None):
        return (client or self.client).get(
            f"{self.root}/{colony or self.colony}", headers={"X-Game-Request": "bootstrap"}
        )

    def build(self, kind="extraction_complex", sector=5, level=1, key=None, client=None, raw=None):
        return (client or self.client).post(
            f"{self.root}/{self.colony}/construction-orders",
            json={
                "idempotency_key": key or uuid4().hex,
                "infrastructure_type": kind,
                "sector_index": sector,
                "target_level": level,
            },
            headers=self.headers(raw),
        )

    def cancel(self, order, client=None, raw=None):
        return (client or self.client).post(
            f"{self.root}/{self.colony}/construction-orders/{order}/cancel",
            json={},
            headers=self.headers(raw),
        )

    def advance(self, **delta):
        self.game.test_clock[0] += timedelta(**delta)

    def stock(self, resource):
        with self.game.factory() as session:
            return session.get(ResourceBalance, (self.colony, resource)).stock


def colony_in(session, universe, rules, at, name="Test only"):
    empire = Empire(universe_id=universe, name=name, controller_type="human")
    system = StellarSystem(universe_id=universe, name=name)
    session.add_all([empire, system])
    session.flush()
    planet = Planet(
        universe_id=universe,
        system_id=system.id,
        name=name,
        sector_capacity=rules.colony.sectors,
        orbital_capacity=rules.colony.orbital_slots,
    )
    session.add(planet)
    session.flush()
    colony = Colony(universe_id=universe, empire_id=empire.id, planet_id=planet.id)
    session.add(colony)
    session.flush()
    initialize_colony(session, universe, empire.id, colony.id, at)
    return empire.id, colony.id


def set_access(service, user, universe, membership, bindings, revision=1, epoch=1, status="active"):
    apply(
        service,
        {
            "kind": "set_universe_access",
            "global_user_id": str(user),
            "universe_id": str(universe),
            "membership_id": str(membership),
            "revision": revision,
            "access_epoch": epoch,
            "account_epoch": 0,
            "status": status,
            "bindings": bindings,
            "portal_confirmed_at": service.clock().isoformat(),
            "valid_until": (service.clock() + timedelta(hours=8)).isoformat(),
        },
    )


@pytest.fixture
def world(game):  # noqa: F811
    def make(permissions=ALL, rules=None, universe=None, user=None):
        rules = rules or load_ruleset()
        universe = universe or uuid4()
        user, membership = user or uuid4(), uuid4()
        with game.factory() as session:
            exists = session.get(UniverseRow, universe) is not None
        if not exists:
            apply(
                game,
                {
                    "kind": "provision_universe",
                    "universe_id": str(universe),
                    "name": "5D test only",
                    "seed": "test",
                },
            )
            with game.factory.begin() as session:
                configure_universe(session, universe, rules)
        with game.factory.begin() as session:
            empire, colony = colony_in(session, universe, rules, game.clock())
        set_access(
            game,
            user,
            universe,
            membership,
            [{"empire_id": str(empire), "permissions": list(permissions)}],
        )
        raw, _, _ = enter(game, (user, universe, membership))
        app = create_app(game.settings)
        app.state.session_factory, app.state.clock = game.factory, Clock(game)
        client = TestClient(app, base_url=game.settings.game_public_origin)
        client.cookies.set(cookie_name(universe), raw)
        return World(game, app, client, raw, user, universe, membership, empire, colony)

    return make


def units(value):
    return int(value) // MICRO_UNITS


def test_projection_exposes_real_pinned_state_without_activity(world):
    w = world()
    with w.game.factory() as session:
        before = session.scalar(select(GameSession.last_activity_at))
    w.advance(minutes=30)
    body = w.read().json()
    assert [units(r["stock"]) for r in body["resources"]] == [2060, 1550, 780]
    assert [units(r["rate_per_hour"]) for r in body["resources"]] == [120, 100, 60]
    assert [r["infrastructure_type"] for r in body["infrastructures"]] == [
        "extraction_complex",
        "flux_reactor",
        "data_node",
        "industrial_complex",
    ]
    assert body["sectors"] == {
        "capacity": 12,
        "built": 4,
        "reserved": 0,
        "free": 8,
        "free_indices": [5, 6, 7, 8, 9, 10, 11, 12],
    }
    assert body["ruleset_version"] == "v0.1" and body["permissions"] == ALL
    build = next(
        o
        for o in body["options"]
        if o["action"] == "build" and o["infrastructure_type"] == "data_node"
    )
    assert build["sector_index"] == 5 and build["available"]
    assert units(build["cost"]["alloys"]) == 250 and build["base_duration_us"] == str(120 * 10**6)
    # Industrial I gives +10 %: 120 s / 1.10, rounded up to the microsecond, as the 5A service.
    assert build["estimated_duration_us"] == str(-(-120 * 10**6 * 10000 // 11000))
    unique = [o for o in body["options"] if o["infrastructure_type"] == "industrial_complex"]
    assert {(o["action"], o["sector_index"], o["reason"]) for o in unique} == {
        ("build", 5, "unique_limit"),
        ("upgrade", 4, None),
    }
    with w.game.factory() as session:
        assert session.scalar(select(GameSession.last_activity_at)) == before


def test_listing_only_returns_bound_empires(world):
    w = world()
    other = world(universe=w.universe)
    listed = w.client.get(w.root, headers={"X-Game-Request": "bootstrap"}).json()["colonies"]
    assert [c["id"] for c in listed] == [str(w.colony)]
    assert other.colony != w.colony


@pytest.mark.parametrize("case", ["other_empire", "other_universe", "unknown", "no_read"])
def test_refusals_never_leak_existence(world, case):
    w = world(permissions=["colony.construct"] if case == "no_read" else ALL)
    if case == "other_empire":
        target = world(universe=w.universe).colony
    elif case == "other_universe":
        target = world().colony
    elif case == "unknown":
        target = uuid4()
    else:
        target = w.colony
    response = w.read(target)
    assert response.status_code == 404
    assert response.json()["error"] == {"code": "colony_not_found"}


def test_session_cookie_is_required_and_scoped_to_its_universe(world):
    w, other = world(), world()
    anonymous = TestClient(w.app, base_url=w.game.settings.game_public_origin)
    assert w.read(client=anonymous).status_code == 401
    foreign = TestClient(w.app, base_url=w.game.settings.game_public_origin)
    foreign.cookies.set(cookie_name(w.universe), other.raw)
    assert w.read(client=foreign).status_code == 401
    assert w.client.get(w.root + f"/{w.colony}").status_code == 403  # bootstrap header missing


def test_read_without_construct_and_construct_without_cancel(world):
    reader = world(permissions=["colony.read"])
    refused = reader.build()
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "permission_denied"
    assert reader.stock("alloys") == 2000 * MICRO_UNITS
    projection = reader.read().json()
    assert {o["reason"] for o in projection["options"] if o["action"] == "build"} >= {
        "permission_denied"
    }
    builder = world(permissions=["colony.read", "colony.construct"])
    order = builder.build().json()["order"]["id"]
    refused = builder.cancel(order)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "permission_denied"
    queue = builder.read().json()["queue"]
    assert queue[0]["cancel"] == {
        "available": False,
        "reason": "permission_denied",
        "refund": queue[0]["cancel"]["refund"],
        "also_cancels": [],
    }


def test_construction_reserves_once_counts_activity_and_replays_by_key(world):
    w = world()
    w.advance(minutes=10)
    key = uuid4().hex
    first = w.build(key=key)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["order"]["status"] == "active"
    assert units(body["colony"]["resources"][0]["stock"]) == 2000 + 20 - 250
    with w.game.factory() as session:
        assert session.scalar(select(GameSession.last_activity_at)) == w.game.clock()
    replay = w.build(key=key)
    assert replay.json()["order"] == body["order"]
    assert units(w.read().json()["resources"][0]["stock"]) == 2000 + 20 - 250
    conflict = w.build(key=key, kind="data_node")
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
    )
    with w.game.factory() as session:
        assert session.scalar(select(func.count()).select_from(ConstructionOrder)) == 1


def test_idempotency_keys_are_namespaced_per_membership(world):
    w = world()
    other = world(universe=w.universe)
    key = uuid4().hex
    assert w.build(key=key).status_code == 200
    # Same client key on another participant's own colony is an independent command.
    response = other.client.post(
        f"{other.root}/{other.colony}/construction-orders",
        json={
            "idempotency_key": key,
            "infrastructure_type": "data_node",
            "sector_index": 5,
            "target_level": 1,
        },
        headers=other.headers(),
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "mutation",
    ["origin", "csrf", "content_type", "extra_field", "boolean_level", "query", "short_key"],
)
def test_command_envelope_is_strict_and_refused_before_effects(world, mutation):
    w = world()
    url = f"{w.root}/{w.colony}/construction-orders"
    payload = {
        "idempotency_key": uuid4().hex,
        "infrastructure_type": "extraction_complex",
        "sector_index": 5,
        "target_level": 1,
    }
    headers = w.headers()
    if mutation == "origin":
        headers["Origin"] = "https://attacker.example"
    elif mutation == "csrf":
        headers["X-CSRF-Token"] = "0" * 64
    elif mutation == "extra_field":
        payload["cost"] = 0
    elif mutation == "boolean_level":
        payload["target_level"] = True
    elif mutation == "query":
        url += "?debug=1"
    elif mutation == "short_key":
        payload["idempotency_key"] = "x"
    if mutation == "content_type":
        response = w.client.post(url, content="{}", headers=headers)
    else:
        response = w.client.post(url, json=payload, headers=headers)
    assert response.status_code in (403, 415, 422)
    assert w.stock("alloys") == 2000 * MICRO_UNITS


def test_refusals_queue_resources_and_sectors(world):
    w = world()
    for sector in (5, 6, 7):
        assert w.build(sector=sector).status_code == 200
    full = w.build(sector=8)
    assert full.status_code == 409 and full.json()["error"]["code"] == "queue_full"
    poor = world()
    skipped = poor.build(kind="extraction_complex", sector=1, level=3)
    assert skipped.status_code == 409 and skipped.json()["error"]["code"] == "sector_unavailable"
    with poor.game.factory.begin() as session:
        session.get(ResourceBalance, (poor.colony, "alloys")).stock = 100 * MICRO_UNITS
    broke = poor.build(sector=5)
    assert broke.status_code == 409 and broke.json()["error"]["code"] == "insufficient_resources"
    assert poor.stock("alloys") == 100 * MICRO_UNITS
    occupied = poor.build(kind="data_node", sector=1)
    assert occupied.status_code == 409 and occupied.json()["error"]["code"] == "sector_unavailable"
    unique = poor.build(kind="industrial_complex", sector=5)
    assert unique.json()["error"]["code"] == "unique_limit"
    unknown = poor.build(kind="population_center")
    assert unknown.status_code == 422


def test_worker_completion_updates_level_rate_and_allows_next_action(world):
    w = world()
    order = w.build(kind="extraction_complex", sector=1, level=2).json()["order"]
    projection = w.read().json()
    active = projection["queue"][0]
    assert active["id"] == order["id"] and active["due_at"]
    w.advance(minutes=20)
    engine = TimeEngine(w.game.factory, Clock(w.game))
    while engine.process_next():
        pass
    after = w.read().json()
    assert after["queue"] == []
    assert after["infrastructures"][0]["level"] == 2
    assert units(after["resources"][0]["rate_per_hour"]) == 210
    following = w.build(kind="data_node", sector=5)
    assert following.status_code == 200 and following.json()["order"]["status"] == "active"


def test_read_catches_up_without_worker_and_applies_new_rate_at_deadline(world):
    w = world()
    w.build(kind="extraction_complex", sector=1, level=2)
    w.advance(hours=1)
    body = w.read().json()
    assert body["infrastructures"][0]["level"] == 2
    assert units(body["resources"][0]["rate_per_hour"]) == 210


def test_cancel_refunds_queued_full_active_eighty_and_is_idempotent(world):
    w = world()
    active = w.build(sector=5).json()["order"]["id"]
    queued = w.build(sector=6).json()["order"]["id"]
    assert w.stock("alloys") == (2000 - 500) * MICRO_UNITS
    q = w.cancel(queued)
    assert q.status_code == 200 and units(q.json()["order"]["refunded"]["alloys"]) == 250
    a = w.cancel(active)
    assert units(a.json()["order"]["refunded"]["alloys"]) == 200
    assert w.stock("alloys") == (2000 - 50) * MICRO_UNITS
    again = w.cancel(active)
    assert again.status_code == 200 and again.json()["order"]["status"] == "cancelled"
    assert w.stock("alloys") == (2000 - 50) * MICRO_UNITS
    assert w.cancel(uuid4()).json()["error"]["code"] == "order_not_found"


def test_cancel_refund_overflow_is_refused_atomically_q39(world):
    w = world()
    order = w.build(sector=5).json()["order"]["id"]
    with w.game.factory.begin() as session:
        balance = session.get(ResourceBalance, (w.colony, "alloys"))
        balance.stock = balance.capacity - MICRO_UNITS
    preview = w.read().json()["queue"][0]["cancel"]
    assert preview["available"] is False and preview["reason"] == "refund_exceeds_capacity"
    refused = w.cancel(order)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "refund_exceeds_capacity"
    assert w.read().json()["queue"][0]["status"] == "active"


def test_completed_order_cannot_be_cancelled(world):
    w = world()
    order = w.build(sector=5).json()["order"]["id"]
    w.advance(minutes=5)
    response = w.cancel(order)
    assert response.status_code == 409 and response.json()["error"]["code"] == "order_completed"


def test_concurrent_double_click_and_last_queue_slot(world):
    w = world()
    service = Colonies(w.app.state)
    key = uuid4().hex

    def submit(args):
        barrier, kind, sector, idempotency = args
        barrier.wait()
        try:
            return service.construct(
                w.raw,
                w.universe,
                w.colony,
                Construction(
                    idempotency_key=idempotency,
                    infrastructure_type=kind,
                    sector_index=sector,
                    target_level=1,
                ),
            )["order"]["id"]
        except (ColonyError, AccessError) as error:
            return getattr(error, "code", "refused")

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        same = list(pool.map(submit, [(barrier, "data_node", 5, key)] * 2))
    assert same[0] == same[1]
    assert w.build(sector=6).status_code == 200
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        race = list(
            pool.map(
                submit,
                [(barrier, "data_node", 7, uuid4().hex), (barrier, "flux_reactor", 8, uuid4().hex)],
            )
        )
    assert sorted(r == "queue_full" for r in race) == [False, True]
    with w.game.factory() as session:
        count = session.scalar(
            select(func.count())
            .select_from(ConstructionOrder)
            .where(ConstructionOrder.colony_id == w.colony)
        )
    assert count == 3


def test_concurrent_cancellation_refunds_once(world):
    w = world()
    order = w.build(sector=5).json()["order"]["id"]
    service = Colonies(w.app.state)
    barrier = Barrier(2)

    def submit(_):
        barrier.wait()
        return service.cancel(w.raw, w.universe, w.colony, order)["order"]["status"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(submit, range(2))) == ["cancelled", "cancelled"]
    assert w.stock("alloys") == (2000 - 50) * MICRO_UNITS


def test_expired_suspended_and_revoked_sessions_refuse_new_commands(world):
    w = world()
    w.advance(hours=2, seconds=1)
    assert w.build().status_code == 401
    assert w.read().status_code == 401
    s = world()
    set_access(
        s.game,
        s.user,
        s.universe,
        s.membership,
        [{"empire_id": str(s.empire), "permissions": ALL}],
        revision=2,
        epoch=2,
        status="suspended",
    )
    assert s.build().status_code == 401
    r = world()
    apply(
        r.game,
        {"kind": "revoke_sessions", "scope": "account", "global_user_id": str(r.user), "epoch": 1},
    )
    assert r.build().status_code == 401
    assert r.stock("alloys") == 2000 * MICRO_UNITS


def test_storage_saturation_before_spend_uses_lazy_settlement(world):
    w = world()
    with w.game.factory.begin() as session:
        session.get(ResourceBalance, (w.colony, "alloys")).stock = 9990 * MICRO_UNITS
    w.advance(hours=1)  # +120/h would exceed 10 000: production is lost at the cap, not hidden.
    body = w.read().json()
    assert units(body["resources"][0]["stock"]) == 10000
    assert w.build(sector=5).status_code == 200
    assert w.stock("alloys") == (10000 - 250) * MICRO_UNITS


def test_concurrent_upgrades_of_the_same_building_accept_one(world):
    w = world()
    service = Colonies(w.app.state)
    barrier = Barrier(2)

    def submit(_):
        barrier.wait()
        command = Construction(
            idempotency_key=uuid4().hex,
            infrastructure_type="extraction_complex",
            sector_index=1,
            target_level=2,
        )
        try:
            return service.construct(w.raw, w.universe, w.colony, command)["order"]["status"]
        except ColonyError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(submit, range(2)))
    assert results == ["active", "sector_unavailable"]
    assert w.stock("alloys") == (2000 - 800) * MICRO_UNITS
