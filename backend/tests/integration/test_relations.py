"""Real PostgreSQL + GameSession tests for Relations (ruleset v0.8, Q18 closed for step 13)."""

# ruff: noqa: F811
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from test_colony_api import Clock, game  # noqa: F401
from test_combat import (
    arm,
    attack,
    engagement_of,
    launched,
    planet_of,
    resolve_due,
    stacks,
    until_battle,
)
from test_fleet import FULL, fleets, rebind, view  # noqa: F401

from app.colony.rules import load_ruleset
from app.combat.models import CombatReport
from app.galaxy import service as g
from app.persistence.database import create_session_factory
from app.persistence.models import Colony, Planet, StellarSystem
from app.relations import service as relations
from app.relations.models import RelationContact, RelationEvent, RelationPact, RelationPair
from app.relations.rules import pair
from app.simulation.models import ResourceBalance
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration
M = 1_000_000
COMBAT = ["colony.expand", "combat.read", "combat.attack"]
REL = [*FULL, *COMBAT, "relations.read", "relations.negotiate"]


def world(fleets, **kwargs):
    return fleets(**({"permissions": REL, "ruleset": "v0.8"} | kwargs))


def rivals(fleets, **kwargs):
    """Empires A and B in one v0.8 Universe; A knows the whole map (test-only)."""
    a = world(fleets, **kwargs)
    b = world(fleets, universe=a.universe, other=True, **kwargs)
    with a.game.factory.begin() as s:
        for system in s.scalars(
            select(StellarSystem.id).where(StellarSystem.universe_id == a.universe)
        ):
            g.map_system(s, a.universe, a.empire, system, a.game.clock())
        for w in (a, b):  # test-only funds; every spending still goes through the services
            for r in ("alloys", "flux", "data"):
                s.get(ResourceBalance, (w.colony, r)).stock = 9_000 * M
    return a, b


def reenter(*worlds):
    """After a long wait the access window lapsed: a new binding revision and session."""
    for w in worlds:
        w.revision = getattr(w, "revision", 1) + 1
        rebind(w, REL, revision=w.revision)


def rel(w):
    return w.client.get(
        f"/game/{w.universe}/relations/{w.empire}", headers={"X-Game-Request": "bootstrap"}
    )


def act(w, other, action, key=None):
    return w.client.post(
        f"/game/{w.universe}/relations/{w.empire}/{other.empire}/{action}",
        headers=w.headers(),
        json={"idempotency_key": key or uuid4().hex},
    )


def code(response):
    return response.json()["error"]["code"]


def relation_of(w, other):
    rows = rel(w).json()["relations"]
    return next((r for r in rows if r["empire"]["id"] == str(other.empire)), None)


def meet(a, b, *, both=True):
    """Test-only legitimate contact: a dated presence observation, as the refresh would write."""
    with a.game.factory.begin() as s:
        at = a.game.clock()
        planet, _ = planet_of(b)
        relations.record_contact(s, a.universe, a.empire, b.empire, "presence", at, planet)
        if both:
            planet, _ = planet_of(a)
            relations.record_contact(s, a.universe, b.empire, a.empire, "presence", at, planet)


def pacted(a, b):
    meet(a, b)
    assert act(a, b, "propose").status_code == 200
    assert act(b, a, "accept").status_code == 200


# --- Contacts ---------------------------------------------------------------------------------


