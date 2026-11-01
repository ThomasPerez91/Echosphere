"""Real PostgreSQL + GameSession tests for Colonization (ruleset v0.5): worker-only founding."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_colony_api import Clock, game  # noqa: F401
from test_fleet import (
    FULL,
    built,
    fleets,  # noqa: F401
    garrison,
    order,
    post,
    rebind,
    stocks,
    surveyed,
    view,
    worker,
)
from test_game_sessions import enter

from app.access.http import cookie_name
from app.colony.models import ColonyInfrastructure
from app.fleet import service as fleet_service
from app.fleet.models import Fleet, FleetCargo, FleetMission, FleetReport, FleetStack, ShipOrder
from app.galaxy import service as g
from app.galaxy.models import PlanetKnowledge, SystemKnowledge
from app.persistence.models import Colony, Planet
from app.simulation.models import ResourceBalance, ScheduledEvent
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration
M = 1_000_000
EXPAND = [*FULL, "colony.expand"]
PACKAGE = {"alloys": 600, "flux": 300, "data": 100}


def world(fleets, **kwargs):
    return fleets(**({"permissions": EXPAND, "ruleset": "v0.5"} | kwargs))


def rich(w, colony=None):
    """Test-only stock top-up so several colonizers can be afforded (prices progress)."""
    with w.game.factory.begin() as s:
        for r in ("alloys", "flux", "data"):
            balance = s.get(ResourceBalance, (colony or w.colony, r))
            balance.stock, balance.rate_per_hour = 9_000 * M, 0


def reenter(w):
    """A new GameSession after a long absence (sessions expire after 2 h idle)."""
    raw, _, _ = enter(w.game, (w.user, w.universe, w.membership))
    w.raw = raw
    w.client.cookies.set(cookie_name(w.universe), raw)


def colonizer_garrison(w, package=PACKAGE):
    assert order(w, "colonizer", 1).status_code == 200
    w.advance(hours=3, minutes=1)
    assert worker(w) >= 1
    reenter(w)
    home = garrison(w)
    loaded = post(
        w,
        f"/{home['id']}/load",
        {"idempotency_key": uuid4().hex, "colony_id": str(w.colony), "cargo": package},
    )
    assert loaded.status_code == 200, loaded.json()
    return garrison(w)


def home_system(w):
    return next(s for s in view(w).json()["systems"] if s["state"] == "MONITORED")


def free_planet(system):
    return next(p["id"] for p in system["planets"] if p["colony_id"] is None)


def colonize(w, fleet_id, planet, *, cargo=None, units=None, key=None):
    body = {
        "idempotency_key": key or uuid4().hex,
        "fleet_id": str(fleet_id),
        "kind": "COLONIZE",
        "target_planet_id": str(planet),
        "units": units or {"colonizer": 1},
    }
    if cargo:
        body["cargo"] = cargo
    return post(w, "/missions", body)


def station(w, system, package=PACKAGE):
    """Test-only: a colonizer task fleet placed in `system`, which this Empire then knows."""
    with w.game.factory.begin() as s:
        known = s.get(SystemKnowledge, (w.empire, UUID(system)))
        if known is None or known.state == "DETECTED":
            g.map_system(s, w.universe, w.empire, UUID(system), w.game.clock())
        fleet = Fleet(
            empire_id=w.empire,
            universe_id=w.universe,
            home_colony_id=w.colony,
            kind="TASK",
            status="STATIONED",
            system_id=UUID(system),
            name="Colonisateur de test",
        )
        s.add(fleet)
        s.flush()
        s.add(FleetStack(fleet_id=fleet.id, ship_class="colonizer", count=1))
        for resource, value in package.items():
            s.add(FleetCargo(fleet_id=fleet.id, resource=resource, amount=value * M))
        return fleet.id


def resolve(w, max_attempts=3):
    """Process this Empire's Operations stream only: lets a test choose the worker order."""
    with w.game.factory.begin() as s:
        stream = g.state_for(s, w.universe, w.empire).stream_id
        engine = TimeEngine(w.game.factory, Clock(w.game), max_attempts=max_attempts)
        engine.catch_up_stream(s, stream, w.universe, w.game.clock())


