"""Ruleset v0.12 on real PostgreSQL: research tiers III-IV effects on new orders only, frozen in
their snapshot (a ship order completes even after its bonus changed)."""

# ruff: noqa: F811
import pytest
from sqlalchemy import select
from test_colony_api import Clock, game  # noqa: F401
from test_colony_v011_gates import build, set_level
from test_fleet import FULL, fleets, order, worker  # noqa: F401
from test_unit_delivery import probes

from app.colony.models import ConstructionOrder
from app.colony.rules import load_ruleset
from app.fleet.models import ShipOrder
from app.research.models import AcquiredTechnology

pytestmark = pytest.mark.integration


def acquire(w, technology_id):
    rules = load_ruleset("v0.12").research.technologies[technology_id]
    with w.game.factory.begin() as s:
        s.add(
            AcquiredTechnology(
                empire_id=w.empire,
                universe_id=w.universe,
                technology_id=technology_id,
                acquired_at=w.game.clock(),
                effect=rules.effect,
                reduction_bps=rules.reduction_bps,
            )
        )


def test_ship_effects_are_frozen_in_the_order_and_its_units_still_come_out(fleets):
    w = fleets(permissions=FULL, ruleset="v0.12")
    set_level(w, "industrial_complex", 2, 4)
    set_level(w, "orbital_shipyard", 1, 5)
    acquire(w, "engineering_4")  # ship_cost -15 %
    acquire(w, "energy_4")  # ship_duration -20 %
    sent = order(w, "probe", 2)
    assert sent.status_code == 200, sent.json()
    probe = load_ruleset("v0.12").fleets.classes["probe"]
    with w.game.factory() as s:
        row = s.scalar(select(ShipOrder).where(ShipOrder.colony_id == w.colony))
        assert row.snapshot["bonus_bps"] == {"ship_cost": 1500, "ship_duration": 2000}
        alloys = probe.cost["alloys"] * 1_000_000 * 2
        assert row.snapshot["cost"]["alloys"] == -(-alloys * 8500 // 10000)
        assert row.snapshot["duration_us"] == probe.build_seconds * 1_000_000 * 2 * 8 // 10
    # A later change of the Empire's technologies never changes the accepted order.
    with w.game.factory.begin() as s:
        s.query(AcquiredTechnology).filter_by(empire_id=w.empire).delete()
    w.advance(seconds=probe.build_seconds * 2 * 8 // 10 + 1)
    worker(w)
    assert probes(w) == 2


def test_colony_duration_shortens_new_constructions_only(fleets):
    w = fleets(permissions=FULL, ruleset="v0.12")
    rules = load_ruleset("v0.12")
    acquire(w, "computation_4")  # colony_duration -15 %
    sent = build(w, "extraction_complex", 1, 2)
    assert sent.status_code in (200, 201), sent.json()
    with w.game.factory() as s:
        row = s.scalar(select(ConstructionOrder).where(ConstructionOrder.colony_id == w.colony))
        base = rules.quote("extraction_complex", 2).base_duration_us
        assert row.snapshot["quote"]["base_duration_us"] == -(-base * 8500 // 10000)
