"""Frontier entries and reactions resolved outside TimelineEngine handlers (13B), run by the
Combat worker process of the same Game image.

Entry resolution (C01/C02), one entry per transaction, rank (entered_at, mission_id, sequence):
1. lock, sorted by UUID, the mover's Operations stream and those of every Empire that may hold a
   protocol in the system (`frontier.candidate_empires`), then the passage row; streams → row →
   relation pair → contacts, as Combat. A protocol command holds its own stream lock: it either
   commits before (seen) or waits after (its instant is then >= the entry: never covering it);
2. refuse while a better-ranked unresolved entry shares the system or one of these Empires;
3. settle every locked stream through `entered_at - 1 µs` (the mover is fenced exactly there);
4. detections for every covering period (D1–D3), then AMBUSH/INTERCEPTION engagements in Fleet
   order on the state strictly before the entry (D4–D6), release the mover's fence, atomically.
Friendly retreats (D7) stay planned reactions, resolved after their entry, at its instant.
A crash before commit changes nothing; after commit nothing is ever applied twice.
"""

from datetime import timedelta

from sqlalchemy import literal, or_, select, text, tuple_
from sqlalchemy.orm import aliased

from app.colony.service import ColonyError, rules_for
from app.combat.models import CombatEngagement
from app.combat.resolver import resolve, spec_from_rules
from app.fleet import service as fleet_service
from app.fleet.models import Fleet, FleetMission, FleetReport
from app.frontier import service as frontier
from app.frontier.encounter import (
    AGGRESSIVE,
    ENGAGEMENT,
    engagement_outcome,
    known_enemy,
    subtract,
)
from app.frontier.models import FleetPassage, FleetProtocolPeriod, FrontierEncounter
from app.persistence.models import Colony
from app.relations import service as relations
from app.relations.models import RelationContact
from app.simulation.clock import utc
from app.simulation.models import EventStream, ScheduledEvent
from app.simulation.scheduler import TimelineError, lock_stream
from app.simulation.service import TimeEngine

CONTENTION = {"55P03", "57014"}
NOT_HOSTILE = ("target_unavailable", "voided_by_pact")
PATH_FAILURES = {"destination_unreachable", "destination_unmapped", "system_not_found"}


def contention(error):
    return getattr(getattr(error, "orig", None), "sqlstate", None) in CONTENTION


def military(stacks, classes):
    return {c: n for c, n in sorted(stacks.items()) if c in classes and n}


def rank_columns(e):
    return tuple_(e.encounter_at, e.kind, e.mission_id, e.sequence, e.watch_fleet_id)


def passage_rank(p):
    return tuple_(p.entered_at, p.mission_id, p.sequence)


def passage_blocker(session, passage, empires):
    """A better-ranked unresolved entry in the same system or moved by one of these Empires: its
    engagements could change the Fleets, contacts or hostile acts this entry reads."""
    p = FleetPassage
    mine = tuple_(
        literal(passage.entered_at), literal(passage.mission_id), literal(passage.sequence)
    )
    return session.scalar(
        select(p.mission_id)
        .where(
            p.universe_id == passage.universe_id,
            p.state.in_(frontier.UNRESOLVED),
            passage_rank(p) < mine,
            or_(p.system_id == passage.system_id, p.empire_id.in_(empires)),
        )
        .limit(1)
    )


def blocker(session, encounter):
    """A retreat waits for its own entry, then for any better-ranked unresolved reaction sharing
    one of the Empires."""
    entry = session.get(FleetPassage, (encounter.mission_id, encounter.sequence))
    if entry.state in frontier.UNRESOLVED:
        return entry.mission_id
    e = FrontierEncounter
    mine = tuple_(
        literal(encounter.encounter_at),
        literal(encounter.kind),
        literal(encounter.mission_id),
        literal(encounter.sequence),
        literal(encounter.watch_fleet_id),
    )
    empires = [encounter.watcher_empire_id, encounter.mover_empire_id]
    return session.scalar(
        select(e.id)
        .where(
            e.universe_id == encounter.universe_id,
            e.state.in_(["pending", "blocked"]),
            e.id != encounter.id,
            rank_columns(e) < mine,
            or_(e.watcher_empire_id.in_(empires), e.mover_empire_id.in_(empires)),
        )
        .limit(1)
    )


covers = frontier.covers


