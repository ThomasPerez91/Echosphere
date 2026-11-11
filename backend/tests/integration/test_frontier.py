"""Real PostgreSQL tests for 13B (v0.9): passages, protocols, entry resolution (detections,
engagements), friendly retreats, and the C02 concurrency/replay/restart guarantees."""

# ruff: noqa: F811
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_colony_api import Clock, game  # noqa: F401
from test_combat import arm, attack, launched, planet_of, resolve_due, until_battle
from test_fleet import FULL, fleets, post, rebind, view, worker  # noqa: F401

from app.fleet.models import Fleet, FleetMission, FleetMissionLeg
from app.frontier.models import FleetPassage, FleetProtocolPeriod, FrontierDetection
from app.galaxy import service as g
from app.galaxy.models import GalaxyRoute
from app.persistence.models import StellarSystem
from app.relations import service as relations
from app.relations.models import RelationContact
from app.simulation.models import ResourceBalance

pytestmark = pytest.mark.integration
M = 1_000_000
RIGHTS = [
    *FULL,
    *("colony.expand", "combat.read", "combat.attack", "relations.read", "relations.negotiate"),
]


def rivals(fleets, ruleset="v0.9"):
    a = fleets(permissions=RIGHTS, ruleset=ruleset)
    b = fleets(permissions=RIGHTS, ruleset=ruleset, universe=a.universe, other=True)
    with a.game.factory.begin() as s:
        for system in s.scalars(
            select(StellarSystem.id).where(StellarSystem.universe_id == a.universe)
        ):
            for w in (a, b):  # test-only knowledge so either side can route anywhere
                g.map_system(s, w.universe, w.empire, system, w.game.clock())
        for w in (a, b):  # test-only funds; spending still goes through the services
            for r in ("alloys", "flux", "data"):
                s.get(ResourceBalance, (w.colony, r)).stock = 9_000 * M
    a.peers = b.peers = (a, b)
    return a, b


def reenter(*worlds):
    """After a long wait the access window lapsed: a new binding revision and session."""
    for w in worlds:
        w.revision = getattr(w, "revision", 1) + 1
        rebind(w, RIGHTS, revision=w.revision)


def deploy(w, fleet, destination, units):
    body = {
        "idempotency_key": uuid4().hex,
        "fleet_id": str(fleet),
        "kind": "DEPLOY",
        "destination_id": str(destination),
        "units": units,
    }
    return launched(w, post(w, "/missions", body))


def passages(w, mission_id):
    with w.game.factory() as s:
        return list(
            s.scalars(
                select(FleetPassage)
                .where(FleetPassage.mission_id == UUID(mission_id))
                .order_by(FleetPassage.sequence)
            )
        )


def chain(w, mission_id):
    """Systems entered along the persisted legs (origin excluded)."""
    with w.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
        node, systems = mission.origin_id, []
        for leg in s.scalars(
            select(FleetMissionLeg)
            .where(FleetMissionLeg.mission_id == mission.id)
            .order_by(FleetMissionLeg.ordinal)
        ):
            route = s.get(GalaxyRoute, leg.route_id)
            node = route.b_id if route.a_id == node else route.a_id
            systems.append(node)
        return mission, systems


def far_target(a, b):
    _, system = planet_of(b)
    return system


def reactions(w):
    from app.frontier.orchestrator import FrontierOrchestrator

    return FrontierOrchestrator(w.game.factory, Clock(w.game))


def entries(w, limit=50):
    """Resolve due frontier entries and reactions like the combat-worker; returns the outcomes."""
    runner, done = reactions(w), []
    while len(done) < limit:
        outcome = runner.process_next()
        if outcome is None:
            return done
        done.append(outcome)
    return done


def advance(w, limit=50):
    """Frontier work and ordinary events alternately, as the two workers do in production."""
    for _ in range(limit):
        if not entries(w) and worker(w, limit=limit) == 0:
            return


def test_v09_launch_records_every_entered_system_at_its_logical_instant(fleets):
    a, b = rivals(fleets)
    strike = arm(a, {"frigate": 1})
    mission_id, _ = deploy(a, strike, far_target(a, b), {"frigate": 1})
    mission, systems = chain(a, mission_id)
    rows = passages(a, mission_id)
    assert [r.system_id for r in rows] == systems and len(rows) >= 1
    assert {r.direction for r in rows} == {"outbound"} and all(r.cancelled_at is None for r in rows)
    assert rows[-1].entered_at == mission.travel_arrival_at  # destination entered on arrival
    instants = [r.entered_at for r in rows]
    assert instants == sorted(instants) and len(set(instants)) == len(instants)
    assert all(mission.started_at < t <= mission.travel_arrival_at for t in instants)


def test_historical_v08_universe_records_no_passage(fleets):
    a, b = rivals(fleets, ruleset="v0.8")
    strike = arm(a, {"frigate": 1})
    mission_id, _ = deploy(a, strike, far_target(a, b), {"frigate": 1})
    assert passages(a, mission_id) == []


