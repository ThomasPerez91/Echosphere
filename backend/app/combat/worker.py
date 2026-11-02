"""Run the shared monolith's Combat orchestrator and, in v0.9 Universes, the frontier reactions
(13B: interceptions, ambushes, friendly retreats); explicit operator commands. No payload logged."""

import argparse
import json
import logging
import signal
from threading import Event
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.combat.models import CombatEngagement
from app.combat.orchestrator import CombatOrchestrator, retry_blocked
from app.core.config import Settings
from app.frontier.models import FleetPassage, FrontierEncounter
from app.frontier.orchestrator import FrontierOrchestrator, retry_passage
from app.frontier.orchestrator import retry_blocked as retry_frontier
from app.persistence.database import create_database_engine, create_session_factory
from app.simulation.clock import SystemClock

logger = logging.getLogger(__name__)


LAG_WARNING_SECONDS = 300


def lag(factory, now):
    """C05 operator diagnostic: how far behind the frontier work is. A due entry keeps its
    mover's Operations stream frozen until resolved, so a growing lag is worth an alert."""
    with factory() as session:
        entry = session.scalar(
            select(FleetPassage.entered_at)
            .where(FleetPassage.state.in_(["pending", "blocked"]), FleetPassage.entered_at <= now)
            .order_by(FleetPassage.entered_at)
            .limit(1)
        )
        reaction = session.scalar(
            select(FrontierEncounter.encounter_at)
            .where(
                FrontierEncounter.state.in_(["pending", "blocked"]),
                FrontierEncounter.encounter_at <= now,
            )
            .order_by(FrontierEncounter.encounter_at)
            .limit(1)
        )
    oldest = min((t for t in (entry, reaction) if t is not None), default=None)
    seconds = (now - oldest).total_seconds() if oldest is not None else 0.0
    return {
        "oldest_entry_at": entry.isoformat() if entry else None,
        "oldest_reaction_at": reaction.isoformat() if reaction else None,
        "lag_seconds": seconds,
        "alert": seconds > LAG_WARNING_SECONDS,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Process one bounded batch then exit")
    mode.add_argument("--blocked", action="store_true", help="List blocked engagement IDs")
    mode.add_argument("--retry", type=UUID, help="Requeue one repaired blocked engagement")
    mode.add_argument(
        "--retry-frontier", type=UUID, help="Requeue one repaired blocked frontier reaction"
    )
    mode.add_argument(
        "--retry-passage",
        metavar="MISSION:SEQUENCE",
        help="Requeue one repaired blocked frontier entry",
    )
    mode.add_argument(
        "--lag", action="store_true", help="Oldest due unresolved frontier entry and reaction"
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000 or not 0.1 <= args.poll_interval <= 600:
        parser.error("limit must be 1..1000 and poll-interval 0.1..600 seconds")
    if not 1 <= args.max_attempts <= 10 or not 1 <= args.retry_delay <= 3600:
        parser.error("max-attempts must be 1..10 and retry-delay 1..3600 seconds")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    database = create_database_engine(Settings())
    factory, clock = create_session_factory(database), SystemClock()
    stop = Event()
    signal.signal(signal.SIGTERM, lambda signum, frame: stop.set())
    signal.signal(signal.SIGINT, lambda signum, frame: stop.set())
    try:
        if args.blocked:
            with factory() as session:
                rows = session.scalars(
                    select(CombatEngagement)
                    .where(CombatEngagement.state == "blocked")
                    .order_by(CombatEngagement.battle_at, CombatEngagement.id)
                    .limit(args.limit)
                ).all()
                reactions = session.scalars(
                    select(FrontierEncounter)
                    .where(FrontierEncounter.state == "blocked")
                    .order_by(FrontierEncounter.encounter_at, FrontierEncounter.id)
                    .limit(args.limit)
                ).all()
                entries = session.scalars(
                    select(FleetPassage)
                    .where(FleetPassage.state == "blocked")
                    .order_by(FleetPassage.entered_at, FleetPassage.mission_id)
                    .limit(args.limit)
                ).all()
                print(
                    json.dumps(
                        [
                            {"id": str(r.id), "attempts": r.attempts, "error_code": r.error_code}
                            for r in rows
                        ]
                        + [
                            {
                                "id": str(r.id),
                                "kind": "frontier",
                                "attempts": r.attempts,
                                "error_code": r.error_code,
                            }
                            for r in reactions
                        ]
                        + [
                            {
                                "passage": f"{r.mission_id}:{r.sequence}",
                                "kind": "frontier-entry",
                                "entered_at": r.entered_at.isoformat(),
                                "attempts": r.attempts,
                                "error_code": r.error_code,
                            }
                            for r in entries
                        ]
                    )
                )
            return
        if args.lag:
            print(json.dumps(lag(factory, clock.now())))
            return
        if args.retry_passage:
            mission, _, sequence = args.retry_passage.partition(":")
            with factory.begin() as session:
                retry_passage(session, UUID(mission), int(sequence), clock.now())
            print(json.dumps({"requeued": args.retry_passage}))
            return
        if args.retry_frontier:
            with factory.begin() as session:
                retry_frontier(session, args.retry_frontier, clock.now())
            print(json.dumps({"requeued": str(args.retry_frontier)}))
            return
        if args.retry:
            with factory.begin() as session:
                retry_blocked(session, args.retry, clock.now())
            print(json.dumps({"requeued": str(args.retry)}))
            return
        runner = CombatOrchestrator(
            factory, clock, retry_seconds=args.retry_delay, max_attempts=args.max_attempts
        )
        reactions = FrontierOrchestrator(
            factory, clock, retry_seconds=args.retry_delay, max_attempts=args.max_attempts
        )
        while not stop.is_set():
            processed = 0
            try:
                for _ in range(args.limit):
                    if stop.is_set():
                        break
                    # Each orchestrator waits on the other's earlier fences: both progress in
                    # global logical order, whichever process picks them up first.
                    outcome = runner.process_next()
                    reaction = reactions.process_next()
                    if outcome is None and reaction is None:
                        break
                    processed += (outcome is not None) + (reaction is not None)
                    if outcome is not None:
                        logger.info(
                            "engagement=%s outcome=%s",
                            outcome["engagement_id"],
                            outcome["outcome"],
                        )
                    if reaction is not None:
                        logger.info(
                            "reaction=%s outcome=%s",
                            reaction.get("encounter_id") or reaction.get("passage"),
                            reaction["outcome"],
                        )
            except SQLAlchemyError:
                if args.once:
                    raise
                logger.warning("Database unavailable; retrying after poll interval")
            if args.once:
                print(json.dumps({"processed": processed}))
                return
            try:
                behind = lag(factory, clock.now())
                if behind["alert"]:
                    logger.warning("frontier lag_seconds=%.0f", behind["lag_seconds"])
            except SQLAlchemyError:
                logger.warning("Database unavailable; retrying after poll interval")
            stop.wait(args.poll_interval)
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
