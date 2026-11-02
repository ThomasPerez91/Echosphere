"""Frontier services (13B, ruleset v0.9).

Locks and streams:
- Passages are recorded inside the Fleet transaction that decides a movement (launch, recall,
  return after battle), under the moving Empire's Operations stream lock, and each one schedules
  a `FRONTIER_PASSAGE` event on that same stream at its `entered_at`. No other stream is locked.
- The passage handler runs on the moving Empire's stream at the logical instant `entered_at`
  (even if processed late). It only reads protocol periods (FOR SHARE, so a concurrent change
  is seen once committed) and appends unique detection facts: replay never duplicates.
- Contacts introduced by FRIENDLY_CONTACT are materialised later, at the same points as presence
  contacts (reads, AI turn after its command), never inside a handler: global order pair →
  contact preserved (a handler may run inside a Combat catch-up that locks a pair afterwards).

Detection (D1–D3): every Empire has detection level 0 until Q58 defines a technology, so every
encounter between a real passage and a protocol-holding stationed Fleet is mutual. An observer
learns the system, the instant and an anonymous foreign signature; the Empire only if it was
already its contact at that instant or if a FRIENDLY_CONTACT introduction took place.
"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.colony.service import ColonyError
from app.frontier.encounter import AGGRESSIVE, ENGAGEMENT, RETREAT, add, kind_for
from app.frontier.encounter import FRIENDLY as FRIENDLY_PROTOCOL
from app.frontier.models import (
    FleetPassage,
    FleetProtocolPeriod,
    FrontierDetection,
    FrontierEncounter,
)
from app.frontier.transit import OUTBOUND, Passage, cancelled, outbound, way_back
from app.galaxy.models import EmpireExploration, GalaxyRoute
from app.relations import service as relations
from app.relations.models import RelationContact
from app.simulation.clock import utc
from app.simulation.models import ColonyTimeline, EventStream, ScheduledEvent, StreamFence
from app.simulation.scheduler import TimelineError, schedule

DETECTION_LIMIT = 50
FRIENDLY = "FRIENDLY_CONTACT"


class FrontierError(ColonyError):
    pass


def enabled(rules):
    return getattr(rules, "frontier", None) is not None


def detection_level(session, universe_id, empire_id, at):
    """D1: provisional level 0 for every Empire until Q58 defines a detection technology."""
    return 0


# --- B01 passages ------------------------------------------------------------------------------


def crossed_systems(session, universe_id, origin_id, path):
    """Systems entered along known routes, in order (origin excluded, destination included)."""
    node, systems = origin_id, []
    for route_id in path:
        route = session.get(GalaxyRoute, route_id)
        if route is None or route.universe_id != universe_id:
            raise TimelineError("Inconsistent mission path")
        if node not in (route.a_id, route.b_id):
            raise TimelineError("Inconsistent mission path")
        node = route.b_id if route.a_id == node else route.a_id
        systems.append(node)
    return systems


def passage_key(mission_id, sequence):
    return f"frontier-passage:{mission_id}:{sequence}"


def persist(session, mission, stream_id, passages):
    for p in passages:
        session.add(row(mission, p))
    session.flush()
    for p in passages:
        schedule(
            session,
            stream_id,
            mission.universe_id,
            key=passage_key(mission.id, p.sequence),
            kind="FRONTIER_PASSAGE",
            due_at=p.entered_at,
            payload={"mission_id": str(mission.id), "sequence": p.sequence},
        )


def record_outbound(session, rules, mission, stream_id, path, travel_us):
    if not enabled(rules) or not path:
        return []
    systems = crossed_systems(session, mission.universe_id, mission.origin_id, path)
    passages = outbound(mission.started_at, travel_us, systems)
    persist(session, mission, stream_id, passages)
    return passages


def planned(session, mission):
    return list(
        session.scalars(
            select(FleetPassage)
            .where(FleetPassage.mission_id == mission.id)
            .order_by(FleetPassage.sequence)
            .with_for_update()
        )
    )


def record_way_back(session, rules, mission, stream_id, depart_at, progress_at):
    """The mirrored way back; unreached outbound entries and their events are cancelled."""
    if not enabled(rules):
        return []
    rows = planned(session, mission)
    if not rows:
        return []
    if any(r.direction != OUTBOUND for r in rows):
        raise TimelineError("Way back already recorded")
    passages = [Passage(r.sequence, r.system_id, r.entered_at, r.direction) for r in rows]
    unreached = {p.sequence for p in cancelled(passages, progress_at)}
    for r in rows:
        if r.sequence in unreached:
            r.cancelled_at = progress_at
            cancel_event(session, stream_id, mission, r.sequence, progress_at)
            cancel_encounters(session, progress_at, passage=r)
    back = way_back(passages, mission.origin_id, mission.started_at, depart_at, progress_at)
    persist(session, mission, stream_id, back)
    return back


def cancel_event(session, stream_id, mission, sequence, at):
    event = session.scalar(
        select(ScheduledEvent).where(
            ScheduledEvent.stream_id == stream_id,
            ScheduledEvent.idempotency_key == passage_key(mission.id, sequence),
        )
    )
    if event is not None and event.status == "pending":
        event.status, event.completed_at, event.error_code = "completed", utc(at), "cancelled"


def row(mission, p):
    return FleetPassage(
        mission_id=mission.id,
        sequence=p.sequence,
        empire_id=mission.empire_id,
        universe_id=mission.universe_id,
        system_id=p.system_id,
        entered_at=p.entered_at,
        direction=p.direction,
    )


def cancel_unreached(session, mission, stream_id, at):
    """A mission ended for good at `at` (Fleet destroyed): later entries, outbound or on the
    way back, never happen; their detections and reactions are cancelled too."""
    for r in planned(session, mission):
        if r.cancelled_at is None and r.entered_at > at:
            r.cancelled_at = at
            cancel_event(session, stream_id, mission, r.sequence, at)
            cancel_encounters(session, at, passage=r)


# --- B02 protocol periods ----------------------------------------------------------------------


def check_protocol(rules, protocol):
    """None clears the protocol; otherwise it must be enabled by the pinned ruleset."""
    if not enabled(rules):
        raise FrontierError("Frontier absent from pinned ruleset", "frontier_unavailable")
    if protocol is not None and protocol not in rules.frontier.protocols:
        raise FrontierError("Protocol not enabled by this ruleset", "protocol_unavailable")


def end_protocol(session, fleet, at):
    """Close the open period (if any) at the logical instant the stationing or protocol ends."""
    period = session.scalar(
        select(FleetProtocolPeriod)
        .where(FleetProtocolPeriod.fleet_id == fleet.id, FleetProtocolPeriod.ended_at.is_(None))
        .with_for_update()
    )
    if period is not None:
        period.ended_at = max(utc(at), period.started_at)
        # The protocol no longer covers later entries: their reactions never happen.
        cancel_encounters(session, period.ended_at, period=period)
    fleet.protocol = None


def start_protocol(session, fleet, protocol, at):
    end_protocol(session, fleet, at)
    session.flush()
    if protocol is not None:
        session.add(
            FleetProtocolPeriod(
                fleet_id=fleet.id,
                empire_id=fleet.empire_id,
                universe_id=fleet.universe_id,
                system_id=fleet.system_id,
                protocol=protocol,
                started_at=utc(at),
            )
        )
    fleet.protocol = protocol
    session.flush()
    if protocol is not None:
        opened = session.scalar(
            select(FleetProtocolPeriod).where(
                FleetProtocolPeriod.fleet_id == fleet.id, FleetProtocolPeriod.ended_at.is_(None)
            )
        )
        plan_for_period(session, opened)


# --- B05/B06 automatic reactions: planning, fences, cancellation ------------------------------


def encounter_owner(encounter_id):
    return f"frontier:{encounter_id}"


def fence_instant(kind, t):
    """Engagements see the state strictly before the entry (an arrival at that instant cannot
    settle the mover first); a retreat is paid at the entry instant itself (inclusive)."""
    return t - timedelta(microseconds=1) if kind == ENGAGEMENT else t


def operations_stream(session, universe_id, empire_id):
    state = session.get(EmpireExploration, empire_id)
    if state is None or state.universe_id != universe_id:
        raise TimelineError("Operations stream missing")
    return state.stream_id


def fenced_streams(session, encounter):
    """Streams frozen by one reaction, in a stable sorted order (also the lock order)."""
    watcher = operations_stream(session, encounter.universe_id, encounter.watcher_empire_id)
    if encounter.kind == ENGAGEMENT:
        mover = operations_stream(session, encounter.universe_id, encounter.mover_empire_id)
        return sorted({watcher, mover}, key=str)
    from app.fleet.models import Fleet

    fleet = session.get(Fleet, encounter.watch_fleet_id)
    colony = session.get(ColonyTimeline, fleet.home_colony_id)
    return sorted({watcher, colony.stream_id}, key=str)


def add_fences(session, encounter):
    at = fence_instant(encounter.kind, encounter.encounter_at)
    for stream_id in fenced_streams(session, encounter):
        cursor = session.scalar(select(EventStream.cursor_at).where(EventStream.id == stream_id))
        if cursor is None or cursor > at:
            # Only possible for a late orchestrator decision: never fight on a passed state.
            raise TimelineError("A fenced stream already passed the encounter instant")
        session.add(
            StreamFence(
                stream_id=stream_id,
                universe_id=encounter.universe_id,
                fence_at=at,
                owner=encounter_owner(encounter.id),
            )
        )
    session.flush()


def release(session, encounter, at):
    for fence in session.scalars(
        select(StreamFence).where(
            StreamFence.owner == encounter_owner(encounter.id), StreamFence.released_at.is_(None)
        )
    ):
        fence.released_at = utc(at)
    session.flush()


def cancel_encounters(session, at, *, period=None, passage=None):
    query = select(FrontierEncounter).where(FrontierEncounter.state.in_(["pending", "blocked"]))
    if period is not None:
        query = query.where(
            FrontierEncounter.period_id == period.id, FrontierEncounter.encounter_at >= at
        )
    if passage is not None:
        query = query.where(
            FrontierEncounter.mission_id == passage.mission_id,
            FrontierEncounter.sequence == passage.sequence,
        )
    for row in session.scalars(query.with_for_update().order_by(FrontierEncounter.id)):
        row.state, row.cancelled_at = "cancelled", utc(at)
        release(session, row, at)


def hostile_arrival(session, passage):
    """Retreat trigger (FC6): the passage is an ATTACK force entering its target system, whose
    bound defender is returned (internal truth, never projected). None otherwise."""
    from app.combat.models import CombatEngagement
    from app.fleet.models import FleetMission

    mission = session.get(FleetMission, passage.mission_id)
    if (
        mission is None
        or mission.kind != "ATTACK"
        or passage.direction != OUTBOUND
        or passage.system_id != mission.destination_id
        or passage.entered_at != mission.travel_arrival_at
    ):
        return None
    engagement = session.scalar(
        select(CombatEngagement).where(
            CombatEngagement.mission_id == mission.id, CombatEngagement.state == "pending"
        )
    )
    return engagement.defender_empire_id if engagement is not None else None


def create_encounter(session, passage, period):
    kind = kind_for(period.protocol)
    if kind is None or period.empire_id == passage.empire_id:
        return None
    if kind == RETREAT and hostile_arrival(session, passage) != period.empire_id:
        return None
    existing = session.scalar(
        select(FrontierEncounter).where(
            FrontierEncounter.mission_id == passage.mission_id,
            FrontierEncounter.sequence == passage.sequence,
            FrontierEncounter.watch_fleet_id == period.fleet_id,
            FrontierEncounter.kind == kind,
        )
    )
    if existing is not None:
        return existing
    row = FrontierEncounter(
        universe_id=passage.universe_id,
        kind=kind,
        mission_id=passage.mission_id,
        sequence=passage.sequence,
        period_id=period.id,
        watch_fleet_id=period.fleet_id,
        protocol=period.protocol,
        watcher_empire_id=period.empire_id,
        mover_empire_id=passage.empire_id,
        system_id=passage.system_id,
        encounter_at=passage.entered_at,
        state="pending",
        attempts=0,
    )
    session.add(row)
    session.flush()
    add_fences(session, row)
    return row


REACTIVE = (*AGGRESSIVE, FRIENDLY_PROTOCOL)


def plan_for_mission(session, rules, mission):
    """After a movement decision: reactions of protocols open now on the future entries.
    A protocol set later plans its own reactions (plan_for_period)."""
    if not enabled(rules):
        return []
    created = []
    for passage in session.scalars(
        select(FleetPassage)
        .where(
            FleetPassage.mission_id == mission.id,
            FleetPassage.cancelled_at.is_(None),
        )
        .order_by(FleetPassage.sequence)
    ):
        for period in session.scalars(
            select(FleetProtocolPeriod)
            .where(
                FleetProtocolPeriod.universe_id == passage.universe_id,
                FleetProtocolPeriod.system_id == passage.system_id,
                FleetProtocolPeriod.empire_id != passage.empire_id,
                FleetProtocolPeriod.ended_at.is_(None),
                FleetProtocolPeriod.started_at < passage.entered_at,
                FleetProtocolPeriod.protocol.in_(REACTIVE),
            )
            .order_by(FleetProtocolPeriod.fleet_id)
        ):
            row = create_encounter(session, passage, period)
            if row is not None:
                created.append(row)
    return created


def plan_for_period(session, period):
    """After a protocol command: reactions to entries already decided, strictly after it."""
    if period is None or period.protocol not in REACTIVE:
        return []
    created = []
    for passage in session.scalars(
        select(FleetPassage)
        .where(
            FleetPassage.universe_id == period.universe_id,
            FleetPassage.system_id == period.system_id,
            FleetPassage.empire_id != period.empire_id,
            FleetPassage.cancelled_at.is_(None),
            FleetPassage.entered_at > period.started_at,
        )
        .order_by(FleetPassage.entered_at, FleetPassage.mission_id, FleetPassage.sequence)
    ):
        row = create_encounter(session, passage, period)
        if row is not None:
            created.append(row)
    return created


def intercepted_losses(session, mission_id):
    """Units of a mission destroyed by resolved frontier engagements: launch = now + these."""
    total = {}
    for result in session.scalars(
        select(FrontierEncounter.result).where(
            FrontierEncounter.mission_id == mission_id,
            FrontierEncounter.kind == ENGAGEMENT,
            FrontierEncounter.state == "resolved",
            FrontierEncounter.outcome == "fought",
        )
    ):
        total = add(total, result["mover"]["losses"])
    return total


# --- B03/B04 detection -------------------------------------------------------------------------


def knew(session, observer, observed, at):
    first = session.scalar(
        select(RelationContact.first_seen_at).where(
            RelationContact.observer_empire_id == observer,
            RelationContact.observed_empire_id == observed,
        )
    )
    return first is not None and first <= at


def watchers(session, passage):
    """Protocol periods of other Empires covering the logical entry instant, in stable order."""
    t = passage.entered_at
    return list(
        session.scalars(
            select(FleetProtocolPeriod)
            .where(
                FleetProtocolPeriod.universe_id == passage.universe_id,
                FleetProtocolPeriod.system_id == passage.system_id,
                FleetProtocolPeriod.empire_id != passage.empire_id,
                FleetProtocolPeriod.started_at <= t,
                or_(FleetProtocolPeriod.ended_at.is_(None), FleetProtocolPeriod.ended_at > t),
            )
            .order_by(FleetProtocolPeriod.fleet_id)
            .with_for_update(read=True)
        )
    )


def detect(session, passage, period):
    """One encounter, both sides (equal levels: mutual), as unique append-only facts."""
    t, mover, watcher = passage.entered_at, passage.empire_id, period.empire_id
    friendly = period.protocol == FRIENDLY
    sides = (
        ("watch", watcher, mover, friendly or knew(session, watcher, mover, t)),
        ("transit", mover, watcher, friendly or knew(session, mover, watcher, t)),
    )
    for role, observer, observed, identified in sides:
        session.execute(
            insert(FrontierDetection)
            .values(
                universe_id=passage.universe_id,
                mission_id=passage.mission_id,
                sequence=passage.sequence,
                watch_fleet_id=period.fleet_id,
                role=role,
                observer_empire_id=observer,
                observed_empire_id=observed,
                system_id=passage.system_id,
                detected_at=t,
                identified=identified,
                friendly=friendly,
            )
            .on_conflict_do_nothing(constraint="uq_frontier_detections")
        )


def complete_passage(session, event, processed_at):
    """FRONTIER_PASSAGE handler on the moving Empire's stream, evaluated at `entered_at`."""
    if set(event.payload) != {"mission_id", "sequence"}:
        raise TimelineError("Invalid passage payload")
    try:
        mission_id, sequence = UUID(event.payload["mission_id"]), int(event.payload["sequence"])
    except (TypeError, ValueError):
        raise TimelineError("Invalid passage payload") from None
    passage = session.get(FleetPassage, (mission_id, sequence))
    if (
        passage is None
        or passage.universe_id != event.universe_id
        or event.idempotency_key != passage_key(mission_id, sequence)
        or passage.entered_at != event.due_at
    ):
        raise TimelineError("Passage outside its event")
    if passage.cancelled_at is not None:
        return []  # never reached: no detection
    if detection_level(session, passage.universe_id, passage.empire_id, passage.entered_at) != 0:
        raise TimelineError("Only the provisional equal detection level is supported")
    found = watchers(session, passage)
    for period in found:
        detect(session, passage, period)
    session.flush()
    return found