def hostile_acts(session, universe_id, actor, victim, t, window):
    """Resolved hostile acts of `actor` against `victim` in (t - window, t]: fought battles of an
    ATTACK (never target_unavailable nor voided_by_pact) and fought frontier engagements."""
    low = t - window
    battles = session.scalars(
        select(CombatEngagement.battle_at).where(
            CombatEngagement.universe_id == universe_id,
            CombatEngagement.attacker_empire_id == actor,
            CombatEngagement.defender_empire_id == victim,
            CombatEngagement.state == "resolved",
            CombatEngagement.battle_at > low,
            CombatEngagement.battle_at <= t,
            CombatEngagement.result["outcome"].astext.not_in(NOT_HOSTILE),
        )
    ).all()
    meetings = session.scalars(
        select(FrontierEncounter.encounter_at).where(
            FrontierEncounter.universe_id == universe_id,
            FrontierEncounter.kind == ENGAGEMENT,
            FrontierEncounter.watcher_empire_id == actor,
            FrontierEncounter.mover_empire_id == victim,
            FrontierEncounter.state == "resolved",
            FrontierEncounter.outcome == "fought",
            FrontierEncounter.encounter_at > low,
            FrontierEncounter.encounter_at <= t,
        )
    ).all()
    return [*battles, *meetings]


def contact_since(session, observer, observed):
    return session.scalar(
        select(RelationContact.first_seen_at).where(
            RelationContact.observer_empire_id == observer,
            RelationContact.observed_empire_id == observed,
        )
    )


def side(combat, role):
    return {k: combat[k][role] for k in ("initial", "losses", "survivors")}


def cancel_movement_events(session, stream_id, mission, at):
    for key in (f"fleet-arrival:{mission.id}", f"fleet-return:{mission.id}"):
        event = session.scalar(
            select(ScheduledEvent).where(
                ScheduledEvent.stream_id == stream_id, ScheduledEvent.idempotency_key == key
            )
        )
        if event is not None and event.status == "pending":
            event.status, event.completed_at, event.error_code = "completed", utc(at), "cancelled"


def destroy_mover(session, encounter, mission, fleet, t, processed_at):
    """D6: a mover left without any unit is destroyed at t; its mission ends for good, later
    entries, arrival/return and any pending planetary battle never happen."""
    stream_id = frontier.operations_stream(session, mission.universe_id, mission.empire_id)
    fleet.status, fleet.system_id, fleet.active_mission_id = "DESTROYED", None, None
    mission.status, mission.completed_at = "completed", t
    session.flush()
    cancel_movement_events(session, stream_id, mission, t)
    frontier.cancel_unreached(session, mission, stream_id, t)
    if mission.kind == "ATTACK":
        engagement = session.scalar(
            select(CombatEngagement).where(CombatEngagement.mission_id == mission.id)
        )
        if engagement is not None and engagement.state == "pending":
            from app.combat.service import cancel_engagement

            cancel_engagement(session, mission, t)
    session.add(
        FleetReport(
            mission_id=mission.id,
            empire_id=mission.empire_id,
            universe_id=mission.universe_id,
            observed_at=t,
            processed_at=utc(processed_at),
            result={
                "kind": "INTERCEPTED",
                "destroyed": True,
                "system_id": str(encounter.system_id),
                "encounter_id": str(encounter.id),
            },
        )
    )


def finish(session, encounter, outcome, result, processed_at):
    encounter.state, encounter.outcome = "resolved", outcome
    encounter.result, encounter.processed_at = result, utc(processed_at)
    encounter.error_code = encounter.retry_at = None
    session.flush()


