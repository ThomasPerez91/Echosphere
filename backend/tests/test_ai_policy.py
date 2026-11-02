from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from app.ai.controller import next_slot
from app.ai.policy import choose, circular_page
from app.colony.rules import load_ruleset


def candidate(key, goal, cost=0, bootstrap=False):
    return {
        "key": key,
        "goal": goal,
        "utility": 1000,
        "reason": None,
        "bootstrap": bootstrap,
        "cost": {"alloys": cost, "flux": 0, "data": 0},
        "duration_us": 10,
    }


def test_profiles_differ_and_choices_replay_without_mutating_input():
    rules = load_ruleset("v0.6").ai
    obs = {"candidates": [candidate("grow", "economy"), candidate("expand", "expansion")]}
    original = deepcopy(obs)
    assert choose(obs, {}, "economic_cautious", rules)["choice"] == "grow"
    assert choose(obs, {}, "expansionist", rules)["choice"] == "expand"
    assert choose(obs, {}, "expansionist", rules) == choose(original, {}, "expansionist", rules)
    assert obs == original
    obs["candidates"].reverse()
    assert choose(obs, {}, "economic_cautious", rules)["choice"] == "grow"


def test_lexical_cost_duration_and_stable_key_ties_and_bootstrap():
    rules = load_ruleset("v0.6").ai
    obs = {"candidates": [candidate("b", "economy", 2), candidate("a", "economy", 1)]}
    assert choose(obs, {}, "economic_cautious", rules)["choice"] == "a"
    obs["candidates"][0]["bootstrap"] = True
    assert choose(obs, {}, "economic_cautious", rules)["choice"] == "b"
    for c in obs["candidates"]:
        c["reason"] = "insufficient_resources"
    assert choose(obs, {}, "economic_cautious", rules)["choice"] is None


@pytest.mark.parametrize("count,page", [(250, 32), (65, 64), (128, 24), (3, 64), (1, 1)])
def test_circular_families_have_a_bounded_no_starvation_cover(count, page):
    cursor, seen = 0, set()
    values = list(range(count))
    for _ in range((count + page - 1) // page):
        batch, cursor = circular_page(values, cursor, page)
        assert len(batch) <= page and len(batch) == len(set(batch))
        seen.update(batch)
    assert seen == set(values)


def test_no_retroactive_turns_grid_does_not_drift():
    start = datetime(2099, 1, 1, tzinfo=UTC)
    assert next_slot(start, start + timedelta(hours=3, seconds=7)) == start + timedelta(
        hours=3, minutes=10
    )
    assert next_slot(start, start + timedelta(minutes=10)) == start + timedelta(minutes=20)


def test_v07_priority_defence_preempts_without_changing_v06_choices():
    rules = load_ruleset("v0.7").ai
    grow = candidate("grow", "economy")
    defend = candidate("defend", "military") | {"priority": True}
    assert (
        choose({"candidates": [grow, defend]}, {}, "economic_cautious", rules)["choice"] == "defend"
    )
    calm = candidate("defend", "military")
    assert choose({"candidates": [grow, calm]}, {}, "economic_cautious", rules)["choice"] == "grow"
    blocked = defend | {"reason": "insufficient_resources"}
    assert (
        choose({"candidates": [grow, blocked]}, {}, "economic_cautious", rules)["choice"] == "grow"
    )
