"""Frontier persistence (migration 0014, ruleset v0.9 Universes only).

`fleet_mission_passages`: every system a moving Fleet enters, at its logical instant, written
when the movement is decided (launch, recall, return after battle) from the pure transit rules.
Immutable facts, except their resolution state: `pending` until the frontier orchestrator
resolves the entry (`resolved`), `cancelled` if the Fleet never reaches it (recalled or destroyed
before), `blocked` for the operator after repeated failures. A `local` row (sequence 0) anchors a
0-hop ATTACK inside its target system (C03): resolved at once, never an entry.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models import Base, Record


class FleetPassage(Base):
    __tablename__ = "fleet_mission_passages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "empire_id", "universe_id"],
            ["fleet_missions.id", "fleet_missions.empire_id", "fleet_missions.universe_id"],
            name="fk_fleet_mission_passages_mission",
        ),
        ForeignKeyConstraint(
            ["system_id", "universe_id"],
            ["galaxy_systems.system_id", "galaxy_systems.universe_id"],
            name="fk_fleet_mission_passages_system",
        ),
        CheckConstraint("sequence >= 0", name="sequence"),
        CheckConstraint("direction IN ('outbound','return','local')", name="direction"),
        CheckConstraint(
            "cancelled_at IS NULL OR cancelled_at < entered_at",
            name="cancellation",
        ),
        CheckConstraint(
            "state IN ('pending','resolved','cancelled','blocked')", name="state"
        ),
        CheckConstraint("(state = 'resolved') = (resolved_at IS NOT NULL)", name="resolution"),
        CheckConstraint("(state = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancelled"),
        CheckConstraint(
            "direction <> 'local' OR (sequence = 0 AND state = 'resolved')", name="local"
        ),
        CheckConstraint("attempts >= 0", name="attempts"),
        # Who entered a system and when: the future detection query (B03).
        Index(
            "ix_fleet_mission_passages_system",
            "universe_id",
            "system_id",
            "entered_at",
            postgresql_where=text("cancelled_at IS NULL"),
        ),
        # Due entries in rank order (frontier orchestrator).
        Index(
            "ix_fleet_mission_passages_due",
            "entered_at",
            "mission_id",
            "sequence",
            postgresql_where=text("state = 'pending'"),
        ),
    )

    mission_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sequence: Mapped[int] = mapped_column(primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    system_id: Mapped[UUID] = mapped_column(Uuid)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    direction: Mapped[str] = mapped_column(String(8))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(10))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(32))


class FleetProtocolPeriod(Record, Base):
    """Dated history of a stationed Fleet's protocol: what was active at any logical instant.

    Opened by the protocol command, closed (`ended_at`) by a change, a departure, a merge or a
    destruction. An entry at t is evaluated against the period covering it
    (started_at < t <= ended_at, C04), so a protocol set at or after an entry, or a Fleet gone
    before it, never detects retroactively, and a change at t never alters what t saw."""

    __tablename__ = "fleet_protocol_periods"
    __table_args__ = (
        ForeignKeyConstraint(
            ["fleet_id", "empire_id", "universe_id"],
            ["fleets.id", "fleets.empire_id", "fleets.universe_id"],
            name="fk_fleet_protocol_periods_fleet",
        ),
        ForeignKeyConstraint(
            ["system_id", "universe_id"],
            ["galaxy_systems.system_id", "galaxy_systems.universe_id"],
            name="fk_fleet_protocol_periods_system",
        ),
        CheckConstraint(
            "protocol IN ('SURVEILLANCE','AMBUSH','INTERCEPTION','FRIENDLY_CONTACT')",
            name="protocol",
        ),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="period"),
        Index(
            "uq_fleet_protocol_periods_open",
            "fleet_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index("ix_fleet_protocol_periods_system", "universe_id", "system_id", "started_at"),
    )

    fleet_id: Mapped[UUID] = mapped_column(Uuid)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    system_id: Mapped[UUID] = mapped_column(Uuid)
    protocol: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FrontierDetection(Record, Base):
    """One side of an encounter between a passage and a protocol-holding stationed Fleet.

    Detection levels are all 0 (D1, Q58 open): equal levels, so each encounter is mutual and
    yields two rows, one per observer (`watch`: the stationed Fleet's Empire, `transit`: the
    moving Fleet's Empire). `observed_empire_id` is internal truth, projected only when
    `identified` (already a contact of the observer at `detected_at`, or a FRIENDLY_CONTACT
    introduction). No composition, cargo, origin, destination, route or direction is kept."""

    __tablename__ = "frontier_detections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "sequence"],
            ["fleet_mission_passages.mission_id", "fleet_mission_passages.sequence"],
            name="fk_frontier_detections_passage",
        ),
        ForeignKeyConstraint(
            ["watch_fleet_id"], ["fleets.id"], name="fk_frontier_detections_watch_fleet"
        ),
        ForeignKeyConstraint(
            ["observer_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_frontier_detections_observer",
        ),
        ForeignKeyConstraint(
            ["observed_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_frontier_detections_observed",
        ),
        UniqueConstraint(
            "mission_id", "sequence", "watch_fleet_id", "role", name="uq_frontier_detections"
        ),
        CheckConstraint("role IN ('watch','transit')", name="role"),
        CheckConstraint("observer_empire_id <> observed_empire_id", name="sides"),
        Index("ix_frontier_detections_observer", "observer_empire_id", "detected_at"),
    )

    universe_id: Mapped[UUID] = mapped_column(Uuid)
    mission_id: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column()
    watch_fleet_id: Mapped[UUID] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(String(8))
    observer_empire_id: Mapped[UUID] = mapped_column(Uuid)
    observed_empire_id: Mapped[UUID] = mapped_column(Uuid)
    system_id: Mapped[UUID] = mapped_column(Uuid)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    identified: Mapped[bool] = mapped_column()
    friendly: Mapped[bool] = mapped_column()


class FrontierEncounter(Record, Base):
    """B05/B06: an automatic frontier reaction to one real passage, resolved outside handlers.

    `engagement` (AMBUSH, INTERCEPTION): a meeting of two Fleets physically in the same system at
    the logical entry instant (D5: no 24 h delay, never a planetary attack). Both Operations
    streams are fenced just before `encounter_at` (state strictly before the entry, so a mover's
    arrival at that instant cannot settle it first) until the resolution.
    `retreat` (FRIENDLY_CONTACT, D7): the stationed Fleet leaves when a hostile force enters its
    system. The watcher's Operations stream and home Colony are fenced at `encounter_at`
    (inclusive) so the move is paid at that exact logical instant, whatever the worker delay.
    Created only by decisions taken before the instant (launch, recall, protocol command), or by an
    orchestrator decision whose involved streams have not passed it (otherwise a TimelineError)."""

    __tablename__ = "frontier_encounters"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "sequence"],
            ["fleet_mission_passages.mission_id", "fleet_mission_passages.sequence"],
            name="fk_frontier_encounters_passage",
        ),
        ForeignKeyConstraint(
            ["period_id"], ["fleet_protocol_periods.id"], name="fk_frontier_encounters_period"
        ),
        ForeignKeyConstraint(
            ["watch_fleet_id"], ["fleets.id"], name="fk_frontier_encounters_watch_fleet"
        ),
        ForeignKeyConstraint(
            ["watcher_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_frontier_encounters_watcher",
        ),
        ForeignKeyConstraint(
            ["mover_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_frontier_encounters_mover",
        ),
        UniqueConstraint(
            "mission_id", "sequence", "watch_fleet_id", "kind", name="uq_frontier_encounters"
        ),
        CheckConstraint("kind IN ('engagement','retreat')", name="kind"),
        CheckConstraint(
            "(kind = 'engagement' AND protocol IN ('AMBUSH','INTERCEPTION')) "
            "OR (kind = 'retreat' AND protocol = 'FRIENDLY_CONTACT')",
            name="protocol",
        ),
        CheckConstraint("state IN ('pending','resolved','cancelled','blocked')", name="state"),
        CheckConstraint("watcher_empire_id <> mover_empire_id", name="sides"),
        CheckConstraint(
            "(state = 'resolved') = (processed_at IS NOT NULL AND outcome IS NOT NULL)",
            name="resolution",
        ),
        CheckConstraint("(state = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancellation"),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index(
            "ix_frontier_encounters_due",
            "encounter_at",
            "id",
            postgresql_where=text("state = 'pending'"),
        ),
        Index("ix_frontier_encounters_watcher", "watcher_empire_id", "encounter_at"),
        Index("ix_frontier_encounters_mover", "mover_empire_id", "encounter_at"),
    )

    universe_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(12))
    mission_id: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column()
    period_id: Mapped[UUID] = mapped_column(Uuid)
    watch_fleet_id: Mapped[UUID] = mapped_column(Uuid)
    protocol: Mapped[str] = mapped_column(String(20))
    watcher_empire_id: Mapped[UUID] = mapped_column(Uuid)
    mover_empire_id: Mapped[UUID] = mapped_column(Uuid)
    system_id: Mapped[UUID] = mapped_column(Uuid)
    encounter_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(12))
    attempts: Mapped[int] = mapped_column(default=0)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(32))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(24))
    result: Mapped[dict | None] = mapped_column(JSONB)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
