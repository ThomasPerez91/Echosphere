"""Typed Universe/Empire-scoped galaxy state. UNKNOWN is absence of knowledge."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
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
