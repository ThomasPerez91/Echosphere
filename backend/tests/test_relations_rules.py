"""Ruleset v0.8 (Q18) and pure relation rules: logical dates only, no worker order."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.ai.rules import GOALS_V3, AIRulesV2, AIRulesV3, fingerprint
from app.colony.rules import Ruleset, load_ruleset
from app.relations.rules import cooled_down, covers, pair, proposal_open, recent

T = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
H = timedelta(hours=1)


def test_v08_is_a_full_copy_of_v07_plus_relations_and_ai_v3_only():
    old, new = load_ruleset("v0.7").model_dump(), load_ruleset("v0.8").model_dump()
    for part in ("resources", "colony", "catalogue", "research", "galaxy", "fleets"):
        assert {**new[part], "version": "v0.7"} == old[part], part
    for part in ("colonization", "combat"):
        assert {**new[part], "version": "v0.7"} == old[part], part
    assert old["relations"] is None
    assert new["relations"] == {
        "version": "v0.8",
        "relations_version": "relations-v1",
        "proposal_ttl_seconds": 72 * 3600,
        "refusal_cooldown_seconds": 24 * 3600,
        "notice_seconds": 24 * 3600,
    }


def test_ai_v3_weights_are_the_validated_ones_and_sum_to_100():
    ai = load_ruleset("v0.8").ai
    assert type(ai) is AIRulesV3 and ai.policy_version == "utility-goals-v3"
    assert ai.goals == GOALS_V3 and GOALS_V3[-1] == "diplomacy"
    assert ai.profiles["economic_cautious"] == {
        "economy": 35,
        "research": 20,
        "exploration": 15,
        "expansion": 10,
        "logistics": 5,
        "military": 10,
        "diplomacy": 5,
    }
    assert ai.profiles["expansionist"] == {
        "economy": 20,
        "research": 15,
        "exploration": 15,
        "expansion": 30,
        "logistics": 5,
        "military": 10,
        "diplomacy": 5,
    }
    assert sum(ai.family_pages.values()) <= ai.candidate_limit
    assert ai.diplomacy.grievance_seconds == 72 * 3600
    assert ai.diplomacy.proposal_rules == {
        "economic_cautious": "no_recent_grievance",
        "expansionist": "past_grievance_only",
    }


def test_historical_rulesets_and_pinned_ai_digests_are_unchanged():
    for version in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5", "v0.6", "v0.7"):
        rules = load_ruleset(version)
        assert rules.relations is None
        assert Ruleset.model_validate(rules.model_dump()) == rules
    assert type(load_ruleset("v0.7").ai) is AIRulesV2
    # A controller pinned on v0.7 compares this digest: v0.8 must not move it.
    v07 = load_ruleset("v0.7").ai.model_dump()
    assert "diplomacy" not in v07 and fingerprint(v07) == fingerprint(deepcopy(v07))


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(relations=None),
        lambda d: d["relations"].update(version="v0.7"),
        lambda d: d["relations"].update(proposal_ttl_seconds=0),
        lambda d: d["relations"].update(relations_version="relations-v2"),
        lambda d: d["ai"]["profiles"]["expansionist"].update(diplomacy=6),
        lambda d: d["ai"]["diplomacy"]["proposal_rules"].pop("expansionist"),
        lambda d: d["ai"]["family_pages"].update(diplomacy=1),
        lambda d: d["ai"]["diplomacy"]["proposal_rules"].update(expansionist="attack"),
    ],
)
def test_invalid_v08_relations_or_diplomacy_configuration_is_refused(change):
    data = load_ruleset("v0.8").model_dump()
    change(data)
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)


def test_relations_never_appear_in_historical_rulesets():
    data = load_ruleset("v0.7").model_dump()
    data["relations"] = load_ruleset("v0.8").model_dump()["relations"] | {"version": "v0.7"}
    with pytest.raises(ValueError):
        Ruleset.model_validate(data)


def test_pair_is_canonical_and_refuses_self():
    a = UUID("00000000-0000-4000-8000-000000000001")
    b = UUID("ffffffff-0000-4000-8000-000000000001")
    assert pair(a, b) == pair(b, a) == (a, b)
    with pytest.raises(ValueError):
        pair(a, a)


def test_pact_covers_from_acceptance_until_the_end_of_notice_exclusive():
    assert covers(T, None, T)  # accepted exactly at battle_at: protected
    assert not covers(T, None, T - timedelta(seconds=1))  # battle before acceptance
    assert covers(T, None, T + 1000 * H)  # no notice: open-ended
    ends = T + 24 * H
    assert covers(T, ends, ends - timedelta(seconds=1))  # still protected during notice
    assert not covers(T, ends, ends)  # notice over: NO_AGREEMENT again


def test_a_late_notice_never_uncovers_an_already_elapsed_instant():
    battle = T + 5 * H
    # Notice given after the battle instant (a late worker would see it already): still covered.
    notice_at = battle + 2 * H
    assert covers(T, notice_at + 24 * H, battle)


def test_proposal_expiry_cooldown_and_grievance_are_pure_date_comparisons():
    expires = T + 72 * H
    assert proposal_open(expires, expires - timedelta(seconds=1))
    assert not proposal_open(expires, expires) and not proposal_open(None, T)
    assert cooled_down(None, T) and cooled_down(T, T) and not cooled_down(T + H, T)
    window = 72 * H
    assert not recent(None, T, window)
    assert recent(T - 71 * H, T, window)
    assert not recent(T - 72 * H, T, window)  # exactly 72 h old: no longer a recent grievance
