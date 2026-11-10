"""User decision 10/11/2026 on real PostgreSQL: ship units come out one at a time; cancelling
keeps the units already out and refunds only the others."""

# ruff: noqa: F811
import pytest
from test_colony_api import Clock, game  # noqa: F401
from test_fleet import cancel, fleets, garrison, order, view, worker  # noqa: F401

from app.colony.rules import load_ruleset  # noqa: E402

pytestmark = pytest.mark.integration


def probes(w):
    g = garrison(w)
    return (g or {}).get("stacks", {}).get("probe", 0)


def test_five_probes_come_out_every_twenty_minutes_not_all_after_a_hundred(fleets):
    w = fleets()
    sent = order(w, "probe", 5)
    assert sent.status_code == 200, sent.json()
    order_id = sent.json()["result"]["order_id"]
    w.advance(minutes=19)
    worker(w)
    assert probes(w) == 0
    w.advance(minutes=2)
    worker(w)
    assert probes(w) == 1
    w.advance(minutes=20)
    worker(w)
    assert probes(w) == 2
    colony = view(w).json()["colonies"][0]
    (row,) = colony["orders"]
    assert row["delivered"] == 2 and row["status"] == "active"
    refunded = cancel(w, order_id)
    assert refunded.status_code == 200, refunded.json()
    assert probes(w) == 2
    # Three undelivered probes refunded at the active rate, never the two already out.
    rules = load_ruleset("v0.4").fleets
    cost = rules.classes["probe"].cost["alloys"] * 1_000_000 * 5
    expected = cost * 3 // 5 * rules.refund_active_bps // 10000
    assert refunded.json()["result"]["refunded"]["alloys"] == str(expected)
    w.advance(minutes=60)  # more than the 3 remaining units would take (session still valid)
    worker(w)
    assert probes(w) == 2
