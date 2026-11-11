"""Run the shared monolith's strategic AI orchestrator; explicit operator lifecycle commands.

Same image and database as the Game backend, outside TimeEngine handlers. Never logs payloads.
"""

import argparse
import json
import logging
import signal
from datetime import datetime
from threading import Event
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.ai.bootstrap import bootstrap
from app.ai.controller import change_state
from app.ai.models import AIController
from app.ai.orchestrator import Orchestrator
from app.colony.rules import load_ruleset
from app.core.config import Settings
from app.persistence.database import create_database_engine, create_session_factory
from app.simulation.clock import SystemClock, utc
from app.simulation.service import TimeEngine

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Process one bounded batch then exit")
    mode.add_argument("--blocked", action="store_true", help="List blocked controller IDs")
    mode.add_argument("--pause", type=UUID, help="Stop new decisions of one controller")
    mode.add_argument("--resume", type=UUID, help="Re-enable one controller on the future grid")
    mode.add_argument("--bootstrap", type=UUID, help="Create one v0.6+ universe start")
    parser.add_argument("--name")
    parser.add_argument("--seed")
    parser.add_argument("--profiles", default="economic_cautious,expansionist")
    parser.add_argument(
        "--ruleset",
        choices=["v0.6", "v0.7", "v0.8", "v0.9", "v0.10", "v0.11", "v0.12", "v0.13"],
        default="v0.6",
    )
    parser.add_argument("--at", help="Explicit aware ISO start, bootstrap only")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-delay", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.limit <= 1000 or not 0.1 <= args.poll_interval <= 600:
        parser.error("limit must be 1..1000 and poll-interval 0.1..600 seconds")
    if not 1 <= args.max_attempts <= 10 or not 1 <= args.retry_delay <= 3600:
        parser.error("max-attempts must be 1..10 and retry-delay 1..3600 seconds")
    if args.bootstrap and not (args.name and args.seed):
        parser.error("bootstrap requires --name and --seed")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    database = create_database_engine(Settings())
    factory, clock = create_session_factory(database), SystemClock()
    stop = Event()
    signal.signal(signal.SIGTERM, lambda signum, frame: stop.set())
    signal.signal(signal.SIGINT, lambda signum, frame: stop.set())
    try:
        if args.bootstrap:
            at = utc(datetime.fromisoformat(args.at)) if args.at else clock.now()
            if at > clock.now():
                parser.error("bootstrap --at cannot anchor timelines in the future")
            profiles = [p for p in args.profiles.split(",") if p]
            with factory.begin() as session:
                result = bootstrap(
                    session,
                    TimeEngine(factory, clock),
                    args.bootstrap,
                    args.name,
                    args.seed,
                    profiles,
                    at,
                    rules=load_ruleset(args.ruleset),
                )
            print(json.dumps(result))
            return
        if args.blocked:
            with factory() as session:
                rows = session.scalars(
                    select(AIController)
                    .where(AIController.state == "blocked")
                    .order_by(AIController.next_decision_at, AIController.id)
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
        if args.pause or args.resume:
            target, state = (args.pause, "paused") if args.pause else (args.resume, "enabled")
            with factory.begin() as session:
                row = change_state(session, target, state, clock.now())
                print(json.dumps({"id": str(row.id), "state": row.state}))
            return
        runner = Orchestrator(
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
                        "controller=%s sequence=%s outcome=%s",
                        outcome.get("controller_id"),
                        outcome.get("sequence"),
                        outcome["outcome"],
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
