"""EXP-02b on real PostgreSQL + GameSession: EXTRACT claims share a deposit, stop, refusals."""

# ruff: noqa: F811
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_colony_api import Clock, game  # noqa: F401
from test_fleet import FULL, fleets, order, post, view, worker  # noqa: F401

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


def fleet_by(w, fleet_id):
    return next(f for f in view(w).json()["fleets"] if f["id"] == fleet_id)


def test_two_claims_share_the_throughput_by_extractors_then_one_stops_on_recall(fleets):
    w = fleets(permissions=FULL, ruleset="v0.10")
    deposit = seed_deposit(w)
    hidden = seed_deposit(w, known=False)
    assert order(w, "extractor", 2).status_code == 200
    w.advance(minutes=101)
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
    w.advance(minutes=121)
    assert worker(w) >= 1
    assert fleet_by(w, b_fleet)["cargo"]["alloys"] == str(30 * M)
    w.advance(minutes=120)
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
    w.advance(minutes=60)
    stop = post(w, f"/missions/{mission}/recall", {"idempotency_key": uuid4().hex})
    assert stop.status_code == 200, stop.json()
    stopped = fleet_by(w, b_fleet)
    assert stopped["status"] == "STATIONED" and stopped["cargo"]["alloys"] == str(50 * M)
    w.advance(minutes=180)
    worker(w)  # the cancelled end event never credits twice
    assert fleet_by(w, b_fleet)["cargo"]["alloys"] == str(50 * M)
    with w.game.factory() as s:
        assert s.get(GalaxyOpportunity, deposit).reserve_remaining == 4880 * M


def test_a_probe_cannot_extract(fleets):
    w = fleets(permissions=FULL, ruleset="v0.10")
    deposit = seed_deposit(w)
    assert order(w, "probe", 1).status_code == 200
    w.advance(minutes=21)
    worker(w)
    garrison = next(f for f in view(w).json()["fleets"] if f["kind"] == "GARRISON")
    refused = extract(w, garrison["id"], deposit, {"probe": 1}, 2)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "extract_units"
