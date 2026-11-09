"""EXP-02b on real PostgreSQL + GameSession: EXTRACT claims share a deposit, stop, refusals."""

# ruff: noqa: F811
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_colonization import reenter
from test_colony_api import Clock, game  # noqa: F401
from test_fleet import FULL, fleets, order, post, surveyed, view, worker  # noqa: F401

from app.fleet.models import FleetReport
from app.fleet.service import colony_system
from app.galaxy.models import DepositClaim, GalaxyOpportunity, OpportunityKnowledge
from app.persistence.models import Colony
from app.simulation.production import MICRO_UNITS as M

pytestmark = pytest.mark.integration


def seed_deposit(w, known=True):
    """A slow deposit in the home system, prospected or not (test world data)."""
    with w.game.factory.begin() as s:
        system = colony_system(s, s.get(Colony, w.colony))
        start = len(s.scalars(select(GalaxyOpportunity.id).where(
            GalaxyOpportunity.system_id == system)).all())
        deposit = GalaxyOpportunity(
            universe_id=w.universe, system_id=system, ordinal=start, family="deposit",
            kind="metal_belt", tier="common", resource="alloys", reserve_total=5000 * M,
            reserve_remaining=5000 * M, throughput_per_hour=30 * M,
        )
        s.add(deposit)
        s.flush()
        if known:
            s.add(OpportunityKnowledge(
                empire_id=w.empire, opportunity_id=deposit.id, universe_id=w.universe,
                observed_at=w.game.clock(), observed_reserve=deposit.reserve_remaining,
            ))
        return deposit.id


def extract(w, fleet, deposit, units, hours, key=None):
    body = {"idempotency_key": key or uuid4().hex, "fleet_id": str(fleet), "kind": "EXTRACT",
            "target_opportunity_id": str(deposit), "units": units, "duration_hours": hours}
    return post(w, "/missions", body)


def wait(w, minutes):
    """Advance the clock; a new GameSession afterwards (sessions expire after 2 h idle)."""
    w.advance(minutes=minutes)
    reenter(w)


def fleet_by(w, fleet_id):
    return next(f for f in view(w).json()["fleets"] if f["id"] == fleet_id)


def test_two_claims_share_the_throughput_by_extractors_then_one_stops_on_recall(fleets):
    w = fleets(permissions=FULL, ruleset="v0.10")
    deposit = seed_deposit(w)
    hidden = seed_deposit(w, known=False)
    assert order(w, "extractor", 2).status_code == 200
    wait(w, 101)
    assert worker(w) >= 1
    garrison = next(f for f in view(w).json()["fleets"] if f["kind"] == "GARRISON")
    assert garrison["stacks"]["extractor"] == 2
    # Refusals before any write: unknown deposit, length out of bounds, no extractor.
    unknown = extract(w, garrison["id"], hidden, {"extractor": 1}, 4)
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "opportunity_not_found"
    too_long = extract(w, garrison["id"], deposit, {"extractor": 1}, 25)
    assert too_long.json()["error"]["code"] == "invalid_request"
    a = extract(w, garrison["id"], deposit, {"extractor": 1}, 4)
    b = extract(w, garrison["id"], deposit, {"extractor": 1}, 2)
    assert a.status_code == 200 and b.status_code == 200, (a.json(), b.json())
    a_fleet, b_fleet = a.json()["result"]["fleet_id"], b.json()["result"]["fleet_id"]
    # 0-2 h: 30/h shared 15/15 (each asks 20/h); 2-4 h: A alone at its own 20/h.
    wait(w, 121)
    assert worker(w) >= 1
    assert fleet_by(w, b_fleet)["cargo"]["alloys"] == str(30 * M)
    wait(w, 120)
    assert worker(w) >= 1
    assert fleet_by(w, a_fleet)["cargo"]["alloys"] == str(70 * M)
    with w.game.factory() as s:
        row = s.get(GalaxyOpportunity, deposit)
        assert row.reserve_remaining == 4900 * M
        assert sorted(c.credited for c in s.scalars(select(DepositClaim).where(
            DepositClaim.opportunity_id == deposit))) == [30 * M, 70 * M]
    # The stationed B fleet works again 3 h, recalled after 1 h: stopped, 20 more aboard.
    again = extract(w, b_fleet, deposit, {"extractor": 1}, 3)
    assert again.status_code == 200, again.json()
    mission = again.json()["result"]["mission_id"]
    wait(w, 60)
    stop = post(w, f"/missions/{mission}/recall", {"idempotency_key": uuid4().hex})
    assert stop.status_code == 200, stop.json()
    stopped = fleet_by(w, b_fleet)
    assert stopped["status"] == "STATIONED" and stopped["cargo"]["alloys"] == str(50 * M)
    wait(w, 180)
    worker(w)  # the cancelled end event never credits twice
    assert fleet_by(w, b_fleet)["cargo"]["alloys"] == str(50 * M)
    with w.game.factory() as s:
        assert s.get(GalaxyOpportunity, deposit).reserve_remaining == 4880 * M


