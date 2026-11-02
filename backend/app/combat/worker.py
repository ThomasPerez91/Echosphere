"""Run the shared monolith's Combat orchestrator; explicit operator commands. No payload logged."""

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
from app.persistence.database import create_database_engine, create_session_factory
from app.simulation.clock import SystemClock

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Process one bounded batch then exit")
    mode.add_argument("--blocked", action="store_true", help="List blocked engagement IDs")
    mode.add_argument("--retry", type=UUID, help="Requeue one repaired blocked engagement")
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
                print(
                    json.dumps(
                        [
                            {"id": str(r.id), "attempts": r.attempts, "error_code": r.error_code}
                            for r in rows
                        ]
                    )
                )
            return
        if args.retry:
            with factory.begin() as session:
                retry_blocked(session, args.retry, clock.now())
            print(json.dumps({"requeued": str(args.retry)}))
            return
        runner = CombatOrchestrator(
            factory, clock, retry_seconds=args.retry_delay, max_attempts=args.max_attempts
        )
        while not stop.is_set():
            processed = 0
            try:
                for _ in range(args.limit):
                    if stop.is_set():
                        break
                    outcome = runner.process_next()
                    if outcome is None:
                        break
                    processed += 1
                    logger.info(
                        "engagement=%s outcome=%s", outcome["engagement_id"], outcome["outcome"]
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
