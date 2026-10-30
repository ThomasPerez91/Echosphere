"""Pure Q39 allocations: finite storage, exact micro-units and aggregate overflow."""

from uuid import uuid4

import pytest

from app.colony.service import cancellation_plan, recoverable_refunds
from app.simulation.models import ResourceBalance
from app.simulation.production import MAX_AMOUNT, RESOURCES


@pytest.mark.parametrize("free", [0, 1, 600, 1000, 1500])
def test_refund_allocation_is_exact_capped_and_ordered(free):
    balances = {r: ResourceBalance(stock=2000 - free, capacity=2000) for r in RESOURCES}
    per_order = {"active": {"alloys": 200, "flux": 96}, "queued": {"alloys": 800}}
    before = {r: b.stock for r, b in balances.items()}
    actual, recovered, lost = recoverable_refunds(balances, per_order)
    assert recovered["alloys"] == min(free, 1000)
    assert actual["active"]["alloys"] == min(free, 200)
    assert actual["queued"]["alloys"] == min(max(0, free - 200), 800)
    for r in RESOURCES:
        theoretical = sum(v.get(r, 0) for v in per_order.values())
        assert recovered[r] + lost[r] == theoretical
        assert sum(v[r] for v in actual.values()) == recovered[r]
        assert before[r] + recovered[r] <= balances[r].capacity
        assert balances[r].stock == before[r]  # Projection never mutates storage.


def test_theoretical_totals_can_exceed_bigint_but_credited_stock_cannot():
    from types import SimpleNamespace

    # Each snapshot is valid; the transient sum across orders can exceed a persisted BIGINT.
    from app.colony.rules import load_ruleset
    from app.colony.service import OrderSnapshot

    rules = load_ruleset()
    snapshot = OrderSnapshot(
        ruleset_version=rules.version,
        infrastructure_type="extraction_complex",
        sector_index=5,
        target_level=1,
        quote=rules.quote("extraction_complex", 1),
        construction_speed=rules.colony.speeds["construction"],
        refund_queued_bps=10000,
        refund_active_bps=8000,
    ).model_dump()
    snapshot["quote"]["cost"]["alloys"] = MAX_AMOUNT
    root = SimpleNamespace(
        id=uuid4(),
        sector_index=5,
        sequence=1,
        status="queued",
        snapshot=snapshot,
        infrastructure_type="extraction_complex",
        target_level=1,
    )
    dependent = SimpleNamespace(
        id=uuid4(),
        sector_index=5,
        sequence=2,
        status="queued",
        snapshot=snapshot,
        infrastructure_type="extraction_complex",
        target_level=1,
    )
    _, per_order, totals = cancellation_plan([root, dependent], root)
    assert totals["alloys"] == 2 * MAX_AMOUNT
    balances = {r: ResourceBalance(stock=0, capacity=MAX_AMOUNT) for r in RESOURCES}
    _, recovered, lost = recoverable_refunds(balances, per_order)
    assert recovered["alloys"] == lost["alloys"] == MAX_AMOUNT
