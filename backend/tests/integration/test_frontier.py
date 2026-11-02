"""Real PostgreSQL tests for 13B B01 (per-hop passages) and B02 (stationed protocol), v0.9."""

# ruff: noqa: F811
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_colony_api import Clock, game  # noqa: F401
from test_combat import arm, attack, launched, planet_of, resolve_due, until_battle
from test_fleet import FULL, fleets, post, view, worker  # noqa: F401

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
    return a, b


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


def protocol(w, fleet, value, key=None):
    return post(w, f"/{fleet}/protocol", {"idempotency_key": key or uuid4().hex, "protocol": value})


def fleet_view(w, fleet):
    return next(f for f in view(w).json()["fleets"] if f["id"] == str(fleet))


def test_protocol_is_set_changed_cleared_and_ends_with_the_stationing(fleets):
    a, b = rivals(fleets)
    watch = arm(a, {"frigate": 1})
    frontier = view(a).json()["frontier"]
    assert frontier["protocols"] == ["SURVEILLANCE", "FRIENDLY_CONTACT"]
    assert frontier["detections"] == []
    key = uuid4().hex
    assert protocol(a, watch, "SURVEILLANCE", key).status_code == 200
    assert protocol(a, watch, "SURVEILLANCE", key).status_code == 200  # same intention
    assert protocol(a, watch, "FRIENDLY_CONTACT", key).json()["error"]["code"] == (
        "idempotency_conflict"
    )
    assert fleet_view(a, watch)["protocol"] == "SURVEILLANCE"
    # Not enabled by v0.9 yet (runtime not implemented): never silently accepted.
    assert protocol(a, watch, "AMBUSH").json()["error"]["code"] == "protocol_unavailable"
    assert protocol(a, watch, "INTERCEPTION").json()["error"]["code"] == "protocol_unavailable"
    assert protocol(a, watch, "FRIENDLY_CONTACT").status_code == 200
    assert fleet_view(a, watch)["protocol"] == "FRIENDLY_CONTACT"
    assert protocol(a, watch, None).status_code == 200
    assert fleet_view(a, watch)["protocol"] is None
    # A garrison never holds a protocol.
    garrison = next(f for f in view(a).json()["fleets"] if f["kind"] == "GARRISON")
    assert protocol(a, garrison["id"], "SURVEILLANCE").json()["error"]["code"] == "protocol_task"
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
    with pytest.raises(IntegrityError), a.game.factory.begin() as s:
        garrison = s.scalar(
            select(Fleet).where(Fleet.empire_id == a.empire, Fleet.kind == "GARRISON")
        )
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


def test_surveillance_detects_a_real_entry_mutually_and_anonymously_at_its_instant(fleets):
    a, b, watch, mission_id, entry = encounter(fleets)
    assert rows(a) == []  # nothing before the logical entry instant
    a.game.test_clock[0] = entry.entered_at + timedelta(minutes=5)  # worker late: same result
    worker(b, limit=50)
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


def test_detection_replay_never_duplicates(fleets):
    from app.frontier.service import complete_passage
    from app.simulation.models import ScheduledEvent

    a, b, _, mission_id, entry = encounter(fleets)
    a.game.test_clock[0] = entry.entered_at
    worker(b, limit=50)
    with a.game.factory.begin() as s:
        event = s.scalar(
            select(ScheduledEvent).where(
                ScheduledEvent.idempotency_key == f"frontier-passage:{mission_id}:{entry.sequence}"
            )
        )
        complete_passage(s, event, entry.entered_at)  # replayed handler
    assert len(rows(a)) == 2


def test_identity_only_when_already_known_at_the_instant(fleets):
    a, b, _, _, entry = encounter(fleets)
    with a.game.factory.begin() as s:
        relations.record_contact(s, a.universe, a.empire, b.empire, "presence", a.game.clock())
    a.game.test_clock[0] = entry.entered_at
    worker(b, limit=50)
    assert detections(a)[0]["empire"]["id"] == str(b.empire)  # A knew B
    assert detections(b)[0]["empire"] is None  # B did not know A


def test_protocol_set_after_the_entry_never_detects_retroactively(fleets):
    a, b, watch, _, entry = encounter(fleets, protocol_late=True)
    a.game.test_clock[0] = entry.entered_at + timedelta(seconds=1)
    assert protocol_set(a, watch, "SURVEILLANCE").status_code == 200  # set after the entry
    worker(b, limit=50)
    assert rows(a) == []


def test_watcher_gone_before_the_entry_never_detects(fleets):
    a, b, watch, _, entry = encounter(fleets)
    deploy(a, watch, planet_of(b)[1], {"frigate": 1})
    with a.game.factory() as s:
        period = s.scalar(select(FleetProtocolPeriod).where(FleetProtocolPeriod.fleet_id == watch))
        assert period.ended_at is not None and period.ended_at < entry.entered_at
    a.game.test_clock[0] = entry.entered_at
    worker(b, limit=50)
    assert [d for d in rows(a) if d.watch_fleet_id == watch] == []


def test_cancelled_entry_never_detects(fleets):
    a, b, _, mission_id, entry = encounter(fleets)
    with b.game.factory() as s:
        mission = s.get(FleetMission, UUID(mission_id))
    b.game.test_clock[0] = mission.started_at + timedelta(seconds=1)
    recalled = post(b, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert recalled.status_code == 200
    a.game.test_clock[0] = entry.entered_at + timedelta(minutes=1)
    worker(b, limit=50)
    assert rows(a) == []


def test_friendly_contact_introduces_both_empires_after_the_encounter(fleets):
    a, b, _, _, entry = encounter(fleets, "FRIENDLY_CONTACT")
    a.game.test_clock[0] = entry.entered_at
    worker(b, limit=50)
    assert detections(a)[0]["friendly"] and detections(a)[0]["empire"]["id"] == str(b.empire)
    assert detections(b)[0]["empire"]["id"] == str(a.empire)
    # Contacts are materialised at read points (never inside the handler), dated at the encounter.
    for w in (a, b):
        path = f"/game/{w.universe}/relations/{w.empire}"
        assert w.client.get(path, headers={"X-Game-Request": "bootstrap"}).status_code == 200
    with a.game.factory() as s:
        for observer, observed in ((a.empire, b.empire), (b.empire, a.empire)):
            contact = s.get(RelationContact, (observer, observed))
            assert contact.first_source == "frontier" and contact.first_seen_at == entry.entered_at
            assert contact.presence_planet_id is None
