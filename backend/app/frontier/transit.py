"""Pure per-hop transit (13B / FC9). No database, no clock, integers and aware datetimes only.

The Fleet engine already prices a mission in whole hops of the slowest class: every hop of one
mission therefore lasts the same time. The k-th system of an n-hop path is entered at
`started_at + ceil(travel_us * k / n)` microseconds: deterministic, strictly increasing, and the
last entry is exactly `travel_arrival_at`. Nothing here decides gameplay; it only states *when*
a Fleet enters each system it physically crosses, so detection can later be evaluated at that
logical instant (never at departure or final arrival instead).

A way back mirrors the way out. A Fleet leaving at `depart_at` from the point it had reached at
outbound time `progress_at` re-enters every system it had already passed (entered strictly
before `progress_at`), in reverse order, at `depart_at + (progress_at - entered_at)`, and finally
its origin at `depart_at + (progress_at - started_at)`. This is exactly the existing symmetric
recall (progress = recall instant) and the full return after arrival or battle (progress =
travel arrival).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

OUTBOUND, RETURN = "outbound", "return"


@dataclass(frozen=True)
class Passage:
    sequence: int
    system_id: UUID
    entered_at: datetime
    direction: str


def offsets(travel_us: int, hops: int) -> list[int]:
    """Entry offsets (µs) of hops 1..n; integer ceiling, last one equals travel_us."""
    if type(travel_us) is not int or type(hops) is not int or hops < 1 or travel_us < 1:
        raise ValueError("A transit needs whole hops and a positive travel time")
    return [-(-travel_us * k // hops) for k in range(1, hops + 1)]


def outbound(started_at: datetime, travel_us: int, systems: list[UUID]) -> list[Passage]:
    """`systems`: the systems entered in order (origin excluded, destination included)."""
    if not systems:
        return []
    entries = zip(systems, offsets(travel_us, len(systems)), strict=True)
    return [
        Passage(i, system, started_at + timedelta(microseconds=offset), OUTBOUND)
        for i, (system, offset) in enumerate(entries)
    ]


def way_back(
    passages: list[Passage],
    origin_id: UUID,
    started_at: datetime,
    depart_at: datetime,
    progress_at: datetime,
) -> list[Passage]:
    """Return passages after the outbound ones (sequence continues). Mirror of the way out.

    A system entered exactly at `progress_at` is where the Fleet stands: it is left, not
    re-entered. The origin is re-entered last, unless the Fleet never left it."""
    if not started_at <= progress_at <= depart_at:
        raise ValueError("Inconsistent way back")
    out = [p for p in passages if p.direction == OUTBOUND]
    behind = [p for p in out if p.entered_at < progress_at]
    sequence = len(out)
    result = []
    for p in reversed(behind):
        result.append(
            Passage(sequence, p.system_id, depart_at + (progress_at - p.entered_at), RETURN)
        )
        sequence += 1
    if progress_at > started_at:
        result.append(Passage(sequence, origin_id, depart_at + (progress_at - started_at), RETURN))
    return result


def cancelled(passages: list[Passage], progress_at: datetime) -> list[Passage]:
    """Outbound entries that never happen once the Fleet turns back at `progress_at`."""
    return [p for p in passages if p.direction == OUTBOUND and p.entered_at > progress_at]