def report(w, mission_id):
    with w.game.factory() as s:
        row = s.get(FleetReport, UUID(mission_id))
        return row.result if row else None


def own_planet(w):
    with w.game.factory() as s:
        return s.get(Colony, w.colony).planet_id


def colony_on(w, planet):
    with w.game.factory() as s:
        return s.scalar(select(Colony).where(Colony.planet_id == UUID(planet)))


def test_local_colonize_founds_a_real_colony_from_the_package_by_worker_only(fleets):
    w = world(fleets)
    home = colonizer_garrison(w)
    system = home_system(w)
    planet = free_planet(system)
    assert w.read().status_code == 200
    before = stocks(w)
    body = colonize(w, home["id"], planet, cargo=PACKAGE).json()
    mission_id, fleet_id = body["result"]["mission_id"], body["result"]["fleet_id"]
    assert stocks(w) == before  # 0 hop: no fuel at all
    with w.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        assert mission.snapshot["path"] == [] and mission.snapshot["travel_us"] == 0
        assert mission.started_at == mission.travel_arrival_at == mission.due_at
        assert s.get(Colony, w.colony).planet_id != UUID(planet)
    # Never founded synchronously, nor by a read: the worker resolves the persisted event.
    assert colony_on(w, planet) is None and view(w).status_code == 200
    assert colony_on(w, planet) is None
    refused = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert refused.json()["error"]["code"] == "recall_too_late"  # no recall window locally
    assert worker(w) == 1
    colony = colony_on(w, planet)
    assert colony.empire_id == w.empire and colony.founding_mission_id == UUID(mission_id)
    with w.game.factory() as s:
        planet_row = s.get(Planet, UUID(planet))
        assert colony.founded_at == s.get(FleetMission, UUID(mission_id)).due_at
        balances = {r: s.get(ResourceBalance, (colony.id, r)) for r in ("alloys", "flux", "data")}
        assert {r: b.stock for r, b in balances.items()} == {r: v * M for r, v in PACKAGE.items()}
        assert all(b.rate_per_hour == 0 and b.capacity == 10_000 * M for b in balances.values())
        infrastructures = select(func.count()).select_from(ColonyInfrastructure)
        assert s.scalar(infrastructures.where(ColonyInfrastructure.colony_id == colony.id)) == 0
        fleet = s.get(Fleet, UUID(fleet_id))
        assert (fleet.status, fleet.system_id, fleet.active_mission_id) == ("SETTLED", None, None)
        assert (
            s.scalar(
                select(func.count()).select_from(FleetStack).where(FleetStack.fleet_id == fleet.id)
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count()).select_from(FleetCargo).where(FleetCargo.fleet_id == fleet.id)
            )
            == 0
        )
    sectors = w.read(colony.id).json()["sectors"]
    assert sectors["capacity"] == planet_row.sector_capacity and sectors["built"] == 0
    assert report(w, mission_id)["outcome"] == "founded"
    listing = w.client.get(f"/game/{w.universe}/colonies", headers={"X-Game-Request": "bootstrap"})
    assert str(colony.id) in [c["id"] for c in listing.json()["colonies"]]
    projection = view(w).json()
    assert fleet_id not in [f["id"] for f in projection["fleets"]]  # SETTLED like MERGED
    owned = next(s for s in projection["systems"] if s["id"] == system["id"])
    assert owned["state"] == "MONITORED"
    assert {p["colony_id"] for p in owned["planets"]} >= {str(w.colony), str(colony.id)}
    assert worker(w) == 0  # replay-safe, nothing else scheduled


