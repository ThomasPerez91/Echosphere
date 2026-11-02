"""Real PostgreSQL + GameSession tests for Combat MVP (ruleset v0.7): worker-only resolution."""

# ruff: noqa: F811
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from test_colony_api import Clock, game  # noqa: F401
from test_fleet import (  # noqa: F401
    FULL,
    fleets,
    garrison,
    order,
    post,
    rebind,
    stocks,
    view,
    worker,
)

from app.colony.models import ColonyInfrastructure
from app.combat.models import CombatEngagement, CombatReport
from app.combat.orchestrator import CombatOrchestrator
from app.combat.resolver import resolve
from app.fleet import service as fleet_service
from app.fleet.models import Fleet, FleetCargo, FleetMission, FleetReport, FleetStack, ShipOrder
from app.galaxy import service as g
from app.galaxy.models import PlanetKnowledge, SystemKnowledge
from app.persistence.models import Colony, Planet, StellarSystem
from app.research.models import AcquiredTechnology
from app.simulation.models import ResourceBalance, ScheduledEvent, StreamFence

pytestmark = pytest.mark.integration
M = 1_000_000
COMBAT = [*FULL, "colony.expand", "combat.read", "combat.attack"]
DAY = timedelta(hours=24)


def reenter(w):
    """After a day-long wait the access window lapsed: a new binding revision and session."""
    w.revision = getattr(w, "revision", 1) + 1
    rebind(w, COMBAT, revision=w.revision)


def world(fleets, **kwargs):
    return fleets(**({"permissions": COMBAT, "ruleset": "v0.7"} | kwargs))


def rivals(fleets, **kwargs):
    """Attacker A and defender B in one v0.7 Universe; A knows the whole map (test-only)."""
    a = world(fleets, **kwargs)
    b = world(fleets, universe=a.universe, other=True, **kwargs)
    with a.game.factory.begin() as s:
        for system in s.scalars(
            select(StellarSystem.id).where(StellarSystem.universe_id == a.universe)
        ):
            g.map_system(s, a.universe, a.empire, system, a.game.clock())
        for w in (a, b):  # test-only funds; every spending still goes through the services
            for r in ("alloys", "flux", "data"):
                s.get(ResourceBalance, (w.colony, r)).stock = 9_000 * M
    return a, b


def planet_of(w):
    with w.game.factory() as s:
        planet = s.get(Planet, s.get(Colony, w.colony).planet_id)
        return planet.id, planet.system_id


def arm(w, units, system=None, kind="TASK", cargo=None):
    """Test-only military placement: a stationed task fleet, or units added to the garrison."""
    with w.game.factory.begin() as s:
        colony = s.get(Colony, w.colony)
        if kind == "GARRISON":
            fleet = fleet_service.garrison_for(s, colony)
            fleet_service.add_units(s, fleet.id, units)
            return fleet.id
        fleet = Fleet(
            empire_id=w.empire,
            universe_id=w.universe,
            home_colony_id=w.colony,
            kind="TASK",
            status="STATIONED",
            system_id=system or fleet_service.colony_system(s, colony),
            name="Escadre de test",
        )
        s.add(fleet)
        s.flush()
        for ship, count in units.items():
            s.add(FleetStack(fleet_id=fleet.id, ship_class=ship, count=count))
        for resource, value in (cargo or {}).items():
            s.add(FleetCargo(fleet_id=fleet.id, resource=resource, amount=value * M))
        return fleet.id


def attack(w, fleet, planet, units, key=None, **extra):
    body = {
        "idempotency_key": key or uuid4().hex,
        "fleet_id": str(fleet),
        "kind": "ATTACK",
        "target_planet_id": str(planet),
        "units": units,
    } | extra
    return post(w, "/missions", body)


def preview(w, fleet, planet, units):
    body = {"fleet_id": str(fleet), "kind": "ATTACK", "target_planet_id": str(planet)}
    return post(w, "/missions/preview", body | {"units": units})


def resolve_due(w, engagement_id=None, **kwargs):
    runner = CombatOrchestrator(w.game.factory, Clock(w.game), **kwargs)
    return runner.process_next(engagement_id=engagement_id)


def engagement_of(w, mission_id):
    with w.game.factory() as s:
        return s.scalar(
            select(CombatEngagement).where(CombatEngagement.mission_id == UUID(mission_id))
        )


