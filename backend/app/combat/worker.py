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
from app.frontier.models import FrontierEncounter
from app.frontier.orchestrator import FrontierOrchestrator
from app.frontier.orchestrator import retry_blocked as retry_frontier
from app.persistence.database import create_database_engine, create_session_factory
from app.simulation.clock import SystemClock

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Process one bounded batch then exit")
    mode.add_argument("--blocked", action="store_true", help="List blocked engagement IDs")
    mode.add_argument("--retry", type=UUID, help="Requeue one repaired blocked engagement")
    mode.add_argument(
        "--retry-frontier", type=UUID, help="Requeue one repaired blocked frontier reaction"
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
                    )
                )
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
                            reaction["encounter_id"],
                            reaction["outcome"],
                        )
            except SQLAlchemyError:
                if args.once:
                    raise
                logger.warning("Database unavailable; retrying after poll interval")
            if args.once:
                print(json.dumps({"processed": processed}))
                return
            stop.wait(args.poll_interval)
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
