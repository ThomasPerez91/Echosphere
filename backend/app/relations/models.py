"""Relations persistence (migration 0013). Per Universe, FK-scoped, no derived undated state.

- `relation_contacts`: oriented knowledge "observer knows observed", durable, never forgotten.
- `relation_pairs`: one row per unordered pair (low < high): the open proposal, refusal
  cooldowns and the last hostile fact of each side. The relation state itself is derived from
  `relation_pacts` at a logical date, never stored as a mutable flag.
- `relation_pacts`: immutable acceptance; a notice only sets `ends_at` once, so the coverage of
  any already elapsed instant never changes.
- `relation_events`: immutable journal and idempotency ledger of negotiation commands.
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


class RelationContact(Base):
    __tablename__ = "relation_contacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["observer_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_relation_contacts_observer",
        ),
        ForeignKeyConstraint(
            ["observed_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_relation_contacts_observed",
        ),
        ForeignKeyConstraint(
            ["presence_planet_id", "universe_id"],
            ["planets.id", "planets.universe_id"],
            name="fk_relation_contacts_presence_planet",
        ),
        CheckConstraint("observer_empire_id <> observed_empire_id", name="sides"),
        CheckConstraint(
            "first_source IN ('combat','presence','diplomacy','frontier')", name="source"
        ),
        CheckConstraint("last_seen_at >= first_seen_at", name="seen"),
        CheckConstraint(
            "(presence_planet_id IS NULL) = (presence_observed_at IS NULL)", name="presence"
        ),
        Index("ix_relation_contacts_observed", "observed_empire_id"),
    )

    observer_empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    observed_empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    first_source: Mapped[str] = mapped_column(String(12))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    presence_planet_id: Mapped[UUID | None] = mapped_column(Uuid)
    presence_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RelationPair(Base):
    __tablename__ = "relation_pairs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["low_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_relation_pairs_low",
        ),
        ForeignKeyConstraint(
            ["high_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_relation_pairs_high",
        ),
        UniqueConstraint(
            "low_empire_id", "high_empire_id", "universe_id", name="uq_relation_pairs_scope"
        ),
        CheckConstraint("low_empire_id < high_empire_id", name="order"),
        CheckConstraint(
            "(proposal_by_empire_id IS NULL) = (proposed_at IS NULL) "
            "AND (proposed_at IS NULL) = (proposal_expires_at IS NULL)",
            name="proposal",
        ),
        CheckConstraint(
            "proposal_by_empire_id IS NULL "
            "OR proposal_by_empire_id IN (low_empire_id, high_empire_id)",
            name="proposal_side",
        ),
        CheckConstraint(
            "proposal_expires_at IS NULL OR proposal_expires_at > proposed_at",
            name="proposal_window",
        ),
        Index("ix_relation_pairs_high", "high_empire_id"),
    )

    low_empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    high_empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    proposal_by_empire_id: Mapped[UUID | None] = mapped_column(Uuid)
    proposed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposal_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    low_cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    high_cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_hostile_by_low_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_hostile_by_high_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RelationPact(Record, Base):
    __tablename__ = "relation_pacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["low_empire_id", "high_empire_id", "universe_id"],
            [
                "relation_pairs.low_empire_id",
                "relation_pairs.high_empire_id",
                "relation_pairs.universe_id",
            ],
            name="fk_relation_pacts_pair",
        ),
        CheckConstraint(
            "proposed_by_empire_id IN (low_empire_id, high_empire_id) "
            "AND accepted_by_empire_id IN (low_empire_id, high_empire_id) "
            "AND proposed_by_empire_id <> accepted_by_empire_id",
            name="signatories",
        ),
        CheckConstraint(
            "(notice_by_empire_id IS NULL) = (notice_at IS NULL) "
            "AND (notice_at IS NULL) = (ends_at IS NULL)",
            name="notice",
        ),
        CheckConstraint(
            "notice_by_empire_id IS NULL "
            "OR notice_by_empire_id IN (low_empire_id, high_empire_id)",
            name="notice_side",
        ),
        CheckConstraint(
            "notice_at IS NULL OR (notice_at >= accepted_at AND ends_at > notice_at)",
            name="notice_window",
        ),
        # At most one pact without notice per pair; overlap is refused by the service lock.
        Index(
            "uq_relation_pacts_open",
            "low_empire_id",
            "high_empire_id",
            unique=True,
            postgresql_where=text("ends_at IS NULL"),
        ),
        Index("ix_relation_pacts_pair", "low_empire_id", "high_empire_id", "accepted_at"),
    )

    universe_id: Mapped[UUID] = mapped_column(Uuid)
    low_empire_id: Mapped[UUID] = mapped_column(Uuid)
    high_empire_id: Mapped[UUID] = mapped_column(Uuid)
    proposed_by_empire_id: Mapped[UUID] = mapped_column(Uuid)
    accepted_by_empire_id: Mapped[UUID] = mapped_column(Uuid)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notice_by_empire_id: Mapped[UUID | None] = mapped_column(Uuid)
    notice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RelationEvent(Record, Base):
    __tablename__ = "relation_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["low_empire_id", "high_empire_id", "universe_id"],
            [
                "relation_pairs.low_empire_id",
                "relation_pairs.high_empire_id",
                "relation_pairs.universe_id",
            ],
            name="fk_relation_events_pair",
        ),
        ForeignKeyConstraint(
            ["actor_empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_relation_events_actor",
        ),
        UniqueConstraint("actor_empire_id", "idempotency_key", name="uq_relation_events_intent"),
        CheckConstraint(
            "kind IN ('proposed','withdrawn','accepted','refused','notice')", name="kind"
        ),
        CheckConstraint("actor_empire_id IN (low_empire_id, high_empire_id)", name="actor"),
        CheckConstraint("length(idempotency_key) BETWEEN 1 AND 160", name="key"),
        Index("ix_relation_events_pair", "low_empire_id", "high_empire_id", "at"),
    )

    universe_id: Mapped[UUID] = mapped_column(Uuid)
    low_empire_id: Mapped[UUID] = mapped_column(Uuid)
    high_empire_id: Mapped[UUID] = mapped_column(Uuid)
    actor_empire_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(12))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    details: Mapped[dict] = mapped_column(JSONB)
