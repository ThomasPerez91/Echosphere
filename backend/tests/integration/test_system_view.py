"""System View: stored Knowledge only, current own links authorized separately."""

# ruff: noqa: F811
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_colony_api import game, set_access  # noqa: F401
from test_galaxy import detected, galaxy, read, send  # noqa: F401
from test_game_sessions import ticket

from app.access.http import cookie_name
from app.access.models import GameSession
from app.galaxy import service
from app.galaxy.models import (
    EmpireExploration,
    ExplorationMission,
    ExplorationReport,
    GalaxySystem,
    PlanetKnowledge,
    SystemKnowledge,
)
from app.persistence.models import Planet, StellarSystem
from app.simulation.models import EventStream, ScheduledEvent
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration


def origin(w):
    with w.game.factory() as s:
        return s.scalar(
            select(SystemKnowledge.system_id).where(
                SystemKnowledge.empire_id == w.empire, SystemKnowledge.state == "MONITORED"
            )
        )


def test_current_own_presence_has_snapshot_structure_and_authorized_colony_link(galaxy):
    w = galaxy()
    system_id = origin(w)
    with w.game.factory() as s:
        previous = s.scalar(
            select(GameSession.last_activity_at).where(GameSession.universe_id == w.universe)
        )
    w.advance(minutes=5)
    response = read(w, system_id)
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "MONITORED" and body["last_seen_at"] == w.game.clock().isoformat()
    link = body["colony_links"][0]
    assert link["colony_id"] == str(w.colony)
    assert link["planet_id"] in {p["id"] for p in body["planets"]}
    assert body["presences"][0]["colony"] == link
    assert body["presences"][0]["current"] is True
    assert len(body["routes"]) == 3
    assert all(
        r["neighbor"]["state"] == "DETECTED" and "name" not in r["neighbor"] for r in body["routes"]
    )
    with w.game.factory() as s:
        assert (
            s.scalar(
                select(GameSession.last_activity_at).where(GameSession.universe_id == w.universe)
            )
            == previous
        )
        # Current physical names/capacities do not enrich known structure.
    with w.game.factory.begin() as s:
        s.get(Planet, UUID(link["planet_id"])).name = "HIDDEN LIVE NAME"
        s.get(Planet, UUID(link["planet_id"])).sector_capacity = 99
        s.get(StellarSystem, system_id).name = "HIDDEN LIVE SYSTEM"
    newer = read(w, system_id).json()
    assert newer["planets"] == body["planets"] and newer["name"] == body["name"]
    assert "HIDDEN LIVE" not in str(newer)


def test_without_colony_read_observation_is_generic_and_has_no_protected_links(galaxy):
    w = galaxy(permissions=["galaxy.read"])
    body = read(w, origin(w)).json()
    assert body["presences"] and body["presences"][0]["kind"] == "own_colony"
    assert body["presences"][0]["colony"] is None
    assert body["colony_links"] == [] and body["permissions"] == ["galaxy.read"]
    # Only the pre-existing own_colony_ids observation is exposed, never a Colony record.
    assert not any(p.get("colony") for p in body["presences"])


def test_overdue_detail_get_cannot_finish_mission_or_advance_cursor(galaxy):
    w = galaxy()
    target = detected(w)
    mission = UUID(send(w, target).json()["mission_id"])
    with w.game.factory() as s:
        state = s.get(EmpireExploration, w.empire)
        cursor = s.get(EventStream, state.stream_id).cursor_at
    w.advance(minutes=60)
    detail = read(w, target).json()
    assert detail["state"] == "DETECTED"
    assert not {"name", "planets", "presences", "colony_links", "routes"} & detail.keys()
    with w.game.factory() as s:
        assert s.get(ExplorationMission, mission).status == "active"
        assert s.get(ExplorationReport, mission) is None
        assert s.get(EventStream, state.stream_id).cursor_at == cursor
        assert (
            s.scalar(
                select(ScheduledEvent.status).where(ScheduledEvent.stream_id == state.stream_id)
            )
            == "pending"
        )
    assert TimeEngine(w.game.factory, w.app.state.clock).process_next().status == "completed"
    mapped = read(w, target).json()
    assert mapped["state"] == "MAPPED" and mapped["planets"]
    assert mapped["presences"] == [] and mapped["colony_links"] == []


