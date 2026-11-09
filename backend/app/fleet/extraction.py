"""EXP-02b (ruleset v0.10): shared settlement of a deposit worked by EXTRACT claims.

A deposit has an hourly throughput. Every claim (one EXTRACT mission, any Empire) working it
between `active_from` and `active_until` asks for extractors x rate per hour, never more than
its free hold. When the asks exceed the throughput, it is shared in proportion to extractors;
what a full claim cannot take goes to the others (water-filling). The reserve never goes below
zero and is debited by the sum. No first-comer owns anything (A3, neutral Empires).

Settlement runs in time order on the deposit row lock (`FOR UPDATE`), from `settled_at` to a
date, over the claims' persisted windows only: whatever Empire's handler or command settles,
the result is the same. Integer micro-units; the supply fraction below one micro-unit is kept on
the deposit (`settle_remainder`); a claim's ask is floored (the rest stays in the reserve).
Each settlement date floors once more, so the result depends on the persisted dates (event
deadlines, command times) by at most a micro-unit per date, never on which Empire settles.
"""

from sqlalchemy import select

from app.fleet.sharing import HOUR_US, Claim, settle
from app.galaxy.models import DepositClaim, GalaxyOpportunity
from app.simulation.production import MICRO_UNITS


def lock_deposit(session, opportunity_id):
    return session.scalar(
        select(GalaxyOpportunity)
        .where(GalaxyOpportunity.id == opportunity_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def settle_deposit(session, rules, deposit, until):
    """Settle the locked deposit up to `until` (never backwards). Writes the deposit cursor,
    its reserve and the `credited` of the claims concerned, of any Empire."""
    if deposit.settled_at is None:
        deposit.settled_at = until
        session.flush()
        return
    if until <= deposit.settled_at:
        return
    rows = session.scalars(
        select(DepositClaim)
        .where(
            DepositClaim.opportunity_id == deposit.id,
            DepositClaim.active_until > deposit.settled_at,
            DepositClaim.active_from < until,
        )
        .order_by(DepositClaim.mission_id)
        .with_for_update()
    ).all()
    claims = [
        Claim(str(r.mission_id), r.extractors, r.room - r.credited, r.active_from, r.active_until)
        for r in rows
    ]
    rate = rules.opportunities.operations.extraction_per_hour * MICRO_UNITS
    credits, _, reserve, remainder = settle(
        deposit.throughput_per_hour, deposit.reserve_remaining, deposit.settle_remainder, rate,
        claims, deposit.settled_at, until,
    )
    for r in rows:
        r.credited += credits[str(r.mission_id)]
    deposit.reserve_remaining, deposit.settle_remainder = reserve, remainder
    deposit.settled_at = until
    session.flush()


def planned_us(rules, deposit, extractors, room, hours):
    """Planned extraction length: the chosen hours, or less when the hold would be full working
    alone at min(extractors x rate, throughput). Competition only slows a claim down, so it never
    fills before this date; the actual credit is what the settlement gives by then."""
    rate = rules.opportunities.operations.extraction_per_hour * MICRO_UNITS
    alone = min(extractors * rate, deposit.throughput_per_hour)
    fill_us = -(-room * HOUR_US // alone)
    return max(1, min(hours * HOUR_US, fill_us))


def open_claim(session, rules, mission, extractors, room, at):
    """At launch: the claim exists from the arrival to the planned end. Settling first keeps the
    shares already due to others unchanged by this newcomer."""
    deposit = lock_deposit(session, mission.target_opportunity_id)
    settle_deposit(session, rules, deposit, at)
    start = max(mission.travel_arrival_at, deposit.settled_at)
    session.add(
        DepositClaim(
            mission_id=mission.id,
            empire_id=mission.empire_id,
            universe_id=mission.universe_id,
            opportunity_id=deposit.id,
            extractors=extractors,
            room=room,
            active_from=start,
            active_until=max(mission.due_at, start),
            credited=0,
        )
    )
    session.flush()


def close_claim(session, rules, mission, at):
    """End of the claim at `at` (its planned end, or earlier on a stop/recall): settled up to
    then, the credit is final. Returns (resource, credited)."""
    deposit = lock_deposit(session, mission.target_opportunity_id)
    row = session.get(DepositClaim, mission.id, with_for_update=True, populate_existing=True)
    if row is None:
        raise ValueError("Extraction claim missing")
    # Never settled past `at`: a recall while travelling leaves an empty window.
    settle_deposit(session, rules, deposit, min(at, row.active_until))
    row.active_until = min(row.active_until, max(at, row.active_from))
    session.flush()
    return deposit.resource, row.credited
