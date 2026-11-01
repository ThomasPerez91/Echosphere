"""Durable AI identity and decisions; no Account, membership, session or gameplay inventory."""

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


class AIController(Record, Base):
    __tablename__ = "ai_controllers"
    __table_args__ = (
        ForeignKeyConstraint(["empire_id", "universe_id"], ["empires.id", "empires.universe_id"]),
        UniqueConstraint("empire_id"),
        UniqueConstraint("id", "empire_id", "universe_id", name="uq_ai_controller_scope"),
        CheckConstraint("state IN ('enabled','paused','blocked')", name="state"),
        CheckConstraint("profile IN ('economic_cautious','expansionist')", name="profile"),
        CheckConstraint("sequence > 0 AND attempts >= 0", name="counters"),
        CheckConstraint("next_decision_at > started_at", name="deadline"),
        Index("ix_ai_controllers_due", "state", "next_decision_at"),
    )
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    profile: Mapped[str] = mapped_column(String(32))
    policy_version: Mapped[str] = mapped_column(String(64))
    policy_digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(12))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_decision_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sequence: Mapped[int] = mapped_column(BigInteger, default=1)
    memory: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(default=0)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(32))


class AIDecision(Base):
    __tablename__ = "ai_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["controller_id", "empire_id", "universe_id"],
            ["ai_controllers.id", "ai_controllers.empire_id", "ai_controllers.universe_id"],
        ),
        CheckConstraint("sequence > 0", name="sequence"),
        CheckConstraint("outcome IN ('wait','accepted','refusal')", name="outcome"),
    )
    controller_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    sequence: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(12))
    observation: Mapped[dict] = mapped_column(JSONB)
    trace: Mapped[dict] = mapped_column(JSONB)


class AIBootstrap(Base):
    __tablename__ = "ai_bootstraps"
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
