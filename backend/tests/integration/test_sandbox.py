"""Test game (sandbox, recette 10/11/2026) on real PostgreSQL: an almost finished world created
through the control plane, then resource and ship grants and instant completion."""

# ruff: noqa: F811
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_colony_api import Clock, World, game, set_access  # noqa: F401
from test_fleet import FULL
from test_game_sessions import apply, enter

from app.access.http import cookie_name
from app.colony.models import ColonyInfrastructure, ConstructionOrder
from app.fleet.models import Fleet, FleetStack, ShipOrder
from app.galaxy.models import GalaxySystem, SystemKnowledge
from app.main import create_app
from app.persistence.models import Colony
from app.relations.models import RelationContact
from app.research.models import AcquiredTechnology
from app.simulation.models import ResourceBalance

pytestmark = pytest.mark.integration
M = 1_000_000
RIGHTS = sorted({*FULL, "colony.cancel"})


def started(game, sandbox=True):
    universe, user, membership = uuid4(), uuid4(), uuid4()
    message = {
        "kind": "start_universe",
        "universe_id": str(universe),
        "name": "Partie de test",
        "seed": "sandbox-seed",
        "family": "solo",
        "ruleset": "v0.11",
        "size": 100,
        "profiles": ["expansionist"],
    }
    if sandbox:
        message["sandbox"] = True
    receipt = apply(game, message)
    empire = UUID(receipt["result"]["human_empire_id"])
    with game.factory() as s:
        colony = s.scalar(select(Colony.id).where(Colony.empire_id == empire))
    bindings = [{"empire_id": str(empire), "permissions": RIGHTS}]
    set_access(game, user, universe, membership, bindings)
    raw, _, _ = enter(game, (user, universe, membership))
    app = create_app(game.settings)
    app.state.session_factory, app.state.clock = game.factory, Clock(game)
    client = TestClient(app, base_url=game.settings.game_public_origin)
    client.cookies.set(cookie_name(universe), raw)
    return World(game, app, client, raw, user, universe, membership, empire, colony)


def sandbox(w, path="", body=None):
    url = f"/game/{w.universe}/sandbox/{w.empire}{path}"
    if body is None:
        return w.client.get(url, headers={"X-Game-Request": "bootstrap"})
    return w.client.post(url, headers=w.headers(), json=body)


def garrison(w):
    with w.game.factory() as s:
        fleet = s.scalar(select(Fleet.id).where(Fleet.home_colony_id == w.colony))
        return {
            r.ship_class: r.count
            for r in s.scalars(select(FleetStack).where(FleetStack.fleet_id == fleet))
        }


def levels(w):
    with w.game.factory() as s:
        return {
            r.infrastructure_type: r.level
            for r in s.scalars(
                select(ColonyInfrastructure).where(ColonyInfrastructure.colony_id == w.colony)
            )
        }


def test_a_test_game_starts_almost_finished_and_other_empires_stay_unknown(game):
    w = started(game)
    assert levels(w) == dict.fromkeys(
        [
            "extraction_complex",
            "flux_reactor",
            "data_node",
            "industrial_complex",
            "logistics_center",
            "orbital_shipyard",
            "research_center",
        ],
        10,
    )
    with game.factory() as s:
        assert s.scalar(
            select(func.count()).where(AcquiredTechnology.empire_id == w.empire)
        ) == 8
        systems = s.scalar(
            select(func.count()).where(GalaxySystem.universe_id == w.universe)
        )
        known = s.scalars(
            select(SystemKnowledge.state).where(SystemKnowledge.empire_id == w.empire)
        ).all()
        assert len(known) == systems and "DETECTED" not in known
        assert s.scalar(
            select(func.count()).where(RelationContact.observer_empire_id == w.empire)
        ) == 0
        assert s.get(ResourceBalance, (w.colony, "alloys")).stock == 250_000 * M
    assert garrison(w)["cruiser"] == 4 and garrison(w)["probe"] == 10
    galaxy = w.client.get(
        f"/game/{w.universe}/galaxy/{w.empire}", headers={"X-Game-Request": "bootstrap"}
    ).json()
    presences = galaxy["sandbox"]["presences"]
    assert len(presences) == 1 and presences[0]["empire"] == 1
    assert "name" not in presences[0]
    # Relations know nobody: the AI Empire is visible on the map, not a contact.
    status = sandbox(w).json()
    assert status["sandbox"] is True and status["colonies"][0]["id"] == str(w.colony)


