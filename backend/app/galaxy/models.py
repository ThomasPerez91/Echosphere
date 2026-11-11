"""Typed Universe/Empire-scoped galaxy state. UNKNOWN is absence of knowledge."""

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


class UniverseGalaxy(Base):
    __tablename__ = "universe_galaxies"
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"), primary_key=True)
    generator_version: Mapped[str] = mapped_column(String(32))
    inputs: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    # v0.12 shaped galaxy: density layout for the map backdrop (None: lattice blob).
    layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class GalaxySystem(Base):
    __tablename__ = "galaxy_systems"
    __table_args__ = (
        ForeignKeyConstraint(
            ["system_id", "universe_id"], ["stellar_systems.id", "stellar_systems.universe_id"]
        ),
        UniqueConstraint("system_id", "universe_id", name="uq_galaxy_system_scope"),
        UniqueConstraint("universe_id", "ordinal", name="uq_galaxy_system_ordinal"),
        CheckConstraint("ordinal >= 0 AND x >= 0 AND y >= 0", name="coordinates"),
    )
    system_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universe_galaxies.universe_id"))
    ordinal: Mapped[int]
    x: Mapped[int]
    y: Mapped[int]


class GalaxyPlanet(Base):
    __tablename__ = "galaxy_planets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["planet_id", "system_id", "universe_id"],
            ["planets.id", "planets.system_id", "planets.universe_id"],
        ),
        ForeignKeyConstraint(
            ["system_id", "universe_id"], ["galaxy_systems.system_id", "galaxy_systems.universe_id"]
        ),
        UniqueConstraint("planet_id", "universe_id", name="uq_galaxy_planet_scope"),
        UniqueConstraint("planet_id", "system_id", "universe_id", name="uq_galaxy_planet_parent"),
        UniqueConstraint("system_id", "ordinal", name="uq_galaxy_planet_ordinal"),
        CheckConstraint("ordinal >= 0", name="ordinal"),
    )
    planet_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    system_id: Mapped[UUID] = mapped_column(Uuid)
    ordinal: Mapped[int]


class GalaxyRoute(Record, Base):
    __tablename__ = "galaxy_routes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["a_id", "universe_id"], ["galaxy_systems.system_id", "galaxy_systems.universe_id"]
        ),
        ForeignKeyConstraint(
            ["b_id", "universe_id"], ["galaxy_systems.system_id", "galaxy_systems.universe_id"]
        ),
        UniqueConstraint("id", "universe_id", name="uq_galaxy_route_scope"),
        UniqueConstraint("id", "a_id", "b_id", "universe_id", name="uq_galaxy_route_endpoints"),
        UniqueConstraint("a_id", "b_id", name="uq_galaxy_route_pair"),
        CheckConstraint("a_id < b_id", name="ordered_endpoints"),
    )
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    a_id: Mapped[UUID] = mapped_column(Uuid)
    b_id: Mapped[UUID] = mapped_column(Uuid)


class StartingSite(Base):
    __tablename__ = "galaxy_starting_sites"
    __table_args__ = (
        ForeignKeyConstraint(
            ["planet_id", "system_id", "universe_id"],
            ["galaxy_planets.planet_id", "galaxy_planets.system_id", "galaxy_planets.universe_id"],
        ),
    )
    planet_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    system_id: Mapped[UUID] = mapped_column(Uuid)


class EmpireExploration(Base):
    __tablename__ = "empire_exploration"
    __table_args__ = (
        ForeignKeyConstraint(["empire_id", "universe_id"], ["empires.id", "empires.universe_id"]),
        ForeignKeyConstraint(
            ["stream_id", "universe_id"], ["event_streams.id", "event_streams.universe_id"]
        ),
        UniqueConstraint("empire_id", "universe_id", name="uq_exploration_scope"),
        UniqueConstraint("stream_id", name="uq_exploration_stream"),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universe_galaxies.universe_id"))
    stream_id: Mapped[UUID] = mapped_column(Uuid)


class SystemKnowledge(Base):
    __tablename__ = "system_knowledge"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empire_exploration.empire_id", "empire_exploration.universe_id"],
        ),
        ForeignKeyConstraint(
            ["system_id", "universe_id"], ["galaxy_systems.system_id", "galaxy_systems.universe_id"]
        ),
        UniqueConstraint("empire_id", "system_id", "universe_id", name="uq_knowledge_scope"),
        CheckConstraint("state IN ('DETECTED','MAPPED','MONITORED')", name="state"),
        # DETECTED carries no structure; MAPPED/MONITORED keep it durably.
        CheckConstraint(
            "(state = 'DETECTED' AND mapped_at IS NULL AND known_name IS NULL "
            "AND known_x IS NULL AND known_y IS NULL AND last_seen_at IS NULL "
            "AND observation IS NULL) OR (state <> 'DETECTED' AND mapped_at IS NOT NULL "
            "AND known_name IS NOT NULL AND known_x IS NOT NULL AND known_y IS NOT NULL)",
            name="structure",
        ),
        CheckConstraint(
            "state <> 'MONITORED' OR (last_seen_at IS NOT NULL AND observation IS NOT NULL)",
            name="monitoring",
        ),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    system_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(12))
    approximate_x: Mapped[int]
    approximate_y: Mapped[int]
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mapped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observation: Mapped[dict | None] = mapped_column(JSONB)
    known_name: Mapped[str | None] = mapped_column(String(120))
    known_x: Mapped[int | None]
    known_y: Mapped[int | None]


