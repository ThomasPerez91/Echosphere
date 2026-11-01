"""Operator-only trusted controller lifecycle. Pausing never transfers control to a human."""

from datetime import timedelta

from sqlalchemy import select

from app.ai.models import AIController
from app.ai.rules import fingerprint
from app.colony.service import rules_for
from app.control.models import EmpireBinding
from app.persistence.models import Empire
from app.simulation.clock import utc


class AIDenied(ValueError):
    pass


def next_slot(started_at, observed_at, cadence=600):
    start, observed = utc(started_at), utc(observed_at)
    elapsed = (observed - start) // timedelta(seconds=cadence)
    return start + timedelta(seconds=(max(-1, elapsed) + 1) * cadence)


def no_human_binding(session, empire_id):
    if session.scalar(select(EmpireBinding.empire_id).where(
        EmpireBinding.empire_id == empire_id).limit(1)) is not None:
        raise AIDenied("human_binding_present")


def activate(session, universe_id, empire_id, profile, at):
    # Same parent lock as the control-plane grant path, BEFORE inspecting either side.
    empire = session.scalar(select(Empire).where(
        Empire.id == empire_id, Empire.universe_id == universe_id).with_for_update())
    rules = rules_for(session, universe_id)
    if empire is None or empire.controller_type != "ai" or rules.ai is None:
        raise AIDenied("ai_scope_unavailable")
    if profile not in rules.ai.profiles:
        raise AIDenied("invalid_profile")
    no_human_binding(session, empire.id)
    if session.scalar(select(AIController.id).where(AIController.empire_id == empire.id)):
        raise AIDenied("controller_already_exists")
    row = AIController(
        universe_id=universe_id, empire_id=empire.id, profile=profile,
        policy_version=rules.ai.policy_version, policy_digest=fingerprint(rules.ai.model_dump()),
        state="enabled", started_at=utc(at), next_decision_at=utc(at) + timedelta(seconds=600),
        sequence=1, memory={}, attempts=0,
    )
    session.add(row)
    session.flush()
    return row


def authorize(session, controller):
    # Always derives scopes from the locked row, never from a policy-supplied identity.
    empire = session.get(Empire, controller.empire_id)
    rules = rules_for(session, controller.universe_id)
    if (controller.state != "enabled" or empire is None
            or empire.universe_id != controller.universe_id or empire.controller_type != "ai"
            or rules.ai is None or controller.profile not in rules.ai.profiles
            or controller.policy_version != rules.ai.policy_version
            or controller.policy_digest != fingerprint(rules.ai.model_dump())):
        raise AIDenied("ai_scope_or_policy_mismatch")
    no_human_binding(session, empire.id)
    return rules


def change_state(session, controller_id, state, now):
    if state not in {"enabled", "paused", "blocked"}:
        raise AIDenied("invalid_state")
    row = session.get(AIController, controller_id, with_for_update=True)
    if row is None:
        raise AIDenied("controller_not_found")
    if state == "enabled":
        prior = row.state
        row.state = state
        try:
            authorize(session, row)
        except Exception:
            row.state = prior
            raise
        row.next_decision_at = next_slot(row.started_at, now)
        row.attempts, row.retry_at, row.error_code = 0, None, None
    else:
        row.state = state
    return row