def resolve_engagement(session, encounter, processed_at):
    rules = rules_for(session, encounter.universe_id)
    k, t = rules.combat, encounter.encounter_at
    passage = session.get(FleetPassage, (encounter.mission_id, encounter.sequence))
    period = session.get(FleetProtocolPeriod, encounter.period_id, populate_existing=True)
    mission = session.get(FleetMission, encounter.mission_id, populate_existing=True)
    mover = session.get(Fleet, mission.fleet_id, populate_existing=True)
    watch = session.get(Fleet, encounter.watch_fleet_id, populate_existing=True)
    if not (
        k is not None
        and rules.frontier is not None
        and passage.cancelled_at is None
        and covers(period, t)
        and watch.status == "STATIONED"
        and watch.system_id == encounter.system_id
        and mover.status == "MOVING"
        and mover.active_mission_id == mission.id
    ):
        finish(session, encounter, "void", {"outcome": "void"}, processed_at)
        return "void"
    # The meeting is a detection on both sides first (identity only if already known, D3).
    frontier.detect(session, passage, period)
    watcher, mover_empire = encounter.watcher_empire_id, encounter.mover_empire_id
    pair = pact = None
    if rules.relations is not None:
        pair = relations.ensure_pair(session, encounter.universe_id, watcher, mover_empire)
        pact = relations.covering_pact(session, pair.low_empire_id, pair.high_empire_id, t)
    enemy = encounter.protocol == "AMBUSH" and known_enemy(
        contact_since(session, watcher, mover_empire),
        hostile_acts(
            session, encounter.universe_id, mover_empire, watcher, t, rules.frontier.ambush_window
        ),
        t,
        rules.frontier.ambush_window,
    )
    watcher_units = fleet_service.stacks_of(session, watch.id)
    mover_units = fleet_service.stacks_of(session, mover.id)
    watcher_mil, mover_mil = military(watcher_units, k.classes), military(mover_units, k.classes)
    reason = engagement_outcome(
        pact=pact is not None,
        protocol=encounter.protocol,
        enemy=enemy,
        watcher_military=watcher_mil,
        mover_military=mover_mil,
    )
    if reason is not None:
        # Nothing fought: no loss, no hostile act, no report (it would reveal the force, D3).
        finish(session, encounter, reason, {"outcome": reason}, processed_at)
        return reason
    spec = spec_from_rules(k, watcher_mil, mover_mil)
    combat = resolve(spec)
    lost_watch = {c: n for c, n in combat["losses"]["attacker"].items() if n}
    lost_mover = {c: n for c, n in combat["losses"]["defender"].items() if n}
    # Military losses only (Q02): civilians aboard never fight and are never destroyed.
    left_watch = subtract(watcher_units, lost_watch)
    left_mover = subtract(mover_units, lost_mover)
    watch_destroyed = watch.kind == "TASK" and not any(left_watch.values())
    mover_destroyed = not any(left_mover.values())
    result = {
        "outcome": "fought",
        "battle": combat["outcome"],
        "protocol": encounter.protocol,
        "spec": spec,
        "rounds": len(combat["rounds"]),
        "watcher": {**side(combat, "attacker"), "losses": lost_watch,
                    "destroyed": watch_destroyed},
        "mover": {**side(combat, "defender"), "losses": lost_mover,
                  "destroyed": mover_destroyed},
    }
    # Resolved before any cascade, so the watcher's own later reactions are cancelled, not this.
    finish(session, encounter, "fought", result, processed_at)
    fleet_service.set_stacks(session, watch.id, left_watch)
    if watch_destroyed:
        frontier.end_protocol(session, watch, t)
        watch.status, watch.system_id = "DESTROYED", None
    fleet_service.set_stacks(session, mover.id, left_mover)
    if mover_destroyed:
        destroy_mover(session, encounter, mission, mover, t, processed_at)
    # A fought meeting is the watcher's hostile act; the report names each side to the other.
    if pair is not None:
        relations.record_hostile(pair, watcher, t)
        for observer, observed in ((watcher, mover_empire), (mover_empire, watcher)):
            relations.record_contact(
                session, encounter.universe_id, observer, observed, "combat", t
            )
    session.flush()
    return "fought"