def test_recall_mirrors_passed_systems_and_cancels_unreached_ones(fleets):
    a, b = rivals(fleets)
    strike = arm(a, {"frigate": 1})
    mission_id, _ = deploy(a, strike, far_target(a, b), {"frigate": 1})
    mission, _ = chain(a, mission_id)
    a.game.test_clock[0] = mission.started_at + (mission.travel_arrival_at - mission.started_at) / 2
    entries(a)  # entries already passed are resolved; the mover's stream is fenced until then
    recalled = post(a, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert recalled.status_code == 200
    with a.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
    rows = passages(a, mission_id)
    out = [r for r in rows if r.direction == "outbound"]
    back = [r for r in rows if r.direction == "return"]
    assert all(
        (r.cancelled_at == mission.recalled_at) == (r.entered_at > mission.recalled_at)
        for r in out
    )
    reached = [r for r in out if r.entered_at < mission.recalled_at]
    assert [r.system_id for r in back[:-1]] == [r.system_id for r in reversed(reached)]
    assert back[-1].system_id == mission.origin_id and back[-1].entered_at == mission.return_at
    assert all(
        r.entered_at == mission.recalled_at + (mission.recalled_at - p.entered_at)
        for r, p in zip(back[:-1], reversed(reached), strict=True)
    )
    # Replaying the recall intention never records a second way back.
    again = post(a, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert again.status_code == 200 and len(passages(a, mission_id)) == len(rows)


def test_attack_return_after_battle_is_entered_system_by_system(fleets):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    strike = arm(a, {"frigate": 3})
    mission_id, _ = launched(a, attack(a, strike, planet, {"frigate": 3}))
    until_battle(a, mission_id)
    assert resolve_due(a) is None  # C04: the entry into the target system comes first
    entries(a)
    assert resolve_due(a)["outcome"] == "unopposed"
    with a.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
    rows = passages(a, mission_id)
    back = [r for r in rows if r.direction == "return"]
    assert back and back[-1].system_id == mission.origin_id
    assert back[-1].entered_at == mission.return_at == mission.due_at + (
        mission.travel_arrival_at - mission.started_at
    )
    assert all(r.cancelled_at is None for r in rows)


def test_each_entry_fences_only_the_movers_own_stream_until_resolved(fleets):
    from app.simulation.models import StreamFence

    a, b = rivals(fleets)
    strike = arm(a, {"frigate": 1})
    mission_id, _ = deploy(a, strike, far_target(a, b), {"frigate": 1})
    rows = passages(a, mission_id)
    with a.game.factory() as s:
        owner = StreamFence.owner.like(f"frontier-passage:{mission_id}:%")
        fences = list(s.scalars(select(StreamFence).where(owner)))
        state = g.state_for(s, a.universe, a.empire)
    assert {f.stream_id for f in fences} == {state.stream_id}
    just_before = [r.entered_at - timedelta(microseconds=1) for r in rows]
    assert sorted(f.fence_at for f in fences) == just_before
    assert {r.state for r in rows} == {"pending"}
    a.game.test_clock[0] = rows[0].entered_at + timedelta(seconds=1)
    # Until the entry is resolved, the mover cannot command past it.
    assert protocol(a, arm(a, {"frigate": 1}), "SURVEILLANCE").json()["error"]["code"] == (
        "combat_pending"
    )
    assert entries(a)[0]["outcome"] == "resolved"
    assert passages(a, mission_id)[0].state == "resolved"


def protocol(w, fleet, value, key=None):
    return post(w, f"/{fleet}/protocol", {"idempotency_key": key or uuid4().hex, "protocol": value})


def fleet_view(w, fleet):
    return next(f for f in view(w).json()["fleets"] if f["id"] == str(fleet))


def test_protocol_is_set_changed_cleared_and_ends_with_the_stationing(fleets):
    a, b = rivals(fleets)
    watch = arm(a, {"frigate": 1})
    frontier = view(a).json()["frontier"]
    assert frontier["protocols"] == ["SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT"]
    assert frontier["detections"] == [] and frontier["encounters"] == []
    key = uuid4().hex
    assert protocol(a, watch, "SURVEILLANCE", key).status_code == 200
    assert protocol(a, watch, "SURVEILLANCE", key).status_code == 200  # same intention
    assert protocol(a, watch, "FRIENDLY_CONTACT", key).json()["error"]["code"] == (
        "idempotency_conflict"
    )
    assert fleet_view(a, watch)["protocol"] == "SURVEILLANCE"
    for value in ("AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT"):  # B05/B06 implemented
        assert protocol(a, watch, value).status_code == 200
        assert fleet_view(a, watch)["protocol"] == value
    assert fleet_view(a, watch)["protocol"] == "FRIENDLY_CONTACT"
    assert protocol(a, watch, None).status_code == 200
    assert fleet_view(a, watch)["protocol"] is None
    # A garrison never holds a protocol.
    garrison = arm(a, {"frigate": 1}, kind="GARRISON")
    assert protocol(a, garrison, "SURVEILLANCE").json()["error"]["code"] == "protocol_task"
    # Departure ends the stationing and the protocol.
    assert protocol(a, watch, "SURVEILLANCE").status_code == 200
    deploy(a, watch, far_target(a, b), {"frigate": 1})
    with a.game.factory() as s:
        assert s.get(Fleet, watch).protocol is None


def test_merge_clears_the_source_protocol_and_keeps_the_target_one(fleets):
    a, _ = rivals(fleets)
    source, target = arm(a, {"frigate": 1}), arm(a, {"interceptor": 1})
    assert protocol(a, source, "SURVEILLANCE").status_code == 200
    assert protocol(a, target, "FRIENDLY_CONTACT").status_code == 200
    merged = post(a, f"/{source}/merge", {"idempotency_key": uuid4().hex, "target_id": str(target)})
    assert merged.status_code == 200
    with a.game.factory() as s:
        assert s.get(Fleet, source).protocol is None and s.get(Fleet, source).status == "MERGED"
        assert s.get(Fleet, target).protocol == "FRIENDLY_CONTACT"


def test_v08_universe_has_no_frontier(fleets):
    a, _ = rivals(fleets, ruleset="v0.8")
    watch = arm(a, {"frigate": 1})
    assert view(a).json()["frontier"] is None
    assert protocol(a, watch, "SURVEILLANCE").json()["error"]["code"] == "frontier_unavailable"


def test_database_refuses_a_protocol_outside_a_stationed_task_fleet(fleets):
    from sqlalchemy.exc import IntegrityError

    a, _ = rivals(fleets)
    garrison_id = arm(a, {"frigate": 1}, kind="GARRISON")
    with pytest.raises(IntegrityError), a.game.factory.begin() as s:
        garrison = s.get(Fleet, garrison_id)
        garrison.protocol = "SURVEILLANCE"
        s.flush()


# --- B03/B04 detection -------------------------------------------------------------------------


def encounter(fleets, protocol="SURVEILLANCE", *, protocol_late=False):
    """A watches its home system; B deploys a frigate into it. Returns (a, b, mission, passage)."""
    a, b = rivals(fleets)
    _, home = planet_of(a)
    watch = arm(a, {"frigate": 1})
    if not protocol_late:
        assert protocol_set(a, watch, protocol).status_code == 200
    mover = arm(b, {"frigate": 1})
    mission_id, _ = deploy(b, mover, home, {"frigate": 1})
    entry = passages(b, mission_id)[-1]
    assert entry.system_id == home
    return a, b, watch, mission_id, entry


def protocol_set(w, fleet, value):
    return post(w, f"/{fleet}/protocol", {"idempotency_key": uuid4().hex, "protocol": value})


def detections(w):
    return view(w).json()["frontier"]["detections"]


def rows(w):
    with w.game.factory() as s:
        return list(
            s.scalars(select(FrontierDetection).where(FrontierDetection.universe_id == w.universe))
        )


def watched_rows(w, entry):
    return [r for r in rows(w) if (r.mission_id, r.sequence) == (entry.mission_id, entry.sequence)]


def through(w, entry, extra=timedelta(0)):
    """Clock just after `entry`, every earlier entry resolved."""
    w.game.test_clock[0] = entry.entered_at + extra
    reenter(*w.peers)
    advance(w)


def test_surveillance_detects_a_real_entry_mutually_and_anonymously_at_its_instant(fleets):
    a, b, watch, mission_id, entry = encounter(fleets)
    assert rows(a) == []  # nothing before the logical entry instant
    through(a, entry, timedelta(minutes=5))  # worker late: same result
    seen = detections(a)
    assert len(seen) == 1 and seen[0]["detected_at"] == entry.entered_at.isoformat()
    assert seen[0]["role"] == "watch" and seen[0]["empire"] is None and not seen[0]["friendly"]
    assert set(seen[0]) == {"id", "system", "detected_at", "role", "friendly", "empire"}
    other = detections(b)
    assert len(other) == 1 and other[0]["role"] == "transit" and other[0]["empire"] is None
    leak = str(view(a).json()["frontier"])
    assert str(b.empire) not in leak and str(mission_id) not in leak and "frigate" not in leak
    # An anonymous detection creates no named contact.
    with a.game.factory() as s:
        assert s.get(RelationContact, (a.empire, b.empire)) is None


def test_entry_resolution_replay_never_duplicates(fleets):
    from app.frontier import service as frontier

    a, b, _, _, entry = encounter(fleets)
    through(a, entry)
    assert len(watched_rows(a, entry)) == 2
    assert reactions(a).process_next() is None  # resolved once, never again
    with a.game.factory.begin() as s:  # even a replayed evaluation only re-asserts the facts
        row = s.get(FleetPassage, (entry.mission_id, entry.sequence))
        for period in frontier.watchers(s, row):
            frontier.detect(s, row, period)
    assert len(watched_rows(a, entry)) == 2


def test_identity_only_when_already_known_at_the_instant(fleets):
    a, b, _, _, entry = encounter(fleets)
    with a.game.factory.begin() as s:
        relations.record_contact(s, a.universe, a.empire, b.empire, "presence", a.game.clock())
    through(a, entry)
    assert detections(a)[0]["empire"]["id"] == str(b.empire)  # A knew B
    assert detections(b)[0]["empire"] is None  # B did not know A


def test_protocol_set_after_the_entry_never_detects_retroactively(fleets):
    a, b, watch, _, entry = encounter(fleets, protocol_late=True)
    a.game.test_clock[0] = entry.entered_at + timedelta(seconds=1)
    reenter(a)
    assert protocol_set(a, watch, "SURVEILLANCE").status_code == 200  # set after the entry
    advance(a)
    assert watched_rows(a, entry) == []


def test_covering_is_open_ended_at_exactly_the_entry_instant(fleets):
    """C04 tie-break: a protocol started at t does not see an entry at t; one ended at t does."""
    from app.fleet import service as fleet_service
    from app.simulation.service import TimeEngine

    a, b, watch, _, entry = encounter(fleets, protocol_late=True)
    other = arm(a, {"frigate": 1})
    assert protocol_set(a, other, "SURVEILLANCE").status_code == 200
    t = entry.entered_at
    a.game.test_clock[0] = t
    engine = TimeEngine(a.game.factory, Clock(a.game))
    with a.game.factory.begin() as s:
        fleet_service.set_protocol(
            s, engine, a.universe, a.empire, watch, "SURVEILLANCE", key=uuid4().hex, at=t
        )
        fleet_service.set_protocol(
            s, engine, a.universe, a.empire, other, None, key=uuid4().hex, at=t
        )
    advance(a)
    seen = {r.watch_fleet_id for r in watched_rows(a, entry) if r.role == "watch"}
    assert seen == {other}


def test_watcher_gone_before_the_entry_never_detects(fleets):
    a, b, watch, _, entry = encounter(fleets)
    deploy(a, watch, planet_of(b)[1], {"frigate": 1})
    with a.game.factory() as s:
        period = s.scalar(select(FleetProtocolPeriod).where(FleetProtocolPeriod.fleet_id == watch))
        assert period.ended_at is not None and period.ended_at < entry.entered_at
    through(a, entry)
    assert [d for d in rows(a) if d.watch_fleet_id == watch] == []


def test_cancelled_entry_never_detects(fleets):
    a, b, _, mission_id, entry = encounter(fleets)
    with b.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
    b.game.test_clock[0] = mission.started_at + timedelta(seconds=1)
    recalled = post(b, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert recalled.status_code == 200
    through(a, entry, timedelta(minutes=1))
    assert watched_rows(a, entry) == []
    assert passages(b, mission_id)[-1].state != "pending"


def test_friendly_contact_introduces_both_empires_after_the_encounter(fleets):
    a, b, _, _, entry = encounter(fleets, "FRIENDLY_CONTACT")
    through(a, entry)
    assert detections(a)[0]["friendly"] and detections(a)[0]["empire"]["id"] == str(b.empire)
    assert detections(b)[0]["empire"]["id"] == str(a.empire)
    # Contacts are materialised at read points (never inside a resolution), dated at the entry.
    for w in (a, b):
        path = f"/game/{w.universe}/relations/{w.empire}"
        assert w.client.get(path, headers={"X-Game-Request": "bootstrap"}).status_code == 200
    with a.game.factory() as s:
        for observer, observed in ((a.empire, b.empire), (b.empire, a.empire)):
            contact = s.get(RelationContact, (observer, observed))
            assert contact.first_source == "frontier" and contact.first_seen_at == entry.entered_at
            assert contact.presence_planet_id is None


# --- C02 concurrency, replay, restart (two real connections) -----------------------------------


def hold(factory, work, ready, release, box):
    """Run `work(session)` in its own transaction, signal `ready`, wait `release`, commit."""

    def run():
        try:
            with factory.begin() as s:
                box["result"] = work(s)
                ready.set()
                release.wait(10)
        except Exception as error:  # surfaced to the test thread
            box["error"] = error
            ready.set()

    return run


def test_protocol_committed_after_the_entry_became_due_is_seen_by_the_resolution(fleets):
    """Command dated before t still uncommitted when the resolution starts: the resolution waits
    for the watcher's stream lock, then sees the period (no lost detection)."""
    import threading

    from app.fleet import service as fleet_service
    from app.simulation.service import TimeEngine

    a, b, watch, _, entry = encounter(fleets, protocol_late=True)
    t = entry.entered_at
    a.game.test_clock[0] = t - timedelta(seconds=1)
    engine = TimeEngine(a.game.factory, Clock(a.game))
    ready, release, box = threading.Event(), threading.Event(), {}
    command = threading.Thread(
        target=hold(
            a.game.factory,
            lambda s: fleet_service.set_protocol(
                s, engine, a.universe, a.empire, watch, "SURVEILLANCE", key=uuid4().hex,
                at=t - timedelta(seconds=1),
            ),
            ready,
            release,
            box,
        )
    )
    command.start()
    assert ready.wait(10) and "error" not in box
    a.game.test_clock[0] = t + timedelta(seconds=1)
    resolved = {}
    resolver = threading.Thread(target=lambda: resolved.update(out=entries(a)))
    resolver.start()
    resolver.join(0.5)
    assert resolver.is_alive()  # waiting for the watcher's stream lock, not resolving blind
    release.set()
    command.join(10)
    resolver.join(10)
    assert watched_rows(a, entry) and {r.role for r in watched_rows(a, entry)} == {
        "watch",
        "transit",
    }


def test_protocol_dated_before_an_already_resolved_entry_is_refused(fleets):
    """Reverse commit order: the resolution holds the watcher's lock and commits first; a command
    dated before t that waited for that lock is refused, never recorded behind the resolution."""
    import threading

    from app.colony.service import ColonyError
    from app.fleet import service as fleet_service
    from app.simulation.scheduler import TimelineError
    from app.simulation.service import TimeEngine

    a, b, watch, _, entry = encounter(fleets, protocol_late=True)
    t = entry.entered_at
    a.game.test_clock[0] = t - timedelta(seconds=1)
    entries(a)  # earlier entries of the route first: the watcher's stream is not part of them
    a.game.test_clock[0] = t + timedelta(seconds=1)
    holding, go = threading.Event(), threading.Event()

    def pause(session):
        holding.set()
        go.wait(10)

    out = {}
    resolver = threading.Thread(
        target=lambda: out.update(r=reactions(a).process_next(after_resolve=pause))
    )
    resolver.start()
    assert holding.wait(10)
    engine = TimeEngine(a.game.factory, Clock(a.game))
    late = {}

    def command():
        try:
            with a.game.factory.begin() as s:
                fleet_service.set_protocol(
                    s, engine, a.universe, a.empire, watch, "SURVEILLANCE", key=uuid4().hex,
                    at=t - timedelta(seconds=1),
                )
        except (ColonyError, TimelineError) as error:
            late["error"] = error

    blocked = threading.Thread(target=command)
    blocked.start()
    blocked.join(0.5)
    assert blocked.is_alive()  # waits for the resolution's lock on the watcher's stream
    go.set()
    resolver.join(10)
    blocked.join(10)
    assert out["r"]["outcome"] == "resolved" and "error" in late
    with a.game.factory() as s:
        assert s.scalar(
            select(FleetProtocolPeriod).where(FleetProtocolPeriod.fleet_id == watch)
        ) is None
    assert watched_rows(a, entry) == []  # consistent: nothing covered t
    reenter(a)
    assert protocol_set(a, watch, "SURVEILLANCE").status_code == 200  # a fresh instant is fine


def test_crash_before_commit_changes_nothing_and_restart_gives_the_same_result(fleets):
    a, b, _, _, entry = encounter(fleets, "INTERCEPTION")
    a.game.test_clock[0] = entry.entered_at + timedelta(minutes=2)
    before = passages(b, str(entry.mission_id))

    def crash(session):
        raise RuntimeError("worker killed before commit")

    with pytest.raises(RuntimeError):
        reactions(a).process_next(after_resolve=crash, raise_errors=True)
    assert passages(b, str(entry.mission_id))[-1].state == "pending" and rows(a) == []
    assert encounter_rows(a) == []
    first = entries(a)
    assert first and first[-1]["outcome"] == "resolved"
    assert len(watched_rows(a, entry)) == 2 and len(encounter_rows(a)) == 1
    assert entries(a) == [] and len(before) == len(passages(b, str(entry.mission_id)))


@pytest.mark.parametrize("friendly_first", [True, False])
def test_attack_launch_and_friendly_protocol_plan_one_retreat_in_either_commit_order(
    fleets, friendly_first
):
    """The ATTACK launch holds the defender's stream FOR KEY SHARE (battle fence) before reading
    protocol periods; the protocol command holds it FOR UPDATE: serialised either way."""
    import threading

    from app.fleet import service as fleet_service
    from app.simulation.service import TimeEngine

    a, b, friend, _ = friendly_home(fleets)
    planet, _ = planet_of(a)
    raid = arm(b, {"interceptor": 1})
    assert protocol_set(a, friend, None).status_code == 200  # cleared, then set concurrently
    now = a.game.clock()
    engine = TimeEngine(a.game.factory, Clock(a.game))

    def friendly(s):
        return fleet_service.set_protocol(
            s, engine, a.universe, a.empire, friend, "FRIENDLY_CONTACT", key=uuid4().hex, at=now
        )

    def strike(s):
        return fleet_service.launch(
            s,
            engine,
            b.universe,
            b.empire,
            raid,
            "ATTACK",
            None,
            {"interceptor": 1},
            None,
            key=uuid4().hex,
            at=now,
            target_planet_id=planet,
        )

    first, second = (friendly, strike) if friendly_first else (strike, friendly)
    ready, release, box = threading.Event(), threading.Event(), {}
    t1 = threading.Thread(target=hold(a.game.factory, first, ready, release, box))
    t1.start()
    assert ready.wait(10) and "error" not in box, box
    box2, release2 = {}, threading.Event()
    release2.set()  # the second commits as soon as it gets through
    t2 = threading.Thread(target=hold(a.game.factory, second, threading.Event(), release2, box2))
    t2.start()
    t2.join(0.5)
    assert t2.is_alive()  # serialised on the defender's Operations stream row
    release.set()
    t1.join(10)
    t2.join(10)
    assert "error" not in box and "error" not in box2, (box, box2)
    retreats = [r for r in encounter_rows(a) if r.kind == "retreat" and r.state == "pending"]
    assert len(retreats) == 1 and retreats[0].watch_fleet_id == friend


# --- B05 automatic engagements, B06 friendly retreat ------------------------------------------


def encounter_rows(w):
    from app.frontier.models import FrontierEncounter

    with w.game.factory() as s:
        return list(
            s.scalars(
                select(FrontierEncounter)
                .where(FrontierEncounter.universe_id == w.universe)
                .order_by(FrontierEncounter.encounter_at, FrontierEncounter.id)
            )
        )


def meet(fleets, protocol, watcher_units, mover_units):
    """A's watch Fleet holds `protocol` in A's home; B deploys `mover_units` into it."""
    a, b = rivals(fleets)
    _, home = planet_of(a)
    watch = arm(a, watcher_units)
    assert protocol_set(a, watch, protocol).status_code == 200
    mover = arm(b, mover_units)
    mission_id, fleet_id = deploy(b, mover, home, mover_units)
    entry = passages(b, mission_id)[-1]
    return a, b, watch, mission_id, fleet_id, entry


def stacks_now(w, fleet):
    from app.fleet import service as fleet_service

    with w.game.factory() as s:
        return fleet_service.stacks_of(s, UUID(str(fleet)))


def fight(w, entry, extra=timedelta(0)):
    """Clock at `entry` (+extra), earlier entries resolved, then this entry: its engagements."""
    w.game.test_clock[0] = entry.entered_at + extra
    reenter(*w.peers)
    out = []
    for outcome in entries(w):
        if outcome.get("passage") == f"{entry.mission_id}:{entry.sequence}":
            out = outcome["engagements"]
    return out


def test_engagement_is_decided_at_the_entry_never_planned_and_freezes_both_fleets(fleets):
    a, b, watch, mission_id, _, entry = meet(
        fleets, "INTERCEPTION", {"frigate": 4}, {"interceptor": 1}
    )
    assert encounter_rows(a) == []  # nothing planned: the entry decides
    a.game.test_clock[0] = entry.entered_at + timedelta(seconds=30)
    # Unresolved due entry: the mover's stream is fenced, the covering watcher keeps its units.
    split = post(a, f"/{watch}/split", {"idempotency_key": uuid4().hex, "units": {"frigate": 1}})
    assert split.json()["error"]["code"] == "combat_pending"
    recall = post(b, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert recall.json()["error"]["code"] == "combat_pending"
    # A protocol change after t is allowed and never alters what t saw (open end, C04).
    assert protocol_set(a, watch, "SURVEILLANCE").status_code == 200
    assert fight(a, entry, timedelta(seconds=30)) == ["fought"]
    assert reactions(a).process_next() is None  # never applied twice
    again = post(a, f"/{watch}/split", {"idempotency_key": uuid4().hex, "units": {"frigate": 1}})
    assert again.status_code == 200


def test_interception_destroys_an_unknown_military_mover_at_the_entry_instant(fleets):
    a, b, watch, mission_id, fleet_id, entry = meet(
        fleets, "INTERCEPTION", {"frigate": 4}, {"interceptor": 1}
    )
    assert fight(a, entry, timedelta(minutes=10)) == ["fought"]  # late worker: same result
    (row,) = encounter_rows(a)
    assert row.result["mover"]["destroyed"] is True
    with b.game.factory() as s:
        fleet, mission = s.get(Fleet, UUID(fleet_id)), s.get(FleetMission, UUID(mission_id))
        assert fleet.status == "DESTROYED" and mission.status == "completed"
        assert mission.completed_at == entry.entered_at
    worker(b, limit=50)  # the cancelled arrival never happens
    with b.game.factory() as s:
        assert s.get(Fleet, UUID(fleet_id)).status == "DESTROYED"
    # Both sides get a battle report naming the other; the interception is A's hostile act.
    mine = view(a).json()["frontier"]["encounters"][0]
    theirs = view(b).json()["frontier"]["encounters"][0]
    assert mine["role"] == "watcher" and mine["opponent"]["id"] == str(b.empire)
    assert theirs["role"] == "mover" and theirs["destroyed"] is True
    with a.game.factory() as s:
        low, high = sorted([a.empire, b.empire], key=lambda u: u.bytes)
        from app.relations.models import RelationPair

        pair = s.get(RelationPair, (low, high))
        by_a = pair.last_hostile_by_low_at if a.empire == low else pair.last_hostile_by_high_at
        assert by_a == entry.entered_at
        assert s.get(RelationContact, (a.empire, b.empire)).first_source == "combat"


def test_surviving_mover_continues_its_mission_with_its_losses(fleets):
    a, b, _, mission_id, fleet_id, entry = meet(
        fleets, "INTERCEPTION", {"interceptor": 1}, {"frigate": 3}
    )
    assert fight(a, entry) == ["fought"]
    (row,) = encounter_rows(a)
    assert row.result["mover"]["destroyed"] is False
    left = stacks_now(b, fleet_id)
    lost = row.result["mover"]["losses"]
    assert {c: left.get(c, 0) + lost.get(c, 0) for c in {"frigate"}} == {"frigate": 3}
    advance(b)  # the arrival verifies the launch = survivors + losses, then settles
    with b.game.factory() as s:
        fleet = s.get(Fleet, UUID(fleet_id))
        assert fleet.status == "STATIONED" and fleet.system_id == entry.system_id


def test_purely_civilian_mover_is_never_engaged_nor_reported(fleets):
    a, b, _, _, fleet_id, entry = meet(fleets, "INTERCEPTION", {"frigate": 4}, {"freighter": 1})
    assert fight(a, entry) == ["no_military_target"]
    assert stacks_now(b, fleet_id) == {"freighter": 1}
    assert view(a).json()["frontier"]["encounters"] == []  # the reason would reveal the force
    assert view(b).json()["frontier"]["encounters"] == []


def test_active_pact_prevents_the_interception(fleets):
    a, b, _, _, fleet_id, entry = meet(fleets, "INTERCEPTION", {"frigate": 4}, {"interceptor": 1})
    with a.game.factory.begin() as s:
        at = a.game.clock()
        relations.record_contact(s, a.universe, a.empire, b.empire, "presence", at)
        relations.propose(s, a.universe, a.empire, b.empire, key="test:pact", at=at)
        relations.accept(s, a.universe, b.empire, a.empire, key="test:accept", at=at)
    assert fight(a, entry) == ["pact"]
    assert stacks_now(b, fleet_id) == {"interceptor": 1}


def test_ambush_ignores_an_empire_without_recent_hostility(fleets):
    a, b, _, _, fleet_id, entry = meet(fleets, "AMBUSH", {"frigate": 4}, {"interceptor": 1})
    with a.game.factory.begin() as s:  # known, but never hostile: not an enemy (D4)
        relations.record_contact(s, a.universe, a.empire, b.empire, "presence", a.game.clock())
    assert fight(a, entry) == ["not_enemy"]
    assert stacks_now(b, fleet_id) == {"interceptor": 1}


def test_ambush_engages_an_empire_that_attacked_us_within_72_hours(fleets):
    a, b = rivals(fleets)
    with a.game.factory.begin() as s:  # B needs A's map to attack
        for system in s.scalars(
            select(StellarSystem.id).where(StellarSystem.universe_id == a.universe)
        ):
            g.map_system(s, a.universe, b.empire, system, a.game.clock())
    planet, home = planet_of(a)
    raid = arm(b, {"interceptor": 1})
    arm(a, {"frigate": 2}, kind="GARRISON")
    raid_id, _ = launched(b, attack(b, raid, planet, {"interceptor": 1}))
    until_battle(b, raid_id)
    entries(b)  # the raid's own entries first (C04)
    assert resolve_due(b) is not None  # a fought battle: B's dated hostile act against A
    reenter(a, b)
    watch = arm(a, {"frigate": 4})
    assert protocol_set(a, watch, "AMBUSH").status_code == 200
    mover = arm(b, {"interceptor": 1})
    mission_id, _ = deploy(b, mover, home, {"interceptor": 1})
    entry = passages(b, mission_id)[-1]
    assert fight(a, entry) == ["fought"]


def test_successive_watchers_resolve_in_fleet_order_on_the_survivors(fleets):
    a, b = rivals(fleets)
    _, home = planet_of(a)
    first, second = arm(a, {"interceptor": 1}), arm(a, {"interceptor": 1})
    for watch in (first, second):
        assert protocol_set(a, watch, "INTERCEPTION").status_code == 200
    mover = arm(b, {"frigate": 3})
    mission_id, fleet_id = deploy(b, mover, home, {"frigate": 3})
    entry = passages(b, mission_id)[-1]
    outcomes = fight(a, entry)
    assert len(outcomes) == 2  # one entry, both watchers, one transaction
    rows_ = encounter_rows(a)
    assert sorted(str(r.watch_fleet_id) for r in rows_) == sorted(map(str, (first, second)))
    resolved = [r for r in rows_ if r.outcome == "fought"]
    if len(resolved) == 2:  # the second watcher met the survivors of the first meeting
        one, two = sorted(resolved, key=lambda r: str(r.watch_fleet_id))
        assert two.result["mover"]["initial"] == one.result["mover"]["survivors"]


def test_planetary_battle_waits_for_an_entry_at_or_before_its_instant(fleets):
    """C04: an entry at t <= battle_at (state strictly before t) is resolved before the battle."""
    a, b = rivals(fleets)
    with a.game.factory.begin() as s:
        for system in s.scalars(
            select(StellarSystem.id).where(StellarSystem.universe_id == a.universe)
        ):
            g.map_system(s, a.universe, b.empire, system, a.game.clock())
    planet, home = planet_of(a)
    watch = arm(a, {"frigate": 4})
    assert protocol_set(a, watch, "INTERCEPTION").status_code == 200
    raid = arm(b, {"interceptor": 1})
    raid_id, _ = launched(b, attack(b, raid, planet, {"interceptor": 1}))
    entry = [p for p in passages(b, raid_id) if p.direction == "outbound"][-1]
    until_battle(b, raid_id)
    assert resolve_due(b) is None  # blocked: the entry into the target system comes first
    assert fight(a, entry, b.game.test_clock[0] - entry.entered_at) == ["fought"]
    # The raid was destroyed at its entry: its planetary battle never happens.
    assert resolve_due(b) is None


def friendly_home(fleets):
    """A's friendly Fleet came home from a neighbour by a real v0.9 move, then watches home."""
    a, b = rivals(fleets)
    _, home = planet_of(a)
    with a.game.factory.begin() as s:
        neighbour = s.scalar(
            select(GalaxyRoute.b_id).where(
                GalaxyRoute.universe_id == a.universe, GalaxyRoute.a_id == home
            )
        ) or s.scalar(
            select(GalaxyRoute.a_id).where(
                GalaxyRoute.universe_id == a.universe, GalaxyRoute.b_id == home
            )
        )
        for system in s.scalars(
            select(StellarSystem.id).where(StellarSystem.universe_id == a.universe)
        ):
            g.map_system(s, a.universe, b.empire, system, a.game.clock())
    friend = arm(a, {"frigate": 1})
    out_id, _ = deploy(a, friend, neighbour, {"frigate": 1})
    a.game.test_clock[0] = passages(a, out_id)[-1].entered_at + timedelta(minutes=1)
    advance(a)
    back_id, _ = deploy(a, friend, home, {"frigate": 1})
    a.game.test_clock[0] = passages(a, back_id)[-1].entered_at + timedelta(minutes=1)
    advance(a)
    assert fleet_view(a, friend)["system"]["id"] == str(home)
    assert protocol_set(a, friend, "FRIENDLY_CONTACT").status_code == 200
    return a, b, friend, neighbour


def test_friendly_fleet_retreats_to_its_previous_system_when_a_hostile_force_enters(fleets):
    a, b, friend, neighbour = friendly_home(fleets)
    planet, _ = planet_of(a)
    raid = arm(b, {"interceptor": 1})
    raid_id, _ = launched(b, attack(b, raid, planet, {"interceptor": 1}))
    entry = [p for p in passages(b, raid_id) if p.direction == "outbound"][-1]
    (row,) = [r for r in encounter_rows(a) if r.kind == "retreat"]
    assert row.encounter_at == entry.entered_at and row.watch_fleet_id == friend
    with a.game.factory() as s:
        flux_before = s.get(ResourceBalance, (a.colony, "flux")).stock
    a.game.test_clock[0] = entry.entered_at + timedelta(minutes=3)
    outcomes = entries(a)
    assert [o["outcome"] for o in outcomes if "encounter_id" in o] == ["retreated"]
    # The entry itself (a friendly presentation) is resolved before the retreat it triggers.
    assert any(o.get("passage") == f"{entry.mission_id}:{entry.sequence}" for o in outcomes)
    with a.game.factory() as s:
        fleet = s.get(Fleet, friend)
        mission = s.get(FleetMission, fleet.active_mission_id)
        assert fleet.status == "MOVING" and mission.destination_id == neighbour
        assert mission.started_at == entry.entered_at  # left at the logical entry instant
        assert s.get(ResourceBalance, (a.colony, "flux")).stock != flux_before  # paid, not free
    report = [e for e in view(a).json()["frontier"]["encounters"] if e["kind"] == "retreat"][0]
    assert report["outcome"] == "retreated" and report["destination"]["id"] == str(neighbour)
    assert [e for e in view(b).json()["frontier"]["encounters"] if e["kind"] == "retreat"] == []
    assert reactions(a).process_next() is None  # one aggression, one retreat, one debit


def test_recalled_attack_before_its_entry_cancels_the_retreat(fleets):
    a, b, friend, _ = friendly_home(fleets)
    planet, _ = planet_of(a)
    raid = arm(b, {"interceptor": 1})
    raid_id, _ = launched(b, attack(b, raid, planet, {"interceptor": 1}))
    with b.game.factory() as s:
        started = s.get(FleetMission, UUID(raid_id)).started_at
    b.game.test_clock[0] = started + timedelta(seconds=1)
    recalled = post(b, f"/missions/{raid_id}/recall", {"idempotency_key": uuid4().hex})
    assert recalled.status_code == 200
    assert [r.state for r in encounter_rows(a) if r.kind == "retreat"] == ["cancelled"]


# --- C03 local (0-hop) attack and targeting -----------------------------------------------------


def test_local_attack_triggers_the_friendly_retreat_at_launch_before_the_battle(fleets):
    a, b, friend, neighbour = friendly_home(fleets)
    planet, home = planet_of(a)
    # C04: a protocol covers only what happens strictly after its start, not at the same instant.
    a.game.test_clock[0] += timedelta(minutes=1)
    raid = arm(b, {"interceptor": 1}, system=home)  # B already stands in A's home system
    raid_id, _ = launched(b, attack(b, raid, planet, {"interceptor": 1}))
    with b.game.factory() as s:
        mission = s.get(FleetMission, UUID(raid_id))
        started, battle = mission.started_at, mission.due_at
    (local,) = passages(b, raid_id)
    assert (local.direction, local.sequence, local.state) == ("local", 0, "resolved")
    assert local.entered_at == started and battle > started  # Q02 window untouched
    (row,) = [r for r in encounter_rows(a) if r.kind == "retreat"]
    assert row.encounter_at == started and row.watch_fleet_id == friend
    with a.game.factory() as s:
        flux_before = s.get(ResourceBalance, (a.colony, "flux")).stock
    a.game.test_clock[0] = started + timedelta(minutes=5)
    outcomes = entries(a)
    assert [o["outcome"] for o in outcomes if "encounter_id" in o] == ["retreated"]
    with a.game.factory() as s:
        fleet = s.get(Fleet, friend)
        moved = s.get(FleetMission, fleet.active_mission_id)
        assert moved.started_at == started and moved.destination_id == neighbour
        flux_after = s.get(ResourceBalance, (a.colony, "flux")).stock
        assert flux_after != flux_before  # normal fuel
    assert entries(a) == []  # idempotent: one hostile act, one retreat, one debit
    with a.game.factory() as s:
        assert s.get(ResourceBalance, (a.colony, "flux")).stock == flux_after
    # The battle still waits its warning window and finds the friendly Fleet gone.
    until_battle(b, raid_id)
    entries(a)
    battle_outcome = resolve_due(b)
    assert battle_outcome is not None
    with a.game.factory() as s:
        assert s.get(Fleet, friend).status in {"MOVING", "STATIONED"}


def test_an_attack_on_no_empire_of_the_watcher_triggers_no_retreat(fleets):
    from app.persistence.models import Colony, Planet

    a, b = rivals(fleets)
    with a.game.factory() as s:
        empty = s.scalar(
            select(Planet)
            .where(
                Planet.universe_id == a.universe,
                ~select(Colony.id).where(Colony.planet_id == Planet.id).exists(),
            )
            .order_by(Planet.id)
            .limit(1)
        )
        target, system = empty.id, empty.system_id
    friend = arm(a, {"frigate": 1}, system=system)
    assert protocol_set(a, friend, "FRIENDLY_CONTACT").status_code == 200
    raid = arm(b, {"interceptor": 1})
    response = attack(b, raid, target, {"interceptor": 1})
    assert response.status_code == 200, response.json()
    assert [r for r in encounter_rows(a) if r.kind == "retreat"] == []


# --- Migration 0014 -------------------------------------------------------------------------------


def test_frontier_migration_matches_metadata_and_populated_downgrade_is_refused(
    fleets, migration_config, database_engine
):
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.persistence.models import Base

    with database_engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    a, b = rivals(fleets)
    deploy(a, arm(a, {"frigate": 1}), far_target(a, b), {"frigate": 1})  # live passages
    with pytest.raises(RuntimeError, match="live Frontier data"):
        command.downgrade(migration_config, "0013_relations")