def stacks(w, fleet_id):
    with w.game.factory() as s:
        return fleet_service.stacks_of(s, UUID(str(fleet_id)))


def fleet_row(w, fleet_id):
    with w.game.factory() as s:
        return s.get(Fleet, UUID(str(fleet_id)))


def launched(w, response):
    assert response.status_code == 200, response.json()
    return response.json()["result"]["mission_id"], response.json()["result"]["fleet_id"]


def until_battle(w, mission_id, extra=timedelta(minutes=1)):
    with w.game.factory() as s:
        due = s.get(FleetMission, UUID(mission_id)).due_at
    w.game.test_clock[0] = due + extra


def colony_state(w):
    """Everything Combat must never touch on a Colony: stocks, buildings, Research."""
    with w.game.factory() as s:
        return (
            sorted(
                (b.resource, b.stock, b.rate_per_hour)
                for b in s.scalars(
                    select(ResourceBalance).where(ResourceBalance.colony_id == w.colony)
                )
            ),
            sorted(
                (i.sector_index, i.infrastructure_type, i.level)
                for i in s.scalars(
                    select(ColonyInfrastructure).where(ColonyInfrastructure.colony_id == w.colony)
                )
            ),
            sorted(
                t.technology_id
                for t in s.scalars(
                    select(AcquiredTechnology).where(AcquiredTechnology.empire_id == w.empire)
                )
            ),
        )


def test_distant_attack_waits_24h_pays_round_trip_and_resolves_by_worker_only(fleets):
    a, b = rivals(fleets)
    planet, system = planet_of(b)
    strike = arm(a, {"frigate": 4})
    arm(b, {"interceptor": 3}, kind="GARRISON")
    before = stocks(a)
    quote = preview(a, strike, planet, {"frigate": 4}).json()
    assert quote["hops"] >= 1 and quote["battle_at"] == quote["due_at"]
    mission_id, fleet_id = launched(a, attack(a, strike, planet, {"frigate": 4}))
    with a.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        one_way = 12 * quote["hops"] * 4 * M
        assert stocks(a)["flux"] == before["flux"] - 2 * one_way  # round trip, paid once
        assert mission.due_at == mission.started_at + DAY > mission.travel_arrival_at
        assert mission.snapshot["battle_at"] == mission.due_at.isoformat()
        # No arrival event: the Combat orchestrator alone resolves the engagement.
        assert not s.scalar(
            select(func.count()).where(
                ScheduledEvent.idempotency_key == f"fleet-arrival:{mission_id}"
            )
        )
        engagement = s.scalar(
            select(CombatEngagement).where(CombatEngagement.mission_id == mission.id)
        )
        assert engagement.defender_empire_id == b.empire and engagement.state == "pending"
        fences = s.scalars(
            select(StreamFence).where(StreamFence.owner == f"combat:{engagement.id}")
        )
        assert {f.fence_at for f in fences} == {mission.due_at}
    # Attacker sees its battle instant, never the defender.
    own = next(m for m in view(a).json()["missions"] if m["id"] == mission_id)
    assert own["attack"]["state"] == "pending" and str(b.empire) not in str(view(a).json())
    # Defender: a dated alert on its planet, nothing about the attacker.
    alert = view(b).json()["combat"]["alerts"][0]
    assert alert == {
        "id": str(engagement.id),
        "planet_id": str(planet),
        "system_id": str(system),
        "battle_at": mission.due_at.isoformat(),
        "state": "pending",
    }
    assert str(a.empire) not in str(view(b).json()) and str(fleet_id) not in str(alert)
    assert b.read().json()["incoming"] == [
        {"id": str(engagement.id), "battle_at": mission.due_at.isoformat(), "state": "pending"}
    ]
    defender_colony = colony_state(b)
    until_battle(a, mission_id)
    assert worker(a) == 0 and resolve_due(a) is not None
    reenter(a), reenter(b)
    engagement = engagement_of(a, mission_id)
    assert engagement.state == "resolved" and engagement.result["outcome"] == "attacker_win"
    # Deterministic replay from the stored snapshot.
    assert resolve(engagement.snapshot["spec"]) == engagement.result["combat"]
    assert colony_state(b) == defender_colony  # no loot, no building, no Research touched
    attacker_report = next(r for r in view(a).json()["combat"]["reports"])
    assert attacker_report["opponent_empire_id"] == str(b.empire)
    assert attacker_report["opponent"]["initial"]["interceptor"] == 3
    assert set(attacker_report) >= {"own", "opponent", "rounds", "outcome", "battle_at"}
    assert "stock" not in str(attacker_report) and "cargo" not in str(attacker_report)
    assert view(b).json()["combat"]["reports"][0]["opponent_empire_id"] == str(a.empire)
    assert view(b).json()["combat"]["alerts"] == []
    assert garrison(b)["stacks"] == {} and garrison(b)["status"] == "STATIONED"
    with a.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        assert mission.status == "returning"
        assert mission.return_at == mission.due_at + (
            mission.travel_arrival_at - mission.started_at
        )
    a.game.test_clock[0] = mission.return_at
    assert worker(a) == 1
    back = fleet_row(a, fleet_id)
    assert back.status == "STATIONED" and back.system_id == UUID(own["origin"]["id"])
    with a.game.factory() as s:
        assert s.get(FleetReport, UUID(mission_id)).result["outcome"] == "attacker_win"
    assert resolve_due(a) is None  # never fought twice


