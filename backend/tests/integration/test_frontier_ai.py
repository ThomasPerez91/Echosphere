"""Real PostgreSQL tests for 13B B08: AI frontier protocol policy (ruleset v0.9, policy v4)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from app.ai.controller import AIDenied, authorize
from app.ai.models import AIController
from app.ai.observation import collect
from app.ai.policy import choose
from app.colony.rules import load_ruleset
from app.fleet import service as fleet_service
from app.fleet.models import Fleet, FleetOperation, FleetStack
from app.persistence.database import create_session_factory
from app.persistence.models import Colony, Planet, StellarSystem
from app.relations import service as relations
from app.simulation.service import TimeEngine

pytestmark = pytest.mark.integration


class Clock:
    def __init__(self):
        self.at = datetime(2099, 1, 1, tzinfo=UTC)

    def now(self):
        return self.at


@pytest.fixture
def ai_world_v09(database_engine):
    from app.ai.bootstrap import bootstrap

    factory = create_session_factory(database_engine)
    clock = Clock()
    engine = TimeEngine(factory, clock)
    universe = uuid4()
    with factory.begin() as session:
        result = bootstrap(
            session,
            engine,
            universe,
            "AI v0.9 test",
            "test-galaxy",
            ["economic_cautious", "expansionist"],
            clock.now(),
            rules=load_ruleset("v0.9"),
        )
    try:
        yield factory, clock, engine, result
    finally:
        with factory.begin() as session:
            session.execute(text("TRUNCATE universes, game_principals, control_operations CASCADE"))


def home_system(s, actor):
    colony = s.get(Colony, UUID(actor["colony_id"]))
    return s.get(Planet, colony.planet_id).system_id


def station(factory, actor, units, system=None):
    """Test-only placement of an operational Fleet (the AI never receives free units in play)."""
    with factory.begin() as s:
        fleet = Fleet(
            empire_id=UUID(actor["empire_id"]),
            universe_id=s.get(Colony, UUID(actor["colony_id"])).universe_id,
            home_colony_id=UUID(actor["colony_id"]),
            kind="TASK",
            status="STATIONED",
            system_id=system or home_system(s, actor),
            name="Test-only",
        )
        s.add(fleet)
        s.flush()
        for ship, count in units.items():
            s.add(FleetStack(fleet_id=fleet.id, ship_class=ship, count=count))
        return fleet.id


def observe(factory, clock, actor):
    with factory() as s:
        c = s.get(AIController, UUID(actor["controller_id"]))
        rules = authorize(s, c)
        assert rules.ai.policy_version == "utility-goals-v4"
        return collect(s, c, rules, clock.now())[0], c.profile, rules


def protocol_candidates(observation):
    return [c for c in observation["candidates"] if c["operation"] == "protocol"]


def test_both_profiles_watch_their_presence_zone_through_the_military_page(ai_world_v09):
    factory, clock, _, result = ai_world_v09
    for actor in result["actors"][1:]:
        watch = station(factory, actor, {"interceptor": 1})
        obs, _, rules = observe(factory, clock, actor)
        (candidate,) = protocol_candidates(obs)
        assert candidate["goal"] == "military" and candidate["reason"] is None
        assert candidate["body"] == {"fleet_id": str(watch), "protocol": "SURVEILLANCE"}
        assert candidate["utility"] == rules.ai.frontier.surveillance_utility
        (posture,) = obs["frontier"]
        assert posture["basis"] == "presence" and posture["current"] is None
        military = [c for c in obs["candidates"] if c["goal"] == "military"]
        assert len(military) <= rules.ai.family_pages["military"]  # same budget, no extra page
        assert len(obs["candidates"]) <= rules.ai.candidate_limit


def test_logistics_fleets_and_garrisons_get_no_protocol(ai_world_v09):
    factory, clock, _, result = ai_world_v09
    actor = result["actors"][1]
    rules = load_ruleset("v0.9")
    station(factory, actor, {rules.colonization.colonizer_class: 1})
    obs, _, _ = observe(factory, clock, actor)
    assert protocol_candidates(obs) == [] and obs["frontier"] == []


def test_expansionist_ambushes_only_a_known_recent_aggressor_without_pact(ai_world_v09):
    factory, clock, _, result = ai_world_v09
    human = UUID(result["actors"][0]["empire_id"])
    cautious, bold = result["actors"][1], result["actors"][2]
    u = UUID(result["universe_id"])
    for actor in (cautious, bold):
        station(factory, actor, {"interceptor": 2})
    with factory.begin() as s:
        for actor in (cautious, bold):
            e = UUID(actor["empire_id"])
            relations.record_contact(s, u, e, human, "presence", clock.at - timedelta(days=5))
            row = relations.ensure_pair(s, u, human, e)
            relations.record_hostile(row, human, clock.at - timedelta(hours=1))
    bold_obs, _, rules = observe(factory, clock, bold)
    assert [c["body"]["protocol"] for c in protocol_candidates(bold_obs)] == ["AMBUSH"]
    assert protocol_candidates(bold_obs)[0]["utility"] == rules.ai.frontier.ambush_utility
    assert bold_obs["frontier"][0]["basis"] == "known_enemy"
    cautious_obs, _, _ = observe(factory, clock, cautious)
    assert [c["body"]["protocol"] for c in protocol_candidates(cautious_obs)] == ["SURVEILLANCE"]
    # Outside the D4 window, or under a pact, the hostile posture is no longer justified.
    clock.at += timedelta(hours=72)
    later, _, _ = observe(factory, clock, bold)
    assert [c["body"]["protocol"] for c in protocol_candidates(later)] == ["SURVEILLANCE"]
    clock.at -= timedelta(hours=72)
    with factory.begin() as s:
        e = UUID(bold["empire_id"])
        relations.record_contact(s, u, human, e, "presence", clock.at - timedelta(days=5))
        relations.propose(s, u, human, e, key="test:pact", at=clock.at)
        relations.accept(s, u, e, human, key="test:accept", at=clock.at)
    covered, _, _ = observe(factory, clock, bold)
    assert [c["body"]["protocol"] for c in protocol_candidates(covered)] == ["SURVEILLANCE"]


def test_voluntary_contact_needs_a_real_anonymous_sighting_and_no_grievance(ai_world_v09):
    """A real v0.9 passage of the human Fleet into the AI home system is detected anonymously
    by the AI's surveillance; only then is FRIENDLY_CONTACT worth it."""
    from app.frontier.orchestrator import FrontierOrchestrator
    from app.galaxy import service as galaxy

    factory, clock, engine, result = ai_world_v09
    human, cautious = result["actors"][0], result["actors"][1]
    u = UUID(result["universe_id"])
    watch = station(factory, cautious, {"interceptor": 1})
    with factory.begin() as s:
        fleet_service.set_protocol(
            s, engine, u, UUID(cautious["empire_id"]), watch, "SURVEILLANCE",
            key=uuid4().hex, at=clock.at,
        )
        for system in s.scalars(select(StellarSystem.id).where(StellarSystem.universe_id == u)):
            galaxy.map_system(s, u, UUID(human["empire_id"]), system, clock.at)
        target = home_system(s, cautious)
    mover = station(factory, human, {"interceptor": 1})
    with factory.begin() as s:
        mission = fleet_service.launch(
            s, engine, u, UUID(human["empire_id"]), mover, "DEPLOY", target,
            {"interceptor": 1}, None, key=uuid4().hex, at=clock.at,
        )
        arrival = mission.travel_arrival_at
    obs, _, _ = observe(factory, clock, cautious)
    assert protocol_candidates(obs) == []  # already SURVEILLANCE, nothing sighted yet
    clock.at = arrival + timedelta(minutes=1)
    runner = FrontierOrchestrator(factory, clock)
    while runner.process_next() is not None:
        pass
    obs, _, _ = observe(factory, clock, cautious)
    assert [c["body"]["protocol"] for c in protocol_candidates(obs)] == ["FRIENDLY_CONTACT"]
    assert obs["frontier"][0]["basis"] == "anonymous_sighting"
    assert human["empire_id"] not in str(obs["frontier"])  # Fog: the signature stays anonymous
    with factory.begin() as s:  # a recent hostile act against the AI: risk no longer acceptable
        row = relations.ensure_pair(s, u, UUID(human["empire_id"]), UUID(cautious["empire_id"]))
        relations.record_hostile(row, UUID(human["empire_id"]), clock.at - timedelta(hours=1))
    risky, _, _ = observe(factory, clock, cautious)
    assert protocol_candidates(risky) == []  # stays SURVEILLANCE: no change without reason


