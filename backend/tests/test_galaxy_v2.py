"""galaxy-v2 (Q61 + 09/11 mesh decision): sizes, dead ends, chokepoints, no isolated Empire."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.colony.rules import Ruleset, load_ruleset
from app.galaxy.generator import adjacency
from app.galaxy.generator_v2 import (
    GalaxyRulesV2,
    _bridges,
    _distances,
    generate_v2,
    validate_v2,
)
from app.galaxy.rules import GalaxyRules

V10 = load_ruleset("v0.10").galaxy
CAPS = {100: 4, 300: 12, 500: 20, 1000: 40, 2000: 40}


def test_v010_uses_galaxy_v2_with_the_validated_caps_and_older_rulesets_keep_v1():
    assert isinstance(V10, GalaxyRulesV2)
    assert {int(k): v for k, v in V10.sizes.items()} == CAPS
    assert (V10.max_humans, V10.max_ai) == (10, 30)
    for version in ["v0.3", "v0.9"]:
        assert isinstance(load_ruleset(version).galaxy, GalaxyRules)
    mixed = load_ruleset("v0.9").model_dump()
    mixed["galaxy"] = {**V10.model_dump(), "version": "v0.9"}
    with pytest.raises(ValidationError):
        Ruleset.model_validate(mixed)


@pytest.mark.parametrize(
    "change",
    [
        {"sizes": {"100": 4, "300": 12}},
        {"sizes": {**{"100": 4, "300": 12, "500": 20, "1000": 40}, "2000": 41}},
        {"sizes": {"100": 5, "300": 12, "500": 20, "1000": 40, "2000": 40}},  # 5 x 25 > 100
        {"jitter": 25},
        {"max_route_length": 120},
        {"planet_counts": {"2": 50, "3": 40}},
    ],
)
def test_invalid_galaxy_v2_rules_are_refused(change):
    with pytest.raises(ValidationError):
        GalaxyRulesV2.model_validate({**V10.model_dump(), **change})


def check(world, empires):
    systems, routes, sites = world["systems"], world["routes"], world["starting_sites"]
    count = len(systems)
    graph = adjacency(count, [tuple(r) for r in routes])
    # Never an isolated Empire: one connected galaxy, two exits from every starting zone.
    assert len(_distances(graph, 0)) == count
    assert len(sites) == empires
    for site in sites:
        reach = _distances(graph, site)
        assert all(reach[o] >= V10.min_start_distance for o in sites if o != site)
        assert len(graph[site]) >= 3
    degrees = [len(g) for g in graph]
    assert max(degrees) <= V10.max_degree and min(degrees) >= 1
    # Not everything is linked: dead ends and real chokepoints exist.
    bridges = _bridges(count, graph)
    assert sum(d == 1 for d in degrees) >= count // 20
    assert [b for b in bridges if min(degrees[b[0]], degrees[b[1]]) > 1]
    return graph, bridges


@pytest.mark.parametrize("size", [100, 300, 500, 1000])
def test_every_size_generates_a_valid_galaxy_with_its_empire_cap(size):
    result = generate_v2(f"size-{size}", V10, size=size)
    assert len(result["world"]["systems"]) == size
    check(result["world"], CAPS[size])
    assert validate_v2(result["world"], V10, CAPS[size])[0] == []


def test_largest_size_and_fewer_empires_than_the_cap():
    result = generate_v2("big", V10, size=2000, empires=12)
    assert len(result["world"]["systems"]) == 2000
    check(result["world"], 12)


@pytest.mark.parametrize("seed", [f"mesh-{n}" for n in range(8)])
def test_mesh_has_dead_ends_and_chokepoints_on_many_seeds(seed):
    check(generate_v2(seed, V10, size=100)["world"], 4)


def test_generation_is_deterministic_and_inputs_are_checked():
    first = generate_v2("same", V10, size=300, empires=6)
    assert first == generate_v2("same", V10, size=300, empires=6)
    assert first["world"] != generate_v2("other", V10, size=300, empires=6)["world"]
    for bad in [{"size": 150}, {"size": "100"}, {"size": 100, "empires": 5},
                {"size": 100, "empires": 0}]:
        with pytest.raises(ValueError):
            generate_v2("x", V10, **bad)


def test_equitable_starts_share_one_core_zone_budget():
    world = generate_v2("fair", V10, size=500)["world"]
    graph = adjacency(len(world["systems"]), [tuple(r) for r in world["routes"]])
    cores = []
    for site in world["starting_sites"]:
        near = sorted(_distances(graph, site).items(), key=lambda kv: (kv[1], kv[0]))
        zone = [n for n, d in near if d <= 2][: V10.min_start_zone_size]
        cores.append([[(p["sectors"], p["orbitals"]) for p in world["systems"][n]["planets"]]
                      for n in zone])
    assert all(core == cores[0] for core in cores)
    home = world["systems"][world["starting_sites"][0]]["planets"][0]
    assert (home["sectors"], home["orbitals"]) == (V10.starting_sectors, V10.starting_orbitals)


def test_acceptance_refuses_an_isolated_or_overlinked_galaxy():
    world = generate_v2("tamper", V10, size=100)["world"]
    cut = deepcopy(world)
    site = cut["starting_sites"][0]
    cut["routes"] = [r for r in cut["routes"] if site not in r]
    assert "connected" in validate_v2(cut, V10, 4)[0]
    dense = deepcopy(world)
    dense["routes"] = sorted({tuple(sorted((a, b))) for a in range(100) for b in range(a + 1, 100)
                              if abs(a - b) <= 3})
    dense["routes"] = [list(r) for r in dense["routes"]]
    assert {"degree"} <= set(validate_v2(dense, V10, 4)[0])