def test_mapped_old_observation_not_enriched_and_unknown_planets_never_joined(galaxy):
    w = galaxy()
    target = UUID(detected(w))
    with w.game.factory.begin() as s:
        service.catch_up(
            s, TimeEngine(w.game.factory, w.app.state.clock), w.universe, w.empire, w.game.clock()
        )
        service.map_system(s, w.universe, w.empire, target, w.game.clock())
        known = s.get(SystemKnowledge, (w.empire, target))
        known.state = "MONITORED"
        known.last_seen_at = w.game.clock() - timedelta(hours=1)
        known.observation = {"own_colony_ids": [str(w.colony)]}
        previous = known.last_seen_at
        unknown_planet = Planet(
            universe_id=w.universe,
            system_id=target,
            name="HIDDEN NEW WORLD",
            sector_capacity=18,
            orbital_capacity=3,
        )
        s.add(unknown_planet)
        expected = s.scalar(
            select(func.count())
            .select_from(PlanetKnowledge)
            .where(PlanetKnowledge.empire_id == w.empire, PlanetKnowledge.system_id == target)
        )
    body = read(w, target).json()
    assert body["state"] == "MAPPED" and body["last_seen_at"] == previous.isoformat()
    assert len(body["planets"]) == expected and "HIDDEN NEW WORLD" not in str(body)
    assert body["presences"][0] == {
        "kind": "own_colony",
        "current": False,
        "observed_at": previous.isoformat(),
        "colony": None,
    }
    assert body["colony_links"] == []


def test_unknown_foreign_absent_and_other_universe_are_non_enumerable(galaxy):
    w = galaxy()
    other = galaxy(universe=w.universe, other=True)
    foreign = origin(other)
    with w.game.factory() as s:
        known = set(
            s.scalars(
                select(SystemKnowledge.system_id).where(SystemKnowledge.empire_id == w.empire)
            )
        )
        hidden = next(
            i
            for i in s.scalars(
                select(GalaxySystem.system_id).where(GalaxySystem.universe_id == w.universe)
            )
            if i not in known
        )
    absent = read(w, uuid4())
    for identifier in [foreign, hidden]:
        response = read(w, identifier)
        assert response.status_code == absent.status_code == 404
        assert response.json() == absent.json()
    response = w.client.get(
        f"/game/{uuid4()}/galaxy/{w.empire}/systems/{origin(w)}",
        headers={"X-Game-Request": "bootstrap"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("case", ["no_read", "revoked", "expired", "foreign_empire", "no_binding"])
def test_scope_and_session_refusals(galaxy, case):
    w = galaxy()
    system_id = origin(w)
    if case in {"no_read", "revoked", "no_binding"}:
        bindings = (
            []
            if case == "no_binding"
            else [
                {
                    "empire_id": str(w.empire),
                    "permissions": ["colony.read"] if case == "no_read" else ["galaxy.read"],
                }
            ]
        )
        set_access(
            w.game,
            w.user,
            w.universe,
            w.membership,
            bindings,
            revision=2,
            epoch=2,
            status="suspended" if case == "revoked" else "active",
        )
        if case in {"no_read", "no_binding"}:
            encoded, pre, _ = ticket(
                w.game, (w.user, w.universe, w.membership), revision=2, access_epoch=2
            )
            raw, _ = w.game.exchange(encoded, pre, None, w.universe)
            w.client.cookies.set(cookie_name(w.universe), raw)
    elif case == "expired":
        w.advance(hours=9)
    if case == "foreign_empire":
        response = w.client.get(
            f"/game/{w.universe}/galaxy/{uuid4()}/systems/{system_id}",
            headers={"X-Game-Request": "bootstrap"},
        )
    else:
        response = read(w, system_id)
    assert response.status_code == (401 if case in {"revoked", "expired"} else 404)
    assert "planets" not in response.json()
