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

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.colony.service import ColonyError
from app.frontier.models import FleetPassage, FleetProtocolPeriod, FrontierDetection
from app.frontier.transit import OUTBOUND, Passage, cancelled, outbound, way_back
from app.galaxy.models import GalaxyRoute
from app.relations import service as relations
from app.relations.models import RelationContact
from app.simulation.clock import utc
from app.simulation.models import ScheduledEvent
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
    """A mission ended for good at `at` (e.g. Fleet destroyed): later entries never happen."""
    for r in planned(session, mission):
        if r.cancelled_at is None and r.direction == OUTBOUND and r.entered_at > at:
            r.cancelled_at = at
            cancel_event(session, stream_id, mission, r.sequence, at)


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