def test_protocol_goes_through_the_common_command_and_never_repeats(ai_world_v09):
    from app.ai.dispatcher import dispatch

    factory, clock, engine, result = ai_world_v09
    actor = result["actors"][1]
    watch = station(factory, actor, {"interceptor": 1})
    obs, _, _ = observe(factory, clock, actor)
    (candidate,) = protocol_candidates(obs)
    with factory.begin() as s:
        c = s.get(AIController, UUID(actor["controller_id"]))
        dispatch(s, engine, c, candidate, f"ai:{c.id}:1:protocol", clock.now())
    with factory() as s:
        assert s.get(Fleet, watch).protocol == "SURVEILLANCE"
        key = f"ai:{actor['controller_id']}:1:protocol"
        ledger = s.get(FleetOperation, (UUID(actor["empire_id"]), key))
        assert ledger.kind == "protocol"
    again, _, _ = observe(factory, clock, actor)
    assert protocol_candidates(again) == []  # same state, same posture: no new command


@pytest.mark.parametrize(
    ("index", "protocol"),
    [(1, "AMBUSH"), (1, "INTERCEPTION"), (2, "INTERCEPTION")],
)
def test_dispatcher_refuses_protocols_outside_the_profile_policy(ai_world_v09, index, protocol):
    from app.ai.dispatcher import dispatch

    factory, clock, engine, result = ai_world_v09
    actor = result["actors"][index]
    watch = station(factory, actor, {"interceptor": 1})
    forged = {"operation": "protocol", "body": {"fleet_id": str(watch), "protocol": protocol}}
    with pytest.raises(AIDenied, match="ai_protocol_denied"), factory.begin() as s:
        c = s.get(AIController, UUID(actor["controller_id"]))
        dispatch(s, engine, c, forged, "ai:forged", clock.now())


