"""v0.12 map (recette 11/11/2026) on real PostgreSQL: foreign Colonies an Empire legitimately
knows appear in its galaxy projection with the class of their Empire (ally, neutral, hostile);
nothing is revealed beyond the contact sources (own MONITORED system, own attack report)."""

# ruff: noqa: F811
import pytest
from sqlalchemy import select
from test_colony_api import game  # noqa: F401
from test_combat import arm, attack, launched, planet_of, resolve_due, until_battle
from test_fleet import fleets  # noqa: F401
from test_relations import REL, pacted, reenter, rivals

from app.persistence.models import Colony, Planet

pytestmark = pytest.mark.integration


def galaxy(w):
    return w.client.get(
        f"/game/{w.universe}/galaxy/{w.empire}", headers={"X-Game-Request": "bootstrap"}
    ).json()


def settle_beside(a, b):
    """Test-only placement of a B Colony on another world of A's own (MONITORED) system."""
    _, home = planet_of(a)
    with a.game.factory.begin() as s:
        free = s.scalar(
            select(Planet.id)
            .where(Planet.system_id == home, ~Planet.id.in_(select(Colony.planet_id)))
            .order_by(Planet.id)
            .limit(1)
        )
        s.add(Colony(universe_id=a.universe, empire_id=b.empire, planet_id=free))
    return free, home


def test_a_foreign_colony_beside_an_own_one_is_known_dated_and_classed(fleets):
    a, b = rivals(fleets, ruleset="v0.12")
    free, home = settle_beside(a, b)
    seen = galaxy(a)["foreign"]
    assert len(seen) == 1
    item = seen[0]
    where = (item["planet_id"], item["system_id"], item["source"])
    assert where == (str(free), str(home), "monitoring")
    # The refresh made B a contact: named, and neutral without pact nor hostile fact.
    assert item["empire"]["id"] == str(b.empire) and item["relation"] == "neutral"
    assert set(item) == {"planet_id", "system_id", "observed_at", "source", "relation", "empire"}
    # Oriented: B observes nothing of A (no own Colony in A's system).
    assert galaxy(b)["foreign"] == []
    pacted(a, b)
    assert galaxy(a)["foreign"][0]["relation"] == "ally"


def test_the_target_of_an_own_attack_is_known_from_the_report_as_hostile(fleets):
    a, b = rivals(fleets, ruleset="v0.12")
    planet, system = planet_of(b)
    strike = arm(a, {"frigate": 2})
    arm(b, {"interceptor": 1}, kind="GARRISON")
    mission_id, _ = launched(a, attack(a, strike, planet, {"frigate": 2}))
    until_battle(a, mission_id)
    assert resolve_due(a)["outcome"] in {"attacker_win", "defender_win", "mutual_destruction"}
    reenter(a, b)
    item = next(i for i in galaxy(a)["foreign"] if i["planet_id"] == str(planet))
    assert (item["system_id"], item["source"]) == (str(system), "combat")
    assert item["relation"] == "hostile"  # A's own hostile fact is recent
    # The defender learns the attacker, not where its Colonies are.
    assert galaxy(b)["foreign"] == []


def test_older_rulesets_and_missing_rights_carry_no_foreign_presence(fleets):
    a, b = rivals(fleets, ruleset="v0.11")
    settle_beside(a, b)
    assert "foreign" not in galaxy(a)
    c, d = rivals(fleets, ruleset="v0.12", permissions=[p for p in REL if p != "relations.read"])
    settle_beside(c, d)
    assert "foreign" not in galaxy(c)