class PlanetKnowledge(Base):
    __tablename__ = "planet_knowledge"
    __table_args__ = (
        ForeignKeyConstraint(
            ["planet_id", "system_id", "universe_id"],
            ["galaxy_planets.planet_id", "galaxy_planets.system_id", "galaxy_planets.universe_id"],
        ),
        ForeignKeyConstraint(
            ["empire_id", "system_id", "universe_id"],
            [
                "system_knowledge.empire_id",
                "system_knowledge.system_id",
                "system_knowledge.universe_id",
            ],
        ),
        CheckConstraint("sector_capacity > 0 AND orbital_capacity >= 0", name="capacities"),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    planet_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    system_id: Mapped[UUID] = mapped_column(Uuid)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    known_name: Mapped[str] = mapped_column(String(120))
    sector_capacity: Mapped[int]
    orbital_capacity: Mapped[int]


class RouteKnowledge(Base):
    __tablename__ = "route_knowledge"
    __table_args__ = (
        ForeignKeyConstraint(
            ["route_id", "a_id", "b_id", "universe_id"],
            [
                "galaxy_routes.id",
                "galaxy_routes.a_id",
                "galaxy_routes.b_id",
                "galaxy_routes.universe_id",
            ],
        ),
        *[
            ForeignKeyConstraint(
                ["empire_id", endpoint, "universe_id"],
                [
                    "system_knowledge.empire_id",
                    "system_knowledge.system_id",
                    "system_knowledge.universe_id",
                ],
                name=f"fk_route_knowledge_{endpoint}",
            )
            for endpoint in ("a_id", "b_id")
        ],
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    route_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    a_id: Mapped[UUID] = mapped_column(Uuid)
    b_id: Mapped[UUID] = mapped_column(Uuid)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExplorationMission(Record, Base):
    __tablename__ = "exploration_missions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empire_exploration.empire_id", "empire_exploration.universe_id"],
        ),
        ForeignKeyConstraint(
            ["colony_id", "empire_id", "universe_id"],
            ["colonies.id", "colonies.empire_id", "colonies.universe_id"],
        ),
        ForeignKeyConstraint(
            ["destination_id", "universe_id"],
            ["galaxy_systems.system_id", "galaxy_systems.universe_id"],
        ),
        UniqueConstraint("id", "empire_id", "universe_id", name="uq_exploration_mission_scope"),
        UniqueConstraint("empire_id", "idempotency_key", name="uq_exploration_key"),
        CheckConstraint("status IN ('active','completed')", name="status"),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completion"),
        CheckConstraint("due_at > started_at", name="deadline"),
        Index(
            "ix_exploration_active",
            "empire_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    colony_id: Mapped[UUID] = mapped_column(Uuid)
    destination_id: Mapped[UUID] = mapped_column(Uuid)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(12))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MissionLeg(Base):
    __tablename__ = "exploration_mission_legs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "empire_id", "universe_id"],
            [
                "exploration_missions.id",
                "exploration_missions.empire_id",
                "exploration_missions.universe_id",
            ],
        ),
        ForeignKeyConstraint(
            ["route_id", "universe_id"], ["galaxy_routes.id", "galaxy_routes.universe_id"]
        ),
        CheckConstraint("ordinal >= 0", name="ordinal"),
    )
    mission_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    route_id: Mapped[UUID] = mapped_column(Uuid)


class ExplorationReport(Base):
    __tablename__ = "exploration_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "empire_id", "universe_id"],
            [
                "exploration_missions.id",
                "exploration_missions.empire_id",
                "exploration_missions.universe_id",
            ],
        ),
        CheckConstraint("processed_at >= observed_at", name="processing"),
    )
    mission_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    discoveries: Mapped[dict] = mapped_column(JSONB)


DEPOSIT_SHAPE = (
    "(family = 'deposit' AND resource IN ('alloys','flux','data') AND reserve_total > 0 "
    "AND reserve_remaining >= 0 AND reserve_remaining <= reserve_total "
    "AND throughput_per_hour > 0 AND study_seconds IS NULL AND data_reward IS NULL) OR "
    "(family = 'curiosity' AND resource IS NULL AND reserve_total IS NULL "
    "AND reserve_remaining IS NULL AND throughput_per_hour IS NULL AND study_seconds > 0 "
    "AND data_reward > 0)"
)


