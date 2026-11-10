"""EXP-02b pure settlement: proportional sharing, water-filling, reserve, remainder, order."""

from datetime import UTC, datetime, timedelta

from app.fleet.sharing import Claim, fill, settle

M = 1_000_000
T0 = datetime(2099, 1, 1, tzinfo=UTC)


def at(hours):
    return T0 + timedelta(hours=hours)


def claim(key, extractors, room, start, end):
    return Claim(key, extractors, room * M, at(start), at(end))


def test_alone_a_claim_takes_its_ask_below_the_throughput():
    credits, extracted, reserve, _ = settle(
        90 * M, 5000 * M, 0, 20 * M, [claim("a", 2, 400, 0, 10)], at(0), at(10)
    )
    assert credits == {"a": 400 * M} and extracted == 400 * M and reserve == 4600 * M


def test_over_demand_is_shared_by_extractors_and_the_throughput_is_never_exceeded():
    claims = [claim("a", 3, 1000, 0, 10), claim("b", 1, 1000, 0, 10)]
    credits, extracted, _, _ = settle(40 * M, 5000 * M, 0, 20 * M, claims, at(0), at(10))
    assert credits == {"a": 300 * M, "b": 100 * M}  # 40/h shared 3:1 instead of 60/h + 20/h
    assert extracted == 400 * M


def test_a_full_hold_gives_its_share_to_the_others():
    claims = [claim("a", 1, 50, 0, 10), claim("b", 1, 1000, 0, 10)]
    credits, _, _, _ = settle(30 * M, 5000 * M, 0, 20 * M, claims, at(0), at(10))
    assert credits["a"] == 50 * M and credits["b"] == 200 * M  # b: its own 20/h cap


def test_windows_split_the_interval_and_the_reserve_bounds_everything():
    claims = [claim("a", 1, 1000, 0, 4), claim("b", 1, 1000, 2, 6)]
    credits, extracted, reserve, _ = settle(30 * M, 70 * M, 0, 20 * M, claims, at(0), at(6))
    # 0-2h: a alone 40; 2-4h: 30 shared 15/15 but only 30 left in reserve; 4-6h: nothing left.
    assert credits == {"a": 55 * M, "b": 15 * M} and extracted == 70 * M and reserve == 0


def test_settling_in_steps_differs_by_rounding_only_and_conserves_the_reserve():
    claims = [claim("a", 2, 900, 0, 7), claim("b", 1, 900, 1, 9)]
    once = settle(37 * M + 3, 10**12, 0, 20 * M, claims, at(0), at(9))
    credits, reserve, remainder = dict.fromkeys("ab", 0), 10**12, 0
    for a, b in [(0, 1), (1, 2.5), (2.5, 7), (7, 9)]:
        rooms = [Claim(c.key, c.extractors, c.room - credits[c.key], c.active_from,
                       c.active_until) for c in claims]
        step, _, reserve, remainder = settle(37 * M + 3, reserve, remainder, 20 * M, rooms,
                                             at(a), at(b))
        credits = {k: credits[k] + step[k] for k in credits}
    # Each settlement date floors once more: at most one micro-unit per claim and extra step.
    assert all(0 <= once[0][k] - credits[k] <= 3 for k in credits)
    assert reserve + sum(credits.values()) == 10**12


def test_fill_is_deterministic_and_never_gives_more_than_supply():
    claims = [Claim(k, n, 0, T0, T0) for k, n in [("b", 1), ("a", 1), ("c", 1)]]
    given = fill(10, claims, {"a": 10, "b": 10, "c": 10})
    assert sum(given.values()) <= 10 and given == {"b": 3, "a": 3, "c": 3}


def test_reserves_regenerate_up_to_their_total_even_without_any_claim():
    """v0.11 (10/11/2026): 10 % of the total per day, capped; extraction meanwhile still works."""
    from app.fleet.sharing import regenerate

    day = 24 * 3600 * 10**6
    assert regenerate(500 * M, 1000 * M, 1000, 0, day) == (600 * M, 0)
    assert regenerate(950 * M, 1000 * M, 1000, 0, day) == (1000 * M, 0)
    half, rest = regenerate(0, 3, 1000, 0, day)  # 0.3 micro-unit: kept, never lost
    assert half == 0 and rest > 0
    assert regenerate(*[0, 3, 1000, rest, 3 * day])[0] == 1
    credits, extracted, reserve, _, _ = settle(
        30 * M, 0, 0, 20 * M, [claim("a", 1, 1000, 24, 48)], at(0), at(48),
        total=1000 * M, regeneration_bps=1000, regen_remainder=0,
    )
    # Day 1: +100 alone; day 2: +100 trickling in while the claim takes what grows back.
    assert extracted == credits["a"] and 0 < extracted <= 200 * M
    assert reserve == 200 * M - extracted
