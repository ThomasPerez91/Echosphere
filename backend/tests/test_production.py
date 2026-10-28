from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.simulation.clock import utc
from app.simulation.production import MAX_AMOUNT, ProductionState, produce

START = datetime(2026, 1, 1, tzinfo=UTC)


def test_many_reads_equal_one_long_absence_without_rounding_loss():
    original = ProductionState(7, 123456789, START, remainder=157)
    split = original
    for i in range(1, 1001):
        split = produce(split, START + timedelta(milliseconds=i))
    assert split == produce(original, START + timedelta(seconds=1))
    assert split.stock > original.stock
    assert split.remainder != 0


def test_hourly_rate_and_microsecond_precision():
    assert (
        produce(ProductionState(0, 1_000_000, START), START + timedelta(hours=1)).stock == 1_000_000
    )
    assert (
        produce(ProductionState(0, 3_600_000_000, START), START + timedelta(microseconds=1)).stock
        == 1
    )


def test_zero_elapsed_does_not_change_stock_or_remainder():
    state = ProductionState(8, 100, START, remainder=55)
    assert produce(state, START) == state


def test_explicit_capacity_discards_overflow_instead_of_banking_it():
    full = produce(ProductionState(0, 1000, START, capacity=10), START + timedelta(hours=10))
    assert (full.stock, full.remainder) == (10, 0)
    spent = ProductionState(0, full.rate_per_hour, full.at, full.remainder, full.capacity)
    assert produce(spent, full.at + timedelta(microseconds=1)).stock == 0


def test_backwards_time_rejected():
    with pytest.raises(ValueError, match="backwards"):
        produce(ProductionState(0, 1, START), START - timedelta(microseconds=1))


def test_naive_time_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        utc(datetime(2026, 1, 1))


def test_offsets_refer_to_the_same_instant():
    local = datetime(2026, 1, 1, 2, tzinfo=timezone(timedelta(hours=2)))
    assert utc(local) == START


@pytest.mark.parametrize("value", [-1, True, 0.5, MAX_AMOUNT + 1])
def test_invalid_amount_rejected(value):
    with pytest.raises(ValueError):
        ProductionState(value, 0, START)


def test_overflow_fails_explicitly():
    with pytest.raises(ValueError):
        produce(ProductionState(1, MAX_AMOUNT, START), START + timedelta(hours=1))


def test_zero_rate_preserves_fractional_production():
    state = ProductionState(0, 0, START, remainder=123)
    result = produce(state, START + timedelta(days=100))
    assert (result.stock, result.remainder) == (0, 123)
