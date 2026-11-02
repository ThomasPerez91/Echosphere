from copy import deepcopy

import pytest

from app.colony.rules import load_ruleset
from app.combat.resolver import CombatInputError, allocate_losses, resolve, spec_from_rules

RULES = load_ruleset("v0.7").combat


def fight(attacker, defender, rules=RULES):
    return resolve(spec_from_rules(rules, attacker, defender))


def test_v07_catalogue_matchups_and_exact_round_arithmetic():
    # 1 interceptor vs 1 cruiser: 50 x 15000 = 750 000 per round vs 8 000 000 hull points;
    # the cruiser answers 260 x 7500 = 1 950 000 >= 1 000 000 and kills it in round 1.
    result = fight({"interceptor": 1}, {"cruiser": 1})
    assert result["outcome"] == "defender_win" and len(result["rounds"]) == 1
    first = result["rounds"][0]
    assert first["damage"]["attacker"]["cruiser"] == 750_000
    assert first["damage"]["defender"]["interceptor"] == 1_950_000
    assert result["survivors"]["defender"] == {"interceptor": 0, "frigate": 0, "cruiser": 1}


@pytest.mark.parametrize(
    "strong,weak", [("interceptor", "cruiser"), ("frigate", "interceptor"), ("cruiser", "frigate")]
)
def test_each_counter_wins_an_equal_cost_matchup(strong, weak):
    # Rock-paper-scissors at an equal Alloys budget (180/450/1000 per unit): the counter wins.
    budget = {"interceptor": 50, "frigate": 20, "cruiser": 9}
    assert fight({strong: budget[strong]}, {weak: budget[weak]})["outcome"] == "attacker_win"
    assert fight({weak: budget[weak]}, {strong: budget[strong]})["outcome"] == "defender_win"


def test_symmetry_mutual_destruction_and_simultaneous_losses():
    # No first strike: identical forces destroy each other in the same round.
    result = fight({"interceptor": 4}, {"interceptor": 4})
    assert result["outcome"] == "mutual_destruction"
    assert result["survivors"] == {
        "attacker": {"interceptor": 0, "frigate": 0, "cruiser": 0},
        "defender": {"interceptor": 0, "frigate": 0, "cruiser": 0},
    }
    mirrored = fight({"frigate": 3, "cruiser": 2}, {"frigate": 3, "cruiser": 2})
    assert mirrored["losses"]["attacker"] == mirrored["losses"]["defender"]


def test_partial_damage_accumulates_across_rounds_and_extinct_surplus_is_lost():
    # 1 frigate vs 1 frigate: 1 000 000 per round vs 3 000 000 → both die in round 3.
    result = fight({"frigate": 1}, {"frigate": 1})
    assert [r["losses"]["defender"]["frigate"] for r in result["rounds"]] == [0, 0, 1]
    assert result["outcome"] == "mutual_destruction"
    # Overkill on a single interceptor is lost, never carried to another class.
    crushing = fight({"frigate": 20}, {"interceptor": 1, "cruiser": 1})
    assert crushing["rounds"][0]["losses"]["defender"] == {
        "interceptor": 1,
        "frigate": 0,
        "cruiser": 0,
    }


def test_targeting_uses_best_living_multiplier_in_canonical_order():
    result = fight({"interceptor": 2}, {"frigate": 5, "cruiser": 1})
    assert result["rounds"][0]["targets"]["attacker"] == {"interceptor": "cruiser"}
    # Once cruisers are gone, interceptors fall back to the best remaining (frigate).
    later = [r for r in result["rounds"] if r["before"]["defender"]["cruiser"] == 0]
    assert all(r["targets"]["attacker"].get("interceptor") == "frigate" for r in later)
    # Equal multipliers fall back to the canonical class order, never dict or SQL order.
    data = load_ruleset("v0.7").model_dump()["combat"]
    data["matchups_bps"]["interceptor"] |= {"frigate": 9000, "cruiser": 9000, "interceptor": 100}
    spec = spec_from_rules(RULES, {"interceptor": 1}, {"frigate": 1, "cruiser": 1})
    spec["matchups_bps"] = data["matchups_bps"]
    spec["classes"] = ["interceptor", "frigate", "cruiser"]
    assert resolve(spec)["rounds"][0]["targets"]["attacker"]["interceptor"] == "frigate"


def test_strong_asymmetry_unopposed_and_input_bounds():
    assert fight({"cruiser": 20}, {"interceptor": 1})["rounds"][0]["losses"]["attacker"] == {
        "interceptor": 0,
        "frigate": 0,
        "cruiser": 0,
    }
    unopposed = fight({"interceptor": 3}, {})
    assert unopposed["outcome"] == "unopposed" and unopposed["rounds"] == []
    assert unopposed["survivors"]["attacker"]["interceptor"] == 3
    for attacker, defender in [({}, {"frigate": 1}), ({"probe": 1}, {}), ({"frigate": -1}, {})]:
        with pytest.raises(CombatInputError):
            fight(attacker, defender)
    spec = spec_from_rules(RULES, {"cruiser": 1}, {"cruiser": 1})
    spec["max_rounds"] = 1
    with pytest.raises(CombatInputError, match="round bound"):
        resolve(spec)


def test_replay_is_exact_pure_and_never_random():
    spec = spec_from_rules(RULES, {"interceptor": 7, "frigate": 3}, {"frigate": 4, "cruiser": 2})
    original = deepcopy(spec)
    runs = [resolve(spec) for _ in range(5)]
    assert all(run == runs[0] for run in runs) and spec == original
    # Large multi-round battles stay well inside the round bound.
    big = fight({"interceptor": 20, "frigate": 20, "cruiser": 20}, {"cruiser": 20, "frigate": 20})
    assert len(big["rounds"]) < 50


def test_largest_remainder_allocation_is_split_merge_neutral():
    fleets = {"b": {"frigate": 3}, "a": {"frigate": 3}, "c": {"frigate": 1}}
    # Quotas 12/7, 12/7, 4/7: floors 1, 1, 0; the two largest remainders (a, b tie) get +1.
    assert allocate_losses(fleets, {"frigate": 4}) == {
        "a": {"frigate": 2},
        "b": {"frigate": 2},
        "c": {},
    }
    assert allocate_losses({"x": {"frigate": 7}}, {"frigate": 4}) == {"x": {"frigate": 4}}
    full = allocate_losses(fleets, {"frigate": 7})
    assert full == {"a": {"frigate": 3}, "b": {"frigate": 3}, "c": {"frigate": 1}}
    with pytest.raises(CombatInputError):
        allocate_losses(fleets, {"frigate": 8})