def materialise_introductions(session, universe_id, empire_id, at):
    """FRIENDLY_CONTACT introductions observed by this Empire become durable oriented contacts
    (source frontier, dated at the encounter). Called only where contacts may be written."""
    rows = session.execute(
        select(FrontierDetection.observed_empire_id, FrontierDetection.detected_at)
        .outerjoin(
            RelationContact,
            and_(
                RelationContact.observer_empire_id == FrontierDetection.observer_empire_id,
                RelationContact.observed_empire_id == FrontierDetection.observed_empire_id,
            ),
        )
        .where(
            FrontierDetection.universe_id == universe_id,
            FrontierDetection.observer_empire_id == empire_id,
            FrontierDetection.friendly.is_(True),
            FrontierDetection.detected_at <= utc(at),
            RelationContact.observer_empire_id.is_(None),
        )
        .order_by(FrontierDetection.detected_at, FrontierDetection.observed_empire_id)
        .limit(DETECTION_LIMIT)
    ).all()
    for observed, detected_at in rows:
        relations.record_contact(session, universe_id, empire_id, observed, "frontier", detected_at)


def detections_for(session, universe_id, empire_id, names, system_ref, limit=DETECTION_LIMIT):
    """Observer view: system, instant, signature; identity only when identified. No direction,
    composition, cargo, origin, destination or route (D3)."""
    rows = session.scalars(
        select(FrontierDetection)
        .where(
            FrontierDetection.universe_id == universe_id,
            FrontierDetection.observer_empire_id == empire_id,
        )
        .order_by(FrontierDetection.detected_at.desc(), FrontierDetection.id)
        .limit(limit)
    )
    result = []
    for d in rows:
        result.append(
            {
                "id": str(d.id),
                "system": system_ref(d.system_id),
                "detected_at": d.detected_at.isoformat(),
                "role": d.role,
                "friendly": d.friendly,
                "empire": {"id": str(d.observed_empire_id), "name": names(d.observed_empire_id)}
                if d.identified
                else None,
            }
        )
    return result


