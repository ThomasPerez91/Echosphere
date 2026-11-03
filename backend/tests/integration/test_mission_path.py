"""UX-API-01 on real PostgreSQL + GameSession: `path` in mission previews and projections.

The path is the server's own route (known_path at quote time, persisted legs afterwards), read
from the Empire's Knowledge only, never recomputed on a GET and never invented.
"""

# ruff: noqa: F811
from collections import deque
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_colonization import EXPAND, colonize, home_system, station
from test_colony_api import Clock, game  # noqa: F401
from test_combat import arm, attack, launched, planet_of, resolve_due, until_battle
from test_fleet import built, detected, fleets, post, rebind, view, worker  # noqa: F401
from test_frontier import (
    chain,
    entries,
    fight,
    friendly_home,
    meet,
    passages,
    reenter,
    rivals,
)
from test_frontier import (
    deploy as deploy_units,
)

from app.fleet.models import Fleet, FleetMission, FleetMissionLeg
from app.galaxy import service as g
from app.galaxy.models import GalaxyRoute, SystemKnowledge
from app.simulation.models import ScheduledEvent

pytestmark = pytest.mark.integration


def preview(w, fleet, kind, units, destination=None, planet=None):
    body = {"fleet_id": str(fleet), "kind": kind, "units": units}
    if destination:
        body["destination_id"] = str(destination)
    if planet:
        body["target_planet_id"] = str(planet)
    return post(w, "/missions/preview", body)


def mission_json(w, mission_id):
    return next(m for m in view(w).json()["missions"] if m["id"] == mission_id)


def persisted(w, mission_id):
    """[origin, every system entered along the persisted legs] as strings."""
    mission, systems = chain(w, mission_id)
    return [str(mission.origin_id), *map(str, systems)]


def route_pairs(w):
    with w.game.factory() as s:
        return {
            frozenset((r.a_id, r.b_id))
            for r in s.scalars(select(GalaxyRoute).where(GalaxyRoute.universe_id == w.universe))
        }


def known(w):
    with w.game.factory() as s:
        return {
            str(k.system_id)
            for k in s.scalars(select(SystemKnowledge).where(SystemKnowledge.empire_id == w.empire))
        }


def coherent(w, path, origin, destination, hops):
    assert path[0] == str(origin) and path[-1] == str(destination)
    assert len(path) == hops + 1
    pairs = route_pairs(w)
    assert all(frozenset((UUID(x), UUID(y))) in pairs for x, y in zip(path, path[1:], strict=False))
    assert set(path) <= known(w)  # Fog of War: only systems this Empire knows


def farthest(w, origin):
    """The system the most hops away on the real route graph (all of it is known to rivals)."""
    graph = {}
    for pair in route_pairs(w):
        a, b = tuple(pair)
        graph.setdefault(a, []).append(b)
        graph.setdefault(b, []).append(a)
    depth, queue = {origin: 0}, deque([origin])
    while queue:
        node = queue.popleft()
        for other in graph.get(node, []):
            if other not in depth:
                depth[other] = depth[node] + 1
                queue.append(other)
    return max(depth, key=lambda s: (depth[s], str(s)))


def frozen(w, mission_id):
    """Everything a GET must never change for this mission."""
    with w.game.factory() as s:
        m = s.get(FleetMission, UUID(mission_id))
        legs = s.scalars(
            select(FleetMissionLeg.route_id)
            .where(FleetMissionLeg.mission_id == m.id)
            .order_by(FleetMissionLeg.ordinal)
        ).all()
        pending = s.scalar(
            select(func.count())
            .select_from(ScheduledEvent)
            .where(ScheduledEvent.status == "pending")
        )
        return m.status, m.snapshot, m.recalled_at, m.return_at, m.completed_at, legs, pending


