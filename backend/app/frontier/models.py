"""Frontier persistence (migration 0014, ruleset v0.9 Universes only).

`fleet_mission_passages`: every system a moving Fleet enters, at its logical instant, written
when the movement is decided (launch, recall, return after battle) from the pure transit rules.
Immutable facts, except that an outbound entry the Fleet never reaches (recalled before it) is
marked `cancelled_at` instead of being deleted. Only non-cancelled rows ever happened or will.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models import Base


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
        CheckConstraint("direction IN ('outbound','return')", name="direction"),
        CheckConstraint(
            "cancelled_at IS NULL OR (direction = 'outbound' AND cancelled_at < entered_at)",
            name="cancellation",
        ),
        # Who entered a system and when: the future detection query (B03).
        Index(
            "ix_fleet_mission_passages_system",
            "universe_id",
            "system_id",
            "entered_at",
            postgresql_where=text("cancelled_at IS NULL"),
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