def test_grants_set_stocks_within_capacity_and_add_ships(game):
    w = started(game)
    granted = sandbox(
        w, "/resources", {"colony_id": str(w.colony), "alloys": 100_000_000, "flux": 1234}
    )
    assert granted.status_code == 200, granted.text
    capacity = int(granted.json()["colonies"][0]["capacity"])
    with game.factory() as s:
        assert s.get(ResourceBalance, (w.colony, "alloys")).stock == capacity * M
        assert s.get(ResourceBalance, (w.colony, "flux")).stock == 1234 * M
        assert s.get(ResourceBalance, (w.colony, "data")).stock == 250_000 * M
    ships = sandbox(w, "/ships", {"colony_id": str(w.colony), "ships": {"probe": 5}})
    assert ships.status_code == 200, ships.text
    assert garrison(w)["probe"] == 15
    refused = sandbox(w, "/ships", {"colony_id": str(w.colony), "ships": {"titan": 1}})
    assert refused.status_code == 422


def test_finish_completes_queued_constructions_and_ship_orders_now(game):
    w = started(game)
    for kind, level in (("extraction_complex", 11), ("flux_reactor", 11)):
        sector = {"extraction_complex": 1, "flux_reactor": 2}[kind]
        built = w.client.post(
            f"/game/{w.universe}/colonies/{w.colony}/construction-orders",
            headers=w.headers(),
            json={"idempotency_key": uuid4().hex, "infrastructure_type": kind,
                  "sector_index": sector, "target_level": level},
        )
        assert built.status_code in (200, 201), built.text
    ordered = w.client.post(
        f"/game/{w.universe}/fleets/{w.empire}/orders",
        headers=w.headers(),
        json={"idempotency_key": uuid4().hex, "colony_id": str(w.colony),
              "ship_class": "frigate", "quantity": 3},
    )
    assert ordered.status_code in (200, 201), ordered.text
    done = sandbox(w, "/finish", {})
    assert done.status_code == 200, done.text
    assert done.json()["result"] == {"constructions": 2, "research": 0, "ships": 1}
    assert levels(w)["extraction_complex"] == 11 and levels(w)["flux_reactor"] == 11
    assert garrison(w)["frigate"] == 13
    with game.factory() as s:
        assert s.scalar(
            select(func.count()).where(
                ConstructionOrder.colony_id == w.colony, ConstructionOrder.status != "completed"
            )
        ) == 0
        assert s.scalar(select(ShipOrder.delivered).where(ShipOrder.colony_id == w.colony)) == 3
    # Nothing left: a second call completes nothing and fails nothing.
    again = sandbox(w, "/finish", {})
    assert again.json()["result"] == {"constructions": 0, "research": 0, "ships": 0}


def test_a_normal_game_never_offers_the_sandbox_tools(game):
    w = started(game, sandbox=False)
    assert sandbox(w).status_code == 404
    assert sandbox(w).json()["error"]["code"] == "sandbox_unavailable"
    refused = sandbox(w, "/resources", {"colony_id": str(w.colony), "alloys": 1})
    assert refused.status_code == 404
    galaxy = w.client.get(
        f"/game/{w.universe}/galaxy/{w.empire}", headers={"X-Game-Request": "bootstrap"}
    ).json()
    assert "sandbox" not in galaxy
    assert levels(w)["extraction_complex"] == 1