def test_a_probe_cannot_extract(fleets):
    w = fleets(permissions=FULL, ruleset="v0.10")
    deposit = seed_deposit(w)
    assert order(w, "probe", 1).status_code == 200
    wait(w, 21)
    worker(w)
    garrison = next(f for f in view(w).json()["fleets"] if f["kind"] == "GARRISON")
    refused = extract(w, garrison["id"], deposit, {"probe": 1}, 2)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "extract_units"


def test_an_extraction_elsewhere_can_come_back_home_with_its_load(fleets):
    w = fleets(permissions=FULL, ruleset="v0.10")
    probe_fleet, target = surveyed(w)
    with w.game.factory.begin() as s:
        deposit = GalaxyOpportunity(
            universe_id=w.universe, system_id=UUID(target), ordinal=90, family="deposit",
            kind="metal_belt", tier="common", resource="alloys", reserve_total=5000 * M,
            reserve_remaining=5000 * M, throughput_per_hour=90 * M,
        )
        s.add(deposit)
        s.flush()
        s.add(OpportunityKnowledge(
            empire_id=w.empire, opportunity_id=deposit.id, universe_id=w.universe,
            observed_at=w.game.clock(), observed_reserve=deposit.reserve_remaining,
        ))
        deposit_id = deposit.id
    ordered = order(w, "extractor", 1)
    assert ordered.status_code == 200, ordered.json()
    wait(w, 51)
    assert worker(w) >= 1
    garrison = next(f for f in view(w).json()["fleets"] if f["kind"] == "GARRISON")
    home_system = garrison["system"]["id"]

    def quote(after):
        body = {"fleet_id": garrison["id"], "kind": "EXTRACT", "units": {"extractor": 1},
                "target_opportunity_id": str(deposit_id), "duration_hours": 1}
        return post(w, "/missions/preview", body | ({"after": after} if after else {})).json()

    one_way, both_ways = quote(None), quote("RETURN")
    assert both_ways["cost"] == {r: str(2 * int(v)) for r, v in one_way["cost"].items()}
    assert both_ways["destination_id"] == target and both_ways["hops"] >= 1
    body = {"idempotency_key": uuid4().hex, "fleet_id": garrison["id"], "kind": "EXTRACT",
            "target_opportunity_id": str(deposit_id), "units": {"extractor": 1},
            "duration_hours": 1, "after": "RETURN"}
    sent = post(w, "/missions", body)
    assert sent.status_code == 200, sent.json()
    fleet, mission = sent.json()["result"]["fleet_id"], sent.json()["result"]["mission_id"]
    wait(w, 6 * 60)
    worker(w)
    back = fleet_by(w, fleet)
    assert back["status"] == "STATIONED" and back["system"]["id"] == home_system
    assert back["cargo"]["alloys"] == str(20 * M)  # one extractor, 1 h at 20/h
    with w.game.factory() as s:
        report = s.get(FleetReport, UUID(mission))
        assert report.result["returned"] is True and report.result["extracted"] == str(20 * M)
    late = post(w, f"/missions/{mission}/recall", {"idempotency_key": uuid4().hex})
    assert late.status_code == 409
    assert probe_fleet  # the surveying probe stays where it mapped the system