def test_multi_hop_preview_path_is_the_launched_and_persisted_route(fleets):
    a, _ = rivals(fleets)
    _, home = planet_of(a)
    target = farthest(a, home)
    strike = arm(a, {"frigate": 1})
    quote = preview(a, strike, "DEPLOY", {"frigate": 1}, destination=target).json()
    assert quote["hops"] >= 2
    coherent(a, quote["path"], home, target, quote["hops"])
    mission_id, _ = deploy_units(a, strike, target, {"frigate": 1})
    shown = mission_json(a, mission_id)
    assert shown["path"] == quote["path"] == persisted(a, mission_id)
    assert shown["hops"] == len(shown["path"]) - 1
    # Reading twice changes nothing: no catch-up, no event, no rewritten mission.
    before = frozen(a, mission_id)
    assert view(a).status_code == view(a).status_code == 200
    assert frozen(a, mission_id) == before


def test_a_get_never_recomputes_the_route_and_withholds_a_drifted_one(fleets, monkeypatch):
    a, _ = rivals(fleets)
    _, home = planet_of(a)
    target = farthest(a, home)
    strike = arm(a, {"frigate": 1})
    mission_id, _ = deploy_units(a, strike, target, {"frigate": 1})
    expected = persisted(a, mission_id)
    assert len(expected) >= 3  # at least two legs, so a reversed chain really differs

    def no_route(*args, **kwargs):
        raise AssertionError("a projection must not compute a route")

    monkeypatch.setattr(g, "known_path", no_route)
    assert mission_json(a, mission_id)["path"] == expected
    monkeypatch.undo()
    # Legs that no longer match the accepted snapshot: the field is withheld, nothing else moves.
    with a.game.factory.begin() as s:
        m = s.get(FleetMission, UUID(mission_id))
        m.snapshot = {**m.snapshot, "path": list(reversed(m.snapshot["path"]))}
    shown = mission_json(a, mission_id)
    assert "path" not in shown and shown["status"] == "active"


def test_recall_keeps_the_outbound_path_and_the_way_back_retraces_it(fleets):
    a, _ = rivals(fleets)
    _, home = planet_of(a)
    target = farthest(a, home)
    strike = arm(a, {"frigate": 1})
    mission_id, _ = deploy_units(a, strike, target, {"frigate": 1})
    path = persisted(a, mission_id)
    mission, _ = chain(a, mission_id)
    a.game.test_clock[0] = mission.started_at + (mission.travel_arrival_at - mission.started_at) / 2
    entries(a)
    reenter(a)
    recalled = post(a, f"/missions/{mission_id}/recall", {"idempotency_key": uuid4().hex})
    assert recalled.status_code == 200
    shown = mission_json(a, mission_id)
    assert shown["status"] == "returning" and shown["path"] == path
    # Engine fact (13B): the way back enters the reached systems in reverse, ending at the origin.
    back = [str(p.system_id) for p in passages(a, mission_id) if p.direction == "return"]
    assert back[-1] == path[0] and back == list(reversed(path[: len(back)]))
    with a.game.factory() as s:
        a.game.test_clock[0] = s.get(FleetMission, UUID(mission_id)).return_at + timedelta(
            seconds=1
        )
    for _ in range(10):
        if not entries(a) and worker(a) == 0:
            break
    reenter(a)  # the access window lapsed during the long wait
    done = mission_json(a, mission_id)
    assert done["status"] == "completed" and done["path"] == path


def test_attack_path_survives_the_battle_and_the_return(fleets):
    a, b = rivals(fleets)
    planet, system = planet_of(b)
    _, home = planet_of(a)
    strike = arm(a, {"frigate": 3})
    quote = preview(a, strike, "ATTACK", {"frigate": 3}, planet=planet).json()
    coherent(a, quote["path"], home, system, quote["hops"])
    mission_id, _ = launched(a, attack(a, strike, planet, {"frigate": 3}))
    assert mission_json(a, mission_id)["path"] == quote["path"]
    until_battle(a, mission_id)
    entries(a)
    assert resolve_due(a) is not None  # the battle happened (its outcome is Combat's business)
    reenter(a, b)
    shown = mission_json(a, mission_id)
    assert shown["status"] == "returning" and shown["path"] == quote["path"]
    # The defender never sees the attacker's route.
    assert all(m["fleet_id"] != shown["fleet_id"] for m in view(b).json()["missions"])


