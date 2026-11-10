"""Durable Combat resolution outside TimeEngine handlers (same Game image, `app.combat.worker`).

One engagement per transaction, in rank order (battle_at, started_at, id):
1. lock the involved Operations streams sorted by UUID, then the engagement row;
2. refuse while a better-ranked engagement on the same system or Empire is unresolved;
3. catch every stream up exactly to its fence at battle_at (inclusive), nothing later;
4. snapshot the military forces, resolve purely, apply losses, write reports, schedule the
   attacker's return and release the fences — all atomically. A crash before commit changes
   nothing; after commit the engagement is resolved and never fought again.

v0.8 (Q18): after the engagement, the pair row of both Empires is locked (streams → engagement
→ pair, never the reverse). A pact covering `battle_at` (accepted_at <= battle_at < ends_at)
voids the battle (`voided_by_pact`): no shot, no loss, no composition reported, the attacker
returns, fuel is not refunded. A fought battle records the attacker's dated hostile act and the
two oriented contacts. The decision depends on logical dates only, never on worker delay.
"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import literal, or_, select, text, tuple_
from sqlalchemy.orm import aliased

from app.colony.service import rules_for
from app.combat.models import CombatEngagement, CombatReport
from app.combat.resolver import allocate_losses, resolve, spec_from_rules
from app.combat.service import release_fences
from app.fleet import service as fleet_service
from app.fleet.models import Fleet, FleetMission, FleetReport
from app.frontier import service as frontier
from app.galaxy import service as galaxy
from app.relations import service as relations
from app.simulation.clock import utc
from app.simulation.scheduler import TimelineError, lock_stream, schedule
from app.simulation.service import TimeEngine


def frontier_blocker(session, engagement):
    """C04 (13B): at equal or earlier instants, frontier first. An unresolved entry into the
    target system at or before battle_at (it sees the state strictly before its own instant) and
    an unresolved friendly retreat of the defender at or before battle_at (the watcher leaves at
    the hostile act) are both resolved before the battle. No row exists before v0.9."""
    from app.frontier.models import FleetPassage, FrontierEncounter

    entry = session.scalar(
        select(FleetPassage.mission_id)
        .where(
            FleetPassage.universe_id == engagement.universe_id,
            FleetPassage.system_id == engagement.target_system_id,
            FleetPassage.state.in_(["pending", "blocked"]),
            FleetPassage.entered_at <= engagement.battle_at,
        )
        .limit(1)
    )
    if entry is not None or engagement.defender_empire_id is None:
        return entry
    return session.scalar(
        select(FrontierEncounter.id)
        .where(
            FrontierEncounter.universe_id == engagement.universe_id,
            FrontierEncounter.watcher_empire_id == engagement.defender_empire_id,
            FrontierEncounter.state.in_(["pending", "blocked"]),
            FrontierEncounter.encounter_at <= engagement.battle_at,
        )
        .limit(1)
    )


def blocker(session, engagement):
    """A better-ranked engagement still awaiting resolution on the same system or Empire, or an
    earlier (or simultaneous) frontier entry/retreat that must come first."""
    frontier_first = frontier_blocker(session, engagement)
    if frontier_first is not None:
        return frontier_first
    rank = tuple_(
        literal(engagement.battle_at), literal(engagement.started_at), literal(engagement.id)
    )
    empires = [e for e in (engagement.attacker_empire_id, engagement.defender_empire_id) if e]
    return session.scalar(
        select(CombatEngagement.id)
        .where(
            CombatEngagement.universe_id == engagement.universe_id,
            CombatEngagement.state.in_(["pending", "blocked"]),
            CombatEngagement.id != engagement.id,
            tuple_(CombatEngagement.battle_at, CombatEngagement.started_at, CombatEngagement.id)
            < rank,
            or_(
                CombatEngagement.target_system_id == engagement.target_system_id,
                CombatEngagement.attacker_empire_id.in_(empires),
                CombatEngagement.defender_empire_id.in_(empires),
            ),
        )
        .limit(1)
    )


# lock_not_available (lock_timeout) and query_canceled (statement_timeout): contention on one
# candidate's streams, never a database outage.
CONTENTION = {"55P03", "57014"}


def contention(error):
    return getattr(getattr(error, "orig", None), "sqlstate", None) in CONTENTION


def military(stacks, classes):
    return {c: n for c, n in sorted(stacks.items()) if c in classes and n}


def side(combat, role):
    return {k: combat[k][role] for k in ("initial", "losses", "survivors")}


def report(engagement, empire_id, role, processed_at, result):
    return CombatReport(
        engagement_id=engagement.id,
        empire_id=empire_id,
        universe_id=engagement.universe_id,
        role=role,
        battle_at=engagement.battle_at,
        processed_at=processed_at,
        result=result,
    )


def resolve_engagement(session, engagement, processed_at):
    rules = rules_for(session, engagement.universe_id)
    k = rules.combat
    mission = session.get(FleetMission, engagement.mission_id, populate_existing=True)
    fleet = session.get(Fleet, mission.fleet_id, populate_existing=True)
    if (
        k is None
        or mission.kind != "ATTACK"
        or mission.status != "active"
        or mission.due_at != engagement.battle_at
        or fleet.active_mission_id != mission.id
        or fleet.status != "MOVING"
    ):
        raise TimelineError("Inconsistent engagement")
    fleet_service.verify_mission_snapshot(session, mission)
    at = engagement.battle_at
    attacking = military(fleet_service.stacks_of(session, fleet.id), k.classes)
    defenders = {}
    if engagement.defender_empire_id is not None:
        # Every military unit of every STATIONED Fleet of the bound defender in the system.
        for row in session.scalars(
            select(Fleet)
            .where(
                Fleet.universe_id == engagement.universe_id,
                Fleet.empire_id == engagement.defender_empire_id,
                Fleet.status == "STATIONED",
                Fleet.system_id == engagement.target_system_id,
            )
            .order_by(Fleet.id)
        ):
            units = military(fleet_service.stacks_of(session, row.id), k.classes)
            if units:
                defenders[str(row.id)] = units
    operations = []
    if engagement.target_opportunity_id is not None and engagement.defender_empire_id is not None:
        # v0.12 (EXP-02c): the defender's extraction operations at work on the deposit at
        # battle_at; their escorts fight, the operation falls with them.
        operations = list(
            session.scalars(
                select(FleetMission)
                .where(
                    FleetMission.universe_id == engagement.universe_id,
                    FleetMission.empire_id == engagement.defender_empire_id,
                    FleetMission.kind == "EXTRACT",
                    FleetMission.status == "active",
                    FleetMission.target_opportunity_id == engagement.target_opportunity_id,
                    FleetMission.travel_arrival_at <= at,
                    FleetMission.due_at > at,
                )
                .order_by(FleetMission.fleet_id)
            )
        )
        for op in operations:
            units = military(fleet_service.stacks_of(session, op.fleet_id), k.classes)
            if units:
                defenders[str(op.fleet_id)] = units
    total = {c: sum(u.get(c, 0) for u in defenders.values()) for c in k.classes}
    spec = combat = pact = relation = None
    if rules.relations is not None and engagement.defender_empire_id is not None:
        relation = relations.ensure_pair(
            session,
            engagement.universe_id,
            engagement.attacker_empire_id,
            engagement.defender_empire_id,
        )
        pact = relations.covering_pact(
            session, relation.low_empire_id, relation.high_empire_id, at
        )
    if engagement.defender_empire_id is None:
        outcome = "target_unavailable"
        attacker_left = attacking
    elif pact is not None:
        # Q18 B7: a pact active at battle_at forbids the battle; nothing is fought or revealed.
        outcome = "voided_by_pact"
        attacker_left = attacking
    else:
        spec = spec_from_rules(k, attacking, total)
        combat = resolve(spec)
        outcome = combat["outcome"]
        attacker_left = military(combat["survivors"]["attacker"], k.classes)
    target = {
        "planet_id": str(engagement.target_planet_id) if engagement.target_planet_id else None,
        "system_id": str(engagement.target_system_id),
    }
    if engagement.target_opportunity_id is not None:
        target["opportunity_id"] = str(engagement.target_opportunity_id)
    engagement.snapshot = {
        "ruleset": rules.version,
        "combat_version": k.combat_version,
        "engagement_id": str(engagement.id),
        "battle_at": at.isoformat(),
        "target": target,
        "attacker": {
            "empire_id": str(engagement.attacker_empire_id),
            "fleet_id": str(fleet.id),
            "units": attacking,
        },
        "defender": {
            "empire_id": str(engagement.defender_empire_id)
            if engagement.defender_empire_id
            else None,
            "fleets": defenders,
        },
        "spec": spec,
    }
    allocation = allocate_losses(defenders, combat["losses"]["defender"]) if combat else {}
    # Defender losses: military units only; civilians and cargo are never touched.
    for fleet_id, lost in allocation.items():
        row = session.get(Fleet, UUID(fleet_id), populate_existing=True)
        stacks = fleet_service.stacks_of(session, row.id)
        left = {c: n - lost.get(c, 0) for c, n in stacks.items()}
        fleet_service.set_stacks(session, row.id, left)
        if row.kind == "TASK" and not any(left.values()):
            frontier.end_protocol(session, row, at)
            row.status, row.system_id = "DESTROYED", None
    destroyed = []
    if combat is not None and outcome in ("attacker_win", "unopposed"):
        # D5 amended (v0.12): an operation left without escort is destroyed with its hold.
        for op in operations:
            destroy_operation(session, rules, op, engagement, at, processed_at)
            destroyed.append(str(op.fleet_id))
    engagement.result = {"outcome": outcome, "combat": combat, "defender_losses": allocation}
    if engagement.target_opportunity_id is not None:
        engagement.result["operations"] = [str(op.fleet_id) for op in operations]
        engagement.result["destroyed_operations"] = destroyed
    engagement.state, engagement.processed_at = "resolved", utc(processed_at)
    engagement.error_code = engagement.retry_at = None
    base = {"outcome": outcome, "target": target}
    if pact is not None:
        # Dated reports on both sides, without any composition: the signatories already know
        # each other (a pact requires a contact), so naming the counterpart reveals nothing.
        for role, empire, opponent in (
            ("attacker", engagement.attacker_empire_id, engagement.defender_empire_id),
            ("defender", engagement.defender_empire_id, engagement.attacker_empire_id),
        ):
            session.add(
                report(
                    engagement,
                    empire,
                    role,
                    processed_at,
                    base | {"opponent_empire_id": str(opponent), "pact_id": str(pact.id)},
                )
            )
    elif combat is None:
        session.add(
            report(engagement, engagement.attacker_empire_id, "attacker", processed_at, base)
        )
    else:
        for role, empire, other, opponent in (
            ("attacker", engagement.attacker_empire_id, "defender", engagement.defender_empire_id),
            ("defender", engagement.defender_empire_id, "attacker", engagement.attacker_empire_id),
        ):
            session.add(
                report(
                    engagement,
                    empire,
                    role,
                    processed_at,
                    base
                    | {
                        "opponent_empire_id": str(opponent),
                        "own": side(combat, role),
                        "opponent": side(combat, other),
                        "rounds": combat["rounds"],
                    },
                )
            )
    if relation is not None and combat is not None:
        # Q18 B2/B4: a fought battle is the attacker's hostile act, dated at battle_at, and both
        # reports name the opponent: each side now knows the other (oriented, durable contacts).
        relations.record_hostile(relation, engagement.attacker_empire_id, at)
        for observer, observed in (
            (engagement.attacker_empire_id, engagement.defender_empire_id),
            (engagement.defender_empire_id, engagement.attacker_empire_id),
        ):
            relations.record_contact(
                session, engagement.universe_id, observer, observed, "combat", at
            )
    # Attacker: survivors return to the mission origin (already paid), never stay at the target.
    origin = UUID(mission.snapshot["origin_id"])
    fleet_service.set_stacks(session, fleet.id, attacker_left)
    closing = {"kind": "ATTACK", "engagement_id": str(engagement.id), "outcome": outcome}
    if not attacker_left:
        fleet.status, fleet.system_id, fleet.active_mission_id = "DESTROYED", None, None
        mission.status, mission.completed_at = "completed", at
        session.add(fleet_report(mission, at, processed_at, closing | {"destroyed": True}))
    elif mission.origin_id == mission.destination_id:
        session.add(
            fleet_report(mission, at, processed_at, closing | {"destination_id": str(origin)})
        )
        fleet_service.settle_fleet(session, mission, origin, at)
    else:
        mission.status = "returning"
        mission.return_at = at + (mission.travel_arrival_at - mission.started_at)
        session.flush()
        state = galaxy.state_for(session, mission.universe_id, mission.empire_id)
        # 13B (v0.9): the full way back from the target, entered system by system.
        frontier.record_way_back(
            session, rules, mission, state.stream_id, at, mission.travel_arrival_at
        )
        schedule(
            session,
            state.stream_id,
            mission.universe_id,
            key=f"fleet-return:{mission.id}",
            kind="FLEET_RETURN",
            due_at=mission.return_at,
            payload={"mission_id": str(mission.id)},
        )
        # Entries on the way back fence only the attacker's own stream (at or after battle_at,
        # where it stands): a late resolution never depends on another Empire's cursor.
    session.flush()
    release_fences(session, engagement, processed_at)
    return outcome


def destroy_operation(session, rules, mission, engagement, at, processed_at):
    """The extraction ends at battle_at: its claim closes (the credit is lost with the hold),
    its pending end is cancelled, the fleet and its ships are destroyed, the owner is told."""
    from app.fleet import extraction
    from app.simulation.models import ScheduledEvent

    extraction.close_claim(session, rules, mission, at)
    for event in session.scalars(
        select(ScheduledEvent).where(
            ScheduledEvent.idempotency_key == f"fleet-arrival:{mission.id}",
            ScheduledEvent.status == "pending",
        )
    ):
        event.status, event.completed_at, event.error_code = "completed", at, "destroyed"
    fleet = session.get(Fleet, mission.fleet_id, populate_existing=True)
    fleet_service.set_stacks(session, fleet.id, {})
    fleet_service.set_cargo(session, fleet.id, {})
    fleet.status, fleet.system_id, fleet.active_mission_id = "DESTROYED", None, None
    mission.status, mission.completed_at = "completed", at
    session.add(
        fleet_report(
            mission,
            at,
            processed_at,
            {
                "kind": "EXTRACT",
                "destroyed": True,
                "engagement_id": str(engagement.id),
                "opportunity_id": str(mission.target_opportunity_id),
            },
        )
    )
    session.flush()


def fleet_report(mission, observed_at, processed_at, result):
    return FleetReport(
        mission_id=mission.id,
        empire_id=mission.empire_id,
        universe_id=mission.universe_id,
        observed_at=observed_at,
        processed_at=utc(processed_at),
        result=result,
    )


class CombatOrchestrator:
    def __init__(
        self,
        factory,
        clock,
        *,
        lock_ms=5000,
        statement_ms=20000,
        retry_seconds=30,
        max_attempts=3,
        scan=20,
        pages=50,
    ):
        if not (
            1 <= lock_ms <= 60000
            and lock_ms <= statement_ms <= 120000
            and 1 <= retry_seconds <= 3600
            and 1 <= max_attempts <= 10
            and 1 <= scan <= 200
            and 1 <= pages <= 1000
        ):
            raise ValueError("Invalid technical Combat limits")
        self.factory, self.clock = factory, clock
        self.engine = TimeEngine(factory, clock)
        self.lock_ms, self.statement_ms = lock_ms, statement_ms
        self.retry_seconds, self.max_attempts, self.scan = retry_seconds, max_attempts, scan
        self.pages = pages

    def due(self, engagement_id=None, after=None):
        """One page of due engagements in rank order, never one waiting on a better-ranked
        unresolved engagement of its system or Empires (a local blockage starves nobody)."""
        now = utc(self.clock.now())
        e, better = CombatEngagement, aliased(CombatEngagement)
        waiting = (
            select(better.id)
            .where(
                better.universe_id == e.universe_id,
                better.state.in_(["pending", "blocked"]),
                better.id != e.id,
                tuple_(better.battle_at, better.started_at, better.id)
                < tuple_(e.battle_at, e.started_at, e.id),
                or_(
                    better.target_system_id == e.target_system_id,
                    better.attacker_empire_id == e.attacker_empire_id,
                    better.defender_empire_id == e.attacker_empire_id,
                    better.attacker_empire_id == e.defender_empire_id,
                    better.defender_empire_id == e.defender_empire_id,
                ),
            )
            .exists()
        )
        query = select(e.id, e.battle_at, e.started_at).where(
            e.state == "pending",
            e.battle_at <= now,
            or_(e.retry_at.is_(None), e.retry_at <= now),
            ~waiting,
        )
        if engagement_id is not None:
            query = query.where(e.id == engagement_id)
        if after is not None:
            query = query.where(
                tuple_(e.battle_at, e.started_at, e.id)
                > tuple_(literal(after[0]), literal(after[1]), literal(after[2]))
            )
        query = query.order_by(e.battle_at, e.started_at, e.id).limit(self.scan)
        with self.factory() as session:
            return list(session.execute(query))

    def process_next(self, *, engagement_id=None, after_resolve=None, raise_errors=False):
        """after_resolve is an internal crash-injection test seam, never a policy callback.

        Pages past candidates that cannot resolve now (blocked event, lock contention), so one
        stuck engagement never stops independent battles; bounded by `pages` per call."""
        after = None
        for _ in range(self.pages):
            page = self.due(engagement_id, after)
            for candidate in page:
                outcome = self.attempt(candidate.id, after_resolve, raise_errors)
                if outcome is not None:
                    return outcome
            if len(page) < self.scan:
                return None
            last = page[-1]
            after = (last.battle_at, last.started_at, last.id)
        return None

    def streams(self, session, engagement):
        empires = [engagement.attacker_empire_id, engagement.defender_empire_id]
        ids = {galaxy.state_for(session, engagement.universe_id, e).stream_id for e in empires if e}
        return sorted(ids, key=str)

    def catch_up(self, session, stream_id, universe_id, until):
        while True:
            progress = self.engine.catch_up_stream(
                session, stream_id, universe_id, until, limit=1000
            )
            if progress.complete:
                return True
            if progress.fenced or progress.processed < 1000:
                return False

    def attempt(self, engagement_id, after_resolve, raise_errors):
        claimed = None
        try:
            with self.factory.begin() as session:
                session.execute(text(f"SET LOCAL lock_timeout = '{self.lock_ms}ms'"))
                session.execute(text(f"SET LOCAL statement_timeout = '{self.statement_ms}ms'"))
                peek = session.get(CombatEngagement, engagement_id)
                if peek is None or peek.state != "pending":
                    return None
                streams = self.streams(session, peek)
                for stream_id in streams:
                    lock_stream(session, stream_id, peek.universe_id)
                engagement = session.scalar(
                    select(CombatEngagement)
                    .where(CombatEngagement.id == engagement_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                now = utc(self.clock.now())
                if (
                    engagement.state != "pending"
                    or engagement.battle_at > now
                    or (engagement.retry_at is not None and engagement.retry_at > now)
                    or blocker(session, engagement) is not None
                ):
                    return None
                for stream_id in streams:
                    if not self.catch_up(
                        session, stream_id, engagement.universe_id, engagement.battle_at
                    ):
                        # An earlier fence or a blocked event: never fight on a partial state.
                        return None
                claimed = engagement.id
                outcome = resolve_engagement(session, engagement, now)
                if after_resolve is not None:
                    after_resolve(session)
                return {"engagement_id": str(engagement.id), "outcome": outcome}
        except Exception as error:
            if claimed is None and contention(error):
                # Rolled back; another worker or command holds these streams: try the next one.
                return None
            if raise_errors or claimed is None:
                raise
            # Every loss, report, return and fence change rolled back; no payload logged.
            with self.factory.begin() as session:
                row = session.get(CombatEngagement, claimed, with_for_update=True)
                if row is None or row.state != "pending":
                    return {"engagement_id": str(claimed), "outcome": "superseded"}
                row.attempts += 1
                row.error_code = "resolution_failed"
                row.retry_at = utc(self.clock.now()) + timedelta(seconds=self.retry_seconds)
                if row.attempts >= self.max_attempts:
                    row.state = "blocked"
                return {
                    "engagement_id": str(claimed),
                    "outcome": "blocked" if row.state == "blocked" else "retry",
                }


def retry_blocked(session, engagement_id, now):
    """Operator: requeue a repaired blocked engagement; its fences never moved meanwhile."""
    row = session.get(CombatEngagement, engagement_id, with_for_update=True)
    if row is None or row.state != "blocked":
        raise TimelineError("Only a blocked engagement can be retried")
    row.state, row.attempts, row.error_code, row.retry_at = "pending", 0, None, utc(now)
    session.flush()
