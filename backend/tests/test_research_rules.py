from copy import deepcopy

import pytest

from app.colony.rules import Ruleset, load_ruleset
from app.research.service import discounted


def test_catalogue_finite_tiers_and_v01_compatibility():
    old = load_ruleset()
    assert old.research is None
    rules = load_ruleset("v0.2")
    assert len(rules.research.technologies) == 8
    for domain in ["engineering", "energy", "computation", "xenoscience"]:
        first, second = [rules.research.technologies[f"{domain}_{n}"] for n in (1, 2)]
        assert first.reduction_bps == 500 and second.reduction_bps == 1000
        assert first.requires == [] and second.requires == [f"{domain}_1"]
    assert old.quote("data_node", 6) == rules.quote("data_node", 6)
    assert discounted(101, 500) == 96
    assert discounted(101, 1000) == 91


@pytest.mark.parametrize(
    "mutation",
    ["unknown", "cycle", "cost", "overflow", "duration", "effect", "version", "duplicate", "v01"],
)
def test_bad_catalogue_refused(mutation):
    data = deepcopy(load_ruleset("v0.2").model_dump())
    tech = data["research"]["technologies"]["engineering_1"]
    if mutation == "unknown":
        tech["requires"] = ["unknown"]
    if mutation == "cycle":
        tech["requires"] = ["engineering_2"]
    if mutation == "cost":
        tech["cost"] = {"alloys": 0, "flux": 0, "data": 0}
    if mutation == "overflow":
        tech["cost"]["data"] = 2**63 - 1
    if mutation == "duration":
        tech["duration_seconds"] = 0
    if mutation == "effect":
        tech["effect"] = "free_resources"
    if mutation == "version":
        data["research"]["version"] = "v9.0"
    if mutation == "duplicate":
        data["research"]["technologies"]["duplicate"] = tech
    if mutation == "v01":
        for key in ["resources", "colony", "catalogue"]:
            data[key]["version"] = "v0.1"
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)
