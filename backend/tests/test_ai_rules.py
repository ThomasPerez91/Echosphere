from copy import deepcopy

import pytest

from app.colony.rules import Ruleset, load_ruleset


def test_v06_only_adds_pinned_ai_configuration_and_preserves_all_gameplay():
    before, after = load_ruleset("v0.5"), load_ruleset("v0.6")
    for key, value in before.model_dump().items():
        if key == "ai":
            continue
        expected = deepcopy(value)
        if isinstance(expected, dict) and "version" in expected:
            expected["version"] = "v0.6"
        assert after.model_dump()[key] == expected
    assert after.ai.profiles["expansionist"]["expansion"] == 35
    for version in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5"):
        old = load_ruleset(version).model_dump()
        old.pop("ai")  # persisted JSON before AI still loads
        assert Ruleset.model_validate(old).ai is None
        with pytest.raises(ValueError):
            Ruleset.model_validate(old | {"ai": after.ai.model_dump()})


@pytest.mark.parametrize(
    "key,value",
    [
        ("ai", None),
        ("ai", {}),
        ("cadence_seconds", 601),
        ("candidate_limit", 129),
        ("fleet_page_size", True),
        ("profiles", {"aggressive": {}}),
        ("family_pages", {"economy": 129}),
        ("unknown", 1),
    ],
)
def test_ai_configuration_is_strict_and_bounded(key, value):
    data = load_ruleset("v0.6").model_dump()
    if key == "ai":
        data[key] = value
    else:
        data["ai"][key] = value
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)
