"""v0.12 map classes (recette 11/11/2026): a known Empire is an ally, neutral or hostile on the
galaxy map, read from the same dated facts as the relation standing."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.colony.rules import Ruleset, load_ruleset
from app.relations.rules import MapClasses, map_class, standing

AT = datetime(2099, 1, 10, tzinfo=UTC)
V12 = load_ruleset("v0.12").relations


def view(state="NO_AGREEMENT", by_self=None, by_counterpart=None, accepted=None, received=False):
    return {
        "state": state,
        "pact": {"accepted_at": accepted.isoformat(), "notice": None} if accepted else None,
        "proposal": {"direction": "received"} if received else None,
        "hostility": {
            "by_self_at": by_self.isoformat() if by_self else None,
            "by_counterpart_at": by_counterpart.isoformat() if by_counterpart else None,
        },
    }


def classed(v):
    return map_class(V12.map, v, standing(V12.standing, v, AT), AT)


def test_v012_classes_and_earlier_rulesets_have_none():
    assert V12.map == MapClasses(hostile_days=7)
    assert "map" not in load_ruleset("v0.11").relations.model_dump()
    mixed = load_ruleset("v0.11").model_dump()
    mixed["relations"]["map"] = {"hostile_days": 7}
    with pytest.raises(ValidationError):
        Ruleset.model_validate(mixed)


def test_a_pact_in_force_is_an_ally_even_with_a_recent_grievance():
    assert classed(view("PACT", accepted=AT - timedelta(days=3))) == "ally"
    recent = AT - timedelta(days=2)
    assert classed(view("PACT", accepted=AT - timedelta(days=1), by_counterpart=recent)) == "ally"


def test_a_recent_hostile_fact_either_way_makes_an_enemy_then_fades():
    assert classed(view(by_counterpart=AT - timedelta(days=2))) == "hostile"
    assert classed(view(by_self=AT - timedelta(days=6))) == "hostile"
    assert classed(view(by_self=AT - timedelta(days=8))) == "neutral"
    assert classed(view(by_counterpart=AT - timedelta(days=20))) == "neutral"  # wary score only


def test_no_fact_is_neutral_and_a_cordial_score_is_an_ally():
    assert classed(view()) == "neutral"
    cordial = {"label": "cordial", "score": 30}
    assert map_class(V12.map, view(), cordial, AT) == "ally"
    assert map_class(V12.map, view(), {"label": "hostile", "score": -60}, AT) == "hostile"