def test_foreign_colony_in_a_monitored_system_creates_an_oriented_dated_contact_only(fleets):
    a, b = rivals(fleets)
    _, home = planet_of(a)
    with a.game.factory.begin() as s:
        # Test-only placement of a B colony on another world of A's own (MONITORED) system.
        free = s.scalar(
            select(Planet.id)
            .where(Planet.system_id == home, ~Planet.id.in_(select(Colony.planet_id)))
            .order_by(Planet.id)
            .limit(1)
        )
        s.add(Colony(universe_id=a.universe, empire_id=b.empire, planet_id=free))
    # Reading Relations refreshes A's own MONITORED observation (even if Galaxy is never
    # opened): the foreign Colony now visible from A's own Colony is a dated presence contact.
    seen = relation_of(a, b)
    assert seen["contact"]["first_source"] == "presence"
    presence = seen["contact"]["presence"]
    assert presence["planet_id"] == str(free) and presence["observed_at"]
    # Empire, planet and date only: no stock, building, fleet, Research or other colony.
    assert set(presence) == {"planet_id", "planet_name", "system_id", "system_name", "observed_at"}
    assert str(b.colony) not in str(rel(a).json())
    # Oriented: B does not know A's system, so its own refresh observes nothing of A.
    assert relation_of(b, a) is None
    # Losing MONITORED never forgets the contact.
    with a.game.factory.begin() as s:
        s.execute(text("DELETE FROM colonies WHERE planet_id = :p"), {"p": free})
        g.refresh_monitoring(s, a.universe, a.empire, a.game.clock())
    assert relation_of(a, b)["contact"]["first_source"] == "presence"


def test_fought_battle_creates_both_contacts_and_the_attackers_dated_hostile_fact(fleets):
    a, b = rivals(fleets)
    planet, _ = planet_of(b)
    strike = arm(a, {"frigate": 2})
    arm(b, {"interceptor": 1}, kind="GARRISON")
    mission_id, _ = launched(a, attack(a, strike, planet, {"frigate": 2}))
    until_battle(a, mission_id)
    assert resolve_due(a)["outcome"] in {"attacker_win", "defender_win", "mutual_destruction"}
    reenter(a, b)
    battle_at = engagement_of(a, mission_id).battle_at.isoformat()
    mine, theirs = relation_of(a, b), relation_of(b, a)
    assert mine["contact"]["first_source"] == theirs["contact"]["first_source"] == "combat"
    assert mine["hostility"] == {"by_self_at": battle_at, "by_counterpart_at": None}
    assert theirs["hostility"] == {"by_self_at": None, "by_counterpart_at": battle_at}
    assert mine["state"] == theirs["state"] == "NO_AGREEMENT"


def test_target_unavailable_creates_no_contact_and_no_hostile_fact(fleets):
    a, b = rivals(fleets)
    _, system = planet_of(b)
    with a.game.factory() as s:
        empty = s.scalar(
            select(Planet.id)
            .where(Planet.system_id == system, ~Planet.id.in_(select(Colony.planet_id)))
            .limit(1)
        )
    strike = arm(a, {"interceptor": 1})
    mission_id, _ = launched(a, attack(a, strike, empty, {"interceptor": 1}))
    until_battle(a, mission_id)
    assert resolve_due(a)["outcome"] == "target_unavailable"
    reenter(a, b)
    assert rel(a).json()["relations"] == [] and rel(b).json()["relations"] == []
    with a.game.factory() as s:
        pairs = select(func.count()).select_from(RelationPair)
        assert s.scalar(pairs.where(RelationPair.universe_id == a.universe)) == 0


# --- Negotiation -------------------------------------------------------------------------------


def test_propose_accept_then_notice_keeps_the_pact_until_its_end(fleets):
    a, b = rivals(fleets)
    meet(a, b)
    sent = act(a, b, "propose")
    assert sent.status_code == 200 and sent.json()["result"]["kind"] == "proposed"
    assert relation_of(a, b)["proposal"]["direction"] == "sent"
    assert relation_of(a, b)["actions"] == ["withdraw"]
    assert relation_of(b, a)["actions"] == ["accept", "refuse"]
    assert code(act(b, a, "propose")) == "proposal_open"  # one open proposal per pair
    accepted = act(b, a, "accept")
    assert accepted.status_code == 200
    assert relation_of(a, b)["state"] == relation_of(b, a)["state"] == "PACT"
    assert code(act(a, b, "propose")) == "pact_active"
    notice = act(a, b, "terminate")
    assert notice.status_code == 200
    ends = datetime.fromisoformat(notice.json()["result"]["ends_at"])
    assert relation_of(b, a)["pact"]["notice"]["by"] == "counterpart"
    assert code(act(b, a, "terminate")) == "notice_pending"
    a.game.test_clock[0] = ends - timedelta(seconds=1)
    reenter(a, b)
    assert relation_of(a, b)["state"] == "PACT"  # fully active during the notice
    a.game.test_clock[0] = ends
    reenter(a, b)
    assert relation_of(a, b)["state"] == "NO_AGREEMENT"
    assert relation_of(a, b)["actions"] == ["propose"]  # a new proposal at once
    # Same logical instant for the three commands here: compare the journal as a set.
    kinds = sorted(h["kind"] for h in rel(b).json()["history"])
    assert kinds == ["accepted", "notice", "proposed"]


