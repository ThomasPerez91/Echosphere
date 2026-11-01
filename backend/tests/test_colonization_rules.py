from copy import deepcopy

import pytest

from app.colony.rules import Ruleset, load_ruleset

M = 1_000_000


def test_v05_is_v04_plus_colonizer_and_colonization_only():
    old, rules = load_ruleset("v0.4"), load_ruleset("v0.5")
    for part in ["colony", "catalogue", "research", "galaxy", "resources"]:
        assert {**rules.model_dump()[part], "version": "v0.4"} == old.model_dump()[part]
    mine, theirs = rules.model_dump()["fleets"], old.model_dump()["fleets"]
    colonizer = mine["classes"].pop("colonizer")
    assert {**mine, "version": "v0.4"} == theirs
    assert colonizer == {
        "name": "Colonisateur",
        "cost": {"alloys": 1200, "flux": 600, "data": 300},
        "build_seconds": 10800,
        "hop_seconds": 1800,
        "flux_per_hop": 20,
        "cargo": 1000,
        "survey": False,
    }
    x = rules.colonization
    assert (x.colonizer_class, x.colonizer_max_quantity, x.max_colonies) == ("colonizer", 1, 12)
    assert x.package_minimum() == {"alloys": 500 * M, "flux": 250 * M, "data": 50 * M}
    for version in ["v0.1", "v0.2", "v0.3", "v0.4"]:
        assert load_ruleset(version).colonization is None


def test_progressive_colonizer_price_is_exact_and_rank_based():
    x = load_ruleset("v0.5").colonization
    assert [x.multiplier_bps(n) for n in (1, 2, 3, 8, 12)] == [10000, 15000, 20000, 45000, 65000]
    for rank in [0, -1, True, 1.0]:
        with pytest.raises(ValueError):
            x.multiplier_bps(rank)


def mutate(data, path, value):
    node = data
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value


@pytest.mark.parametrize(
    "path,value",
    [
        (("colonization",), None),
        (("colonization", "version"), "v0.4"),
        (("colonization", "colonizer_class"), "probe"),
        (("colonization", "colonizer_class"), "missing"),
        (("colonization", "colonizer_max_quantity"), 2),
        (("colonization", "max_active_missions"), 2),
        (("colonization", "minimum_package"), {"alloys": 900, "flux": 200, "data": 0}),
        (("colonization", "minimum_package"), {"alloys": 1}),
        (("fleets", "classes", "colonizer", "cargo"), 20000),
    ],
)
def test_bad_colonization_rulesets_refused(path, value):
    data = deepcopy(load_ruleset("v0.5").model_dump())
    mutate(data, path, value)
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)


def test_historical_rulesets_refuse_colonization():
    data = deepcopy(load_ruleset("v0.4").model_dump())
    data["colonization"] = load_ruleset("v0.5").colonization.model_dump() | {"version": "v0.4"}
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)


def test_v04_snapshot_without_colonization_key_still_validates():
    """Universes pinned before v0.5 keep their stored JSON valid (no new required field)."""
    data = load_ruleset("v0.4").model_dump()
    data.pop("colonization")
    assert Ruleset.model_validate(data).colonization is None