PERSPECTIVE = {
    ("watcher", "attacker_win"): "victory",
    ("watcher", "defender_win"): "defeat",
    ("mover", "attacker_win"): "defeat",
    ("mover", "defender_win"): "victory",
}


def encounters_for(session, universe_id, empire_id, names, system_ref, limit=DETECTION_LIMIT):
    """Own reports only. A fought engagement is a battle report for both sides (opponent named,
    military forces engaged, losses: same reveal as a Combat report); a meeting where nothing was
    fought is never reported, since its reason could reveal the other force (D3). A retreat is
    reported to its owner only: instant, system, outcome and destination."""
    e = FrontierEncounter
    rows = session.scalars(
        select(e)
        .where(
            e.universe_id == universe_id,
            e.state == "resolved",
            or_(
                and_(
                    e.watcher_empire_id == empire_id,
                    or_(e.outcome == "fought", e.kind == RETREAT),
                ),
                and_(e.mover_empire_id == empire_id, e.outcome == "fought"),
            ),
        )
        .order_by(e.encounter_at.desc(), e.id)
        .limit(limit)
    )
    result = []
    for row in rows:
        base = {
            "id": str(row.id),
            "kind": row.kind,
            "at": row.encounter_at.isoformat(),
            "system": system_ref(row.system_id),
        }
        if row.kind == RETREAT:
            destination = row.result.get("destination_id")
            result.append(
                base
                | {
                    "outcome": row.outcome,
                    "reason": row.result.get("reason"),
                    "destination": system_ref(UUID(destination)) if destination else None,
                }
            )
            continue
        role = "watcher" if row.watcher_empire_id == empire_id else "mover"
        other = "mover" if role == "watcher" else "watcher"
        opponent = row.mover_empire_id if role == "watcher" else row.watcher_empire_id
        own, theirs = row.result[role], row.result[other]
        battle = row.result["battle"]
        result.append(
            base
            | {
                "role": role,
                "protocol": row.protocol if role == "watcher" else None,
                "outcome": PERSPECTIVE.get((role, battle), battle),
                "opponent": {"id": str(opponent), "name": names(opponent)},
                "own": {k: own[k] for k in ("initial", "losses", "survivors")},
                "opponent_forces": {k: theirs[k] for k in ("initial", "losses", "survivors")},
                "destroyed": bool(own.get("destroyed")),
                "rounds": row.result["rounds"],
            }
        )
    return result