def test_refusal_cooldown_withdrawal_and_lazy_expiry(fleets):
    a, b = rivals(fleets)
    meet(a, b)
    assert act(a, b, "propose").status_code == 200
    refused = act(b, a, "refuse")
    assert refused.status_code == 200
    assert code(act(a, b, "propose")) == "proposal_cooldown"
    assert relation_of(a, b)["cooldown_until"] == refused.json()["result"]["cooldown_until"]
    # The refusal blocks the author only: B may still propose.
    assert act(b, a, "propose").status_code == 200
    assert act(b, a, "withdraw").status_code == 200
    assert code(act(b, a, "withdraw")) == "proposal_missing"
    a.advance(hours=24)
    reenter(a, b)
    assert act(a, b, "propose").status_code == 200
    a.advance(hours=72)
    reenter(a, b)
    assert relation_of(b, a)["proposal"] is None  # expired without any scheduled event
    assert code(act(b, a, "accept")) == "proposal_missing"
    assert act(a, b, "propose").status_code == 200


def test_unknown_and_nonexistent_empires_are_indistinguishable(fleets):
    a, b = rivals(fleets)
    assert code(act(a, b, "propose")) == "relation_not_found"  # exists, not known
    ghost = type("Ghost", (), {"empire": uuid4()})()
    assert code(act(a, ghost, "propose")) == "relation_not_found"
    assert act(a, b, "propose").status_code == act(a, ghost, "propose").status_code == 404
    assert code(act(a, a, "propose")) == "invalid_request"


def test_intention_replay_is_idempotent_and_a_reused_key_conflicts(fleets):
    a, b = rivals(fleets)
    meet(a, b)
    key = uuid4().hex
    first = act(a, b, "propose", key)
    again = act(a, b, "propose", key)
    assert first.status_code == again.status_code == 200
    assert first.json()["result"] == again.json()["result"]
    assert code(act(a, b, "withdraw", key)) == "idempotency_conflict"
    with a.game.factory() as s:
        events = select(func.count()).select_from(RelationEvent)
        assert s.scalar(events.where(RelationEvent.universe_id == a.universe)) == 1


@pytest.mark.parametrize(
    "rights,action,status",
    [
        ([*FULL, "relations.negotiate"], None, 404),
        ([*FULL, "relations.read"], "propose", 403),
    ],
)
def test_permissions_are_explicit(fleets, rights, action, status):
    a, b = rivals(fleets)
    meet(a, b)
    rebind(a, rights, revision=7)
    response = rel(a) if action is None else act(a, b, action)
    assert response.status_code == status
    if action is not None:
        # Read-only access: the projection never offers an action.
        assert all(r["actions"] == [] for r in rel(a).json()["relations"])


def test_historical_universe_has_no_relations_and_combat_writes_none(fleets):
    a = fleets(permissions=REL, ruleset="v0.7")
    assert code(rel(a)) == "relations_unavailable"
    listing = a.client.get(f"/game/{a.universe}/relations", headers={"X-Game-Request": "bootstrap"})
    assert listing.json()["available"] is False


# --- Pact and Combat: logical dates only --------------------------------------------------------


