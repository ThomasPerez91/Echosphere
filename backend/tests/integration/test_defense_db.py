"""DEF-01 (ruleset v0.13) on real PostgreSQL: the Défense center and its network, modules built
through the colony queue on real sectors and orbital slots, their upkeep, the battle beside the
garrison, damaged modules and their repair."""

# ruff: noqa: F811
from datetime import timedelta
from uuid import uuid4

import pytest
from test_colony_api import game  # noqa: F401
from test_combat import arm, attack, launched, planet_of, resolve_due, until_battle
from test_contested_extraction import settle
from test_fleet import FULL, fleets  # noqa: F401
from test_relations import reenter, rivals

from app.colony.models import ColonyInfrastructure, ConstructionOrder
from app.colony.service import refresh_effects, rules_for
from app.combat.models import CombatEngagement, CombatReport
from app.defense.rules import ORBITAL_BASE
from app.simulation.models import ResourceBalance

pytestmark = pytest.mark.integration
M = 1_000_000


def colony(w):
    return w.client.get(
        f"/game/{w.universe}/colonies/{w.colony}", headers={"X-Game-Request": "bootstrap"}
    ).json()


def build(w, kind, sector, level=1):
    return w.client.post(
        f"/game/{w.universe}/colonies/{w.colony}/construction-orders",
        headers=w.headers(),
        json={"idempotency_key": uuid4().hex, "infrastructure_type": kind,
              "sector_index": sector, "target_level": level},
    )


def defended(w, modules=()):
    """Test world set-up: industry 2, a Défense center 1 on sector 8, funds, optional modules;
    rates follow the buildings as a completion would."""
    with w.game.factory.begin() as s:
        rows = [("industrial_complex", 7, 2, None), ("defense_center", 8, 1, None)]
        rows += [(kind, sector, 1, "operational") for kind, sector in modules]
        for kind, sector, level, condition in rows:
            s.add(ColonyInfrastructure(colony_id=w.colony, universe_id=w.universe,
                                       sector_index=sector, infrastructure_type=kind,
                                       level=level, condition=condition))
        for r in ("alloys", "flux", "data"):
            s.get(ResourceBalance, (w.colony, r)).stock = 9_000 * M
        s.flush()
        refresh_effects(s, w.colony, rules_for(s, w.universe))


def test_modules_are_built_on_real_sectors_and_slots_within_the_network(fleets):
    w = fleets(permissions=FULL, ruleset="v0.13")
    first = colony(w)
    assert first["defense"]["capacity"] == 0
    options = {o["infrastructure_type"]: o for o in first["options"] if o["action"] == "build"}
    assert options["defense_center"]["reason"] == "prerequisites_unmet"
    defended(w)
    view = colony(w)["defense"]
    assert (view["capacity"], view["used"], view["center_level"]) == (2, 0, 1)
    assert view["orbital"]["free_indices"][0] == ORBITAL_BASE + 1
    options = {o["infrastructure_type"]: o for o in colony(w)["options"] if o["action"] == "build"}
    assert options["orbital_platform"]["sector_index"] == ORBITAL_BASE + 1
    # An orbital module never takes a sector, a surface one never an orbital slot.
    wrong = build(w, "orbital_platform", 9)
    assert wrong.status_code == 409 and wrong.json()["error"]["code"] == "sector_unavailable"
    wrong = build(w, "point_defense", ORBITAL_BASE + 1)
    assert wrong.json()["error"]["code"] == "sector_unavailable"
    assert build(w, "point_defense", 9).status_code in (200, 201)
    assert build(w, "orbital_platform", ORBITAL_BASE + 1).status_code in (200, 201)
    full = build(w, "anti_ship_battery", 10)
    assert full.status_code == 409 and full.json()["error"]["code"] == "defense_capacity_full"
    w.advance(hours=3)
    after = colony(w)
    modules = {m["sector_index"]: m for m in after["defense"]["modules"]}
    assert modules[9]["condition"] == "operational"
    assert modules[ORBITAL_BASE + 1]["condition"] == "operational"
    # The orbital slot is not a sector.
    assert ORBITAL_BASE + 1 not in after["sectors"]["free_indices"]
    assert after["defense"]["upkeep_flux_per_hour"] == str(8 * M)
    again = build(w, "point_defense", 9, 2)
    assert again.json()["error"]["code"] == "module_level_fixed"


def test_modules_fight_beside_the_garrison_are_damaged_then_repaired(fleets):
    a, b = rivals(fleets, ruleset="v0.13")
    defended(b, [("point_defense", 9), ("point_defense", 10)])
    flux = next(r for r in colony(b)["resources"] if r["resource"] == "flux")
    planet, _ = planet_of(b)
    raid = arm(a, {"cruiser": 8})
    mission_id, _ = launched(a, attack(a, raid, planet, {"cruiser": 8}))
    until_battle(a, mission_id)
    reenter(a, b)
    settle(a, b)
    outcome = resolve_due(a)
    assert outcome["outcome"] == "attacker_win", outcome
    with a.game.factory() as s:
        engagement = s.query(CombatEngagement).one()
        assert engagement.snapshot["defender"]["modules"] == {
            "9": "point_defense", "10": "point_defense"}
        assert engagement.result["modules"] == {"fought": 2, "damaged_sectors": [9, 10]}
        seen = s.get(CombatReport, (engagement.id, a.empire)).result["opponent"]["initial"]
        assert seen["point_defense"] == 2  # the attacker observed the modules it fought
    reenter(b)
    view = colony(b)
    assert {m["condition"] for m in view["defense"]["modules"]} == {"damaged"}
    assert view["defense"]["upkeep_flux_per_hour"] == "0"
    now = next(r for r in view["resources"] if r["resource"] == "flux")
    assert int(now["rate_per_hour"]) > int(flux["rate_per_hour"])  # no upkeep while damaged
    repair = next(
        o for o in view["options"] if o["action"] == "repair" and o["sector_index"] == 9
    )
    assert repair["available"] and repair["cost"]["alloys"] == str(240 * M)
    assert build(b, "point_defense", 9, 1).status_code in (200, 201)
    with b.game.factory() as s:
        order = s.query(ConstructionOrder).filter_by(colony_id=b.colony, sector_index=9).one()
        assert order.snapshot["repair"] is True
    b.game.test_clock[0] = b.game.test_clock[0] + timedelta(hours=2)
    modules = {m["sector_index"]: m["condition"] for m in colony(b)["defense"]["modules"]}
    assert modules == {9: "operational", 10: "damaged"}


def test_older_rulesets_have_no_defense(fleets):
    w = fleets(permissions=FULL, ruleset="v0.12")
    view = colony(w)
    assert "defense" not in view
    assert all("condition" not in i for i in view["infrastructures"])
