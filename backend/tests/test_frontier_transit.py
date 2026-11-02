"""13B / FC9: deterministic per-hop entry instants and mirrored ways back (pure)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.frontier.transit import OUTBOUND, RETURN, cancelled, offsets, outbound, way_back

T0 = datetime(2099, 1, 1, tzinfo=UTC)
US = timedelta(microseconds=1)
A, B, C, HOME = (UUID(int=i) for i in (1, 2, 3, 9))


def test_offsets_are_integer_increasing_and_end_exactly_at_travel():
    assert offsets(3_600_000_000, 3) == [1_200_000_000, 2_400_000_000, 3_600_000_000]
    uneven = offsets(1_000_000_001, 3)
    assert uneven == [333_333_334, 666_666_668, 1_000_000_001]  # ceiling, exact end
    assert all(a < b for a, b in zip(uneven, uneven[1:], strict=False))
    with pytest.raises(ValueError):
        offsets(10, 0)


def test_outbound_enters_each_crossed_system_once_destination_included():
    route = outbound(T0, 3_000_000, [A, B, C])
    assert [(p.sequence, p.system_id, p.direction) for p in route] == [
        (0, A, OUTBOUND),
        (1, B, OUTBOUND),
        (2, C, OUTBOUND),
    ]
    assert [p.entered_at - T0 for p in route] == [1_000_000 * US, 2_000_000 * US, 3_000_000 * US]
    assert outbound(T0, 5, []) == []  # a local mission crosses nothing


def test_recall_in_transit_mirrors_the_way_out_and_cancels_unreached_entries():
    route = outbound(T0, 3_000_000, [A, B, C])
    recall = T0 + 2_500_000 * US  # past B, before C
    back = way_back(route, HOME, T0, recall, recall)
    assert [(p.system_id, p.entered_at - recall) for p in back] == [
        (B, 500_000 * US),
        (A, 1_500_000 * US),
        (HOME, 2_500_000 * US),  # == existing return_at = recall + (recall - started)
    ]
    assert [p.sequence for p in back] == [3, 4, 5] and {p.direction for p in back} == {RETURN}
    assert [p.system_id for p in cancelled(route, recall)] == [C]


def test_recall_exactly_on_an_entry_leaves_that_system_without_reentering_it():
    route = outbound(T0, 3_000_000, [A, B, C])
    at_b = route[1].entered_at
    back = way_back(route, HOME, T0, at_b, at_b)
    assert [p.system_id for p in back] == [A, HOME]
    assert [p.system_id for p in cancelled(route, at_b)] == [C]


def test_full_return_after_arrival_or_battle_starts_from_the_destination():
    route = outbound(T0, 3_000_000, [A, B, C])
    arrival = route[-1].entered_at
    battle = T0 + timedelta(hours=24)
    back = way_back(route, HOME, T0, battle, arrival)
    assert [(p.system_id, p.entered_at - battle) for p in back] == [
        (B, 1_000_000 * US),
        (A, 2_000_000 * US),
        (HOME, 3_000_000 * US),  # == battle_at + travel, the existing ATTACK return_at
    ]
    assert cancelled(route, arrival) == []


def test_way_back_refuses_incoherent_instants():
    route = outbound(T0, 3_000_000, [A])
    with pytest.raises(ValueError):
        way_back(route, HOME, T0, T0, T0 + US)  # departs before reaching the turning point
    with pytest.raises(ValueError):
        way_back(route, HOME, T0, T0, T0 - US)
    assert way_back(route, HOME, T0, T0, T0) == []  # recalled at launch: never left
