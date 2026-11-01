from copy import deepcopy

import pytest

from app.colony.rules import Ratio, Ruleset, load_ruleset

M = 1_000_000


def test_v04_is_v03_plus_fleets_without_abstract_expedition():
    old, rules = load_ruleset("v0.3"), load_ruleset("v0.4")
    assert old.fleets is None and old.exploration.engagement_version == "abstract-expedition-v1"
    assert rules.exploration is None and rules.fleets.survey_version == "fleet-survey-v1"
    for part in ["colony", "catalogue", "research", "galaxy", "resources"]:
        mine, theirs = rules.model_dump()[part], old.model_dump()[part]
        assert {**mine, "version": "v0.3"} == theirs
    for version in ["v0.1", "v0.2"]:
        assert load_ruleset(version).fleets is None
    probe, freighter = rules.fleets.classes["probe"], rules.fleets.classes["freighter"]
    assert (probe.build_seconds, probe.hop_seconds, probe.flux_per_hop, probe.cargo) == (
        1200,
        600,
        4,
        0,
    )
    assert (freighter.build_seconds, freighter.hop_seconds, freighter.cargo) == (2400, 1200, 500)


def test_batch_quote_is_atomic_and_ignores_fleet_speed():
    fleets = load_ruleset("v0.4").fleets
    cost, duration = fleets.order_quote("probe", 10)
    assert cost == {"alloys": 800 * M, "flux": 400 * M, "data": 400 * M}
    assert duration == 10 * 1200 * M
    for quantity in [0, 21, True]:
        with pytest.raises(ValueError):
            fleets.order_quote("probe", quantity)
    with pytest.raises(ValueError):
        fleets.order_quote("colonizer", 1)


def test_mission_quote_uses_slowest_class_hops_and_exact_speed_ratio():
    fleets = load_ruleset("v0.4").fleets
    normal = Ratio(numerator=1, denominator=1)
    cost, travel, survey = fleets.mission_quote({"probe": 2, "freighter": 1}, 3, normal, False)
    assert travel == 3 * 1200 * M and survey == 0
    assert cost == {"alloys": 0, "flux": 3 * (2 * 4 + 8) * M, "data": 0}
    cost, travel, survey = fleets.mission_quote({"probe": 1}, 2, normal, True)
    assert (travel, survey) == (2 * 600 * M, 900 * M)
    assert cost == {"alloys": 0, "flux": 8 * M, "data": 20 * M}
    # Universe Fleet speed shortens travel (ceil), never analysis nor production.
    _, fast, survey = fleets.mission_quote({"probe": 1}, 1, Ratio(numerator=3, denominator=1), True)
    assert fast == 200 * M and survey == 900 * M
    assert fleets.cargo_capacity({"probe": 4, "freighter": 3}) == 1500 * M
    for hops, stacks in [(0, {"probe": 1}), (1, {})]:
        with pytest.raises(ValueError):
            fleets.mission_quote(stacks, hops, normal, False)


@pytest.mark.parametrize(
    "mutation",
    [
        "exploration",
        "missing",
        "v03",
        "version",
        "no_survey",
        "cost",
        "overflow",
        "bool",
        "identifier",
        "extra",
        "queue",
    ],
)
def test_bad_fleet_rulesets_refused(mutation):
    data = deepcopy(load_ruleset("v0.4").model_dump())
    fleets = data["fleets"]
    probe = fleets["classes"]["probe"]
    if mutation == "exploration":
        data["exploration"] = load_ruleset("v0.3").exploration.model_dump() | {"version": "v0.4"}
    if mutation == "missing":
        data["fleets"] = None
    if mutation == "v03":
        historical = load_ruleset("v0.3").model_dump()
        historical["fleets"] = fleets | {"version": "v0.3"}
        data = historical
    if mutation == "version":
        fleets["version"] = "v0.3"
    if mutation == "no_survey":
        probe["survey"] = False
    if mutation == "cost":
        probe["cost"] = {"alloys": 0, "flux": 0, "data": 0}
    if mutation == "overflow":
        probe["cost"]["alloys"] = 2**62
    if mutation == "bool":
        probe["cargo"] = True
    if mutation == "identifier":
        fleets["classes"]["Probe!"] = probe
    if mutation == "extra":
        probe["attack"] = 3
    if mutation == "queue":
        fleets["queue_limit"] = 4
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)