def test_active_pact_voids_the_battle_without_loss_or_composition(fleets):
    a, b = rivals(fleets)
    pacted(a, b)
    planet, _ = planet_of(b)
    strike = arm(a, {"frigate": 3})
    defence = arm(b, {"interceptor": 2}, kind="GARRISON")
    accepted = launched(a, attack(a, strike, planet, {"frigate": 3}))  # never refused at launch
    mission_id, fleet_id = accepted
    until_battle(a, mission_id)
    assert resolve_due(a)["outcome"] == "voided_by_pact"
    reenter(a, b)
    assert stacks(a, fleet_id) == {"frigate": 3} and stacks(b, defence) == {"interceptor": 2}
    with a.game.factory() as s:
        reports = list(
            s.scalars(select(CombatReport).where(CombatReport.universe_id == a.universe))
        )
        assert {r.role for r in reports} == {"attacker", "defender"}
        for r in reports:
            assert r.result["outcome"] == "voided_by_pact"
            assert not {"own", "opponent", "rounds"} & r.result.keys()
    assert view(b).json()["combat"]["alerts"] == []  # the defender's alert is closed
    assert relation_of(a, b)["hostility"] == {"by_self_at": None, "by_counterpart_at": None}


def test_pact_accepted_after_battle_at_never_voids_a_late_resolution(fleets):
    a, b = rivals(fleets)
    meet(a, b)
    planet, _ = planet_of(b)
    strike = arm(a, {"frigate": 2})
    arm(b, {"interceptor": 1}, kind="GARRISON")
    mission_id, _ = launched(a, attack(a, strike, planet, {"frigate": 2}))
    assert act(a, b, "propose").status_code == 200
    until_battle(a, mission_id, extra=timedelta(minutes=30))  # worker late by 30 minutes
    reenter(a, b)
    assert act(b, a, "accept").status_code == 200  # accepted after battle_at, before resolution
    assert resolve_due(a)["outcome"] != "voided_by_pact"


def test_notice_given_after_battle_at_keeps_that_instant_covered(fleets):
    a, b = rivals(fleets)
    pacted(a, b)
    planet, _ = planet_of(b)
    strike = arm(a, {"frigate": 2})
    mission_id, _ = launched(a, attack(a, strike, planet, {"frigate": 2}))
    until_battle(a, mission_id, extra=timedelta(minutes=30))
    reenter(a, b)
    assert act(a, b, "terminate").status_code == 200  # notice after battle_at
    assert resolve_due(a)["outcome"] == "voided_by_pact"


def test_concurrent_accept_and_refuse_have_exactly_one_effect(fleets):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    a, b = rivals(fleets)
    meet(a, b)
    assert act(a, b, "propose").status_code == 200
    barrier = Barrier(2)

    def answer(action):
        barrier.wait()
        return act(b, a, action)

    with ThreadPoolExecutor(2) as pool:
        answers = list(pool.map(answer, ["accept", "refuse"]))
    assert sorted(r.status_code for r in answers) == [200, 409]
    with a.game.factory() as s:
        pacts = s.scalar(
            select(func.count())
            .select_from(RelationPact)
            .where(RelationPact.universe_id == a.universe)
        )
        assert pacts in (0, 1)
        low, high = pair(a.empire, b.empire)
        row = s.get(RelationPair, (low, high))
        assert row.proposal_by_empire_id is None


# --- AI policy v3 ---------------------------------------------------------------------------------


@pytest.fixture
def ai_world_v08(database_engine):
    from app.ai.bootstrap import bootstrap

    class AIClock:
        at = datetime(2099, 1, 1, tzinfo=UTC)

        def now(self):
            return self.at

    factory = create_session_factory(database_engine)
    clock = AIClock()
    engine = TimeEngine(factory, clock)
    universe = uuid4()
    with factory.begin() as session:
        result = bootstrap(
            session,
            engine,
            universe,
            "AI v0.8 test",
            "test-galaxy",
            ["economic_cautious", "expansionist"],
            clock.now(),
            rules=load_ruleset("v0.8"),
        )
    try:
        yield factory, clock, engine, result
    finally:
        with factory.begin() as session:
            session.execute(text("TRUNCATE universes, game_principals, control_operations CASCADE"))


