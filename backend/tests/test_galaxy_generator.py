"""Independent acceptance scenarios and the fixed, non-filtered Q06 robustness corpus."""

import hashlib
import json
import os
import subprocess
import sys
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.colony.rules import Ruleset, load_ruleset
from app.galaxy.generator import GenerationError, canonical, generate, validate


def test_determinism_variability_and_cross_process_hash_order():
    rules = load_ruleset("v0.3").galaxy
    first = generate("fixed-world-é", rules)
    assert first == generate("fixed-world-é", rules)
    assert first["world"] != generate("another-seed", rules)["world"]
    script = (
        "from app.colony.rules import load_ruleset; "
        "from app.galaxy.generator import generate, canonical; "
        'print(canonical(generate("fixed-world-é", load_ruleset("v0.3").galaxy)))'
    )
    for salt in ["17", "56789"]:
        output = subprocess.check_output(
            [sys.executable, "-c", script], env={**os.environ, "PYTHONHASHSEED": salt}, text=True
        )
        assert json.loads(output) == first
    assert hashlib.sha256(canonical(first).encode()).hexdigest() == (
        "4beb834154cb703118a50fc6e08df5631f68392e996a3b6b21f67866b69881ab"
    )


@pytest.mark.parametrize(
    "count,sites,total", [(40, 4, 1000), (30, 1, 100), (30, 4, 100), (50, 1, 100), (50, 4, 100)]
)
def test_fixed_robustness_corpus_all_successes_obey_all_constraints(count, sites, total):
    rules = load_ruleset("v0.3").galaxy
    failures = []
    for i in range(total):
        seed = f"galaxy-v1-corpus-{i:04d}"
        try:
            result = generate(seed, rules, system_count=count, starting_site_count=sites)
        except GenerationError as error:
            failures.append((seed, error.constraints))
            continue
        world = result["world"]
        assert len(world["systems"]) == count and len(world["starting_sites"]) == sites
        assert not validate(world, rules)[0]
        # Concrete, independently inspected contract properties, not just a truthy result.
        assert len({tuple(edge) for edge in world["routes"]}) == len(world["routes"])
        assert all(a < b for a, b in world["routes"])
        assert result["metrics"]["diameter"] <= (count + 3) // 4
        assert 1 <= result["attempt"] <= 64
        assert all(len(s["planets"]) in (2, 3, 4, 5) for s in world["systems"])
    assert failures == [], f"No seed may be silently discarded: {failures}"


@pytest.mark.parametrize(
    "change,reason",
    [
        ("duplicate", "route_integrity"),
        ("loop", "route_integrity"),
        ("position", "positions"),
        ("overlap", "separation"),
        ("world", "useful_world"),
        ("home", "home"),
    ],
)
def test_acceptance_rejects_corrupt_final_world(change, reason):
    rules = load_ruleset("v0.3").galaxy
    world = deepcopy(generate("acceptance", rules)["world"])
    if change == "duplicate":
        world["routes"].append(world["routes"][0])
    elif change == "loop":
        world["routes"].append([0, 0])
    elif change == "position":
        world["systems"][0]["x"] = -1
    elif change == "overlap":
        world["systems"][0]["x"] = world["systems"][1]["x"]
        world["systems"][0]["y"] = world["systems"][1]["y"]
    elif change == "world":
        for planet in world["systems"][1]["planets"]:
            planet.update(sectors=9, orbitals=1)
    else:
        world["systems"][world["starting_sites"][0]]["planets"][0]["sectors"] = 15
    assert reason in validate(world, rules)[0]


def test_explicit_failure_preserves_bounded_attempts(monkeypatch):
    from app.galaxy import generator

    calls = []
    monkeypatch.setattr(generator, "_candidate", lambda *args: calls.append(1))
    with pytest.raises(GenerationError) as exc:
        generate("impossible", load_ruleset("v0.3").galaxy)
    assert len(calls) == 64 and exc.value.constraints == {"layout": 64}


@pytest.mark.parametrize("count,sites", [(29, 4), (51, 4), (40, 0), (40, 5), (True, 4)])
def test_input_bounds_do_not_fallback(count, sites):
    with pytest.raises(ValueError):
        generate("seed", load_ruleset("v0.3").galaxy, system_count=count, starting_site_count=sites)


def test_pinned_data_versions_and_exploration_exact_quotes():
    rules = load_ruleset("v0.3")
    assert rules.galaxy.starting_site_count == 4
    for hops, minutes in [(1, 45), (2, 75), (3, 105)]:
        cost, duration = rules.exploration.quote(hops)
        assert cost == {
            "alloys": 50_000_000,
            "flux": (50 + 10 * hops) * 1_000_000,
            "data": 25_000_000,
        }
        assert duration == minutes * 60_000_000
    for version in ["v0.1", "v0.2"]:
        assert load_ruleset(version).galaxy is None
    bad = rules.model_dump()
    bad["galaxy"]["galaxy_generator_version"] = "galaxy-v2"
    with pytest.raises(ValidationError):
        Ruleset.model_validate(bad)
    bad = rules.model_dump()
    bad["exploration"]["version"] = "v0.2"
    with pytest.raises(ValidationError):
        Ruleset.model_validate(bad)
