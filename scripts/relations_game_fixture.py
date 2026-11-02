"""Test-only helpers for the disposable Relations recipe; refused outside its *_test Game DB.

Appended by `smoke_relations_compose.py` after the Combat fixture (whose `drive` plays the human
through the Fleet service on an injected clock). Here the human only negotiates through the
Relations service, exactly like the HTTP command; contacts, hostile facts, the AI answer and any
pact come from the real combat-worker and ai-worker processes. Nothing is credited or revealed.
"""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.ai.models import AIBootstrap, AIDecision
from app.colony.service import rules_for
from app.combat.models import CombatEngagement
from app.control.models import GamePrincipal
from app.core.config import Settings
from app.fleet.models import FleetMission
from app.persistence.database import create_database_engine, create_session_factory
from app.relations import service as relations
from app.relations.models import RelationContact, RelationEvent, RelationPact, RelationPair
from app.relations.rules import pair, recent
from sqlalchemy import func, select

RELATIONS_DATABASE = "echosphere_relations_game_test"


def relations_factory():
    settings = Settings()
    assert settings.postgres_db == RELATIONS_DATABASE, "Relations fixture is restricted to its DB"
    engine = create_database_engine(settings)
    return engine, create_session_factory(engine)


def sides(session, universe_id):
    human, ai = session.get(AIBootstrap, universe_id).result["actors"]
    return UUID(human["empire_id"]), UUID(ai["empire_id"]), UUID(ai["controller_id"])


def contacts_proof(universe_id):
    """After the real combat-worker: both oriented contacts and the attacker's dated fact."""
    engine, sessions = relations_factory()
    u = UUID(universe_id)
    with sessions() as s:
        human, ai, _ = sides(s, u)
        fought = s.scalars(
            select(CombatEngagement.battle_at).where(
                CombatEngagement.universe_id == u,
                CombatEngagement.state == "resolved",
                CombatEngagement.defender_empire_id.is_not(None),
            )
        ).all()
        # A presence observation may precede the battle (an AI colony in a human-monitored
        # system); either way each side must know the other once a battle was fought.
        contacts = {
            c.observer_empire_id: (c.observed_empire_id, c.first_source)
            for c in s.scalars(select(RelationContact).where(RelationContact.universe_id == u))
        }
        low, high = pair(human, ai)
        row = s.get(RelationPair, (low, high))
        by_human = row.last_hostile_by_low_at if human == low else row.last_hostile_by_high_at
        by_ai = row.last_hostile_by_high_at if human == low else row.last_hostile_by_low_at
        result = {
            "ruleset": rules_for(s, u).version,
            "contacts": len(contacts),
            "mutual": contacts.get(human, (None,))[0] == ai
            and contacts.get(ai, (None,))[0] == human,
            "sources": sorted({source for _, source in contacts.values()}),
            "human_hostile_is_last_battle": by_human == max(fought) if fought else False,
            "ai_hostile": by_ai is not None,
            "state_pacts": s.scalar(
                select(func.count()).select_from(RelationPact).where(RelationPact.universe_id == u)
            ),
            "ai_attacks": s.scalar(
                select(func.count())
                .select_from(FleetMission)
                .where(
                    FleetMission.universe_id == u,
                    FleetMission.empire_id == ai,
                    FleetMission.kind == "ATTACK",
                )
            ),
        }
    engine.dispose()
    print(json.dumps(result))


def propose(universe_id):
    """The human proposes a pact through the same service as POST .../propose (real clock)."""
    engine, sessions = relations_factory()
    u = UUID(universe_id)
    with sessions.begin() as s:
        human, ai, _ = sides(s, u)
        receipt = relations.propose(
            s, u, human, ai, key="recipe:relations:propose", at=datetime.now(UTC)
        )
    engine.dispose()
    print(json.dumps(receipt))


def answer(universe_id):
    """The AI answer, read back from its own trace and the resulting durable state."""
    engine, sessions = relations_factory()
    u = UUID(universe_id)
    with sessions() as s:
        human, ai, controller = sides(s, u)
        rules = rules_for(s, u)
        events = list(
            s.scalars(
                select(RelationEvent)
                .where(RelationEvent.universe_id == u, RelationEvent.actor_empire_id == ai)
                .order_by(RelationEvent.at)
            )
        )
        if not events:
            engine.dispose()
            print(json.dumps({"answered": False}))
            return
        event = events[0]
        decision = s.scalars(
            select(AIDecision)
            .where(AIDecision.controller_id == controller)
            .order_by(AIDecision.sequence.desc())
        ).first()
        trace_choice = next(
            (
                c
                for d in s.scalars(
                    select(AIDecision).where(AIDecision.controller_id == controller)
                )
                for c in d.observation["candidates"]
                if c["key"] == d.trace.get("choice") and c["operation"] == "relation"
            ),
            None,
        )
        low, high = pair(human, ai)
        row = s.get(RelationPair, (low, high))
        by_human = row.last_hostile_by_low_at if human == low else row.last_hostile_by_high_at
        window = timedelta(seconds=rules.ai.diplomacy.grievance_seconds)
        result = {
            "answered": True,
            "kind": event.kind,
            "expected": "refused" if recent(by_human, event.at, window) else "accepted",
            "trace_action": trace_choice["body"]["action"] if trace_choice else None,
            "proposal_cleared": row.proposal_by_empire_id is None,
            "pacts": s.scalar(
                select(func.count()).select_from(RelationPact).where(RelationPact.universe_id == u)
            ),
            "human_cooldown": (row.low_cooldown_until if human == low else row.high_cooldown_until)
            is not None,
            "last_outcome": decision.outcome if decision else None,
            "principals": s.scalar(select(func.count()).select_from(GamePrincipal)),
        }
    engine.dispose()
    print(json.dumps(result))
