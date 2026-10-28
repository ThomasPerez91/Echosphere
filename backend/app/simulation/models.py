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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models import Base, Record


class EventStream(Record, Base):
    __tablename__ = "event_streams"
    __table_args__ = (
        UniqueConstraint("id", "universe_id", name="uq_streams_id_universe"),
        CheckConstraint("next_sequence > 0", name="positive_sequence"),
        Index("ix_streams_universe_id", "universe_id"),
    )

    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"))
    cursor_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_sequence: Mapped[int] = mapped_column(BigInteger, default=1)


class ColonyTimeline(Base):
    __tablename__ = "colony_timelines"
    __table_args__ = (
        UniqueConstraint("stream_id", name="uq_colony_timelines_stream"),
        ForeignKeyConstraint(
            ["colony_id", "universe_id"],
            ["colonies.id", "colonies.universe_id"],
            name="fk_colony_timeline_colony_universe",
        ),
        ForeignKeyConstraint(
            ["stream_id", "universe_id"],
            ["event_streams.id", "event_streams.universe_id"],
            name="fk_colony_timeline_stream_universe",
        ),
    )

    colony_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    stream_id: Mapped[UUID] = mapped_column(Uuid)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResourceBalance(Base):
    __tablename__ = "resource_balances"
    __table_args__ = (
        CheckConstraint("resource IN ('alloys', 'flux', 'data')", name="resource_kind"),
        CheckConstraint("stock >= 0 AND rate_per_hour >= 0", name="nonnegative_amounts"),
        CheckConstraint("remainder >= 0 AND remainder < 3600000000", name="valid_remainder"),
        CheckConstraint(
            "capacity IS NULL OR (capacity >= 0 AND stock <= capacity)", name="capacity"
        ),
    )

    colony_id: Mapped[UUID] = mapped_column(
        ForeignKey("colony_timelines.colony_id"), primary_key=True
    )
    resource: Mapped[str] = mapped_column(String(8), primary_key=True)
    stock: Mapped[int] = mapped_column(BigInteger)
    rate_per_hour: Mapped[int] = mapped_column(BigInteger)
    remainder: Mapped[int] = mapped_column(BigInteger)
    capacity: Mapped[int | None] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduledEvent(Record, Base):
    __tablename__ = "scheduled_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["stream_id", "universe_id"],
            ["event_streams.id", "event_streams.universe_id"],
            name="fk_events_stream_universe",
        ),
        UniqueConstraint("stream_id", "sequence", name="uq_events_stream_sequence"),
        UniqueConstraint("stream_id", "idempotency_key", name="uq_events_stream_key"),
        CheckConstraint("status IN ('pending', 'completed', 'blocked')", name="status"),
        CheckConstraint("sequence > 0 AND attempts >= 0", name="counters"),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completion"),
        Index("ix_events_stream_order", "stream_id", "due_at", "sequence"),
        Index("ix_events_pending", "status", "due_at", "next_attempt_at"),
    )

    stream_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(32))
