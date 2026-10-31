from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
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


class EmpireResearch(Base):
    __tablename__ = "empire_research"
    __table_args__ = (
        ForeignKeyConstraint(["empire_id", "universe_id"], ["empires.id", "empires.universe_id"]),
        ForeignKeyConstraint(
            ["stream_id", "universe_id"], ["event_streams.id", "event_streams.universe_id"]
        ),
        UniqueConstraint("empire_id", "universe_id", name="uq_research_scope"),
        UniqueConstraint("stream_id", name="uq_research_stream"),
        CheckConstraint("next_sequence > 0", name="sequence"),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    stream_id: Mapped[UUID] = mapped_column(Uuid)
    next_sequence: Mapped[int] = mapped_column(BigInteger, default=1)


class ResearchOrder(Record, Base):
    __tablename__ = "research_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empire_research.empire_id", "empire_research.universe_id"],
        ),
        ForeignKeyConstraint(
            ["colony_id", "empire_id", "universe_id"],
            ["colonies.id", "colonies.empire_id", "colonies.universe_id"],
        ),
        UniqueConstraint("empire_id", "idempotency_key", name="uq_research_key"),
        UniqueConstraint("empire_id", "sequence", name="uq_research_sequence"),
        CheckConstraint("sequence > 0", name="sequence"),
        CheckConstraint(
            "status IN ('queued','active','blocked','completed','cancelled')", name="status"
        ),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completion"),
        CheckConstraint("(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancellation"),
        CheckConstraint("(started_at IS NULL) = (due_at IS NULL)", name="schedule"),
        CheckConstraint("status != 'active' OR started_at IS NOT NULL", name="active_start"),
        Index(
            "ix_research_active",
            "empire_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_research_waiting",
            "empire_id",
            unique=True,
            postgresql_where=text("status IN ('queued','blocked')"),
        ),
        Index(
            "ix_research_technology",
            "empire_id",
            "technology_id",
            unique=True,
            postgresql_where=text("status != 'cancelled'"),
        ),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    colony_id: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    technology_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    blocked_reason: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded: Mapped[dict | None] = mapped_column(JSONB)


class AcquiredTechnology(Base):
    __tablename__ = "acquired_technologies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empire_research.empire_id", "empire_research.universe_id"],
        ),
        CheckConstraint("reduction_bps >= 0 AND reduction_bps < 10000", name="reduction"),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    technology_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effect: Mapped[str] = mapped_column(String(32))
    reduction_bps: Mapped[int]