def test_remote_colonize_pays_fuel_and_recall_keeps_colonizer_and_whole_cargo(fleets):
    w = world(fleets)
    probe, mapped = surveyed(w)
    home = colonizer_garrison(w, {"alloys": 700, "flux": 250, "data": 50})
    target = next(
        p["id"] for s in view(w).json()["systems"] if s["id"] == mapped for p in s["planets"]
    )
    assert w.read().status_code == 200
    flux = stocks(w)["flux"]
    cargo = {"alloys": 700, "flux": 250, "data": 50}
    body = colonize(w, home["id"], target, cargo=cargo).json()
    mission_id, fleet_id = body["result"]["mission_id"], body["result"]["fleet_id"]
    assert flux - stocks(w)["flux"] == 20 * M  # one hop
    with w.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        assert mission.travel_arrival_at - mission.started_at == timedelta(minutes=30)
        assert mission.due_at == mission.travel_arrival_at  # no establishment phase
    w.advance(minutes=10)
    key = uuid4().hex
    first = post(w, f"/missions/{mission_id}/recall", {"idempotency_key": key})
    assert first.status_code == 200
    assert (
        post(w, f"/missions/{mission_id}/recall", {"idempotency_key": key}).json()["result"]
        == first.json()["result"]
    )
    w.advance(minutes=11)
    assert worker(w) == 1
    back = next(f for f in view(w).json()["fleets"] if f["id"] == fleet_id)
    assert back["stacks"] == {"colonizer": 1} and back["status"] == "STATIONED"
    assert back["cargo"] == {"alloys": str(700 * M), "flux": str(250 * M), "data": str(50 * M)}
    assert colony_on(w, target) is None


def test_colonizer_price_progresses_with_n_and_cancellation_uses_the_accepted_price(fleets):
    w = world(fleets)
    rich(w)
    quote = view(w).json()["colonization"]["colonizer_quote"]
    assert (quote["rank"], quote["multiplier_bps"]) == (1, 10000)
    assert quote["cost"] == {"alloys": str(1200 * M), "flux": str(600 * M), "data": str(300 * M)}
    first = order(w, "colonizer", 1).json()["result"]["order_id"]
    second = order(w, "colonizer", 1).json()["result"]["order_id"]
    assert order(w, "colonizer", 2).json()["error"]["code"] == "invalid_request"
    with w.game.factory() as s:
        snaps = [s.get(ShipOrder, UUID(o)).snapshot for o in (first, second)]
    assert [(x["colonizer_rank"], x["multiplier_bps"]) for x in snaps] == [(1, 10000), (2, 15000)]
    assert snaps[1]["cost"]["alloys"] == 1800 * M
    assert view(w).json()["colonization"]["colonizer_quote"]["rank"] == 3
    flux = stocks(w)["flux"]
    cancelled = post(w, f"/orders/{second}/cancel", {"idempotency_key": uuid4().hex})
    assert cancelled.json()["result"]["refunded"]["flux"] == str(900 * M)  # queued: 100 % of 900
    assert stocks(w)["flux"] - flux == 900 * M
    assert view(w).json()["colonization"]["colonizer_quote"]["rank"] == 2


def test_concurrent_colonizer_orders_of_two_colonies_get_successive_ranks(fleets):
    w = world(fleets)
    home = colonizer_garrison(w)
    colonize(w, home["id"], free_planet(home_system(w)), cargo=PACKAGE)
    assert worker(w) == 1
    second = next(c for c in view(w).json()["colonies"] if c["id"] != str(w.colony))["id"]
    rich(w)
    rich(w, UUID(second))
    barrier = Barrier(2)

    def place(colony):
        barrier.wait()
        body = {"idempotency_key": uuid4().hex, "colony_id": colony, "ship_class": "colonizer"}
        return post(w, "/orders", body | {"quantity": 1})

    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(place, [str(w.colony), second]))
    assert all(r.status_code == 200 for r in replies), [r.json() for r in replies]
    with w.game.factory() as s:
        ranks = sorted(
            s.get(ShipOrder, UUID(r.json()["result"]["order_id"])).snapshot["colonizer_rank"]
            for r in replies
        )
    # Founding consumed the first colonizer: N = 2 colonies, then the two orders 2 and 3.
    assert ranks == [2, 3]


