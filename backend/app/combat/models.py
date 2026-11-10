"""Durable Combat engagements and per-side reports; the defender stays internal until resolved."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models import Base, Record


class CombatEngagement(Record, Base):
    __tablename__ = "combat_engagements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "attacker_empire_id", "universe_id"],
            ["fleet_missions.id", "fleet_missions.empire_id", "fleet_missions.universe_id"],
        ),
        ForeignKeyConstraint(
            ["defender_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_combat_engagements_defender",
        ),
        ForeignKeyConstraint(
            ["target_planet_id", "target_system_id", "universe_id"],
            ["planets.id", "planets.system_id", "planets.universe_id"],
        ),
        ForeignKeyConstraint(
            ["target_opportunity_id", "universe_id"],
            ["galaxy_opportunities.id", "galaxy_opportunities.universe_id"],
            name="fk_combat_engagements_opportunity",
        ),
        # v0.12 (EXP-02c): a planet or a deposit, exactly one.
        CheckConstraint(
            "(target_planet_id IS NULL) <> (target_opportunity_id IS NULL)", name="target"
        ),
        UniqueConstraint("mission_id", name="uq_combat_engagements_mission"),
        UniqueConstraint("id", "universe_id", name="uq_combat_engagements_scope"),
        CheckConstraint("state IN ('pending','resolved','cancelled','blocked')", name="state"),
        CheckConstraint(
            "travel_arrival_at >= started_at AND battle_at >= travel_arrival_at "
            "AND battle_at > started_at",
            name="timeline",
        ),
        CheckConstraint(
            "defender_empire_id IS NULL OR defender_empire_id <> attacker_empire_id",
            name="sides",
        ),
        CheckConstraint(
            "(state = 'resolved') = (processed_at IS NOT NULL AND result IS NOT NULL "
            "AND snapshot IS NOT NULL)",
            name="resolution",
        ),
        CheckConstraint("attempts >= 0", name="attempts"),
        # Rank order (battle_at, started_at, id) of the engagements still awaiting a worker.
        Index(
            "ix_combat_engagements_due",
            "battle_at",
            "started_at",
            "id",
            postgresql_where=text("state = 'pending'"),
        ),
        Index(
            "ix_combat_engagements_system",
            "universe_id",
            "target_system_id",
            postgresql_where=text("state IN ('pending','blocked')"),
        ),
        Index("ix_combat_engagements_defender", "defender_empire_id", "battle_at"),
    )
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    mission_id: Mapped[UUID] = mapped_column(Uuid)
    attacker_empire_id: Mapped[UUID] = mapped_column(Uuid)
    # Internal binding at launch; never projected to the attacker before the battle.
    defender_empire_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_planet_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_opportunity_id: Mapped[UUID | None] = mapped_column(Uuid)
    target_system_id: Mapped[UUID] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    travel_arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    battle_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(12))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(32))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict | None] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CombatReport(Base):
    """One dated observation per side, written only by the resolution."""

    __tablename__ = "combat_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "universe_id"],
            ["combat_engagements.id", "combat_engagements.universe_id"],
        ),
        ForeignKeyConstraint(["empire_id", "universe_id"], ["empires.id", "empires.universe_id"]),
        CheckConstraint("role IN ('attacker','defender')", name="role"),
        CheckConstraint("processed_at >= battle_at", name="processing"),
        Index("ix_combat_reports_empire", "empire_id", "battle_at"),
    )
    engagement_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    role: Mapped[str] = mapped_column(String(12))
    battle_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict] = mapped_column(JSONB)
