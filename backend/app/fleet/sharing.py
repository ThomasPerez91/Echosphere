"""EXP-02b pure sharing of a deposit throughput between EXTRACT claims (no database).

See app.fleet.extraction for the rules and the settlement on the deposit lock.
"""

from dataclasses import dataclass
from datetime import datetime

HOUR_US = 3_600_000_000
DAY_US = 24 * HOUR_US


def us(delta):
    return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds


@dataclass
class Claim:
    key: str
    extractors: int
    room: int  # free hold left, micro-units
    active_from: datetime
    active_until: datetime


def fill(supply, claims, caps):
    """Integer water-filling of `supply` by extractor weights, each claim capped. Deterministic
    (claims in key order); the integer leftover is not extracted."""
    given = dict.fromkeys((c.key for c in claims), 0)
    pool = sorted((c for c in claims if caps[c.key] > 0), key=lambda c: c.key)
    while pool and supply > 0:
        weight = sum(c.extractors for c in pool)
        shares = {c.key: supply * c.extractors // weight for c in pool}
        full = [c for c in pool if shares[c.key] >= caps[c.key]]
        if not full:
            for c in pool:
                given[c.key] += shares[c.key]
            break
        for c in full:
            given[c.key] += caps[c.key]
            supply -= caps[c.key]
        pool = [c for c in pool if c not in full]
    return given


def regenerate(reserve, total, bps_per_day, remainder, span):
    """v0.11: the reserve grows back by `bps_per_day` of its total per day, never above it; the
    fraction below one micro-unit is kept (`remainder`, in micro-unit x microsecond units)."""
    if not bps_per_day or reserve >= total:
        return reserve, 0 if reserve >= total else remainder
    grown, remainder = divmod(total * bps_per_day * span + remainder, 10000 * DAY_US)
    if reserve + grown >= total:
        return total, 0
    return reserve + grown, remainder


def settle(throughput, reserve, remainder, rate, claims, start, end, *, total=None,
           regeneration_bps=None, regen_remainder=0):
    """Pure settlement of [start, end]: (credits by key, extracted, reserve, remainder) and, with
    `regeneration_bps` (v0.11), the regeneration remainder as a fifth value.
    `throughput` and `rate` are micro-units per hour (rate per extractor)."""
    credits = dict.fromkeys((c.key for c in claims), 0)
    if end <= start:
        return (credits, 0, reserve, remainder) + (
            (regen_remainder,) if regeneration_bps else ())
    rooms = {c.key: c.room for c in claims}
    bounds = sorted(
        {start, end}
        | {t for c in claims for t in (c.active_from, c.active_until) if start < t < end}
    )
    extracted = 0
    for a, b in zip(bounds, bounds[1:], strict=False):
        span = us(b - a)
        if regeneration_bps:
            reserve, regen_remainder = regenerate(
                reserve, total, regeneration_bps, regen_remainder, span
            )
        active = [c for c in claims if c.active_from <= a and c.active_until >= b]
        if not active or reserve == 0:
            continue
        offered, remainder = divmod(throughput * span + remainder, HOUR_US)
        offered = min(offered, reserve)
        caps = {c.key: min(rooms[c.key], c.extractors * rate * span // HOUR_US) for c in active}
        given = fill(offered, active, caps)
        for key, value in given.items():
            credits[key] += value
            rooms[key] -= value
        taken = sum(given.values())
        reserve -= taken
        extracted += taken
    if regeneration_bps:
        return credits, extracted, reserve, remainder, regen_remainder
    return credits, extracted, reserve, remainder
