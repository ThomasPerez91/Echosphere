"""Test-only helpers for the disposable AI recipe; refused outside its *_test Game DB.

The universe is provisioned by Portal and started by the real operator CLI
(`python -m app.ai.worker --bootstrap`) with the unchanged v0.6 ruleset. After that start this
module never writes gameplay state: `drive` only advances an injected test clock through the
real TimeEngine and Orchestrator classes (same code as the worker and ai-worker processes);
everything else reads Game DB directly, never through a GET that could catch up state.
"""

import json
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.ai.models import AIBootstrap, AIController, AIDecision
from app.ai.orchestrator import Orchestrator
from app.colony.models import ColonyInfrastructure, ConstructionOrder
from app.colony.rules import load_ruleset
from app.control.models import EmpireBinding, GamePrincipal
from app.core.config import Settings
from app.fleet.models import Fleet, FleetMission, ShipOrder
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import Colony, Empire, Planet, Universe
from app.research.models import AcquiredTechnology, ResearchOrder
from app.simulation.models import ResourceBalance
from app.simulation.service import TimeEngine
from sqlalchemy import func, select, text

DATABASE = "echosphere_ai_game_test"


def factory():
    settings = Settings()
    assert settings.postgres_db == DATABASE, "AI fixture is restricted to its test DB"
    engine = create_database_engine(settings)
    return engine, create_session_factory(engine)


def provisioned(universe_id):
    engine, sessions = factory()
    for _ in range(60):
        with sessions() as session:
            universe = session.get(Universe, UUID(universe_id))
            if universe is not None:
                break
        time.sleep(0.5)
    else:
        raise RuntimeError("Universe was not provisioned through the control plane")
    engine.dispose()
    print(json.dumps({"name": universe.name, "seed": universe.seed}))


class TestClock:
    """Injected recipe clock: explicit 600 s steps, never ahead of the real clock."""

    def __init__(self, at):
        self.at = at

    def now(self):
        return self.at


def actors(session, universe_id):
    return session.get(AIBootstrap, universe_id).result["actors"]


def milestones(session, empire_id, producers):
    """Durable progress of one AI Empire, from its own rows only."""
    ships = set(
        session.scalars(select(ShipOrder.ship_class).where(ShipOrder.empire_id == empire_id))
    )
    missions = {
        kind: session.scalar(
            select(func.count()).where(
                FleetMission.empire_id == empire_id,
                FleetMission.kind == kind,
                FleetMission.status == "completed",
            )
        )
        for kind in ("SURVEY", "COLONIZE")
    }
    founded = []
    for colony in session.scalars(
        select(Colony)
        .where(Colony.empire_id == empire_id, Colony.founding_mission_id.is_not(None))
        .order_by(Colony.founded_at, Colony.id)
    ):
        kinds = session.scalars(
            select(ConstructionOrder.infrastructure_type)
            .where(ConstructionOrder.colony_id == colony.id)
            .order_by(ConstructionOrder.sequence)
            .limit(3)
        ).all()
        founded.append(
            {
                "colony_id": str(colony.id),
                "cargo": session.get(FleetMission, colony.founding_mission_id).snapshot["cargo"],
                "first_builds": kinds,
                "bootstrapped": kinds == producers,
                "built": session.scalar(
                    select(func.count()).where(ColonyInfrastructure.colony_id == colony.id)
                ),
            }
        )
    return {
        "builds": session.scalar(
            select(func.count())
            .select_from(ConstructionOrder)
            .join(Colony, Colony.id == ConstructionOrder.colony_id)
            .where(Colony.empire_id == empire_id)
        ),
        "research_orders": session.scalar(
            select(func.count()).where(ResearchOrder.empire_id == empire_id)
        ),
        "acquired": session.scalar(
            select(func.count()).where(AcquiredTechnology.empire_id == empire_id)
        ),
        "ships": sorted(ships),
        "surveys": missions["SURVEY"],
        "colonizations": missions["COLONIZE"],
        "founded": founded,
    }


def developed(m):
    return (
        {"probe", "colonizer"} <= set(m["ships"])
        and m["surveys"]
        and m["acquired"]
        and any(f["bootstrapped"] and f["built"] >= 3 for f in m["founded"])
    )


def drive(universe_id, limit_hours):
    """Advance the test clock in 600 s steps, up to the real clock minus one slot, at most."""
    engine, sessions = factory()
    universe_id = UUID(universe_id)
    with sessions() as session:
        started = datetime.fromisoformat(session.get(AIBootstrap, universe_id).result["started_at"])
        ai = [a for a in actors(session, universe_id) if a["controller_id"]]
    producers = [load_ruleset("v0.6").ai.producers[r] for r in ("alloys", "flux", "data")]
    end = min(started + timedelta(hours=limit_hours), datetime.now(UTC) - timedelta(seconds=600))
    clock = TestClock(started)
    processor, runner = TimeEngine(sessions, clock), Orchestrator(sessions, clock)
    turns, reached = 0, {}
    while clock.at + timedelta(seconds=600) <= end and len(reached) < len(ai):
        clock.at += timedelta(seconds=600)
        while processor.process_next() is not None:
            pass
        for actor in ai:
            if runner.process_next(controller_id=UUID(actor["controller_id"]), raise_errors=True):
                turns += 1
        with sessions() as session:
            for actor in ai:
                if developed(milestones(session, UUID(actor["empire_id"]), producers)):
                    reached.setdefault(actor["profile"], clock.at.isoformat())
    engine.dispose()
    print(json.dumps({"turns": turns, "virtual_end": clock.at.isoformat(), "reached": reached}))