def test_launch_refusals_follow_knowledge_rights_limits_and_package(fleets):
    w = world(fleets)
    home = colonizer_garrison(w, {"alloys": 400, "flux": 300, "data": 100})
    system = home_system(w)
    planet = free_planet(system)
    low = colonize(w, home["id"], planet, cargo={"alloys": 400, "flux": 300, "data": 100})
    assert low.json()["error"]["code"] == "package_insufficient"
    mine = colonize(w, home["id"], str(own_planet(w)), cargo={"alloys": 400})
    assert mine.json()["error"]["code"] == "target_owned"
    unknown = colonize(w, home["id"], uuid4(), cargo={"alloys": 400})
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "planet_not_found"
    detected = next(s["id"] for s in view(w).json()["systems"] if s["state"] == "DETECTED")
    with w.game.factory() as s:
        hidden = s.scalar(select(Planet.id).where(Planet.system_id == UUID(detected)).limit(1))
    assert colonize(w, home["id"], hidden).json()["error"]["code"] == "planet_not_found"
    mixed = colonize(w, home["id"], planet, units={"colonizer": 1, "probe": 1})
    assert mixed.json()["error"]["code"] in ("units_unavailable", "colonize_units")
    rebind(w, ["fleet.read", "fleet.command", "galaxy.read"])
    assert colonize(w, home["id"], planet).status_code == 403  # colony.expand is required
    rebind(w, ["fleet.read", "fleet.command", "galaxy.read", "colony.expand"], revision=3)
    # Without colony.read the own colony is not revealed by a specific code.
    hidden_own = colonize(w, home["id"], str(own_planet(w)), cargo={"alloys": 400})
    assert hidden_own.json()["error"]["code"] == "target_unavailable"


def test_one_active_colonize_per_empire_and_v04_has_no_colonization(fleets):
    w = world(fleets)
    probe, mapped = surveyed(w)
    system = home_system(w)
    remote, local = station(w, mapped), station(w, system["id"])
    planets = [p["id"] for p in system["planets"] if p["colony_id"] is None]
    assert colonize(w, remote, planets[0]).status_code == 200  # 30 min in flight: active
    busy = colonize(w, local, planets[-1])
    assert busy.json()["error"]["code"] == "colonization_active"
    old = fleets(permissions=EXPAND)  # v0.4: Fleets and SURVEY, never colonization
    probes = built(old)
    with old.game.factory() as s:
        planet = s.scalar(
            select(PlanetKnowledge.planet_id)
            .where(PlanetKnowledge.empire_id == old.empire)
            .limit(1)
        )
    gone = colonize(old, probes["id"], planet, units={"probe": 1})
    assert gone.json()["error"]["code"] == "colonization_unavailable"


def rivals(fleets):
    """Two Empires of one Universe, both with a colonizer in A's home system (B test-placed)."""
    a = world(fleets)
    b = world(fleets, universe=a.universe, other=True)
    system = home_system(a)
    planet = free_planet(system)
    return a, b, station(a, system["id"]), station(b, system["id"]), planet


@pytest.mark.parametrize("first", ["better", "worse"])
def test_earlier_arrival_wins_whatever_the_worker_order(fleets, first):
    a, b, fa, fb, planet = rivals(fleets)
    better = colonize(a, fa, planet).json()["result"]["mission_id"]
    a.advance(minutes=1)
    worse = colonize(b, fb, planet).json()["result"]["mission_id"]
    for w in (a, b) if first == "better" else (b, a):
        resolve(w)
    assert colony_on(a, planet).empire_id == a.empire
    assert report(a, better)["outcome"] == "founded"
    assert report(b, worse) == {
        "kind": "COLONIZE",
        "destination_id": home_system(a)["id"],
        "planet_id": planet,
        "outcome": "failed",
        "reason": "target_unavailable",
    }
    loser = next(f for f in view(b).json()["fleets"] if f["id"] == str(fb))
    assert loser["status"] == "STATIONED" and loser["stacks"] == {"colonizer": 1}
    assert loser["cargo"]["alloys"] == str(PACKAGE["alloys"] * M)  # package kept aboard
    assert "empire" not in str(report(b, worse)).lower()