def test_ai_answers_an_incoming_proposal_first_and_never_breaks_or_attacks(ai_world_v08):
    from app.ai.models import AIDecision
    from app.ai.orchestrator import Orchestrator

    factory, clock, _, result = ai_world_v08
    human = UUID(result["actors"][0]["empire_id"])
    cautious, bold = result["actors"][1], result["actors"][2]
    u = UUID(result["universe_id"])
    with factory.begin() as s:
        for actor in (cautious, bold):
            relations.record_contact(s, u, human, UUID(actor["empire_id"]), "presence", clock.at)
            relations.propose(
                s, u, human, UUID(actor["empire_id"]), key=f"test:{actor['empire_id']}", at=clock.at
            )
        # A recent grievance of the human against the expansionist AI (test-placed fact).
        row = relations.ensure_pair(s, u, human, UUID(bold["empire_id"]))
        relations.record_hostile(row, human, clock.at - timedelta(hours=1))
    clock.at += timedelta(minutes=10)
    runner = Orchestrator(factory, clock)
    for actor in (cautious, bold):
        cid = UUID(actor["controller_id"])
        assert runner.process_next(controller_id=cid, raise_errors=True)["outcome"] == "accepted"
        with factory() as s:
            trace = s.get(AIDecision, (cid, 1))
            chosen = next(
                c for c in trace.observation["candidates"] if c["key"] == trace.trace["choice"]
            )
            assert chosen["operation"] == "relation"
            expected = "accept" if actor is cautious else "refuse"
            assert chosen["body"] == {"action": expected, "counterpart_id": str(human)}
            assert not any(
                c["operation"] == "launch" and c["body"].get("kind") == "ATTACK"
                for c in trace.observation["candidates"]
            )
            assert not any(
                c["operation"] == "relation" and c["body"]["action"] in {"terminate", "withdraw"}
                for c in trace.observation["candidates"]
            )
    with factory() as s:
        pacts = list(s.scalars(select(RelationPact).where(RelationPact.universe_id == u)))
        assert [p.accepted_by_empire_id for p in pacts] == [UUID(cautious["empire_id"])]


def test_ai_spontaneous_proposal_follows_its_profile_rule(ai_world_v08):
    from app.ai.controller import authorize
    from app.ai.models import AIController
    from app.ai.observation import collect

    factory, clock, _, result = ai_world_v08
    human = UUID(result["actors"][0]["empire_id"])
    u = UUID(result["universe_id"])
    with factory.begin() as s:
        for actor in result["actors"][1:]:
            relations.record_contact(s, u, UUID(actor["empire_id"]), human, "presence", clock.at)

    def proposal(actor):
        with factory() as s:
            c = s.get(AIController, UUID(actor["controller_id"]))
            obs = collect(s, c, authorize(s, c), clock.at)[0]
            return next(
                c for c in obs["candidates"] if c["operation"] == "relation"
                and c["body"] == {"action": "propose", "counterpart_id": str(human)}
            )

    cautious, bold = result["actors"][1], result["actors"][2]
    assert proposal(cautious)["reason"] is None
    assert proposal(bold)["reason"] == "no_past_grievance"
    with factory.begin() as s:
        row = relations.ensure_pair(s, u, human, UUID(bold["empire_id"]))
        relations.record_hostile(row, human, clock.at - timedelta(hours=73))
    assert proposal(bold)["reason"] is None  # an attack suffered more than 72 h ago
    with factory.begin() as s:
        row = relations.ensure_pair(s, u, human, UUID(cautious["empire_id"]))
        relations.record_hostile(row, human, clock.at - timedelta(hours=1))
    assert proposal(cautious)["reason"] == "recent_grievance"


