"""Frontier services (13B, ruleset v0.9).

Locks and streams (C01/C02, 02/11/2026):
- Passages are recorded inside the Fleet transaction that decides a movement (launch, recall,
  return after battle), under the moving Empire's Operations stream lock. Each one fences that
  same stream at `entered_at - 1 µs` (own stream only, never another Empire's): the mover cannot
  move past an entry before the entry is resolved.
- An entry is resolved outside any handler by `app.frontier.orchestrator` once due: it locks the
  mover's stream and the stream of every Empire that may hold a protocol in the system (sorted by
  UUID, lock_timeout), settles each of them through `entered_at - 1 µs`, then evaluates detections
  and engagements in one transaction. A protocol command holds its own Empire's stream lock, so a
  command and an entry resolution are serialised whatever their commit order (no lost entry).
- Covering rule: a period covers an entry at t when `started_at < t <= ended_at` (open end). Any
  protocol change at an instant >= t therefore never alters what an entry at t saw.
- Contacts introduced by FRIENDLY_CONTACT are materialised later, at the same points as presence
  contacts (reads, AI turn after its command), never inside a handler: global order pair →
  contact preserved.

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
from app.frontier.encounter import AGGRESSIVE, ENGAGEMENT, RETREAT, add
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
from app.simulation.models import ColonyTimeline, EventStream, StreamFence
from app.simulation.scheduler import TimelineError

DETECTION_LIMIT = 50
FRIENDLY = "FRIENDLY_CONTACT"
LOCAL = "local"
UNRESOLVED = ("pending", "blocked")


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


def passage_owner(mission_id, sequence):
    return f"frontier-passage:{mission_id}:{sequence}"


def persist(session, mission, stream_id, passages):
    """Passage rows plus, for each, a fence on the mover's own stream just before the entry."""
    for p in passages:
        session.add(row(mission, p))
    session.flush()
    for p in passages:
        session.add(
            StreamFence(
                stream_id=stream_id,
                universe_id=mission.universe_id,
                fence_at=p.entered_at - timedelta(microseconds=1),
                owner=passage_owner(mission.id, p.sequence),
            )
        )
    session.flush()


def release_passage(session, mission_id, sequence, at):
    for fence in session.scalars(
        select(StreamFence).where(
            StreamFence.owner == passage_owner(mission_id, sequence),
            StreamFence.released_at.is_(None),
        )
    ):
        fence.released_at = utc(at)
    session.flush()


def record_outbound(session, rules, mission, stream_id, path, travel_us):
    if not enabled(rules) or not path:
        return []
    systems = crossed_systems(session, mission.universe_id, mission.origin_id, path)
    passages = outbound(mission.started_at, travel_us, systems)
    persist(session, mission, stream_id, passages)
    return passages


def record_local(session, rules, mission):
    """C03: a 0-hop ATTACK enters no system, yet it is a hostile act inside the target system.
    One `local` row (sequence 0, at launch) anchors the friendly retreat; it is not an entry: no
    detection, no engagement, nothing to resolve."""
    if not enabled(rules) or mission.kind != "ATTACK":
        return None
    passage = FleetPassage(
        mission_id=mission.id,
        sequence=0,
        empire_id=mission.empire_id,
        universe_id=mission.universe_id,
        system_id=mission.destination_id,
        entered_at=mission.started_at,
        direction=LOCAL,
        state="resolved",
        attempts=0,
        resolved_at=mission.started_at,
    )
    session.add(passage)
    session.flush()
    return passage


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
    rows = [r for r in planned(session, mission) if r.direction != LOCAL]
    if not rows:
        return []
    if any(r.direction != OUTBOUND for r in rows):
        raise TimelineError("Way back already recorded")
    passages = [Passage(r.sequence, r.system_id, r.entered_at, r.direction) for r in rows]
    unreached = {p.sequence for p in cancelled(passages, progress_at)}
    for r in rows:
        if r.sequence in unreached:
            cancel_passage(session, r, progress_at)
    back = way_back(passages, mission.origin_id, mission.started_at, depart_at, progress_at)
    persist(session, mission, stream_id, back)
    return back


