"""COL-11 on real PostgreSQL: v0.11 colony starts, guided unlocks, level cap, Chantier orbital
for ships and Centre de recherche for technologies."""

# ruff: noqa: F811
from uuid import uuid4

import pytest
from test_colony_api import Clock, game  # noqa: F401
from test_fleet import FULL, fleets, order, view, worker  # noqa: F401
from test_research import send

from app.colony.models import ColonyInfrastructure
from app.colony.service import ColonyError, colony_state, plan_order, rules_for
from app.persistence.models import Colony

pytestmark = pytest.mark.integration


def colony(w):
    return w.client.get(
        f"/game/{w.universe}/colonies/{w.colony}", headers={"X-Game-Request": "bootstrap"}
    ).json()


def build(w, kind, sector, level):
    return w.client.post(
        f"/game/{w.universe}/colonies/{w.colony}/construction-orders",
        headers=w.headers(),
        json={"idempotency_key": uuid4().hex, "infrastructure_type": kind,
              "sector_index": sector, "target_level": level},
    )


def set_level(w, kind, level, sector):
    with w.game.factory.begin() as s:
        row = (
            s.query(ColonyInfrastructure)
            .filter_by(colony_id=w.colony, sector_index=sector)
            .first()
        )
        if row is None:
            s.add(ColonyInfrastructure(colony_id=w.colony, universe_id=w.universe,
                                       sector_index=sector, infrastructure_type=kind, level=level))
        else:
            row.infrastructure_type, row.level = kind, level


def test_a_v011_colony_unlocks_ships_and_research_in_a_guided_order(fleets):
    w = fleets(permissions=FULL, ruleset="v0.11")
    view_ = colony(w)
    assert sorted(i["infrastructure_type"] for i in view_["infrastructures"]) == [
        "data_node", "extraction_complex", "flux_reactor"]
    options = {o["infrastructure_type"]: o for o in view_["options"] if o["action"] == "build"}
    assert options["orbital_shipyard"]["reason"] == "prerequisites_unmet"
    assert options["research_center"]["reason"] == "prerequisites_unmet"
    # No Chantier orbital: no ship; no Centre de recherche: no research.
    refused = order(w, "probe")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "shipyard_required"
    research = send(w)
    assert research.status_code == 409
    assert research.json()["error"]["code"] == "research_center_required"
    # Industrial complex 2 unlocks the shipyard; shipyard 1 unlocks the probe, not the cruiser.
    set_level(w, "industrial_complex", 2, 4)
    set_level(w, "orbital_shipyard", 1, 5)
    assert order(w, "probe").status_code == 200
    cruiser = order(w, "cruiser")
    assert cruiser.json()["error"]["code"] == "shipyard_required"
    # Data node 3 unlocks the research centre; level 1 opens tier 1 technologies.
    set_level(w, "data_node", 3, 3)
    set_level(w, "research_center", 1, 6)
    assert send(w).status_code == 200
    # Unique key buildings: a second shipyard is refused.
    second = build(w, "orbital_shipyard", 7, 1)
    assert second.status_code == 409 and second.json()["error"]["code"] == "unique_limit"


def test_the_planet_size_caps_every_building_level(fleets):
    w = fleets(permissions=FULL, ruleset="v0.11")
    with w.game.factory() as s:
        rules = rules_for(s, w.universe)
        state = colony_state(s, s.get(Colony, w.colony))
        cap = rules.colony.level_cap.cap(state.planet.sector_capacity)
    set_level(w, "extraction_complex", cap, 1)
    with w.game.factory() as s:
        state = colony_state(s, s.get(Colony, w.colony))
        with pytest.raises(ColonyError) as error:
            plan_order(rules, state, "extraction_complex", 1, cap + 1)
    assert error.value.code == "level_cap_reached"
    upgrade = next(o for o in colony(w)["options"]
                   if o["action"] == "upgrade" and o["sector_index"] == 1)
    assert upgrade["reason"] == "level_cap_reached"
