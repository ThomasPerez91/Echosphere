"""EXP-01a: ruleset v0.10 and the pure opportunities-v1 generator (no database)."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.colony.rules import Ruleset, load_ruleset, since
from app.galaxy.generator_v2 import generate_v2
from app.galaxy.opportunities import (
    MAX_SITES,
    OpportunityRules,
    generate_opportunities,
    nearest_start,
    strategic_marks,
)

V10 = load_ruleset("v0.10")


def world_of(seed):
    return generate_v2(seed, V10.galaxy, size=100)["world"]


def test_v010_is_v09_plus_opportunities_and_galaxy_v2_only():
    old, new = load_ruleset("v0.9").model_dump(), V10.model_dump()
    assert set(new) == set(old) and old["opportunities"] is None
    for part in old:
        if part in ("opportunities", "galaxy") or old[part] is None:
            continue  # galaxy-v2 has its own tests (test_galaxy_v2.py)
        assert {**new[part], "version": "v0.9"} == old[part], part
    assert new["opportunities"]["opportunity_generator_version"] == "opportunities-v1"
    for version in [f"v0.{n}" for n in range(1, 10)]:
        assert load_ruleset(version).opportunities is None, version


def test_ruleset_order_is_numeric_and_older_versions_refuse_opportunities():
    assert since("v0.10", "v0.9") and since("v0.9", "v0.9") and not since("v0.9", "v0.10")
    parts = load_ruleset("v0.9").model_dump()
    parts["opportunities"] = {**V10.opportunities.model_dump(), "version": "v0.9"}
    with pytest.raises(ValidationError, match="Opportunities unavailable"):
        Ruleset.model_validate(parts)
    without = V10.model_dump()
    without["opportunities"] = None
    with pytest.raises(ValidationError, match="Missing or mixed Opportunities"):
        Ruleset.model_validate(without)


@pytest.mark.parametrize(
    "change",
    [
        {"sites_per_system": {"0": 50, "1": 40}},
        {"sites_per_system": {"0": 50, "4": 50}},
        {"family_weights": {"deposit": 100}},
        {"deposits": {"metal_belt": {"name": "X", "resource": "gold", "weight": 1,
                                     "reserve": [1, 2], "throughput_per_hour": [1, 2]}}},
        {"deposits": {"metal_belt": {"name": "X", "resource": "alloys", "weight": 1,
                                     "reserve": [5, 2], "throughput_per_hour": [1, 2]}}},
        {"curiosities": {"metal_belt": {"name": "X", "weight": 1, "study_seconds": [1, 2],
                                        "data": [1, 2]}}},
    ],
)
def test_invalid_opportunity_rules_are_refused(change):
    with pytest.raises(ValidationError):
        OpportunityRules.model_validate({**V10.opportunities.model_dump(), **change})


def test_generation_is_deterministic_and_never_touches_the_galaxy():
    world = world_of("exp-seed")
    before = deepcopy(world)
    first = generate_opportunities("exp-seed", world, V10.opportunities)
    assert world == before  # galaxy-v1 world and digest unchanged
    assert first == generate_opportunities("exp-seed", deepcopy(world), V10.opportunities)
    other = generate_opportunities("other", world_of("other"), V10.opportunities)
    assert other["opportunities"] != first["opportunities"]


@pytest.mark.parametrize("seed", [f"exp-{n}" for n in range(12)])
def test_fairness_caps_and_dossiers_hold_on_every_seed(seed):
    rules = V10.opportunities
    world = world_of(seed)
    result = generate_opportunities(seed, world, rules)
    count, sites = len(world["systems"]), world["starting_sites"]
    routes = [tuple(r) for r in world["routes"]]
    ops = result["opportunities"]
    per_system = {}
    for o in ops:
        per_system.setdefault(o["system"], []).append(o)
        assert o["family"] in ("deposit", "curiosity")
        if o["family"] == "deposit":
            spec = rules.deposits[o["kind"]]
            assert o["resource"] == spec.resource
            assert o["reserve"] > 0 and o["throughput_per_hour"] > 0
            assert "data" not in o
        else:
            assert o["data"] > 0 and o["study_seconds"] > 0 and "reserve" not in o
    assert all(len(v) <= MAX_SITES for v in per_system.values())
    assert all([o["index"] for o in v] == list(range(len(v))) for v in per_system.values())
    # No remarkable opportunity near a start, and a capped number of them.
    distance = nearest_start(count, routes, sites)
    remarkable = [o for o in ops if o["tier"] == "remarkable"]
    assert len(remarkable) <= count * rules.remarkable.max_per_100_systems // 100
    assert all(distance[o["system"]] >= rules.remarkable.min_start_distance for o in remarkable)
    # Every starting zone (radius 2) offers an ordinary deposit.
    for site in sites:
        zone = {n for n in range(count) if _hops(routes, site, n) <= rules.starting_zone_radius}
        assert any(o["family"] == "deposit" and o["tier"] == "common"
                   for n in zone for o in per_system.get(n, []))
    # Dossiers: clues are curiosities of distinct systems, each used once.
    seen = set()
    for dossier in result["dossiers"]:
        clues = [tuple(c) for c in dossier["clues"]]
        assert len(clues) == rules.dossiers.clues and len({c[0] for c in clues}) == len(clues)
        assert not seen & set(clues)
        seen |= set(clues)
        for position, (system, index) in enumerate(clues):
            o = per_system[system][index]
            assert o["family"] == "curiosity"
            assert (o["dossier"], o["clue"]) == (dossier["index"], position)


def test_distribution_stays_mixed_across_seeds():
    empty = total = remarkable = 0
    for n in range(20):
        world = world_of(f"dist-{n}")
        ops = generate_opportunities(f"dist-{n}", world, V10.opportunities)["opportunities"]
        used = {o["system"] for o in ops}
        empty += len(world["systems"]) - len(used)
        total += len(world["systems"])
        remarkable += sum(o["tier"] == "remarkable" for o in ops)
    assert 0.3 < empty / total < 0.6  # many ordinary systems, most others with something
    assert 0 < remarkable < total * 0.05  # a few remarkable finds, never a crowd


def test_strategic_marks_come_from_the_routes_given_only():
    systems = ["a", "b", "c", "d", "e"]
    star = [("a", "b"), ("a", "c"), ("a", "d"), ("a", "e")]
    assert strategic_marks(systems, star) == {"a": ["crossroads"]}
    assert strategic_marks(systems, star[:3]) == {}  # an unknown route never counts


def _hops(routes, a, b):
    frontier, seen, depth = {a}, {a}, 0
    while frontier:
        if b in frontier:
            return depth
        frontier = {y for x in frontier for p in routes for y in p if x in p and y != x} - seen
        seen |= frontier
        depth += 1
    return 10**9