def resolve_passage(session, passage, processed_at):
    """One entry at t: every covering period detects (mutual, D1–D3); then each AMBUSH or
    INTERCEPTION period, in Fleet order, meets the mover on the state strictly before t."""
    found = frontier.watchers(session, passage)
    for period in found:
        frontier.detect(session, passage, period)
    outcomes = []
    for period in found:
        if period.protocol not in AGGRESSIVE:
            continue
        encounter = FrontierEncounter(
            universe_id=passage.universe_id,
            kind=ENGAGEMENT,
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
        session.add(encounter)
        session.flush()
        outcomes.append(resolve_engagement(session, encounter, processed_at))
    passage.state, passage.resolved_at = "resolved", utc(processed_at)
    passage.retry_at = passage.error_code = None
    frontier.release_passage(session, passage.mission_id, passage.sequence, processed_at)
    session.flush()
    return {"detections": len(found), "engagements": outcomes}


def retreat_destination(session, fleet):
    """D7 order: previous system of the last real route of this Fleet, else its home system."""
    current = fleet.system_id
    last = session.scalar(
        select(FleetPassage)
        .join(FleetMission, FleetMission.id == FleetPassage.mission_id)
        .where(
            FleetMission.fleet_id == fleet.id,
            FleetPassage.cancelled_at.is_(None),
            FleetPassage.system_id == current,
        )
        .order_by(FleetPassage.entered_at.desc())
        .limit(1)
    )
    previous = None
    if last is not None:
        prior = session.scalar(
            select(FleetPassage.system_id)
            .where(
                FleetPassage.mission_id == last.mission_id,
                FleetPassage.cancelled_at.is_(None),
                FleetPassage.entered_at < last.entered_at,
            )
            .order_by(FleetPassage.entered_at.desc())
            .limit(1)
        )
        previous = prior or session.get(FleetMission, last.mission_id).origin_id
    home = fleet_service.colony_system(session, session.get(Colony, fleet.home_colony_id))
    return (previous if previous != current else None), (home if home != current else None)


def resolve_retreat(session, engine, encounter, processed_at):
    rules = rules_for(session, encounter.universe_id)
    t = encounter.encounter_at
    passage = session.get(FleetPassage, (encounter.mission_id, encounter.sequence))
    period = session.get(FleetProtocolPeriod, encounter.period_id, populate_existing=True)
    watch = session.get(Fleet, encounter.watch_fleet_id, populate_existing=True)
    if not (
        rules.frontier is not None
        and passage.cancelled_at is None
        and covers(period, t)
        and watch.status == "STATIONED"
        and watch.system_id == encounter.system_id
    ):
        finish(session, encounter, "void", {"outcome": "void"}, processed_at)
        return "void"
    frontier.detect(session, passage, period)  # the friendly introduction happened (B04)
    impossible = {"outcome": "retreat_impossible"}
    finish(session, encounter, "retreat_impossible", impossible, processed_at)
    previous, home = retreat_destination(session, watch)
    units = fleet_service.stacks_of(session, watch.id)
    attempts = [("DEPLOY", previous)] if previous else []
    attempts += [("RETURN", home)] if home else []
    for kind, destination in attempts:
        try:
            with session.begin_nested():
                mission = fleet_service.launch(
                    session,
                    engine,
                    encounter.universe_id,
                    encounter.watcher_empire_id,
                    watch.id,
                    kind,
                    destination,
                    units,
                    None,
                    key=f"frontier-retreat:{encounter.id}",
                    at=t,
                )
        except ColonyError as error:
            if error.code in PATH_FAILURES:
                continue  # not accessible: next destination in D7 order
            result = {"outcome": "retreat_failed", "reason": error.code, "kind": kind}
            finish(session, encounter, "retreat_failed", result, processed_at)
            return "retreat_failed"
        result = {
            "outcome": "retreated",
            "kind": kind,
            "destination_id": str(destination),
            "mission_id": str(mission.id),
        }
        finish(session, encounter, "retreated", result, processed_at)
        return "retreated"
    return "retreat_impossible"


class FrontierOrchestrator:
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
            raise ValueError("Invalid technical frontier limits")
        self.factory, self.clock = factory, clock
        self.engine = TimeEngine(factory, clock)
        self.lock_ms, self.statement_ms = lock_ms, statement_ms
        self.retry_seconds, self.max_attempts, self.scan = retry_seconds, max_attempts, scan
        self.pages = pages

    def due_passages(self, after=None):
        """One page of due entries in rank order, never one behind a better-ranked unresolved
        entry of the same system or mover (a local blockage starves nobody else)."""
        now = utc(self.clock.now())
        p, better = FleetPassage, aliased(FleetPassage)
        waiting = (
            select(better.mission_id)
            .where(
                better.universe_id == p.universe_id,
                better.state.in_(frontier.UNRESOLVED),
                passage_rank(better) < passage_rank(p),
                or_(better.system_id == p.system_id, better.empire_id == p.empire_id),
            )
            .exists()
        )
        query = select(p.mission_id, p.sequence, p.entered_at).where(
            p.state == "pending",
            p.entered_at <= now,
            or_(p.retry_at.is_(None), p.retry_at <= now),
            ~waiting,
        )
        if after is not None:
            query = query.where(passage_rank(p) > tuple_(*(literal(v) for v in after)))
        query = query.order_by(p.entered_at, p.mission_id, p.sequence).limit(self.scan)
        with self.factory() as session:
            return list(session.execute(query))

    def next_passage(self, after_resolve=None, raise_errors=False):
        after = None
        for _ in range(self.pages):
            page = self.due_passages(after)
            for candidate in page:
                key = (candidate.mission_id, candidate.sequence)
                outcome = self.attempt_passage(key, after_resolve, raise_errors)
                if outcome is not None:
                    return outcome
            if len(page) < self.scan:
                return None
            last = page[-1]
            after = (last.entered_at, last.mission_id, last.sequence)
        return None

    def settle(self, session, stream_id, universe_id, until):
        cursor = session.scalar(select(EventStream.cursor_at).where(EventStream.id == stream_id))
        if cursor >= until:
            # Already past: every change before `until` is committed and nothing can be dated
            # earlier any more (fences are never inserted behind a cursor).
            return True
        return self.catch_up(session, stream_id, universe_id, until)

    def attempt_passage(self, key, after_resolve, raise_errors):
        claimed = None
        try:
            with self.factory.begin() as session:
                session.execute(text(f"SET LOCAL lock_timeout = '{self.lock_ms}ms'"))
                session.execute(text(f"SET LOCAL statement_timeout = '{self.statement_ms}ms'"))
                peek = session.get(FleetPassage, key)
                if peek is None or peek.state != "pending":
                    return None
                universe_id = peek.universe_id
                empires = frontier.candidate_empires(session, peek)
                streams = sorted(
                    {
                        frontier.operations_stream(session, universe_id, e)
                        for e in (peek.empire_id, *empires)
                    },
                    key=str,
                )
                for stream_id in streams:
                    lock_stream(session, stream_id, universe_id)
                passage = session.scalar(
                    select(FleetPassage)
                    .where(
                        FleetPassage.mission_id == key[0], FleetPassage.sequence == key[1]
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                now = utc(self.clock.now())
                if (
                    passage.state != "pending"
                    or passage.entered_at > now
                    or (passage.retry_at is not None and passage.retry_at > now)
                    # Defensive: the candidate set must not have grown while we were locking.
                    or not set(frontier.candidate_empires(session, passage)) <= set(empires)
                    or passage_blocker(session, passage, [passage.empire_id, *empires])
                    is not None
                ):
                    return None
                until = passage.entered_at - timedelta(microseconds=1)
                for stream_id in streams:
                    if not self.settle(session, stream_id, universe_id, until):
                        return None  # an earlier fence or a blocked event: never a partial state
                claimed = key
                outcome = resolve_passage(session, passage, now)
                if after_resolve is not None:
                    after_resolve(session)
                return {
                    "passage": f"{key[0]}:{key[1]}",
                    "outcome": "resolved",
                    **outcome,
                }
        except Exception as error:
            if claimed is None and contention(error):
                return None
            if raise_errors or claimed is None:
                raise
            with self.factory.begin() as session:
                row = session.get(FleetPassage, claimed, with_for_update=True)
                if row is None or row.state != "pending":
                    return {"passage": f"{claimed[0]}:{claimed[1]}", "outcome": "superseded"}
                row.attempts += 1
                row.error_code = "resolution_failed"
                row.retry_at = utc(self.clock.now()) + timedelta(seconds=self.retry_seconds)
                if row.attempts >= self.max_attempts:
                    row.state = "blocked"
                return {
                    "passage": f"{claimed[0]}:{claimed[1]}",
                    "outcome": "blocked" if row.state == "blocked" else "retry",
                }

    def due(self, encounter_id=None, after=None):
        """One page of due reactions in rank order, never one behind a better-ranked unresolved
        reaction of the same Empires (a local blockage starves nobody else)."""
        now = utc(self.clock.now())
        e, better = FrontierEncounter, aliased(FrontierEncounter)
        waiting = (
            select(better.id)
            .where(
                better.universe_id == e.universe_id,
                better.state.in_(["pending", "blocked"]),
                better.id != e.id,
                rank_columns(better) < rank_columns(e),
                or_(
                    better.watcher_empire_id == e.watcher_empire_id,
                    better.watcher_empire_id == e.mover_empire_id,
                    better.mover_empire_id == e.watcher_empire_id,
                    better.mover_empire_id == e.mover_empire_id,
                ),
            )
            .exists()
        )
        query = select(e.id, e.encounter_at, e.kind, e.mission_id, e.sequence, e.watch_fleet_id)
        query = query.where(
            e.state == "pending",
            e.encounter_at <= now,
            or_(e.retry_at.is_(None), e.retry_at <= now),
            ~waiting,
        )
        if encounter_id is not None:
            query = query.where(e.id == encounter_id)
        if after is not None:
            query = query.where(rank_columns(e) > tuple_(*(literal(v) for v in after)))
        query = query.order_by(
            e.encounter_at, e.kind, e.mission_id, e.sequence, e.watch_fleet_id
        ).limit(self.scan)
        with self.factory() as session:
            return list(session.execute(query))

    def process_next(self, *, encounter_id=None, after_resolve=None, raise_errors=False):
        """Entries first, then retreats; fences and blockers keep the global logical order
        whichever is picked first. after_resolve is an internal crash-injection test seam."""
        if encounter_id is None:
            outcome = self.next_passage(after_resolve, raise_errors)
            if outcome is not None:
                return outcome
        return self.next_reaction(encounter_id, after_resolve, raise_errors)

    def next_reaction(self, encounter_id=None, after_resolve=None, raise_errors=False):
        after = None
        for _ in range(self.pages):
            page = self.due(encounter_id, after)
            for candidate in page:
                outcome = self.attempt(candidate.id, after_resolve, raise_errors)
                if outcome is not None:
                    return outcome
            if len(page) < self.scan:
                return None
            last = page[-1]
            after = (
                last.encounter_at, last.kind, last.mission_id, last.sequence, last.watch_fleet_id
            )
        return None

    def catch_up(self, session, stream_id, universe_id, until):
        while True:
            progress = self.engine.catch_up_stream(
                session, stream_id, universe_id, until, limit=1000
            )
            if progress.complete:
                return True
            if progress.fenced or progress.processed < 1000:
                return False

    def attempt(self, encounter_id, after_resolve, raise_errors):
        claimed = None
        try:
            with self.factory.begin() as session:
                session.execute(text(f"SET LOCAL lock_timeout = '{self.lock_ms}ms'"))
                session.execute(text(f"SET LOCAL statement_timeout = '{self.statement_ms}ms'"))
                peek = session.get(FrontierEncounter, encounter_id)
                if peek is None or peek.state != "pending":
                    return None
                streams = frontier.fenced_streams(session, peek)
                for stream_id in streams:
                    lock_stream(session, stream_id, peek.universe_id)
                encounter = session.scalar(
                    select(FrontierEncounter)
                    .where(FrontierEncounter.id == encounter_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                now = utc(self.clock.now())
                if (
                    encounter.state != "pending"
                    or encounter.encounter_at > now
                    or (encounter.retry_at is not None and encounter.retry_at > now)
                    or blocker(session, encounter) is not None
                ):
                    return None
                until = encounter.encounter_at
                for stream_id in streams:
                    if not self.catch_up(session, stream_id, encounter.universe_id, until):
                        return None  # an earlier fence or a blocked event: never a partial state
                claimed = encounter.id
                outcome = resolve_retreat(session, self.engine, encounter, now)
                frontier.release(session, encounter, now)
                if after_resolve is not None:
                    after_resolve(session)
                return {"encounter_id": str(encounter.id), "outcome": outcome}
        except Exception as error:
            if claimed is None and contention(error):
                return None
            if raise_errors or claimed is None:
                raise
            with self.factory.begin() as session:
                row = session.get(FrontierEncounter, claimed, with_for_update=True)
                if row is None or row.state != "pending":
                    return {"encounter_id": str(claimed), "outcome": "superseded"}
                row.attempts += 1
                row.error_code = "resolution_failed"
                row.retry_at = utc(self.clock.now()) + timedelta(seconds=self.retry_seconds)
                if row.attempts >= self.max_attempts:
                    row.state = "blocked"
                return {
                    "encounter_id": str(claimed),
                    "outcome": "blocked" if row.state == "blocked" else "retry",
                }


def retry_passage(session, mission_id, sequence, now):
    """Operator: requeue a repaired blocked entry; the mover's fence never moved meanwhile."""
    row = session.get(FleetPassage, (mission_id, sequence), with_for_update=True)
    if row is None or row.state != "blocked":
        raise TimelineError("Only a blocked entry can be retried")
    row.state, row.attempts, row.error_code, row.retry_at = "pending", 0, None, utc(now)
    session.flush()


def retry_blocked(session, encounter_id, now):
    """Operator: requeue a repaired blocked reaction; its fences never moved meanwhile."""
    row = session.get(FrontierEncounter, encounter_id, with_for_update=True)
    if row is None or row.state != "blocked":
        raise TimelineError("Only a blocked reaction can be retried")
    row.state, row.attempts, row.error_code, row.retry_at = "pending", 0, None, utc(now)
    session.flush()