def cancel_passage(session, passage, at):
    """An entry that never happens: no resolution, its fence and its reactions go."""
    passage.cancelled_at, passage.state = utc(at), "cancelled"
    passage.retry_at = passage.error_code = None
    release_passage(session, passage.mission_id, passage.sequence, at)
    cancel_encounters(session, at, passage=passage)


def row(mission, p):
    return FleetPassage(
        mission_id=mission.id,
        sequence=p.sequence,
        empire_id=mission.empire_id,
        universe_id=mission.universe_id,
        system_id=p.system_id,
        entered_at=p.entered_at,
        direction=p.direction,
        state="pending",
        attempts=0,
    )


def cancel_unreached(session, mission, stream_id, at):
    """A mission ended for good at `at` (Fleet destroyed): later entries, outbound or on the
    way back, never happen; their detections and reactions are cancelled too."""
    for r in planned(session, mission):
        if r.state in UNRESOLVED and r.entered_at > at:
            cancel_passage(session, r, at)


# --- B02 protocol periods ----------------------------------------------------------------------


def check_protocol(rules, protocol):
    """None clears the protocol; otherwise it must be enabled by the pinned ruleset."""
    if not enabled(rules):
        raise FrontierError("Frontier absent from pinned ruleset", "frontier_unavailable")
    if protocol is not None and protocol not in rules.frontier.protocols:
        raise FrontierError("Protocol not enabled by this ruleset", "protocol_unavailable")


def check_not_behind(session, fleet, at):
    """C02: a period change dated `at` is refused once a foreign entry of this system after `at`
    is already resolved (a command dated before an entry that waited for the stream lock the
    resolution held). Never rewrite what a resolved entry saw; a retry gets a fresh instant."""
    if fleet.system_id is None:
        return
    later = session.scalar(
        select(FleetPassage.mission_id)
        .where(
            FleetPassage.universe_id == fleet.universe_id,
            FleetPassage.system_id == fleet.system_id,
            FleetPassage.empire_id != fleet.empire_id,
            FleetPassage.state == "resolved",
            FleetPassage.direction != LOCAL,
            FleetPassage.entered_at > utc(at),
        )
        .limit(1)
    )
    if later is not None:
        raise FrontierError("A later frontier entry is already resolved; retry", "fleet_busy")


def end_protocol(session, fleet, at):
    """Close the open period (if any) at the logical instant the stationing or protocol ends."""
    period = session.scalar(
        select(FleetProtocolPeriod)
        .where(FleetProtocolPeriod.fleet_id == fleet.id, FleetProtocolPeriod.ended_at.is_(None))
        .with_for_update()
    )
    if period is not None:
        check_not_behind(session, fleet, at)
        period.ended_at = max(utc(at), period.started_at)
        # The protocol no longer covers later entries: their reactions never happen.
        cancel_encounters(session, period.ended_at, period=period)
    fleet.protocol = None


def start_protocol(session, fleet, protocol, at):
    check_not_behind(session, fleet, at)
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


# --- B05/B06 automatic reactions ----------------------------------------------------------------
#
# Engagements (AMBUSH, INTERCEPTION) are decided while an entry is resolved (orchestrator), never
# planned in advance: the mover is already frozen by its own passage fence and the watcher's
# Fleet cannot change while an entry it covers is unresolved (`guard_fleet_change`).
# Friendly retreats (FRIENDLY_CONTACT) launch a movement for the watcher at the instant of the
# hostile act, so they are planned when both facts are known and freeze the watcher's
# Operations stream and the retreating Fleet's home Colony at that instant.


def encounter_owner(encounter_id):
    return f"frontier:{encounter_id}"


def operations_stream(session, universe_id, empire_id):
    state = session.get(EmpireExploration, empire_id)
    if state is None or state.universe_id != universe_id:
        raise TimelineError("Operations stream missing")
    return state.stream_id