def test_diplomatic_answer_and_urgent_defence_keep_priority_over_protocols(ai_world_v09):
    factory, clock, _, result = ai_world_v09
    human = UUID(result["actors"][0]["empire_id"])
    actor = result["actors"][1]
    u = UUID(result["universe_id"])
    station(factory, actor, {"interceptor": 1})
    with factory.begin() as s:
        relations.record_contact(s, u, human, UUID(actor["empire_id"]), "presence", clock.at)
        relations.propose(s, u, human, UUID(actor["empire_id"]), key="test:offer", at=clock.at)
    obs, profile, rules = observe(factory, clock, actor)
    assert protocol_candidates(obs)  # still visible, never starved from the page
    choice = choose(obs, {}, profile, rules.ai)
    chosen = next(c for c in obs["candidates"] if c["key"] == choice["choice"])
    assert chosen["operation"] != "protocol"
    assert chosen.get("priority") or chosen["bootstrap"]


def test_hidden_foreign_fleets_never_change_the_posture(ai_world_v09):
    factory, clock, _, result = ai_world_v09
    human, actor = result["actors"][0], result["actors"][2]
    station(factory, actor, {"interceptor": 1})
    before, _, _ = observe(factory, clock, actor)
    with factory() as s:
        here = home_system(s, actor)
    hidden = station(factory, human, {"interceptor": 5}, system=here)  # never detected
    after, _, _ = observe(factory, clock, actor)
    assert after["frontier"] == before["frontier"]
    assert str(hidden) not in str(after) and human["empire_id"] not in str(after["frontier"])
