"""13B B05/B06 pure decisions: D4 enemy bounds, outcome order, ranking, losses arithmetic."""

from datetime import UTC, datetime, timedelta

import pytest

from app.frontier.encounter import (
    add,
    engagement_outcome,
    kind_for,
    known_enemy,
    rank,
    subtract,
)

T = datetime(2099, 1, 4, tzinfo=UTC)
W = timedelta(hours=72)
S = timedelta(seconds=1)


def test_known_enemy_requires_a_prior_contact_and_a_strictly_recent_resolved_act():
    known = T - timedelta(days=10)
    assert known_enemy(known, [T - W + S], T, W)  # 71:59:59 old: enemy
    assert not known_enemy(known, [T - W], T, W)  # exactly 72 h old: no longer
    assert known_enemy(known, [T], T, W)  # an act at the very instant counts
    assert not known_enemy(known, [T + S], T, W)  # a later act never counts retroactively
    assert not known_enemy(known, [], T, W)  # e.g. only a refused proposal
    assert not known_enemy(None, [T - S], T, W)  # unknown Empire: never ambushed
    assert not known_enemy(T + S, [T - S], T, W)  # contact acquired after the instant


def outcome(**kw):
    base = dict(
        pact=False,
        protocol="INTERCEPTION",
        enemy=False,
        watcher_military={"frigate": 2},
        mover_military={"interceptor": 1},
    )
    return engagement_outcome(**(base | kw))


def test_outcome_order_pact_first_then_enemy_then_forces():
    assert outcome() is None  # interception fights anyone detected, even unknown/superior
    assert outcome(pact=True) == "pact"
    assert outcome(pact=True, watcher_military={}) == "pact"
    assert outcome(protocol="AMBUSH") == "not_enemy"
    assert outcome(protocol="AMBUSH", enemy=True) is None
    assert outcome(watcher_military={"frigate": 0}) == "no_force"
    assert outcome(mover_military={}) == "no_military_target"  # civilians never destroyed
    with pytest.raises(ValueError):
        outcome(protocol="SURVEILLANCE")


def test_kinds_and_total_rank_order():
    assert kind_for("AMBUSH") == kind_for("INTERCEPTION") == "engagement"
    assert kind_for("FRIENDLY_CONTACT") == "retreat" and kind_for("SURVEILLANCE") is None
    a = rank(T, "m2", 0, "f1", "engagement")
    b = rank(T, "m1", 3, "f9", "retreat")
    c = rank(T, "m1", 3, "f2", "engagement")
    assert sorted([b, a, c]) == [c, a, b]  # engagements first at one instant, then ids
    assert rank(T - S, "z", 9, "z", "retreat") < c


def test_losses_never_exceed_units_and_never_resurrect():
    assert subtract({"frigate": 3, "probe": 1}, {"frigate": 2}) == {"frigate": 1, "probe": 1}
    with pytest.raises(ValueError):
        subtract({"frigate": 1}, {"frigate": 2})
    with pytest.raises(ValueError):
        subtract({"frigate": 1}, {"cruiser": 1})
    assert add({"frigate": 1}, {"frigate": 2, "cruiser": 0}) == {"frigate": 3}
