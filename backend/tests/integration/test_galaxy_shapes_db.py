"""Galaxy shapes (v0.12, recette 11/11/2026) on real PostgreSQL: the creation choice reaches the
generator through the control plane, the layout is kept for the map backdrop and served with the
galaxy projection; rulesets without shapes refuse the choice."""

# ruff: noqa: F811
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_colony_api import game  # noqa: F401
from test_game_sessions import apply
from test_sandbox import started

from app.control.service import ControlError
from app.galaxy.models import GalaxySystem, UniverseGalaxy
from app.galaxy.shapes import SHAPES

pytestmark = pytest.mark.integration


def start(game, ruleset="v0.12", **extra):
    universe = uuid4()
    message = {
        "kind": "start_universe",
        "universe_id": str(universe),
        "name": "Formes",
        "seed": "shape-seed",
        "family": "solo",
        "ruleset": ruleset,
        "size": 100,
        "profiles": ["expansionist"],
        **extra,
    }
    return universe, apply(game, message)


def test_a_chosen_shape_is_generated_kept_and_served(game):
    universe, receipt = start(game, shape="spiral2")
    assert UUID(receipt["result"]["human_empire_id"])
    with game.factory() as s:
        manifest = s.get(UniverseGalaxy, universe)
        assert manifest.inputs["shape"] == "spiral2"
        assert manifest.layout["shape"] == "spiral2" and manifest.layout["radius"] > 0
        assert s.scalar(
            select(func.count()).where(GalaxySystem.universe_id == universe)
        ) == 100


def test_random_draws_a_shape_and_no_shape_keeps_the_lattice(game):
    universe, _ = start(game, shape="random")
    plain, _ = start(game)
    with game.factory() as s:
        drawn = s.get(UniverseGalaxy, universe)
        assert drawn.inputs["shape"] == drawn.layout["shape"]
        assert drawn.layout["shape"] in set(SHAPES)
        lattice = s.get(UniverseGalaxy, plain)
        assert lattice.layout is None and "shape" not in lattice.inputs


def test_a_ruleset_without_shapes_refuses_the_choice(game):
    with pytest.raises(ControlError) as refused:
        start(game, ruleset="v0.11", shape="clusters")
    assert refused.value.code == "invalid_bootstrap_configuration"


def test_the_galaxy_projection_carries_the_layout_of_a_shaped_world(game):
    plain = started(game)
    galaxy = plain.client.get(
        f"/game/{plain.universe}/galaxy/{plain.empire}", headers={"X-Game-Request": "bootstrap"}
    ).json()
    assert "layout" not in galaxy
    with game.factory.begin() as s:
        s.get(UniverseGalaxy, plain.universe).layout = {"shape": "clusters", "radius": 1}
    galaxy = plain.client.get(
        f"/game/{plain.universe}/galaxy/{plain.empire}", headers={"X-Game-Request": "bootstrap"}
    ).json()
    assert galaxy["layout"] == {"shape": "clusters", "radius": 1}
