"""Bounded durable strategic rendezvous, outside TimeEngine's single-stream handlers."""

from copy import deepcopy
from datetime import timedelta

from sqlalchemy import delete, or_, select, text

from app.ai.controller import authorize, next_slot
from app.ai.dispatcher import dispatch
from app.ai.models import AIController, AIDecision
from app.ai.observation import ObservationLimit, collect
from app.ai.policy import choose
from app.ai.rules import canonical
from app.colony.service import ColonyError, catch_up_owned
from app.fleet.service import operations
from app.galaxy import service as galaxy
from app.persistence.models import Colony
from app.relations import service as relations
from app.research.service import catch_up as catch_up_research
from app.research.service import lock_research
from app.simulation.clock import utc
from app.simulation.scheduler import lock_stream
from app.simulation.service import TimeEngine, lock_timeline


class Orchestrator:
    def __init__(
        self, factory, clock, *, lock_ms=500, statement_ms=2000, retry_seconds=30, max_attempts=3
    ):
        if not (
            1 <= lock_ms <= 10000
            and lock_ms <= statement_ms <= 60000
            and 1 <= retry_seconds <= 3600
            and 1 <= max_attempts <= 10
        ):
            raise ValueError("Invalid technical AI limits")
        self.factory, self.clock = factory, clock
        self.engine = TimeEngine(factory, clock)
        self.lock_ms, self.statement_ms = lock_ms, statement_ms
        self.retry_seconds, self.max_attempts = retry_seconds, max_attempts

    def process_next(self, *, controller_id=None, after_command=None, raise_errors=False):
        """after_command is an internal crash-injection test seam, never a policy callback."""
        claimed = None
        try:
            with self.factory.begin() as session:
                session.execute(text(f"SET LOCAL lock_timeout = '{self.lock_ms}ms'"))
                session.execute(text(f"SET LOCAL statement_timeout = '{self.statement_ms}ms'"))
                now = utc(self.clock.now())
                query = select(AIController).where(
                    AIController.state == "enabled",
                    AIController.next_decision_at <= now,
                    or_(AIController.retry_at.is_(None), AIController.retry_at <= now),
                )
                if controller_id is not None:
                    query = query.where(AIController.id == controller_id)
                controller = session.scalar(
                    query.order_by(AIController.next_decision_at, AIController.empire_id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                if controller is None:
                    return None
                claimed = (controller.id, controller.sequence)
                rules = authorize(session, controller)
                u, e = controller.universe_id, controller.empire_id
                # Acquire all EXISTING streams in the validated order, before sampling turn time.
                state = galaxy.state_for(session, u, e)
                lock_stream(session, state.stream_id, u)
                lock_research(session, u, e, now)
                colonies = list(
                    session.scalars(
                        select(Colony)
                        .where(Colony.universe_id == u, Colony.empire_id == e)
                        .order_by(Colony.id)
                        .limit(13)
                    )
                )
                if len(colonies) > rules.colonization.max_colonies:
                    raise ObservationLimit("own_colony_budget")
                for colony in colonies:
                    lock_timeline(session, colony.id)
                at = utc(self.clock.now())
                operations(session, self.engine, u, e, at)
                catch_up_research(session, self.engine, u, e, at)
                # A due COLONIZE may have created fresh, transaction-private Colony streams.
                colonies = list(
                    session.scalars(
                        select(Colony)
                        .where(Colony.universe_id == u, Colony.empire_id == e)
                        .order_by(Colony.id)
                        .limit(13)
                    )
                )
                if len(colonies) > rules.colonization.max_colonies:
                    raise ObservationLimit("own_colony_budget")
                for colony in colonies:
                    catch_up_owned(session, self.engine, u, e, colony.id, at)
                # Presence contacts are written after the dispatch (which may lock a relation
                # pair): global order pair → contact, never the reverse.
                monitored = galaxy.refresh_monitoring(session, u, e, at, contacts=False)
                observation, memory = collect(session, controller, rules, at)
                trace = choose(observation, memory, controller.profile, rules.ai)
                trace.update(
                    profile=controller.profile,
                    policy_version=controller.policy_version,
                    policy_digest=controller.policy_digest,
                    sequence=controller.sequence,
                    memory_before=deepcopy(controller.memory),
                    memory_evaluated=deepcopy(memory),
                )
                chosen = next(
                    (c for c in observation["candidates"] if c["key"] == trace["choice"]), None
                )
                # Fixed maximum-size service receipts are reserved BEFORE dispatch. No truncation.
                if len(canonical(observation).encode()) > rules.ai.observation_bytes:
                    raise ObservationLimit("observation_bytes")
                if len(canonical(trace).encode()) + 1024 > rules.ai.result_bytes:
                    raise ObservationLimit("result_bytes")
                outcome, receipt = "wait", {"reason": "no_eligible_candidate"}
                if chosen:
                    key = f"ai:{controller.id}:{controller.sequence}:{chosen['operation']}"
                    trace["intent_key"] = key
                    try:
                        receipt = dispatch(session, self.engine, controller, chosen, key, at)
                        outcome = "accepted"
                        if chosen["manages_project"]:
                            if chosen["project_after"]:
                                memory["project"] = deepcopy(chosen["project_after"])
                            else:
                                memory.pop("project", None)
                    except ColonyError as error:
                        outcome, receipt = "refusal", {"reason": error.code}
                    if after_command is not None:
                        after_command(session)
                if rules.relations is not None:
                    relations.observe_presences(session, u, e, monitored, at)
                trace.update(result=receipt, outcome=outcome, memory_after=deepcopy(memory))
                if len(canonical(trace).encode()) > rules.ai.result_bytes:
                    raise ObservationLimit("result_bytes")
                session.add(
                    AIDecision(
                        controller_id=controller.id,
                        sequence=controller.sequence,
                        universe_id=u,
                        empire_id=e,
                        planned_at=controller.next_decision_at,
                        observed_at=at,
                        outcome=outcome,
                        observation=observation,
                        trace=trace,
                    )
                )
                controller.memory, controller.sequence = memory, controller.sequence + 1
                controller.next_decision_at = next_slot(controller.started_at, at)
                controller.retry_at, controller.error_code, controller.attempts = None, None, 0
                session.execute(
                    delete(AIDecision).where(
                        AIDecision.controller_id == controller.id,
                        AIDecision.sequence < controller.sequence - rules.ai.trace_retention,
                    )
                )
                session.flush()
                return {
                    "controller_id": str(controller.id),
                    "sequence": claimed[1],
                    "outcome": outcome,
                }
        except Exception as error:
            if raise_errors:
                raise
            if claimed is None:
                raise
            # A due Combat freezes this Empire's Operations stream: wait, never a technical
            # failure, never a decision on a state behind the battle.
            waiting = getattr(error, "code", None) == "combat_pending"
            # All gameplay, memory and trace effects rolled back. No exception/payload in logs.
            with self.factory.begin() as session:
                controller = session.get(AIController, claimed[0], with_for_update=True)
                if (
                    controller is None
                    or controller.sequence != claimed[1]
                    or controller.state != "enabled"
                ):
                    return {"outcome": "superseded"}
                if waiting:
                    controller.retry_at = utc(self.clock.now()) + timedelta(
                        seconds=self.retry_seconds
                    )
                    return {
                        "controller_id": str(controller.id),
                        "sequence": claimed[1],
                        "outcome": "combat_pending",
                    }
                controller.attempts += 1
                controller.error_code = "turn_failed"
                controller.retry_at = utc(self.clock.now()) + timedelta(seconds=self.retry_seconds)
                if controller.attempts >= self.max_attempts:
                    controller.state = "blocked"
                return {
                    "controller_id": str(controller.id),
                    "sequence": claimed[1],
                    "outcome": "blocked" if controller.state == "blocked" else "retry",
                }