def test_local_attack_is_zero_hop_free_waits_24h_and_recalls_or_stations_at_once(fleets):
    a, b = rivals(fleets)
    planet, system = planet_of(b)
    strike = arm(a, {"interceptor": 5}, system=system)
    first = arm(a, {"interceptor": 2}, system=system)
    before = stocks(a)
    mission_id, _ = launched(a, attack(a, first, planet, {"interceptor": 2}))
    with a.game.factory() as s:
        m = s.get(FleetMission, UUID(mission_id))
        assert m.snapshot["path"] == [] and m.travel_arrival_at == m.started_at
        assert m.due_at == m.started_at + DAY and stocks(a) == before
    a.advance(hours=2)
    reenter(a), reenter(b)
    recalled = post(a, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert recalled.status_code == 200
    row = fleet_row(a, first)
    assert row.status == "STATIONED" and row.system_id == system  # no artificial return
    assert engagement_of(a, mission_id).state == "cancelled"
    assert view(b).json()["combat"]["alerts"][0]["state"] == "cancelled"
    mission_id, _ = launched(a, attack(a, strike, planet, {"interceptor": 5}))
    until_battle(a, mission_id)
    assert resolve_due(a)["outcome"] == "unopposed"
    row = fleet_row(a, strike)
    assert row.status == "STATIONED" and row.system_id == system  # stationed at once
    with a.game.factory() as s:
        assert s.get(FleetMission, UUID(mission_id)).status == "completed"


@pytest.mark.parametrize(
    "units,cargo,code",
    [
        ({"probe": 1}, None, "attack_units"),
        ({"interceptor": 1, "freighter": 1}, None, "attack_units"),
        ({"interceptor": 1}, {"alloys": 10}, "attack_cargo"),
    ],
)
def test_civilians_and_cargo_never_attack(fleets, units, cargo, code):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    source = arm(a, {"interceptor": 1, "probe": 1, "freighter": 1}, cargo={"alloys": 50})
    response = attack(a, source, planet, units, **({"cargo": cargo} if cargo else {}))
    assert response.json()["error"]["code"] == code


def test_unknown_own_and_unavailable_targets_and_explicit_rights(fleets):
    a, b = rivals(fleets)
    source = arm(a, {"interceptor": 2})
    own, _ = planet_of(a)
    assert attack(a, source, own, {"interceptor": 1}).json()["error"]["code"] == "target_owned"
    with a.game.factory() as s:
        unknown = s.scalar(
            select(Planet.id)
            .where(Planet.universe_id == a.universe)
            .where(~Planet.id.in_(select(PlanetKnowledge.planet_id)))
            .limit(1)
        )
    if unknown is not None:
        code = attack(a, source, unknown, {"interceptor": 1}).json()["error"]["code"]
        assert code == "planet_not_found"
    planet, _ = planet_of(b)
    rebind(a, [*FULL, "combat.read"], revision=5)  # no combat.attack: never implied
    denied = attack(a, source, planet, {"interceptor": 1})
    assert denied.status_code == 403
    rebind(a, [*FULL, "combat.attack"], revision=6)  # nor without combat.read
    assert attack(a, source, planet, {"interceptor": 1}).status_code == 403


def test_empty_target_is_accepted_identically_then_fails_generically_and_returns(fleets):
    a, b = rivals(fleets)
    occupied, system = planet_of(b)
    with a.game.factory() as s:
        empty = s.scalar(
            select(Planet.id)
            .where(Planet.system_id == system, Planet.id != occupied)
            .order_by(Planet.id)
            .limit(1)
        )
    left, right = arm(a, {"cruiser": 1}), arm(a, {"cruiser": 1})
    # Same answer shape whatever the occupation: nothing hidden leaks from a preview.
    p1, p2 = (
        preview(a, left, occupied, {"cruiser": 1}).json(),
        preview(a, right, empty, {"cruiser": 1}).json(),
    )
    for key in ("hops", "cost", "travel_us", "battle_at", "affordable", "units"):
        assert p1[key] == p2[key]
    assert set(p1) == set(p2)
    before = stocks(a)
    mission_id, fleet_id = launched(a, attack(a, right, empty, {"cruiser": 1}))
    spent = {r: before[r] - stocks(a)[r] for r in before}
    assert spent["flux"] == 2 * 25 * p2["hops"] * M
    engagement = engagement_of(a, mission_id)
    assert engagement.defender_empire_id is None
    with a.game.factory() as s:
        owners = s.scalars(
            select(StreamFence).where(StreamFence.owner == f"combat:{engagement.id}")
        )
        assert len(list(owners)) == 1  # attacker fence only
    until_battle(a, mission_id)
    assert resolve_due(a)["outcome"] == "target_unavailable"
    reenter(a)
    (report,) = view(a).json()["combat"]["reports"]
    assert report == {
        "engagement_id": str(engagement.id),
        "role": "attacker",
        "battle_at": engagement.battle_at.isoformat(),
        "processed_at": report["processed_at"],
        "outcome": "target_unavailable",
        "target": {"planet_id": str(empty), "system_id": str(system)},
    }
    assert stacks(a, fleet_id) == {"cruiser": 1}
    with a.game.factory() as s:
        assert s.get(FleetMission, UUID(mission_id)).status == "returning"


def test_recall_in_transit_symmetric_on_approach_full_travel_too_late_after_battle(fleets):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    one, two, three = (arm(a, {"cruiser": 1}) for _ in range(3))
    m1, _ = launched(a, attack(a, one, planet, {"cruiser": 1}))
    a.advance(minutes=5)
    r1 = post(a, f"/missions/{m1}/recall", {"idempotency_key": uuid4().hex}).json()
    with a.game.factory() as s:
        m = s.get(FleetMission, UUID(m1))
        assert m.recalled_at < m.travel_arrival_at
        assert m.return_at == m.recalled_at + (m.recalled_at - m.started_at)
        assert r1["result"]["return_at"] == m.return_at.isoformat()
    m2, _ = launched(a, attack(a, two, planet, {"cruiser": 1}))
    a.advance(hours=12)  # arrived, approaching, battle not yet due
    reenter(a)
    assert post(a, f"/missions/{m2}/recall", {"idempotency_key": uuid4().hex}).status_code == 200
    with a.game.factory() as s:
        m = s.get(FleetMission, UUID(m2))
        assert m.recalled_at > m.travel_arrival_at
        assert m.return_at == m.recalled_at + (m.travel_arrival_at - m.started_at)
    assert engagement_of(a, m2).state == "cancelled"
    m3, _ = launched(a, attack(a, three, planet, {"cruiser": 1}))
    until_battle(a, m3)
    reenter(a)
    # Battle due but not resolved: a temporary refusal, never a move past the battle.
    pending = post(a, f"/missions/{m3}/recall", {"idempotency_key": uuid4().hex})
    assert pending.status_code == 409 and pending.json()["error"]["code"] == "combat_pending"
    assert resolve_due(a) is not None
    late = post(a, f"/missions/{m3}/recall", {"idempotency_key": uuid4().hex})
    assert late.json()["error"]["code"] == "recall_too_late"
    a.advance(days=2)
    assert worker(a) >= 1
    for fleet in (one, two, three):
        assert fleet_row(a, fleet).status == "STATIONED"


def test_production_and_reinforcement_join_only_up_to_battle_at_even_with_a_late_worker(fleets):
    a, b = rivals(fleets)
    planet, system = planet_of(b)
    strike = arm(a, {"cruiser": 2})
    arm(b, {"frigate": 1}, kind="GARRISON")
    mission_id, _ = launched(a, attack(a, strike, planet, {"cruiser": 2}))
    with a.game.factory() as s:
        battle_at = s.get(FleetMission, UUID(mission_id)).due_at
    # One interceptor batch finishes exactly at battle_at (inclusive), another 5 min later.
    with b.game.factory.begin() as s:
        balances = [s.get(ResourceBalance, (b.colony, r)) for r in ("alloys", "flux", "data")]
        for balance in balances:
            balance.stock = 9_000 * M  # test-only funds; production goes through the service
    b.game.test_clock[0] = battle_at - timedelta(minutes=30)
    reenter(b)
    assert order(b, "interceptor", 1).status_code == 200  # due exactly at battle_at
    b.game.test_clock[0] = battle_at - timedelta(minutes=25)
    reenter(b)
    assert order(b, "interceptor", 1).status_code == 200  # queued: due at battle_at + 30 min
    # The Combat worker is late: the stream is frozen at battle_at whatever the real time.
    b.game.test_clock[0] = battle_at + timedelta(hours=2)
    worker(b)
    with b.game.factory() as s:
        statuses = [
            o.status
            for o in s.scalars(
                select(ShipOrder)
                .where(ShipOrder.empire_id == b.empire)
                .order_by(ShipOrder.sequence)
            )
        ]
    assert statuses == ["completed", "active"]
    reenter(b)
    refused = order(b, "interceptor", 1)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "combat_pending"
    assert resolve_due(a) is not None
    engagement = engagement_of(a, mission_id)
    defended = engagement.snapshot["defender"]["fleets"]
    assert sum(u.get("interceptor", 0) for u in defended.values()) == 1  # the 10:00 one only
    assert sum(u.get("frigate", 0) for u in defended.values()) == 1
    worker(b)  # the later batch completes only after the battle, into the post-battle state
    with b.game.factory() as s:
        done = s.scalars(select(ShipOrder.status).where(ShipOrder.empire_id == b.empire))
        assert list(done) == ["completed", "completed"]
    assert stacks(b, garrison(b)["id"]).get("interceptor", 0) >= 1


def test_defender_moves_before_battle_and_reinforcements_after_never_fight(fleets):
    a, b = rivals(fleets)
    planet, system = planet_of(b)
    strike = arm(a, {"interceptor": 4})
    guard = arm(b, {"frigate": 3})
    mission_id, _ = launched(a, attack(a, strike, planet, {"interceptor": 4}))
    # B sends its guard away before battle_at with an ordinary command: no special tactic.
    with b.game.factory() as s:
        other = s.scalar(
            select(SystemKnowledge.system_id).where(
                SystemKnowledge.empire_id == b.empire,
                SystemKnowledge.system_id != system,
                SystemKnowledge.state != "DETECTED",
            )
        )
    if other is None:
        with b.game.factory.begin() as s:
            other = s.scalar(
                select(SystemKnowledge.system_id).where(
                    SystemKnowledge.empire_id == b.empire, SystemKnowledge.system_id != system
                )
            )
            g.map_system(s, b.universe, b.empire, other, b.game.clock())
    sent = post(
        b,
        "/missions",
        {
            "idempotency_key": uuid4().hex,
            "fleet_id": str(guard),
            "kind": "DEPLOY",
            "destination_id": str(other),
            "units": {"frigate": 3},
        },
    )
    assert sent.status_code == 200, sent.json()
    until_battle(a, mission_id)
    worker(b)
    assert resolve_due(a)["outcome"] == "unopposed"
    assert stacks(b, guard) == {"frigate": 3}


def test_losses_split_by_largest_remainder_civilians_untouched_destroyed_and_empty_garrison(fleets):
    a, b = rivals(fleets)
    planet, system = planet_of(b)
    strike = arm(a, {"cruiser": 6})
    home = arm(b, {"frigate": 1, "probe": 2}, kind="GARRISON")
    escort = arm(b, {"frigate": 2})
    convoy = arm(b, {"freighter": 1, "frigate": 1}, cargo={"alloys": 300})
    mission_id, _ = launched(a, attack(a, strike, planet, {"cruiser": 6}))
    until_battle(a, mission_id)
    assert resolve_due(a)["outcome"] == "attacker_win"
    assert stacks(b, home) == {"probe": 2}  # civilians never fight nor die
    assert fleet_row(b, home).status == "STATIONED"
    assert fleet_row(b, escort).status == "DESTROYED" and stacks(b, escort) == {}
    assert fleet_row(b, convoy).status == "STATIONED"
    assert stacks(b, convoy) == {"freighter": 1}
    with b.game.factory() as s:
        cargo = s.scalar(select(FleetCargo.amount).where(FleetCargo.fleet_id == convoy))
    assert cargo == 300 * M  # no cargo stolen or destroyed
    engagement = engagement_of(a, mission_id)
    assert engagement.result["defender_losses"] == {
        str(home): {"frigate": 1},
        str(escort): {"frigate": 2},
        str(convoy): {"frigate": 1},
    }
    reenter(b)
    defender_report = view(b).json()["combat"]["reports"][0]
    assert "probe" not in str(defender_report) and "freighter" not in str(defender_report)
    assert str(escort) not in [f["id"] for f in view(b).json()["fleets"]]  # DESTROYED hidden


def test_mutual_destruction_destroys_the_attacking_task_fleet_without_return(fleets):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    strike = arm(a, {"interceptor": 4})
    arm(b, {"interceptor": 4}, kind="GARRISON")
    mission_id, fleet_id = launched(a, attack(a, strike, planet, {"interceptor": 4}))
    until_battle(a, mission_id)
    assert resolve_due(a)["outcome"] == "mutual_destruction"
    row = fleet_row(a, fleet_id)
    assert (row.status, row.system_id, row.active_mission_id) == ("DESTROYED", None, None)
    with a.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        assert mission.status == "completed" and mission.return_at is None
        assert s.get(FleetReport, mission.id).result["destroyed"] is True
        assert not s.scalar(
            select(func.count()).where(
                ScheduledEvent.idempotency_key == f"fleet-return:{mission_id}"
            )
        )


def test_crash_before_commit_changes_nothing_and_two_workers_resolve_once(fleets):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    strike = arm(a, {"frigate": 3})
    guard = arm(b, {"interceptor": 3}, kind="GARRISON")
    mission_id, _ = launched(a, attack(a, strike, planet, {"frigate": 3}))
    until_battle(a, mission_id)
    runner = CombatOrchestrator(a.game.factory, Clock(a.game))

    def crash(_):
        raise RuntimeError("crash after resolution, before commit")

    assert runner.process_next(after_resolve=crash)["outcome"] == "retry"
    assert stacks(b, guard) == {"interceptor": 3} and stacks(a, strike) == {"frigate": 3}
    with a.game.factory() as s:
        assert not s.scalar(select(func.count()).select_from(CombatReport))
        assert s.scalar(select(func.count()).where(StreamFence.released_at.is_(None))) == 2
    a.advance(seconds=31)
    entered, release = Event(), Event()

    def hold(_):
        entered.set()
        assert release.wait(10)

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(runner.process_next, after_resolve=hold)
        assert entered.wait(10)
        second = pool.submit(CombatOrchestrator(a.game.factory, Clock(a.game)).process_next)
        release.set()
        results = [first.result(timeout=20), second.result(timeout=20)]
    assert sorted(str(r and r["outcome"]) for r in results) == ["None", "attacker_win"]
    with a.game.factory() as s:
        assert s.scalar(select(func.count()).select_from(CombatReport)) == 2
        assert s.scalar(select(func.count()).where(StreamFence.released_at.is_(None))) == 0
    assert runner.process_next() is None  # durable: never a second resolution


@pytest.mark.parametrize("order_", ["better_first", "worse_first"])
def test_concurrent_attacks_on_one_system_resolve_in_rank_order_whatever_the_worker(fleets, order_):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    one, two = arm(a, {"cruiser": 1}), arm(a, {"frigate": 3})
    arm(b, {"frigate": 2}, kind="GARRISON")
    m1, _ = launched(a, attack(a, one, planet, {"cruiser": 1}))
    m2, _ = launched(a, attack(a, two, planet, {"frigate": 3}))  # same frozen instant
    e1, e2 = engagement_of(a, m1), engagement_of(a, m2)
    assert (e1.battle_at, e1.started_at) == (e2.battle_at, e2.started_at)
    better, worse = sorted([e1, e2], key=lambda e: e.id)
    until_battle(a, m1)
    if order_ == "worse_first":
        assert resolve_due(a, worse.id) is None  # never passes a better-ranked active attack
    assert resolve_due(a, better.id) is not None
    assert resolve_due(a, worse.id) is not None
    with a.game.factory() as s:
        rows = {e.id: s.get(CombatEngagement, e.id) for e in (e1, e2)}
        assert rows[better.id].processed_at <= rows[worse.id].processed_at
        first_defence = rows[better.id].snapshot["defender"]["fleets"]
        assert sum(u.get("frigate", 0) for u in first_defence.values()) == 2


def test_blocked_better_rank_keeps_blocking_and_snapshot_drift_never_fights(fleets):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    one, two = arm(a, {"cruiser": 1}), arm(a, {"cruiser": 1})
    guard = arm(b, {"frigate": 2}, kind="GARRISON")
    m1, _ = launched(a, attack(a, one, planet, {"cruiser": 1}))
    a.advance(minutes=1)
    m2, _ = launched(a, attack(a, two, planet, {"cruiser": 1}))
    with a.game.factory.begin() as s:
        mission = s.get(FleetMission, UUID(m1))
        mission.snapshot = mission.snapshot | {"travel_us": 1}  # operator incident
    until_battle(a, m2)
    runner = CombatOrchestrator(a.game.factory, Clock(a.game), max_attempts=1)
    assert runner.process_next()["outcome"] == "blocked"
    assert engagement_of(a, m1).state == "blocked"
    assert stacks(b, guard) == {"frigate": 2}  # drift: no effect at all
    assert runner.process_next() is None  # the worse-ranked attack never overtakes it
    assert engagement_of(a, m2).state == "pending"


def test_gets_never_resolve_and_hidden_changes_never_alter_the_attacker_preview(fleets):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    strike = arm(a, {"interceptor": 2})
    before = preview(a, strike, planet, {"interceptor": 2}).json()
    with b.game.factory.begin() as s:
        for r in ("alloys", "flux", "data"):
            s.get(ResourceBalance, (b.colony, r)).stock = 1 * M
        s.execute(
            text("UPDATE colony_infrastructures SET level = level + 3 WHERE colony_id = :c"),
            {"c": b.colony},
        )
    arm(b, {"cruiser": 9}, kind="GARRISON")
    arm(b, {"probe": 4})
    after = preview(a, strike, planet, {"interceptor": 2}).json()
    assert after == before
    mission_id, _ = launched(a, attack(a, strike, planet, {"interceptor": 2}))
    until_battle(a, mission_id)
    reenter(a), reenter(b)
    for _ in range(2):
        assert view(a).status_code == view(b).status_code == b.read().status_code == 200
    assert engagement_of(a, mission_id).state == "pending"
    assert "defender" not in str(
        next(m for m in view(a).json()["missions"] if m["id"] == mission_id)
    )


def test_ai_defender_waits_on_combat_pending_without_failing(fleets):
    from app.ai.controller import activate
    from app.ai.models import AIController
    from app.ai.orchestrator import Orchestrator
    from app.persistence.models import Empire

    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    with b.game.factory.begin() as s:
        s.execute(text("DELETE FROM empire_bindings WHERE empire_id = :e"), {"e": b.empire})
        s.get(Empire, b.empire).controller_type = "ai"
        controller = activate(s, b.universe, b.empire, "economic_cautious", b.game.clock())
        cid = controller.id
    strike = arm(a, {"interceptor": 1})
    mission_id, _ = launched(a, attack(a, strike, planet, {"interceptor": 1}))
    until_battle(a, mission_id)
    ai = Orchestrator(b.game.factory, Clock(b.game))
    assert ai.process_next(controller_id=cid)["outcome"] == "combat_pending"
    with b.game.factory() as s:
        row = s.get(AIController, cid)
        assert (row.sequence, row.attempts, row.state) == (1, 0, "enabled")
    assert resolve_due(a)["outcome"] == "unopposed"
    b.advance(seconds=31)
    assert ai.process_next(controller_id=cid)["outcome"] in {"accepted", "wait", "refusal"}


def test_populated_combat_data_refuses_downgrade(fleets, migration_config):
    from alembic import command

    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    launched(a, attack(a, arm(a, {"interceptor": 1}), planet, {"interceptor": 1}))
    with pytest.raises(RuntimeError, match="live Combat data"):
        command.downgrade(migration_config, "0011_first_ai")


def test_stuck_engagements_never_starve_an_independent_battle(fleets):
    # Universe 1: a blocked better-ranked attack holds two lower-ranked ones on its system, and
    # a fourth waits on a defender stream stuck on a blocked event. Universe 2 is unrelated.
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    first, second, third = (arm(a, {"cruiser": 1}) for _ in range(3))
    m0, _ = launched(a, attack(a, first, planet, {"cruiser": 1}))
    a.advance(minutes=1)
    m1, _ = launched(a, attack(a, second, planet, {"cruiser": 1}))
    m2, _ = launched(a, attack(a, third, planet, {"cruiser": 1}))
    with a.game.factory.begin() as s:
        mission = s.get(FleetMission, UUID(m0))
        mission.snapshot = mission.snapshot | {"travel_us": 1}  # operator incident
    c, d = rivals(fleets)
    target, _ = planet_of(d)
    c.advance(minutes=1)
    m3, _ = launched(c, attack(c, arm(c, {"frigate": 2}), target, {"frigate": 2}))
    until_battle(c, m3)
    runner = CombatOrchestrator(a.game.factory, Clock(a.game), max_attempts=1, scan=1)
    assert runner.process_next()["outcome"] == "blocked"  # m0, the best rank
    outcome = runner.process_next()
    assert outcome["engagement_id"] == str(engagement_of(c, m3).id)
    assert {engagement_of(a, m).state for m in (m1, m2)} == {"pending"}
    # A due candidate that cannot catch up (blocked defender event) is paged past as well.
    e, f = rivals(fleets)
    goal, _ = planet_of(f)
    e.advance(minutes=1)
    m4, _ = launched(e, attack(e, arm(e, {"frigate": 1}), goal, {"frigate": 1}))
    g_, h = rivals(fleets)
    other, _ = planet_of(h)
    g_.advance(minutes=1)
    m5, _ = launched(g_, attack(g_, arm(g_, {"frigate": 1}), other, {"frigate": 1}))
    with f.game.factory.begin() as s:
        stream = g.state_for(s, f.universe, f.empire).stream_id
        s.add(
            ScheduledEvent(
                stream_id=stream,
                universe_id=f.universe,
                sequence=999,
                idempotency_key="test-only-stuck",
                event_type="SHIP_ORDER_COMPLETE",
                payload={},
                due_at=f.game.clock(),
                next_attempt_at=f.game.clock(),
                status="blocked",
                attempts=3,
            )
        )
    until_battle(g_, m5)
    resolved = runner.process_next()
    assert resolved["engagement_id"] == str(engagement_of(g_, m5).id)
    assert engagement_of(e, m4).state == "pending"


def test_live_threats_come_before_any_cancellation_history(fleets):
    from app.combat.service import alerts_for

    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    live, _ = launched(a, attack(a, arm(a, {"interceptor": 1}), planet, {"interceptor": 1}))
    for _ in range(3):
        a.advance(minutes=10)
        cancelled, _ = launched(
            a, attack(a, arm(a, {"interceptor": 1}), planet, {"interceptor": 1})
        )
        recall = post(a, f"/missions/{cancelled}/recall", {"idempotency_key": uuid4().hex})
        assert recall.status_code == 200
    with b.game.factory() as s:
        (first,) = alerts_for(s, b.universe, b.empire, limit=1)
        assert first["state"] == "pending" and first["id"] == str(engagement_of(a, live).id)
        states = [x["state"] for x in alerts_for(s, b.universe, b.empire, limit=3)]
        assert states == ["pending", "cancelled", "cancelled"]
        assert [x["state"] for x in alerts_for(s, b.universe, b.empire, history=False)] == [
            "pending"
        ]
