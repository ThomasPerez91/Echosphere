"""First persistence model: identity and containment, no production or gameplay actions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    MetaData,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Record:
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Universe(Record, Base):
    __tablename__ = "universes"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),)

    name: Mapped[str] = mapped_column(String(120))
    seed: Mapped[str] = mapped_column(String(200))


class Empire(Record, Base):
    __tablename__ = "empires"
    __table_args__ = (
        UniqueConstraint("id", "universe_id", name="uq_empires_id_universe"),
        CheckConstraint("controller_type IN ('human', 'ai')", name="controller_type"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    controller_type: Mapped[str] = mapped_column(String(8))


class StellarSystem(Record, Base):
    __tablename__ = "stellar_systems"
    __table_args__ = (
        UniqueConstraint("id", "universe_id", name="uq_stellar_systems_id_universe"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))


class Planet(Record, Base):
    __tablename__ = "planets"
    __table_args__ = (
        UniqueConstraint("id", "universe_id", name="uq_planets_id_universe"),
        ForeignKeyConstraint(
            ["system_id", "universe_id"],
            ["stellar_systems.id", "stellar_systems.universe_id"],
            name="fk_planets_system_universe",
        ),
        CheckConstraint("sector_capacity > 0", name="positive_sectors"),
        CheckConstraint("orbital_capacity >= 0", name="nonnegative_orbitals"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"), index=True)
    system_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(120))
    sector_capacity: Mapped[int]
    orbital_capacity: Mapped[int]


class Colony(Record, Base):
    __tablename__ = "colonies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_colonies_empire_universe",
        ),
        ForeignKeyConstraint(
            ["planet_id", "universe_id"],
            ["planets.id", "planets.universe_id"],
            name="fk_colonies_planet_universe",
        ),
        UniqueConstraint("planet_id", name="uq_colonies_planet"),
    )

    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"), index=True)
    empire_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    planet_id: Mapped[UUID] = mapped_column(Uuid)
