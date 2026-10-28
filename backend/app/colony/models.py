from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
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


class UniverseEconomy(Base):
    __tablename__ = "universe_economies"
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"), primary_key=True)
    ruleset_version: Mapped[str] = mapped_column(String(32))
    ruleset_data: Mapped[dict] = mapped_column(JSONB)


class ColonyEconomy(Base):
    __tablename__ = "colony_economies"
    __table_args__ = (
        UniqueConstraint("colony_id", "universe_id", name="uq_colony_economies_scope"),
        ForeignKeyConstraint(
            ["colony_id", "universe_id"],
            ["colonies.id", "colonies.universe_id"],
            name="fk_economies_colony_universe",
        ),
        CheckConstraint("next_order_sequence > 0", name="positive_sequence"),
    )
    colony_id: Mapped[UUID] = mapped_column(
        ForeignKey("colony_timelines.colony_id"), primary_key=True
    )
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universe_economies.universe_id"))
    next_order_sequence: Mapped[int] = mapped_column(BigInteger, default=1)


class ColonyInfrastructure(Record, Base):
    __tablename__ = "colony_infrastructures"
    __table_args__ = (
        ForeignKeyConstraint(
            ["colony_id", "universe_id"],
            ["colony_economies.colony_id", "colony_economies.universe_id"],
            name="fk_infrastructures_economy_scope",
        ),
        UniqueConstraint("colony_id", "sector_index", name="uq_infrastructures_sector"),
        CheckConstraint("sector_index > 0 AND level >= 1", name="sector_level"),
    )
    colony_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    sector_index: Mapped[int]
    infrastructure_type: Mapped[str] = mapped_column(String(64))
    level: Mapped[int] = mapped_column(BigInteger)


class ConstructionOrder(Record, Base):
    __tablename__ = "construction_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["colony_id", "universe_id"],
            ["colony_economies.colony_id", "colony_economies.universe_id"],
            name="fk_orders_economy_scope",
        ),
        UniqueConstraint("colony_id", "sequence", name="uq_orders_sequence"),
        UniqueConstraint("colony_id", "idempotency_key", name="uq_orders_key"),
        CheckConstraint("status IN ('queued', 'active', 'completed', 'cancelled')", name="status"),
        CheckConstraint("sector_index > 0 AND target_level > 0 AND sequence > 0", name="positive"),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completion"),
        CheckConstraint("(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancellation"),
        CheckConstraint("(started_at IS NULL) = (due_at IS NULL)", name="schedule"),
        CheckConstraint("status != 'active' OR started_at IS NOT NULL", name="active_start"),
        Index(
            "ix_orders_one_active",
            "colony_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_orders_queue", "colony_id", "status", "sequence"),
    )
    colony_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    infrastructure_type: Mapped[str] = mapped_column(String(64))
    sector_index: Mapped[int]
    target_level: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    applied_bonus_bps: Mapped[int | None] = mapped_column(BigInteger)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded: Mapped[dict | None] = mapped_column(JSONB)
