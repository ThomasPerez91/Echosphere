"""COL-11: ruleset v0.11 (unique key buildings, level cap, Chantier orbital, Centre de
recherche) and the stability of older rulesets' dumps (no database)."""

import json
from pathlib import Path

import pytest

from app.colony.rules import Ruleset, load_ruleset

M = 1_000_000


def test_v011_unique_key_buildings_guided_by_prerequisites():
    rules = load_ruleset("v0.11")
    cat = rules.catalogue.infrastructures
    assert {k for k, r in cat.items() if r.max_per_colony == 1} == {
        "industrial_complex", "logistics_center", "orbital_shipyard", "research_center"}
    assert cat["orbital_shipyard"].requires == {"industrial_complex": 2}
    assert cat["research_center"].requires == {"data_node": 3}
    assert rules.colony.level_cap.cap(12) == 20 and rules.colony.level_cap.cap(8) == 18
    assert rules.fleets.classes["probe"].requires == {"orbital_shipyard": 1}
    assert rules.fleets.classes["cruiser"].requires == {"orbital_shipyard": 6}
    assert rules.research.facility.level(1) == 1 and rules.research.facility.level(2) == 3
    assert set(rules.ai.unlocks) == {"orbital_shipyard", "research_center"}


def test_v011_early_levels_are_minutes_and_cheap():
    rules = load_ruleset("v0.11")
    first = rules.quote("extraction_complex", 1)
    assert first.base_duration_us == 60 * M and first.cost["alloys"] == 40 * M
    fifth = rules.quote("extraction_complex", 5)
    assert fifth.base_duration_us < 10 * 60 * M
    # Many levels: still under a few hours at level 12, beyond the old v0.10 level 5.
    assert rules.quote("extraction_complex", 12).base_duration_us < 3 * 3600 * M
    assert sum(rules.colony.initial_stocks.values()) < 2000


@pytest.mark.parametrize("version", ["v0.6", "v0.9", "v0.10"])
def test_older_rulesets_dump_without_the_v011_extensions(version):
    """Pinned rulesets are fingerprinted (AI policy digest, bootstrap receipts): v0.11 fields
    must not appear in older dumps, or running games would stop."""
    data = load_ruleset(version).model_dump()
    assert "level_cap" not in data["colony"]
    assert "facility" not in (data.get("research") or {})
    classes = (data.get("fleets") or {"classes": {}})["classes"].values()
    assert all("requires" not in c for c in classes)
    assert "unlocks" not in (data.get("ai") or {})


def test_v011_extensions_are_refused_in_older_rulesets():
    data = load_ruleset("v0.10").model_dump()
    data["colony"]["level_cap"] = {"base": 14, "sectors_divisor": 2}
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)


def test_generator_output_is_committed():
    """game_data/rulesets/v0.11 is produced by scripts/rulesets/make_v011.py (balance source)."""
    root = Path(__file__).resolve().parents[2]
    assert (root / "scripts/rulesets/make_v011.py").exists()
    infra = json.loads((root / "game_data/rulesets/v0.11/infrastructures.json").read_text())
    assert infra["version"] == "v0.11"
