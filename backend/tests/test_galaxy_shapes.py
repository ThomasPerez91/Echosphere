"""Galaxy shapes (v0.12, recette 11/11/2026): systems spread like the reference carte-galaxie.html
(elliptical, two- or four-armed spiral, irregular, clusters) keep every galaxy-v2 guarantee."""

import math
import typing

import pytest
from pydantic import ValidationError

from app.colony.rules import Ruleset, load_ruleset
from app.galaxy.generator import StableRandom
from app.galaxy.generator_v2 import GalaxyRulesV2, GalaxyShapes, generate_v2, validate_v2
from app.galaxy.shapes import SHAPES, density, draw_params, gabriel, hash2

V12 = load_ruleset("v0.12").galaxy


def test_v012_offers_every_shape_and_older_rulesets_none():
    assert tuple(V12.shapes.offered) == SHAPES
    offered = typing.get_args(GalaxyShapes.model_fields["offered"].annotation)[0]
    assert typing.get_args(offered) == SHAPES
    for version in ("v0.10", "v0.11"):
        assert load_ruleset(version).galaxy.shapes is None
        assert "shapes" not in load_ruleset(version).galaxy.model_dump()
    mixed = load_ruleset("v0.11").model_dump()
    mixed["galaxy"]["shapes"] = V12.shapes.model_dump()
    with pytest.raises(ValidationError):
        Ruleset.model_validate(mixed)


@pytest.mark.parametrize(
    "shapes",
    [
        {"offered": [], "max_route_length": 600, "max_link_length": 4000},
        {"offered": ["ring"], "max_route_length": 600, "max_link_length": 4000},
        {"offered": ["spiral2", "spiral2"], "max_route_length": 600, "max_link_length": 4000},
        {"offered": ["spiral2"], "max_route_length": 150, "max_link_length": 4000},
        {"offered": ["spiral2"], "max_route_length": 600, "max_link_length": 500},
    ],
)
def test_invalid_shape_rules_are_refused(shapes):
    with pytest.raises(ValidationError):
        GalaxyRulesV2.model_validate({**V12.model_dump(), "shapes": shapes})


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("size", [100, 300])
def test_every_shape_generates_a_valid_galaxy_with_its_empire_cap(shape, size):
    result = generate_v2(f"shape-{shape}", V12, size=size, shape=shape)
    world = result["world"]
    assert len(world["systems"]) == size
    assert len(world["starting_sites"]) == V12.empire_cap(size)
    assert validate_v2(world, V12, V12.empire_cap(size))[0] == []
    assert result["inputs"]["shape"] == shape
    layout = world["layout"]
    assert layout["shape"] == shape and layout["squash"] == 740 and layout["radius"] > 0
    # Integer coordinates inside the drawn disc; nothing stored as a float.
    assert all(type(s["x"]) is int and s["x"] >= 0 and s["y"] >= 0 for s in world["systems"])


def test_systems_follow_the_density_of_their_shape():
    """Most systems lie where the shape is dense: arms of a spiral, not between them."""
    world = generate_v2("arms", V12, size=300, shape="spiral2")["world"]
    layout = world["layout"]
    at = density("spiral2", layout["params"])
    sq = layout["squash"] / 1000

    def here(s):
        return at((s["x"] - layout["cx"]) / layout["radius"],
                  (s["y"] - layout["cy"]) / (layout["radius"] * sq))

    # About a tenth of the sampled disc reaches 0.2; most systems do.
    dense = sum(here(s) >= 0.2 for s in world["systems"])
    assert dense >= 0.7 * len(world["systems"])


def test_shaped_generation_is_deterministic_and_random_draws_from_the_seed():
    one = generate_v2("same", V12, size=100, shape="clusters")
    assert one == generate_v2("same", V12, size=100, shape="clusters")
    drawn = {generate_v2(seed, V12, size=100, shape="random")["inputs"]["shape"]
             for seed in ("a", "b", "c", "d", "e", "f", "g", "h")}
    assert len(drawn) > 1 and drawn <= set(SHAPES)
    assert generate_v2("a", V12, size=100, shape="random") == generate_v2(
        "a", V12, size=100, shape="random"
    )


def test_unset_shape_keeps_the_lattice_galaxy_and_an_unoffered_shape_is_refused():
    lattice = generate_v2("plain", V12, size=100)
    assert "shape" not in lattice["inputs"] and "layout" not in lattice["world"]
    with pytest.raises(ValueError):
        generate_v2("plain", load_ruleset("v0.11").galaxy, size=100, shape="spiral2")
    with pytest.raises(ValueError):
        generate_v2("plain", V12, size=100, shape="ring")


def test_long_links_only_join_what_density_left_apart():
    world = generate_v2("links", V12, size=300, shape="clusters")["world"]
    points = [(s["x"], s["y"]) for s in world["systems"]]
    longest = max(math.dist(points[a], points[b]) for a, b in world["routes"])
    assert longest <= V12.shapes.max_link_length
    candidates = gabriel(points, V12.shapes.max_route_length)
    extra = [r for r in world["routes"] if tuple(r) not in candidates]
    assert all(math.dist(points[a], points[b]) > V12.shapes.max_route_length for a, b in extra)


def test_gabriel_candidates_never_cross():
    random = StableRandom(["gabriel"])
    points = [(random.below(2000), random.below(2000)) for _ in range(120)]
    pairs = sorted(gabriel(points, 600))

    def cross(p, q):
        (a, b), (c, d) = (points[p[0]], points[p[1]]), (points[q[0]], points[q[1]])

        def side(o, x, y):
            return (x[0] - o[0]) * (y[1] - o[1]) - (x[1] - o[1]) * (y[0] - o[0])

        return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0

    assert not any(
        cross(p, q) for i, p in enumerate(pairs) for q in pairs[i + 1:] if not set(p) & set(q)
    )


def test_noise_matches_the_reference_hash():
    # Values of the reference hash2 (carte-galaxie.html), computed with JavaScript Math.imul.
    assert hash2(0, 0, 0) == 0.05130852316506207
    assert hash2(-3, 7, 11) == 0.8753199882339686
    assert hash2(123, -45, 998) == 0.8319499371573329
    params = draw_params(StableRandom(["p"]), "spiral4")
    assert set(params) == {"ns", "rot"} and all(type(v) is int for v in params.values())
