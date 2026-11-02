"""Ruleset v0.9 (13B): a full copy of v0.8 plus validated frontier vocabulary only."""

import pytest

from app.ai.rules import AIRulesV3, AIRulesV4, fingerprint
from app.colony.rules import Ruleset, load_ruleset
from app.frontier.rules import PROTOCOLS


def test_v09_is_v08_plus_frontier_and_ai_policy_v4_only():
    old, new = load_ruleset("v0.8").model_dump(), load_ruleset("v0.9").model_dump()
    for part in old:
        if part == "frontier" or old[part] is None:
            assert part == "frontier" or new[part] is None, part
            continue
        if part == "ai":  # B08: policy v4 = v3 + frontier protocol choices, nothing else
            ai = {k: v for k, v in new["ai"].items() if k != "frontier"}
            assert {**ai, "version": "v0.8", "policy_version": "utility-goals-v3"} == old["ai"]
            continue
        assert {**new[part], "version": "v0.8"} == old[part], part
    assert old["frontier"] is None
    # The four protocols are implemented; the only number is D4's validated 72 h window.
    assert new["frontier"] == {
        "version": "v0.9",
        "frontier_version": "frontier-v1",
        "protocols": ["SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT"],
        "ambush_hostility_seconds": 72 * 3600,
    }
    assert type(load_ruleset("v0.9").ai) is AIRulesV4
    assert type(load_ruleset("v0.8").ai) is AIRulesV3


def test_ai_frontier_policy_matches_the_validated_b08_rules():
    policy = load_ruleset("v0.9").ai.frontier
    assert policy.protocols == {
        "economic_cautious": ["SURVEILLANCE", "FRIENDLY_CONTACT"],
        "expansionist": ["SURVEILLANCE", "AMBUSH", "FRIENDLY_CONTACT"],
    }
    assert "military" in load_ruleset("v0.9").ai.goals  # protocols live in the military family
    assert load_ruleset("v0.9").ai.family_pages == load_ruleset("v0.8").ai.family_pages


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["ai"]["frontier"]["protocols"]["economic_cautious"].append("AMBUSH"),
        lambda d: d["ai"]["frontier"]["protocols"]["expansionist"].append("INTERCEPTION"),
        lambda d: d["ai"]["frontier"]["protocols"].update(expansionist=["AMBUSH"]),
        lambda d: d["ai"]["frontier"]["protocols"].update(
            expansionist=["SURVEILLANCE", "SURVEILLANCE"]
        ),
        lambda d: d["ai"]["frontier"]["protocols"].pop("expansionist"),
        lambda d: d["ai"].update(policy_version="utility-goals-v3"),
        lambda d: d["ai"].pop("frontier"),
        lambda d: d["ai"]["frontier"].update(ambush_utility=1001),
    ],
)
def test_invalid_ai_frontier_policy_is_refused(change):
    data = load_ruleset("v0.9").model_dump()
    change(data)
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)


def test_historical_rulesets_and_pinned_ai_digests_are_unchanged():
    for version in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5", "v0.6", "v0.7", "v0.8"):
        rules = load_ruleset(version)
        assert rules.frontier is None
        assert Ruleset.model_validate(rules.model_dump()) == rules
    v08 = load_ruleset("v0.8").ai.model_dump()
    assert v08["version"] == "v0.8" and fingerprint(v08) == fingerprint(dict(v08))


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(frontier=None),
        lambda d: d["frontier"].update(version="v0.8"),
        lambda d: d["frontier"].update(protocols=[]),
        lambda d: d["frontier"].update(protocols=["SURVEILLANCE", "SURVEILLANCE"]),
        lambda d: d["frontier"].update(protocols=["FRIENDLY_CONTACT", "SURVEILLANCE"]),
        lambda d: d["frontier"].update(protocols=["PATROL"]),
        lambda d: d["frontier"].update(frontier_version="frontier-v2"),
        lambda d: d["frontier"].update(detection_level=1),
        lambda d: d["frontier"].update(ambush_hostility_seconds=0),
        lambda d: d["frontier"].pop("ambush_hostility_seconds"),
    ],
)
def test_invalid_frontier_configuration_is_refused(change):
    data = load_ruleset("v0.9").model_dump()
    change(data)
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)


def test_frontier_never_appears_before_v09():
    data = load_ruleset("v0.8").model_dump()
    data["frontier"] = load_ruleset("v0.9").model_dump()["frontier"] | {"version": "v0.8"}
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)
    assert PROTOCOLS == ("SURVEILLANCE", "AMBUSH", "INTERCEPTION", "FRIENDLY_CONTACT")