def proof(universe_id):
    engine, sessions = factory()
    universe_id = UUID(universe_id)
    producers = [load_ruleset("v0.6").ai.producers[r] for r in ("alloys", "flux", "data")]
    with sessions() as session:
        result = {"actors": [], "now": datetime.now(UTC).isoformat()}
        for actor in actors(session, universe_id):
            e = UUID(actor["empire_id"])
            colonies = session.scalars(
                select(Colony).where(Colony.empire_id == e).order_by(Colony.created_at, Colony.id)
            ).all()
            starting = colonies[0]
            row = {
                "profile": actor["profile"],
                "empire_id": actor["empire_id"],
                "controller_type": session.get(Empire, e).controller_type,
                "planet": session.get(Planet, starting.planet_id).name,
                "colony_id": str(starting.id),
                "progress": milestones(session, e, producers),
                "keys": sorted(
                    {
                        k.split(":")[0]
                        for k in [
                            *session.scalars(
                                select(ShipOrder.idempotency_key).where(ShipOrder.empire_id == e)
                            ),
                            *session.scalars(
                                select(FleetMission.idempotency_key).where(
                                    FleetMission.empire_id == e
                                )
                            ),
                            *session.scalars(
                                select(ResearchOrder.idempotency_key).where(
                                    ResearchOrder.empire_id == e
                                )
                            ),
                            *session.scalars(
                                select(ConstructionOrder.idempotency_key)
                                .join(Colony, Colony.id == ConstructionOrder.colony_id)
                                .where(Colony.empire_id == e)
                            ),
                        ]
                    }
                ),
            }
            if actor["controller_id"]:
                c = session.get(AIController, UUID(actor["controller_id"]))
                last = session.get(AIDecision, (c.id, c.sequence - 1))
                row["controller"] = {
                    "id": str(c.id),
                    "state": c.state,
                    "sequence": c.sequence,
                    "next_decision_at": c.next_decision_at.isoformat(),
                    "last_planned_at": last.planned_at.isoformat() if last else None,
                    "last_observed_at": last.observed_at.isoformat() if last else None,
                    "last_outcome": last.outcome if last else None,
                }
            result["actors"].append(row)
        # Human accounts only: one Game principal, bindings on the human Empire alone.
        result["principals"] = session.scalar(select(func.count()).select_from(GamePrincipal))
        result["bound_empires"] = sorted(
            str(e)
            for e in session.scalars(
                select(EmpireBinding.empire_id).where(EmpireBinding.universe_id == universe_id)
            )
        )
        result["balances_of_founded"] = [
            {
                b.resource: b.rate_per_hour
                for b in session.scalars(
                    select(ResourceBalance).where(ResourceBalance.colony_id == UUID(f["colony_id"]))
                )
            }
            for a in result["actors"]
            for f in a["progress"]["founded"][:1]
        ]
    engine.dispose()
    print(json.dumps(result))


def starts(universe_id):
    """Right after the operator bootstrap: same stocks, rates and buildings for every actor."""
    engine, sessions = factory()
    with sessions() as session:
        rows = []
        for actor in actors(session, UUID(universe_id)):
            colony, empire = UUID(actor["colony_id"]), session.get(Empire, UUID(actor["empire_id"]))
            rows.append(
                {
                    "profile": actor["profile"],
                    "controller_type": empire.controller_type,
                    "planet": session.get(Planet, session.get(Colony, colony).planet_id).name,
                    "balances": sorted(
                        (b.resource, b.stock, b.rate_per_hour)
                        for b in session.scalars(
                            select(ResourceBalance).where(ResourceBalance.colony_id == colony)
                        )
                    ),
                    "buildings": sorted(
                        (b.sector_index, b.infrastructure_type, b.level)
                        for b in session.scalars(
                            select(ColonyInfrastructure).where(
                                ColonyInfrastructure.colony_id == colony
                            )
                        )
                    ),
                    "fleets": session.scalar(
                        select(func.count()).where(Fleet.empire_id == UUID(actor["empire_id"]))
                    ),
                }
            )
    engine.dispose()
    print(json.dumps(rows))


def expire(universe_id):
    """Simulates reaching the absolute deadline: moves it just after the last activity."""
    engine, sessions = factory()
    with sessions.begin() as session:
        count = session.execute(
            text(
                "UPDATE game_sessions SET expires_at = last_activity_at + interval '1 millisecond' "
                "WHERE universe_id = :universe AND revoked_at IS NULL"
            ),
            {"universe": universe_id},
        ).rowcount
    engine.dispose()
    assert count == 1, "Exactly one live recipe session expected"
    print(json.dumps({"expired": count}))
