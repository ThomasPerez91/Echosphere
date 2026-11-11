"""Engagement lifecycle around the Fleet service: open at launch, cancel on recall, projections.

Lock order everywhere: own Operations stream(s) → engagement row → planet row. A command never
locks another Empire's stream; the defender's fence is inserted without that lock because the
defender's stream cursor never passes the real clock while battle_at is at least 24 h ahead.
"""

from sqlalchemy import select

from app.combat.models import CombatEngagement, CombatReport
from app.fleet.models import FleetMission
from app.galaxy import service as galaxy
from app.persistence.models import Planet
from app.simulation.clock import utc
from app.simulation.models import EventStream, StreamFence
from app.simulation.scheduler import TimelineError


def fence_owner(engagement_id):
    return f"combat:{engagement_id}"


def open_engagement(session, mission, attacker_stream_id, defender_empire_id):
    if mission.target_opportunity_id is not None:
        # v0.12 (EXP-02c): a deposit; its system is the battle's system.
        from app.galaxy.models import GalaxyOpportunity

        system_id = session.get(GalaxyOpportunity, mission.target_opportunity_id).system_id
    else:
        system_id = session.get(Planet, mission.target_planet_id).system_id
    engagement = CombatEngagement(
        universe_id=mission.universe_id,
        mission_id=mission.id,
        attacker_empire_id=mission.empire_id,
        defender_empire_id=defender_empire_id,
        target_planet_id=mission.target_planet_id,
        target_opportunity_id=mission.target_opportunity_id,
        target_system_id=system_id,
        started_at=mission.started_at,
        travel_arrival_at=mission.travel_arrival_at,
        battle_at=mission.due_at,
        state="pending",
        attempts=0,
    )
    session.add(engagement)
    session.flush()
    streams = [attacker_stream_id]
    if defender_empire_id is not None:
        streams.append(galaxy.state_for(session, mission.universe_id, defender_empire_id).stream_id)
    for stream_id in streams:
        cursor = session.scalar(select(EventStream.cursor_at).where(EventStream.id == stream_id))
        if cursor is None or cursor > engagement.battle_at:
            raise TimelineError("A fenced stream already passed the battle instant")
        session.add(
            StreamFence(
                stream_id=stream_id,
                universe_id=mission.universe_id,
                fence_at=engagement.battle_at,
                owner=fence_owner(engagement.id),
            )
        )
    session.flush()
    return engagement


def release_fences(session, engagement, at):
    for fence in session.scalars(
        select(StreamFence).where(
            StreamFence.owner == fence_owner(engagement.id), StreamFence.released_at.is_(None)
        )
    ):
        fence.released_at = utc(at)
    session.flush()


def cancel_engagement(session, mission, at):
    """Recall before battle_at; the attacker's Operations stream is already locked."""
    engagement = session.scalar(
        select(CombatEngagement)
        .where(CombatEngagement.mission_id == mission.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if engagement is None or engagement.state != "pending":
        raise TimelineError("Engagement no longer cancellable")
    engagement.state, engagement.cancelled_at = "cancelled", utc(at)
    release_fences(session, engagement, at)
    return engagement


def operation_losses(session, mission):
    """v0.12 (EXP-02c): escorts of an extraction lost in battles on its deposit since its
    launch (the launch composition is now + these losses)."""
    total = {}
    if mission.kind != "EXTRACT" or mission.target_opportunity_id is None:
        return total
    for result in session.scalars(
        select(CombatEngagement.result).where(
            CombatEngagement.universe_id == mission.universe_id,
            CombatEngagement.target_opportunity_id == mission.target_opportunity_id,
            CombatEngagement.state == "resolved",
            CombatEngagement.battle_at >= mission.started_at,
        )
    ):
        for kind, n in (result.get("defender_losses") or {}).get(str(mission.fleet_id), {}).items():
            total[kind] = total.get(kind, 0) + n
    return total


# --- Projections (read-only, never a catch-up) -------------------------------------------------


def alerts_for(session, universe_id, empire_id, limit=50, *, history=True):
    """Defender view before the battle: target, battle_at and state only. Never the attacker,
    its origin, route, composition or size. Live threats first, nearest battle first; the
    cancellation history only fills what is left, so it can never hide an actual threat."""
    scope = (
        CombatEngagement.universe_id == universe_id,
        CombatEngagement.defender_empire_id == empire_id,
    )
    rows = list(
        session.scalars(
            select(CombatEngagement)
            .where(*scope, CombatEngagement.state.in_(["pending", "blocked"]))
            .order_by(CombatEngagement.battle_at, CombatEngagement.id)
            .limit(limit)
        )
    )
    if history and len(rows) < limit:
        rows += session.scalars(
            select(CombatEngagement)
            .where(*scope, CombatEngagement.state == "cancelled")
            .order_by(CombatEngagement.cancelled_at.desc(), CombatEngagement.id)
            .limit(limit - len(rows))
        )
    return [
        {
            "id": str(e.id),
            "planet_id": str(e.target_planet_id) if e.target_planet_id else None,
            "system_id": str(e.target_system_id),
            "battle_at": e.battle_at.isoformat(),
            # v0.12: an announced attack on one of this Empire's extraction operations.
            **({"opportunity_id": str(e.target_opportunity_id)} if e.target_opportunity_id else {}),
            "state": "cancelled" if e.state == "cancelled" else "pending",
        }
        for e in rows
    ]


def reports_for(session, universe_id, empire_id, limit=50):
    rows = session.scalars(
        select(CombatReport)
        .where(CombatReport.universe_id == universe_id, CombatReport.empire_id == empire_id)
        .order_by(CombatReport.battle_at.desc(), CombatReport.engagement_id)
        .limit(limit)
    )
    return [
        {
            "engagement_id": str(r.engagement_id),
            "role": r.role,
            "battle_at": r.battle_at.isoformat(),
            "processed_at": r.processed_at.isoformat(),
            **r.result,
        }
        for r in rows
    ]


def attack_of(session, mission: FleetMission):
    """Attacker view of its own engagement state; the defender binding is never projected."""
    engagement = session.scalar(
        select(CombatEngagement).where(CombatEngagement.mission_id == mission.id)
    )
    if engagement is None:
        return None
    return {
        "engagement_id": str(engagement.id),
        "battle_at": engagement.battle_at.isoformat(),
        "state": engagement.state if engagement.state != "blocked" else "pending",
    }