def test_contacts_are_stored_once_per_observer_and_only_move_forward(fleets):
    a, b = rivals(fleets)
    meet(a, b)
    first = relation_of(a, b)["contact"]["first_seen_at"]
    a.advance(minutes=5)
    meet(a, b, both=False)
    with a.game.factory() as s:
        count = s.scalar(
            select(func.count())
            .select_from(RelationContact)
            .where(RelationContact.universe_id == a.universe)
        )
        assert count == 2
    contact = relation_of(a, b)["contact"]
    assert contact["first_seen_at"] == first and contact["last_seen_at"] > first


def test_a_proposal_introduces_the_proposer_durably_without_any_place(fleets):
    """Q18 amendment: A knows B, B does not know A; A's valid proposal gives B a durable
    oriented contact (source diplomacy, identity and date only)."""
    a, b = rivals(fleets)
    meet(a, b, both=False)
    assert relation_of(b, a) is None
    sent = act(a, b, "propose")
    assert sent.status_code == 200
    introduced = relation_of(b, a)["contact"]
    assert introduced == {
        "first_source": "diplomacy",
        "first_seen_at": sent.json()["result"]["at"],
        "last_seen_at": sent.json()["result"]["at"],
        "presence": None,
    }
    planet, system = planet_of(a)
    leak = str(rel(b).json())
    assert str(planet) not in leak and str(system) not in leak and str(a.colony) not in leak
    # Refusal never makes B forget A; B may now propose itself (A's cooldown is A's only).
    assert act(b, a, "refuse").status_code == 200
    assert relation_of(b, a)["contact"]["first_source"] == "diplomacy"
    assert relation_of(b, a)["actions"] == ["propose"]
    assert act(b, a, "propose").status_code == 200
    assert act(b, a, "withdraw").status_code == 200  # withdrawal: contact kept as well
    assert relation_of(b, a)["contact"]["first_source"] == "diplomacy"
    # After A's cooldown, A proposes again and lets it expire: B still knows A.
    a.advance(hours=24)
    reenter(a, b)
    assert act(a, b, "propose").status_code == 200
    a.advance(hours=72)
    reenter(a, b)
    assert relation_of(b, a)["proposal"] is None
    assert relation_of(b, a)["contact"]["first_source"] == "diplomacy"
    assert act(b, a, "propose").status_code == 200
    with a.game.factory() as s:
        row = s.get(RelationContact, (b.empire, a.empire))
        assert row.presence_planet_id is None and row.presence_observed_at is None


def test_ai_turn_records_presence_contacts_after_its_dispatch(ai_world_v08):
    """Global lock order pair → contact: an AI turn defers presence contacts until after its
    command, so the observation of that turn does not contain a contact first seen in it."""
    from app.ai.models import AIDecision
    from app.ai.orchestrator import Orchestrator

    factory, clock, _, result = ai_world_v08
    u = UUID(result["universe_id"])
    human = UUID(result["actors"][0]["empire_id"])
    cautious = result["actors"][1]
    with factory.begin() as s:
        home = s.get(Planet, s.get(Colony, UUID(cautious["colony_id"])).planet_id).system_id
        free = s.scalar(
            select(Planet.id)
            .where(Planet.system_id == home, ~Planet.id.in_(select(Colony.planet_id)))
            .order_by(Planet.id)
            .limit(1)
        )
        # Test-only placement of a human colony in the AI's own (MONITORED) home system.
        s.add(Colony(universe_id=u, empire_id=human, planet_id=free))
    clock.at += timedelta(minutes=10)
    cid = UUID(cautious["controller_id"])
    Orchestrator(factory, clock).process_next(controller_id=cid, raise_errors=True)
    with factory() as s:
        contact = s.get(RelationContact, (UUID(cautious["empire_id"]), human))
        assert contact.first_source == "presence" and contact.presence_planet_id == free
        assert contact.first_seen_at == clock.at
        trace = s.get(AIDecision, (cid, 1))
        assert trace.observation["relations"] == []  # deferred: visible from the next turn