def test_zero_hop_colonize_path_is_the_departure_system_only(fleets):
    w = fleets(permissions=EXPAND, ruleset="v0.5")
    system = home_system(w)
    fleet = station(w, system["id"])
    planet = next(p["id"] for p in system["planets"] if p["colony_id"] is None)
    quote = preview(w, fleet, "COLONIZE", {"colonizer": 1}, planet=planet).json()
    assert quote["hops"] == 0 and quote["path"] == [system["id"]]
    mission_id = colonize(w, fleet, planet).json()["result"]["mission_id"]
    assert mission_json(w, mission_id)["path"] == [system["id"]]


def test_v04_survey_path_ends_on_the_anonymous_signal(fleets):
    w = fleets()  # historical v0.4 ruleset: the field works without Combat or Frontier
    home = built(w)
    target = detected(w)
    quote = preview(w, home["id"], "SURVEY", {"probe": 1}, destination=target).json()
    origin = home["system"]["id"]
    coherent(w, quote["path"], origin, target, quote["hops"])
    body = post(
        w,
        "/missions",
        {
            "idempotency_key": uuid4().hex,
            "fleet_id": home["id"],
            "kind": "SURVEY",
            "destination_id": target,
            "units": {"probe": 1},
        },
    ).json()
    shown = mission_json(w, body["result"]["mission_id"])
    assert shown["path"] == quote["path"]
    assert shown["destination"] == {"id": target, "state": "DETECTED"}  # still no name


def test_intercepted_mover_keeps_only_its_own_route(fleets):
    a, b, _, mission_id, fleet_id, entry = meet(
        fleets, "INTERCEPTION", {"frigate": 4}, {"interceptor": 1}
    )
    assert fight(a, entry, timedelta(minutes=1)) == ["fought"]
    with b.game.factory() as s:
        assert s.get(Fleet, UUID(fleet_id)).status == "DESTROYED"
    shown = mission_json(b, mission_id)
    assert shown["status"] == "completed" and shown["path"] == persisted(b, mission_id)
    assert all(m["id"] != mission_id for m in view(a).json()["missions"])


def test_retreat_mission_exposes_its_own_route(fleets):
    a, b, friend, neighbour = friendly_home(fleets)
    planet, home = planet_of(a)
    raid = arm(b, {"interceptor": 1})
    raid_id, _ = launched(b, attack(b, raid, planet, {"interceptor": 1}))
    entry = [p for p in passages(b, raid_id) if p.direction == "outbound"][-1]
    a.game.test_clock[0] = entry.entered_at + timedelta(minutes=3)
    entries(a)
    reenter(a, b)
    with a.game.factory() as s:
        retreat_id = str(s.get(Fleet, friend).active_mission_id)
    shown = mission_json(a, retreat_id)
    assert shown["path"] == persisted(a, retreat_id) == [str(home), str(neighbour)]


def test_other_empires_and_universes_never_see_or_preview_a_route(fleets):
    a, b = rivals(fleets)
    strike = arm(a, {"frigate": 1})
    target = farthest(a, planet_of(a)[1])
    mission_id, _ = deploy_units(a, strike, target, {"frigate": 1})
    assert all(m["id"] != mission_id for m in view(b).json()["missions"])
    foreign = preview(b, strike, "DEPLOY", {"frigate": 1}, destination=target)
    absent = preview(b, uuid4(), "DEPLOY", {"frigate": 1}, destination=target)
    assert foreign.status_code == absent.status_code == 404
    assert foreign.json() == absent.json()
    elsewhere = fleets()
    response = elsewhere.client.post(
        f"/game/{elsewhere.universe}/fleets/{elsewhere.empire}/missions/preview",
        headers=elsewhere.headers(),
        json={
            "fleet_id": str(strike),
            "kind": "DEPLOY",
            "units": {"frigate": 1},
            "destination_id": str(target),
        },
    )
    assert response.status_code == 404
    # A reader without command rights still only gets ids of systems its Empire knows.
    rebind(a, ["fleet.read"])
    shown = mission_json(a, mission_id)
    assert set(shown["path"]) <= known(a)