@pytest.mark.parametrize("first", ["winner", "loser"])
def test_same_due_at_tie_break_is_the_persisted_rank_not_the_worker(fleets, first):
    a, b, fa, fb, planet = rivals(fleets)
    ma = colonize(a, fa, planet).json()["result"]["mission_id"]
    mb = colonize(b, fb, planet).json()["result"]["mission_id"]  # same frozen instant
    with a.game.factory() as s:
        rows = [s.get(FleetMission, UUID(m)) for m in (ma, mb)]
        assert rows[0].due_at == rows[1].due_at and rows[0].started_at == rows[1].started_at
    winner, loser = (a, b) if UUID(ma) < UUID(mb) else (b, a)
    for w in (winner, loser) if first == "winner" else (loser, winner):
        resolve(w)
    assert colony_on(a, planet).empire_id == winner.empire
    with a.game.factory() as s:
        count = select(func.count()).select_from(Colony).where(Colony.planet_id == UUID(planet))
        assert s.scalar(count) == 1


def test_blocked_better_rank_keeps_blocking_and_completed_ones_never_do(fleets):
    a, b, fa, fb, planet = rivals(fleets)
    better = colonize(a, fa, planet).json()["result"]["mission_id"]
    a.advance(minutes=1)
    worse = colonize(b, fb, planet).json()["result"]["mission_id"]
    with a.game.factory.begin() as s:
        mission = s.get(FleetMission, UUID(better))
        mission.snapshot = mission.snapshot | {"travel_us": 1}  # operator incident: blocked
    resolve(a, max_attempts=1)
    with a.game.factory() as s:
        assert s.get(FleetMission, UUID(better)).status == "active"
    resolve(b)
    assert report(b, worse)["reason"] == "target_unavailable" and colony_on(a, planet) is None
    # A historical better-ranked attempt that is completed never blocks a new one.
    c = station(b, home_system(a)["id"])
    with a.game.factory.begin() as s:
        mission = s.get(FleetMission, UUID(better))
        mission.status, mission.completed_at = "completed", mission.due_at
        fleet = s.get(Fleet, mission.fleet_id)
        fleet.status, fleet.active_mission_id, fleet.system_id = (
            "STATIONED",
            None,
            mission.origin_id,
        )
    b.advance(minutes=1)
    retry = colonize(b, c, planet).json()["result"]["mission_id"]
    resolve(b)
    assert report(b, retry)["outcome"] == "founded"
    assert colony_on(a, planet).empire_id == b.empire


def test_a_recalled_better_claim_no_longer_blocks(fleets):
    a, b, fa, fb, planet = rivals(fleets)
    probe, mapped = surveyed(a)
    remote = station(a, mapped)
    target_system = home_system(a)["id"]
    a.advance(seconds=1)
    better = colonize(a, remote, planet).json()["result"]["mission_id"]  # due in 30 min
    with a.game.factory() as s:
        assert s.get(FleetMission, UUID(better)).destination_id == UUID(target_system)
    a.advance(minutes=5)
    assert (
        post(a, f"/missions/{better}/recall", {"idempotency_key": uuid4().hex}).status_code == 200
    )
    a.advance(minutes=30)  # the recalled claim's old rank (due 30 min) beats B's now
    worse = colonize(b, fb, planet).json()["result"]["mission_id"]
    resolve(b)
    assert report(b, worse)["outcome"] == "founded"


def test_recall_racing_the_arrival_is_serialized_and_never_founds_twice(fleets):
    w = world(fleets)
    probe, mapped = surveyed(w)
    home = colonizer_garrison(w)
    target = next(
        p["id"] for s in view(w).json()["systems"] if s["id"] == mapped for p in s["planets"]
    )
    mission_id = colonize(w, home["id"], target, cargo=PACKAGE).json()["result"]["mission_id"]
    w.advance(minutes=30)  # exactly travel_arrival_at: the arrival is now irrevocable
    barrier = Barrier(2)

    def recall(_):
        barrier.wait()
        return post(w, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})

    def arrive(_):
        barrier.wait()
        return TimeEngine(w.game.factory, Clock(w.game)).process_next()

    with ThreadPoolExecutor(2) as pool:
        refused, processed = pool.submit(recall, 0), pool.submit(arrive, 0)
        refused, processed = refused.result(), processed.result()
    if processed is None:  # the recall held the stream (its catch-up rolled back): worker next
        assert worker(w) == 1
    assert refused.json()["error"]["code"] == "recall_too_late"
    with w.game.factory() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(FleetReport)
                .where(FleetReport.mission_id == UUID(mission_id))
            )
            == 1
        )
        events = s.scalars(
            select(ScheduledEvent).where(ScheduledEvent.idempotency_key.like(f"%{mission_id}"))
        ).all()
        assert [(e.event_type, e.error_code) for e in events] == [("FLEET_ARRIVAL", None)]
        colonizers = s.scalar(
            select(func.coalesce(func.sum(FleetStack.count), 0))
            .join(Fleet, Fleet.id == FleetStack.fleet_id)
            .where(Fleet.empire_id == w.empire, FleetStack.ship_class == "colonizer")
        )
    assert colony_on(w, target) is not None and colonizers == 0


