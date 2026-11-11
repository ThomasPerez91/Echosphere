"""EXP-02c (v0.12) on real PostgreSQL: an ATTACK on a deposit fights the extraction operations
of the Empire bound at launch; unescorted extractors fall with their hold, escorted ones keep
extracting and finish normally; a deposit nobody works is an empty target."""

# ruff: noqa: F811
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_colony_api import Clock, game  # noqa: F401
from test_combat import arm, engagement_of, launched, reenter, resolve_due, rivals, until_battle
from test_extract_missions import extract
from test_fleet import fleets, post, worker  # noqa: F401

from app.colony.models import UniverseEconomy
from app.combat.models import CombatReport
from app.fleet.models import Fleet, FleetMission, FleetReport
from app.fleet.service import colony_system
from app.frontier.orchestrator import FrontierOrchestrator
from app.galaxy.models import DepositClaim, GalaxyOpportunity, OpportunityKnowledge
from app.persistence.models import Colony
from app.simulation.production import MICRO_UNITS as M

pytestmark = pytest.mark.integration


def contested_world(fleets):
    """Attacker A, defender B (v0.12); a deposit in B's home system known to both. Test-only:
    a one-hour attack warning in the pinned rules so the battle falls within the extraction."""
    a, b = rivals(fleets, ruleset="v0.12")
    with a.game.factory.begin() as s:
        row = s.get(UniverseEconomy, a.universe)
        data = dict(row.ruleset_data)
        data["combat"] = dict(data["combat"], min_warning_seconds=3600)
        row.ruleset_data = data
        system = colony_system(s, s.get(Colony, b.colony))
        start = len(
            s.scalars(
                select(GalaxyOpportunity.id).where(GalaxyOpportunity.system_id == system)
            ).all()
        )
        deposit = GalaxyOpportunity(
            universe_id=a.universe,
            system_id=system,
            ordinal=start,
            family="deposit",
            kind="metal_belt",
            tier="common",
            resource="alloys",
            reserve_total=90000 * M,
            reserve_remaining=90000 * M,
            throughput_per_hour=500 * M,
        )
        s.add(deposit)
        s.flush()
        for w in (a, b):
            s.add(
                OpportunityKnowledge(
                    empire_id=w.empire,
                    opportunity_id=deposit.id,
                    universe_id=w.universe,
                    observed_at=w.game.clock(),
                    observed_reserve=deposit.reserve_remaining,
                )
            )
        return a, b, deposit.id, system


def strike(a, fleet, deposit, units):
    body = {
        "idempotency_key": uuid4().hex,
        "fleet_id": str(fleet),
        "kind": "ATTACK",
        "target_opportunity_id": str(deposit),
        "units": units,
    }
    return post(a, "/missions", body)


def settle(a, b):
    """Frontier entries first (they rank before the battle), then both Empires' events."""
    runner = FrontierOrchestrator(a.game.factory, Clock(a.game))
    for _ in range(4):
        for _ in range(50):
            if runner.process_next() is None:
                break
        worker(a)
        worker(b)


def test_unescorted_extractors_are_destroyed_with_their_hold(fleets):
    a, b, deposit, system = contested_world(fleets)
    miners = arm(b, {"extractor": 2, "freighter": 4})
    sent = extract(b, miners, deposit, {"extractor": 2, "freighter": 4}, 24)
    assert sent.status_code == 200, sent.json()
    op_id = UUID(sent.json()["result"]["mission_id"])
    raid = arm(a, {"cruiser": 2})
    mission_id, _ = launched(a, strike(a, raid, deposit, {"cruiser": 2}))
    engagement = engagement_of(a, mission_id)
    assert engagement.defender_empire_id == b.empire and engagement.target_planet_id is None
    until_battle(a, mission_id)
    reenter(a)
    reenter(b)
    settle(a, b)
    assert resolve_due(a)["outcome"] == "unopposed"
    with a.game.factory() as s:
        fleet = s.get(Fleet, miners)
        assert (fleet.status, fleet.active_mission_id) == ("DESTROYED", None)
        op = s.get(FleetMission, op_id)
        assert op.status == "completed" and op.completed_at == engagement.battle_at
        assert s.get(FleetReport, op_id).result["destroyed"] is True
        claim = s.get(DepositClaim, op_id)
        assert claim.active_until == engagement.battle_at
        report = s.get(CombatReport, (engagement.id, b.empire))
        assert report.role == "defender" and report.result["target"]["opportunity_id"] == str(
            deposit
        )
        resolved = s.get(type(engagement), engagement.id)
        assert resolved.result["destroyed_operations"] == [str(miners)]


def test_escorted_extraction_defends_itself_and_still_finishes(fleets):
    a, b, deposit, _ = contested_world(fleets)
    miners = arm(b, {"extractor": 2, "freighter": 4, "cruiser": 4})
    sent = extract(b, miners, deposit, {"extractor": 2, "freighter": 4, "cruiser": 4}, 24)
    assert sent.status_code == 200, sent.json()
    op_id = UUID(sent.json()["result"]["mission_id"])
    raid = arm(a, {"interceptor": 1})
    mission_id, _ = launched(a, strike(a, raid, deposit, {"interceptor": 1}))
    until_battle(a, mission_id)
    reenter(a)
    reenter(b)
    settle(a, b)
    assert resolve_due(a)["outcome"] == "defender_win"
    with a.game.factory() as s:
        assert s.get(Fleet, miners).status == "MOVING"
        due = s.get(FleetMission, op_id).due_at
    # The extraction ends on schedule; its snapshot check counts the escorts lost in battle.
    a.game.test_clock[0] = due + timedelta(minutes=1)
    reenter(b)
    settle(a, b)
    with a.game.factory() as s:
        op = s.get(FleetMission, op_id)
        assert op.status == "completed"
        assert int(s.get(FleetReport, op_id).result["extracted"]) > 0


def test_a_deposit_nobody_works_is_an_empty_target(fleets):
    a, b, deposit, _ = contested_world(fleets)
    raid = arm(a, {"cruiser": 1})
    mission_id, _ = launched(a, strike(a, raid, deposit, {"cruiser": 1}))
    assert engagement_of(a, mission_id).defender_empire_id is None
    until_battle(a, mission_id)
    reenter(a)
    settle(a, b)
    assert resolve_due(a)["outcome"] == "target_unavailable"