def covers(period, t):
    """Open-ended covering rule (C04): active strictly before t, not ended before t."""
    return period.started_at < t and (period.ended_at is None or period.ended_at >= t)


def fenced_streams(session, encounter):
    """Streams frozen by one retreat, in a stable sorted order (also the lock order)."""
    from app.fleet.models import Fleet

    watcher = operations_stream(session, encounter.universe_id, encounter.watcher_empire_id)
    fleet = session.get(Fleet, encounter.watch_fleet_id)
    colony = session.get(ColonyTimeline, fleet.home_colony_id)
    return sorted({watcher, colony.stream_id}, key=str)


def add_fences(session, encounter):
    at = encounter.encounter_at
    for stream_id in fenced_streams(session, encounter):
        # FOR KEY SHARE waits for a transaction holding that stream (its cursor may be moving),
        # then reads the committed cursor; it is held to commit, so the stream cannot be locked
        # for an advance before the fence exists.
        cursor = session.scalar(
            select(EventStream.cursor_at)
            .where(EventStream.id == stream_id)
            .with_for_update(read=True, key_share=True)
        )
        if cursor is None or cursor > at:
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
    query = select(FrontierEncounter).where(FrontierEncounter.state.in_(UNRESOLVED))
    if period is not None:
        # Open end (C04): an entry at exactly `at` still saw the period.
        query = query.where(
            FrontierEncounter.period_id == period.id, FrontierEncounter.encounter_at > at
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
    """Retreat trigger (FC6, C03): the passage is an ATTACK force entering its target system, or
    a 0-hop ATTACK launched inside it (`local`); its bound defender is returned (internal truth,
    never projected). None otherwise."""
    from app.combat.models import CombatEngagement
    from app.fleet.models import FleetMission

    mission = session.get(FleetMission, passage.mission_id)
    if mission is None or mission.kind != "ATTACK" or passage.system_id != mission.destination_id:
        return None
    if passage.direction == LOCAL:
        if passage.entered_at != mission.started_at:
            return None
    elif passage.direction != OUTBOUND or passage.entered_at != mission.travel_arrival_at:
        return None
    engagement = session.scalar(
        select(CombatEngagement).where(
            CombatEngagement.mission_id == mission.id, CombatEngagement.state == "pending"
        )
    )
    return engagement.defender_empire_id if engagement is not None else None


def create_retreat(session, passage, period):
    if period.protocol != FRIENDLY_PROTOCOL or period.empire_id == passage.empire_id:
        return None
    if not covers(period, passage.entered_at):
        return None
    if hostile_arrival(session, passage) != period.empire_id:
        return None
    existing = session.scalar(
        select(FrontierEncounter).where(
            FrontierEncounter.mission_id == passage.mission_id,
            FrontierEncounter.sequence == passage.sequence,
            FrontierEncounter.watch_fleet_id == period.fleet_id,
            FrontierEncounter.kind == RETREAT,
        )
    )
    if existing is not None:
        return existing
    row = FrontierEncounter(
        universe_id=passage.universe_id,
        kind=RETREAT,
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


def plan_for_mission(session, rules, mission):
    """After an ATTACK launch (the Combat engagement exists, the defender's Operations stream is
    already held FOR KEY SHARE by its battle fence): friendly retreats of the defender's Fleets
    whose FRIENDLY_CONTACT period is open in the target system. A protocol set later plans its
    own retreats (plan_for_period); the shared stream lock serialises both, whatever the order."""
    if not enabled(rules) or mission.kind != "ATTACK":
        return []
    created = []
    for passage in session.scalars(
        select(FleetPassage)
        .where(
            FleetPassage.mission_id == mission.id,
            FleetPassage.cancelled_at.is_(None),
            FleetPassage.system_id == mission.destination_id,
        )
        .order_by(FleetPassage.sequence)
    ):
        if hostile_arrival(session, passage) is None:
            continue
        for period in session.scalars(
            select(FleetProtocolPeriod)
            .where(
                FleetProtocolPeriod.universe_id == passage.universe_id,
                FleetProtocolPeriod.system_id == passage.system_id,
                FleetProtocolPeriod.empire_id != passage.empire_id,
                FleetProtocolPeriod.ended_at.is_(None),
                FleetProtocolPeriod.started_at < passage.entered_at,
                FleetProtocolPeriod.protocol == FRIENDLY_PROTOCOL,
            )
            .order_by(FleetProtocolPeriod.fleet_id)
        ):
            try:
                row = create_retreat(session, passage, period)
            except TimelineError:
                # Only a 0-hop attack can meet this: the defender's stream moved past the launch
                # instant while we waited for it. Refused as a whole; a retry gets a new instant.
                raise FrontierError("Defender timeline moved; retry", "fleet_busy") from None
            if row is not None:
                created.append(row)
    return created


def plan_for_period(session, period):
    """After a FRIENDLY_CONTACT command: retreats from hostile entries already decided, strictly
    after it (own Empire's streams only)."""
    if period is None or period.protocol != FRIENDLY_PROTOCOL:
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
        row = create_retreat(session, passage, period)
        if row is not None:
            created.append(row)
    return created


def candidate_empires(session, passage):
    """Every other Empire that may hold a protocol period covering this entry: owners of a Fleet
    in the system, or of a mission still heading to it (active) or back to it (returning).

    Complete from committed data once the entry is due: a period needs a Fleet stationed in the
    system, and a Fleet only gets there by a mission committed when it was launched (hops last
    at least one catalogue hop) or by a split/merge of a Fleet already there. Over-inclusion only
    costs a lock."""
    from app.fleet.models import Fleet, FleetMission

    here = select(Fleet.empire_id).where(
        Fleet.universe_id == passage.universe_id, Fleet.system_id == passage.system_id
    )
    coming = select(FleetMission.empire_id).where(
        FleetMission.universe_id == passage.universe_id,
        or_(
            and_(
                FleetMission.status == "active",
                FleetMission.destination_id == passage.system_id,
            ),
            and_(
                FleetMission.status == "returning",
                FleetMission.origin_id == passage.system_id,
            ),
        ),
    )
    found = {*session.scalars(here), *session.scalars(coming)}
    found.discard(passage.empire_id)
    return sorted(found, key=str)


def guard_fleet_change(session, fleet, at):
    """A stationed Fleet whose AMBUSH/INTERCEPTION period covers an unresolved foreign entry keeps
    its composition until that entry is resolved (the engagement sees the Fleet as it was at the
    entry, whatever the worker delay). Raised as `combat_pending`, like any due Combat."""
    if fleet.system_id is None:
        return
    p, period = FleetPassage, FleetProtocolPeriod
    blocking = session.scalar(
        select(p.mission_id)
        .join(
            period,
            and_(
                period.fleet_id == fleet.id,
                period.system_id == p.system_id,
                period.protocol.in_(AGGRESSIVE),
                period.started_at < p.entered_at,
                or_(period.ended_at.is_(None), period.ended_at >= p.entered_at),
            ),
        )
        .where(
            p.universe_id == fleet.universe_id,
            p.system_id == fleet.system_id,
            p.empire_id != fleet.empire_id,
            p.state.in_(UNRESOLVED),
            p.entered_at <= utc(at),
        )
        .limit(1)
    )
    if blocking is not None:
        raise FrontierError("A frontier encounter must be resolved first", "combat_pending")


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
    """Protocol periods of other Empires covering the logical entry instant, in stable order.
    Called by the entry resolution, which holds every candidate watcher's stream lock."""
    t = passage.entered_at
    return list(
        session.scalars(
            select(FleetProtocolPeriod)
            .where(
                FleetProtocolPeriod.universe_id == passage.universe_id,
                FleetProtocolPeriod.system_id == passage.system_id,
                FleetProtocolPeriod.empire_id != passage.empire_id,
                FleetProtocolPeriod.started_at < t,
                or_(FleetProtocolPeriod.ended_at.is_(None), FleetProtocolPeriod.ended_at >= t),
            )
            .order_by(FleetProtocolPeriod.fleet_id)
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
