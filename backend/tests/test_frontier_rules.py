"""Ruleset v0.9 (13B): a full copy of v0.8 plus validated frontier vocabulary only."""

import pytest

from app.ai.rules import AIRulesV3, fingerprint
from app.colony.rules import Ruleset, load_ruleset
from app.frontier.rules import PROTOCOLS


def test_v09_is_v08_plus_frontier_only():
    old, new = load_ruleset("v0.8").model_dump(), load_ruleset("v0.9").model_dump()
    for part in old:
        if part == "frontier" or old[part] is None:
            assert part == "frontier" or new[part] is None, part
            continue
        assert {**new[part], "version": "v0.8"} == old[part], part
    assert old["frontier"] is None
    # Only protocols whose runtime exists are enabled; nothing numeric is invented (Q58 open).
    assert new["frontier"] == {
        "version": "v0.9",
        "frontier_version": "frontier-v1",
        "protocols": ["SURVEILLANCE", "FRIENDLY_CONTACT"],
    }
    assert type(load_ruleset("v0.9").ai) is AIRulesV3


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
