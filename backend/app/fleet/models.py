"""Fleet state scoped by Universe/Empire. A unit exists only as a count in one Fleet stack.

A merged Fleet keeps its row (status MERGED, no location) so mission history stays intact.
Engagement invariant enforced in the database: a stack belongs to one Fleet, a Fleet has at most
one open mission (`active_mission_id` unique + partial index), and MOVING ⇔ open mission. Stacks
and cargo change only while STATIONED, under the Empire Operations stream lock.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
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

OPERATIONS = ["empire_exploration.empire_id", "empire_exploration.universe_id"]
COLONY = ["colonies.id", "colonies.empire_id", "colonies.universe_id"]
KNOWN_SYSTEM = [
    "system_knowledge.empire_id",
    "system_knowledge.system_id",
    "system_knowledge.universe_id",
]


class ShipOrder(Record, Base):
    __tablename__ = "ship_orders"
    __table_args__ = (
        ForeignKeyConstraint(["empire_id", "universe_id"], OPERATIONS),
        ForeignKeyConstraint(["colony_id", "empire_id", "universe_id"], COLONY),
        UniqueConstraint("empire_id", "idempotency_key", name="uq_ship_order_key"),
        UniqueConstraint("colony_id", "sequence", name="uq_ship_order_sequence"),
        CheckConstraint("quantity > 0 AND sequence > 0", name="quantity"),
        CheckConstraint("status IN ('queued','active','completed','cancelled')", name="status"),
        CheckConstraint(
            "status <> 'queued' OR (started_at IS NULL AND due_at IS NULL)", name="queued"
        ),
        CheckConstraint(
            "status NOT IN ('active','completed') "
            "OR (started_at IS NOT NULL AND due_at > started_at)",
            name="schedule",
        ),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completion"),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL AND refunded IS NOT NULL)",
            name="cancellation",
        ),
        Index(
            "ix_ship_order_active",
            "colony_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    colony_id: Mapped[UUID] = mapped_column(Uuid)
    ship_class: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[int] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    refunded: Mapped[dict | None] = mapped_column(JSONB)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Fleet(Record, Base):
    __tablename__ = "fleets"
    __table_args__ = (
        ForeignKeyConstraint(["empire_id", "universe_id"], OPERATIONS),
        ForeignKeyConstraint(["home_colony_id", "empire_id", "universe_id"], COLONY),
        # Stationed only where the Empire has knowledge: never beyond its own map.
        ForeignKeyConstraint(["empire_id", "system_id", "universe_id"], KNOWN_SYSTEM),
        ForeignKeyConstraint(
            ["active_mission_id", "id"],
            ["fleet_missions.id", "fleet_missions.fleet_id"],
            name="fk_fleets_active_mission_id_fleet_missions",
            use_alter=True,
        ),
        UniqueConstraint("id", "empire_id", "universe_id", name="uq_fleet_scope"),
        UniqueConstraint("active_mission_id", name="uq_fleet_active_mission"),
        CheckConstraint("kind IN ('GARRISON','TASK')", name="kind"),
        # SETTLED: a task Fleet whose colonizer founded a Colony; history kept, never deleted.
        CheckConstraint("status IN ('STATIONED','MOVING','MERGED','SETTLED')", name="status"),
        CheckConstraint("(status = 'STATIONED') = (system_id IS NOT NULL)", name="location"),
        CheckConstraint("(status = 'MOVING') = (active_mission_id IS NOT NULL)", name="engagement"),
        CheckConstraint("kind <> 'GARRISON' OR status = 'STATIONED'", name="garrison"),
        CheckConstraint("status <> 'SETTLED' OR kind = 'TASK'", name="settled"),
        CheckConstraint("length(trim(name)) > 0", name="name"),
        Index(
            "ix_fleet_garrison",
            "home_colony_id",
            unique=True,
            postgresql_where=text("kind = 'GARRISON'"),
        ),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    home_colony_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12))
    system_id: Mapped[UUID | None] = mapped_column(Uuid)
    active_mission_id: Mapped[UUID | None] = mapped_column(Uuid)
    name: Mapped[str] = mapped_column(String(80))


class FleetStack(Base):
    __tablename__ = "fleet_stacks"
    __table_args__ = (CheckConstraint("count > 0", name="count"),)
    fleet_id: Mapped[UUID] = mapped_column(ForeignKey("fleets.id"), primary_key=True)
    ship_class: Mapped[str] = mapped_column(String(32), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)


class FleetCargo(Base):
    __tablename__ = "fleet_cargo"
    __table_args__ = (
        CheckConstraint("resource IN ('alloys','flux','data')", name="resource"),
        CheckConstraint("amount > 0", name="amount"),
    )
    fleet_id: Mapped[UUID] = mapped_column(ForeignKey("fleets.id"), primary_key=True)
    resource: Mapped[str] = mapped_column(String(8), primary_key=True)
    amount: Mapped[int] = mapped_column(BigInteger)


class FleetMission(Record, Base):
    __tablename__ = "fleet_missions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["fleet_id", "empire_id", "universe_id"],
            ["fleets.id", "fleets.empire_id", "fleets.universe_id"],
        ),
        ForeignKeyConstraint(
            ["empire_id", "origin_id", "universe_id"],
            KNOWN_SYSTEM,
            name="fk_fleet_missions_origin_system_knowledge",
        ),
        ForeignKeyConstraint(
            ["empire_id", "destination_id", "universe_id"],
            KNOWN_SYSTEM,
            name="fk_fleet_missions_destination_system_knowledge",
        ),
        ForeignKeyConstraint(["payer_colony_id", "empire_id", "universe_id"], COLONY),
        # COLONIZE targets a planet this Empire knows, inside the destination system.
        ForeignKeyConstraint(
            ["empire_id", "target_planet_id"],
            ["planet_knowledge.empire_id", "planet_knowledge.planet_id"],
            name="fk_fleet_missions_target_planet_knowledge",
        ),
        ForeignKeyConstraint(
            ["target_planet_id", "destination_id", "universe_id"],
            ["planets.id", "planets.system_id", "planets.universe_id"],
            name="fk_fleet_missions_target_planet_system",
        ),
        UniqueConstraint("id", "fleet_id", name="uq_fleet_mission_fleet"),
        UniqueConstraint("id", "empire_id", "universe_id", name="uq_fleet_mission_scope"),
        UniqueConstraint("empire_id", "idempotency_key", name="uq_fleet_mission_key"),
        CheckConstraint("kind IN ('DEPLOY','SURVEY','RETURN','COLONIZE')", name="kind"),
        CheckConstraint("status IN ('active','returning','completed')", name="status"),
        CheckConstraint("(kind = 'COLONIZE') = (target_planet_id IS NOT NULL)", name="target"),
        # Only COLONIZE may target the current system: 0 hop, arrival = start, no recall window.
        CheckConstraint("origin_id <> destination_id OR kind = 'COLONIZE'", name="route"),
        CheckConstraint(
            "(origin_id <> destination_id AND travel_arrival_at > started_at) "
            "OR (origin_id = destination_id AND travel_arrival_at = started_at)",
            name="travel",
        ),
        CheckConstraint(
            "(kind = 'SURVEY' AND due_at > travel_arrival_at) "
            "OR (kind <> 'SURVEY' AND due_at = travel_arrival_at)",
            name="deadline",
        ),
        CheckConstraint("(recalled_at IS NULL) = (return_at IS NULL)", name="recall_pair"),
        # Recall only while travelling, never an analysis or a return; time-symmetric way back.
        CheckConstraint(
            "recalled_at IS NULL OR (kind <> 'RETURN' AND recalled_at >= started_at "
            "AND recalled_at < travel_arrival_at "
            "AND return_at = recalled_at + (recalled_at - started_at))",
            name="recall",
        ),
        CheckConstraint("status <> 'returning' OR recalled_at IS NOT NULL", name="returning"),
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)", name="completion"),
        Index(
            "ix_fleet_mission_open",
            "fleet_id",
            unique=True,
            postgresql_where=text("status IN ('active','returning')"),
        ),
        # One active colonization per Empire; competing claims looked up per target planet.
        Index(
            "ix_fleet_mission_colonize_active",
            "empire_id",
            unique=True,
            postgresql_where=text("kind = 'COLONIZE' AND status = 'active'"),
        ),
        Index(
            "ix_fleet_mission_colonize_target",
            "universe_id",
            "target_planet_id",
            postgresql_where=text("kind = 'COLONIZE' AND status = 'active'"),
        ),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    fleet_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12))
    origin_id: Mapped[UUID] = mapped_column(Uuid)
    destination_id: Mapped[UUID] = mapped_column(Uuid)
    payer_colony_id: Mapped[UUID] = mapped_column(Uuid)
    target_planet_id: Mapped[UUID | None] = mapped_column(Uuid)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    travel_arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FleetMissionLeg(Base):
    __tablename__ = "fleet_mission_legs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "empire_id", "universe_id"],
            ["fleet_missions.id", "fleet_missions.empire_id", "fleet_missions.universe_id"],
        ),
        # Only routes this Empire knows can be travelled.
        ForeignKeyConstraint(
            ["empire_id", "route_id"], ["route_knowledge.empire_id", "route_knowledge.route_id"]
        ),
        CheckConstraint("ordinal >= 0", name="ordinal"),
    )
    mission_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    route_id: Mapped[UUID] = mapped_column(Uuid)


class FleetReport(Base):
    __tablename__ = "fleet_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mission_id", "empire_id", "universe_id"],
            ["fleet_missions.id", "fleet_missions.empire_id", "fleet_missions.universe_id"],
        ),
        CheckConstraint("processed_at >= observed_at", name="processing"),
    )
    mission_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(Uuid)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict] = mapped_column(JSONB)


class FleetOperation(Base):
    """Idempotency ledger for stationed operations (split/merge/cargo/recall) per Empire."""

    __tablename__ = "fleet_operations"
    __table_args__ = (
        ForeignKeyConstraint(["empire_id", "universe_id"], OPERATIONS),
        CheckConstraint("kind IN ('split','merge','load','unload','recall')", name="kind"),
    )
    empire_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    universe_id: Mapped[UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(12))
    request: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
