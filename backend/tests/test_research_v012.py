"""Ruleset v0.12 (recette 10/11/2026): research tiers III and IV, generated from v0.11."""

import json
import sys
from pathlib import Path

import pytest

from app.colony.rules import Ruleset, load_ruleset


def test_v012_adds_two_tiers_per_domain_and_their_research_centre_levels():
    rules = load_ruleset("v0.12")
    techs = rules.research.technologies
    assert len(techs) == 16
    assert {t.tier for t in techs.values()} == {1, 2, 3, 4}
    assert rules.research.facility.levels == {"1": 1, "2": 3, "3": 5, "4": 8}
    assert techs["engineering_4"].effect == "ship_cost"
    # Tier IV needs tier III of its domain and tier II of a neighbour domain.
    assert set(techs["engineering_4"].requires) == {"engineering_3", "energy_2"}


def test_tiers_three_four_and_their_effects_are_refused_before_v012():
    data = load_ruleset("v0.11").model_dump()
    extra = load_ruleset("v0.12").research.technologies["energy_4"].model_dump()
    data["research"]["technologies"]["energy_4"] = extra | {"requires": ["energy_2"]}
    data["research"]["facility"]["levels"]["4"] = 8
    with pytest.raises(ValueError, match="v0.12"):
        Ruleset.model_validate(data)


def test_earlier_rulesets_dump_unchanged():
    # Pinned rulesets are fingerprinted: the wider Literals never add fields to v0.11.
    assert "4" not in load_ruleset("v0.11").model_dump()["research"]["facility"]["levels"]


def test_v012_files_are_the_generator_output(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts/rulesets"))
    import make_v012

    monkeypatch.setattr(make_v012, "TARGET", tmp_path / "v0.12")
    make_v012.main()
    for path in (root / "game_data/rulesets/v0.12").glob("*.json"):
        generated = (tmp_path / "v0.12" / path.name).read_text()
        assert json.loads(path.read_text()) == json.loads(generated)


def test_relation_standing_reads_dated_facts_only():
    from datetime import UTC, datetime, timedelta

    from app.relations.rules import standing

    terms = load_ruleset("v0.12").relations.standing
    at = datetime(2026, 11, 10, tzinfo=UTC)
    iso = lambda d: (at - timedelta(days=d)).isoformat()  # noqa: E731
    neutral = standing(terms, {"pact": None, "proposal": None, "hostility": {}}, at)
    assert neutral == {"score": 0, "label": "neutral", "factors": []}
    ally = standing(terms, {"pact": {"accepted_at": iso(30), "notice": None}}, at)
    assert ally["score"] == 60 and ally["label"] == "allied"
    hit = standing(terms, {"hostility": {"by_counterpart_at": iso(2), "by_self_at": iso(1)}}, at)
    assert hit["score"] == -65 and hit["label"] == "hostile"
    old = standing(terms, {"hostility": {"by_counterpart_at": iso(20)}}, at)
    assert old["score"] == -20 and old["label"] == "wary"
    assert "standing" not in load_ruleset("v0.11").model_dump()["relations"]