class GalaxyOpportunity(Record, Base):
    """EXP-01 (v0.10): a deposit or a curiosity of a system, generated with the world
    (opportunities-v1). Immutable except the remaining reserve, debited by extraction (EXP-02)
    under this row lock; never a property of an Empire. Amounts in micro-units."""

    __tablename__ = "galaxy_opportunities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["system_id", "universe_id"], ["galaxy_systems.system_id", "galaxy_systems.universe_id"]
        ),
        UniqueConstraint("id", "universe_id", name="uq_galaxy_opportunity_scope"),
        UniqueConstraint("system_id", "ordinal", name="uq_galaxy_opportunity_ordinal"),
        CheckConstraint("ordinal >= 0", name="ordinal"),
        CheckConstraint("family IN ('deposit','curiosity')", name="family"),
        CheckConstraint("tier IN ('common','remarkable')", name="tier"),
        CheckConstraint(DEPOSIT_SHAPE, name="shape"),
        CheckConstraint("settle_remainder >= 0", name="settle_remainder"),
        CheckConstraint(
            "(dossier IS NULL AND clue IS NULL) OR (family = 'curiosity' AND dossier >= 0 "
            "AND clue >= 0)",
            name="dossier",
        ),
        Index("ix_galaxy_opportunities_system", "universe_id", "system_id"),
    )
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    system_id: Mapped[UUID] = mapped_column(Uuid)
    ordinal: Mapped[int]
    family: Mapped[str] = mapped_column(String(10))
    kind: Mapped[str] = mapped_column(String(32))
    tier: Mapped[str] = mapped_column(String(12))
    resource: Mapped[str | None] = mapped_column(String(8))
    reserve_total: Mapped[int | None] = mapped_column(BigInteger)
    reserve_remaining: Mapped[int | None] = mapped_column(BigInteger)
    throughput_per_hour: Mapped[int | None] = mapped_column(BigInteger)
    study_seconds: Mapped[int | None]
    data_reward: Mapped[int | None] = mapped_column(BigInteger)
    dossier: Mapped[int | None]
    clue: Mapped[int | None]
    # EXP-02b: extraction is settled up to settled_at (shared by every Empire's claim); the
    # supply fraction below one micro-unit is kept, never lost (micro-unit x microsecond / h).
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settle_remainder: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    # v0.11: regeneration fraction below one micro-unit (micro-unit x microsecond / day).
    regen_remainder: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


class OpportunityKnowledge(Base):
    """What one Empire learned of one opportunity by prospection, dated. The observed reserve is
    the value at `observed_at`; later extraction by others is unknown until a new observation."""

    __tablename__ = "opportunity_knowledge"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empire_exploration.empire_id", "empire_exploration.universe_id"],
        ),
        ForeignKeyConstraint(
            ["opportunity_id", "universe_id"],
            ["galaxy_opportunities.id", "galaxy_opportunities.universe_id"],
        ),
        CheckConstraint("observed_reserve IS NULL OR observed_reserve >= 0", name="observed"),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    opportunity_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_reserve: Mapped[int | None] = mapped_column(BigInteger)


class OpportunityStudy(Base):
    """EXP-02: a curiosity studied once per Empire; dossier progress is read from these rows."""

    __tablename__ = "opportunity_studies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empire_exploration.empire_id", "empire_exploration.universe_id"],
        ),
        ForeignKeyConstraint(
            ["opportunity_id", "universe_id"],
            ["galaxy_opportunities.id", "galaxy_opportunities.universe_id"],
        ),
        ForeignKeyConstraint(["mission_id"], ["fleet_missions.id"]),
        CheckConstraint("data_credited >= 0", name="credited"),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    opportunity_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    mission_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    studied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_credited: Mapped[int] = mapped_column(BigInteger)


class DepositClaim(Base):
    """EXP-02b: one EXTRACT mission working a deposit between active_from (arrival) and
    active_until (planned end, or recall). Shares of the deposit throughput are settled on the
    deposit row lock, in time order, across every Empire's claims; credited is final once
    settled past active_until. Never visible to another Empire."""

    __tablename__ = "deposit_claims"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empire_exploration.empire_id", "empire_exploration.universe_id"],
        ),
        ForeignKeyConstraint(
            ["opportunity_id", "universe_id"],
            ["galaxy_opportunities.id", "galaxy_opportunities.universe_id"],
        ),
        ForeignKeyConstraint(["mission_id"], ["fleet_missions.id"]),
        CheckConstraint("extractors > 0", name="extractors"),
        CheckConstraint("room >= 0 AND credited >= 0 AND credited <= room", name="credited"),
        CheckConstraint("active_until >= active_from", name="window"),
        Index("ix_deposit_claims_opportunity", "opportunity_id", "active_until"),
    )
    mission_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    opportunity_id: Mapped[UUID] = mapped_column(Uuid)
    extractors: Mapped[int]
    room: Mapped[int] = mapped_column(BigInteger)
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    credited: Mapped[int] = mapped_column(BigInteger, default=0)
