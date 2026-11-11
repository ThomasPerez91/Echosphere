"""DEF-01 (ruleset v0.13, validated 11/11/2026): defense rules, Flux upkeep and disabling,
capacity, repairs and the module classes of combat, as pure functions."""

from types import SimpleNamespace as Row

import pytest
from pydantic import ValidationError

from app.colony.rules import Ruleset, load_ruleset
from app.colony.service import ColonyError
from app.combat.resolver import resolve, spec_from_rules
from app.defense.rules import ORBITAL_BASE
from app.defense.service import check_module, damage, power, repair_quote, slots, units
from app.simulation.production import MICRO_UNITS as M

V13 = load_ruleset("v0.13")
D = V13.defense


def module(kind, sector, condition="operational"):
    return Row(infrastructure_type=kind, sector_index=sector, level=1, condition=condition)


def test_v013_has_three_modules_and_older_rulesets_none():
    assert set(D.modules) == {"point_defense", "anti_ship_battery", "orbital_platform"}
    assert [D.modules[k].placement for k in sorted(D.modules)] == ["surface", "orbital", "surface"]
    assert V13.combat.all_classes[-3:] == ["point_defense", "anti_ship", "orbital_platform"]
    assert V13.catalogue.infrastructures["defense_center"].max_per_colony == 1
    for version in ("v0.11", "v0.12"):
        rules = load_ruleset(version)
        assert rules.defense is None and rules.combat.modules is None
        assert "modules" not in rules.combat.model_dump()
    mixed = load_ruleset("v0.12").model_dump()
    mixed["defense"] = V13.defense.model_dump() | {"version": "v0.12"}
    with pytest.raises(ValidationError):
        Ruleset.model_validate(mixed)


def test_orbital_modules_use_real_orbital_slots_and_the_rest_real_sectors():
    planet = Row(sector_capacity=12, orbital_capacity=2)
    assert list(slots(V13, planet, "orbital_platform")) == [ORBITAL_BASE + 1, ORBITAL_BASE + 2]
    assert list(slots(V13, planet, "point_defense")) == list(range(1, 13))
    assert list(slots(V13, planet, "flux_reactor")) == list(range(1, 13))


def test_the_network_capacity_counts_queued_modules_and_a_module_never_levels_up():
    center = Row(infrastructure_type="defense_center", sector_index=7, level=1, condition=None)
    state = Row(infrastructures=[center, module("point_defense", 8)], queue=[])
    projected = {7: ("defense_center", 1), 8: ("point_defense", 1)}
    check_module(V13, state, "orbital_platform", None, projected)  # 1 of 2
    projected[ORBITAL_BASE + 1] = ("orbital_platform", 1)  # a queued one counts
    with pytest.raises(ColonyError) as full:
        check_module(V13, state, "anti_ship_battery", None, projected)
    assert full.value.code == "defense_capacity_full"
    with pytest.raises(ColonyError) as fixed:
        check_module(V13, state, "point_defense", ("point_defense", 1), projected)
    assert fixed.value.code == "module_level_fixed"
    check_module(V13, state, "flux_reactor", None, projected)  # not a module: no limit
    no_center = Row(infrastructures=[], queue=[])
    with pytest.raises(ColonyError):
        check_module(V13, no_center, "point_defense", None, {})


def test_upkeep_disables_platforms_then_cannons_then_batteries_and_they_come_back():
    rows = [module("point_defense", 3), module("anti_ship_battery", 2),
            module("orbital_platform", ORBITAL_BASE + 1), module("point_defense", 5, "damaged")]
    # 12 Flux/h of upkeep (2 + 4 + 6); the damaged battery costs nothing.
    assert power(D, rows, 20 * M) == 8 * M
    assert [r.condition for r in rows] == ["operational"] * 3 + ["damaged"]
    assert power(D, rows, 7 * M) == 1 * M  # the platform (6/h) goes first
    assert [r.condition for r in rows][:3] == ["operational", "operational", "disabled"]
    assert power(D, rows, 3 * M) == 1 * M  # then the cannon
    assert [r.condition for r in rows][:3] == ["operational", "disabled", "disabled"]
    assert power(D, rows, 0) == 0 and rows[0].condition == "disabled"
    assert power(D, rows, 50 * M) == 38 * M and rows[2].condition == "operational"


def test_repairs_cost_forty_percent_and_last_half_the_time():
    quote = V13.quote("anti_ship_battery", 1)
    repair = repair_quote(D, quote)
    assert repair.cost == {"alloys": 360 * M, "flux": 160 * M, "data": 0}
    assert repair.base_duration_us == quote.base_duration_us // 2


def test_modules_fight_on_the_defender_side_and_their_losses_damage_them_in_order():
    modules = [module("point_defense", 3), module("point_defense", 4),
               module("orbital_platform", ORBITAL_BASE + 1)]
    defender = {"interceptor": 1} | units(V13, modules)
    assert defender == {"interceptor": 1, "point_defense": 2, "orbital_platform": 1}
    spec = spec_from_rules(V13.combat, {"cruiser": 8}, defender)
    assert spec["defender"]["orbital_platform"] == 1 and spec["attacker"]["point_defense"] == 0
    result = resolve(spec)
    lost = {c: n for c, n in result["losses"]["defender"].items() if c not in V13.combat.classes}
    hit = damage(V13, modules, lost)
    assert len(hit) == sum(lost.values()) > 0
    assert {r.sector_index for r in modules if r.condition == "damaged"} == set(hit)