def test_database_refuses_double_owner_and_misused_colonize_shapes(fleets):
    w = world(fleets)
    planet = free_planet(home_system(w))
    with pytest.raises(IntegrityError):
        with w.game.factory.begin() as s:
            s.add(Colony(universe_id=w.universe, empire_id=w.empire, planet_id=own_planet(w)))
    fleet = station(w, home_system(w)["id"])
    mission = colonize(w, fleet, planet).json()["result"]["mission_id"]
    with w.game.factory() as s:
        row = s.get(FleetMission, UUID(mission))
        values = {c.key: getattr(row, c.key) for c in row.__mapper__.column_attrs}
    for change in (
        {"kind": "DEPLOY", "target_planet_id": None},  # 0 hop stays COLONIZE-only
        {"target_planet_id": None},
        {"status": "completed", "completed_at": values["due_at"], "kind": "DEPLOY"},
    ):
        with pytest.raises(IntegrityError):
            with w.game.factory.begin() as s:
                s.add(
                    FleetMission(
                        **(
                            values
                            | change
                            | {
                                "id": uuid4(),
                                "idempotency_key": uuid4().hex,
                                "status": "completed",
                                "completed_at": values["due_at"],
                            }
                        )
                    )
                )
    other = station(w, home_system(w)["id"])
    with pytest.raises(IntegrityError):  # one active COLONIZE per Empire, even a raw insert
        with w.game.factory.begin() as s:
            s.add(
                FleetMission(
                    **(values | {"id": uuid4(), "idempotency_key": uuid4().hex, "fleet_id": other})
                )
            )


@pytest.mark.parametrize("field", ["target_planet_id", "rank", "package"])
def test_worker_refuses_a_drifted_colonize_without_partial_effect(fleets, field):
    w = world(fleets)
    system = home_system(w)
    planets = [p["id"] for p in system["planets"] if p["colony_id"] is None]
    fleet = station(w, system["id"])
    mission_id = colonize(w, fleet, planets[0]).json()["result"]["mission_id"]
    with w.game.factory.begin() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        if field == "target_planet_id":
            mission.snapshot = mission.snapshot | {"target_planet_id": str(uuid4())}
        elif field == "rank":
            rank = mission.snapshot["rank"] | {"mission_id": str(uuid4())}
            mission.snapshot = mission.snapshot | {"rank": rank}
        else:
            s.get(FleetCargo, (fleet, "alloys")).amount = M  # below the accepted minimum
    blocked = TimeEngine(w.game.factory, Clock(w.game), max_attempts=1).process_next()
    assert blocked.status == "blocked"
    assert colony_on(w, planets[0]) is None and report(w, mission_id) is None
    with w.game.factory() as s:
        assert s.get(Fleet, fleet).status == "MOVING"


def test_without_colony_read_reports_and_planets_never_name_colonies(fleets):
    w = world(fleets)
    home = colonizer_garrison(w)
    mission = colonize(w, home["id"], free_planet(home_system(w)), cargo=PACKAGE)
    assert worker(w) == 1
    mission_id = mission.json()["result"]["mission_id"]
    rebind(w, ["fleet.read", "galaxy.read"])
    projection = view(w).json()
    row = next(m for m in projection["missions"] if m["id"] == mission_id)
    assert row["report"]["result"]["outcome"] == "founded"
    assert row["report"]["result"]["colony_id"] is None
    assert all(p["colony_id"] is None for s in projection["systems"] for p in s.get("planets", []))
    assert projection["colonization"]["colonizer_quote"] is None
    assert str(w.colony) not in str(projection)
    assert fleet_service  # module imported for direct service checks elsewhere
