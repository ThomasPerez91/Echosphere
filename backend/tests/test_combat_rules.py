import json
from pathlib import Path

import pytest

from app.ai.rules import AIRules, AIRulesV2, fingerprint
from app.colony.rules import Ruleset, load_ruleset


def test_v07_is_v06_plus_military_classes_combat_and_v2_policy():
    old, new = load_ruleset("v0.6").model_dump(), load_ruleset("v0.7").model_dump()
    assert old["combat"] is None and new["combat"]["min_warning_seconds"] == 86400
    for key in ("resources", "colony", "catalogue", "research", "galaxy", "colonization"):
        assert {k: v for k, v in old[key].items() if k != "version"} == {
            k: v for k, v in new[key].items() if k != "version"
        }
    added = set(new["fleets"]["classes"]) - set(old["fleets"]["classes"])
    assert added == {"interceptor", "frigate", "cruiser"}
    for ship in old["fleets"]["classes"]:
        assert old["fleets"]["classes"][ship] == new["fleets"]["classes"][ship]
    assert new["fleets"]["classes"]["frigate"] == {
        "name": "Frégate",
        "cost": {"alloys": 450, "flux": 200, "data": 80},
        "build_seconds": 3600,
        "hop_seconds": 1080,
        "flux_per_hop": 12,
        "cargo": 0,
        "survey": False,
    }
    weights = new["ai"]["profiles"]
    assert weights["economic_cautious"]["military"] == weights["expansionist"]["military"] == 10
    assert all(sum(w.values()) == 100 for w in weights.values())


def test_historical_rulesets_and_v06_policy_digest_are_unchanged():
    for version in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5", "v0.6"):
        assert load_ruleset(version).combat is None
    v06 = load_ruleset("v0.6")
    assert type(v06.ai) is AIRules and "military" not in v06.ai.model_dump()
    # Pinned v0.6 controllers compare this exact digest: it must not move with v0.7.
    raw = json.loads((Path(__file__).parents[2] / "game_data/rulesets/v0.6/ai.json").read_text())
    assert fingerprint(v06.ai.model_dump()) == fingerprint(AIRules.model_validate(raw).model_dump())
    assert type(load_ruleset("v0.7").ai) is AIRulesV2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("combat"),
        lambda d: d["combat"]["matchups_bps"]["frigate"].pop("cruiser"),
        lambda d: d["combat"].__setitem__("classes", ["interceptor", "frigate", "probe"]),
        lambda d: d["fleets"]["classes"]["frigate"].__setitem__("cargo", 10),
        lambda d: d["ai"]["military"].__setitem__("ship_class", "probe"),
        lambda d: d["ai"].pop("military"),
        lambda d: d["combat"]["stats"]["cruiser"].__setitem__("hull", 0),
        lambda d: d["combat"].__setitem__("extra", 1),
    ],
)
def test_v07_combat_data_is_strict(mutate):
    data = load_ruleset("v0.7").model_dump()
    mutate(data)
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)


def test_combat_refused_in_historical_rulesets():
    data = load_ruleset("v0.6").model_dump()
    data["combat"] = load_ruleset("v0.7").model_dump()["combat"] | {"version": "v0.6"}
    with pytest.raises(ValueError, match="Combat unavailable"):
        Ruleset.model_validate(data)
