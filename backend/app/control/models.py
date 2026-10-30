"""Game-owned effective rights and permanent anti-replay markers; no Accounts FK."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models import Base


class GamePrincipal(Base):
    __tablename__ = "game_principals"
    __table_args__ = (CheckConstraint("account_epoch >= 0", name="principal_epoch"),)
    global_user_id: Mapped[UUID] = mapped_column(primary_key=True)
    account_epoch: Mapped[int] = mapped_column(BigInteger, default=0)


class GameDevice(Base):
    __tablename__ = "game_devices"
    __table_args__ = (CheckConstraint("device_epoch >= 0", name="device_epoch"),)
    global_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("game_principals.global_user_id"), primary_key=True
    )
    device_id: Mapped[UUID] = mapped_column(primary_key=True)
    device_epoch: Mapped[int] = mapped_column(BigInteger)


class GameAccess(Base):
    __tablename__ = "game_accesses"
    __table_args__ = (
        UniqueConstraint("global_user_id", "universe_id"),
        UniqueConstraint("membership_id", "universe_id"),
        CheckConstraint("revision >= 1 AND access_epoch >= 1", name="access_revision"),
        CheckConstraint("status IN ('active', 'suspended', 'revoked')", name="access_status"),
        CheckConstraint(
            "valid_until > portal_confirmed_at "
            "AND valid_until <= portal_confirmed_at + interval '8 hours'",
            name="access_lifetime",
        ),
    )
    membership_id: Mapped[UUID] = mapped_column(primary_key=True)
    global_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("game_principals.global_user_id"), index=True
    )
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"), index=True)
    revision: Mapped[int] = mapped_column(BigInteger)
    access_epoch: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16))
    portal_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    snapshot_digest: Mapped[str] = mapped_column(String(64))


class EmpireBinding(Base):
    __tablename__ = "empire_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "universe_id"],
            ["game_accesses.membership_id", "game_accesses.universe_id"],
        ),
        ForeignKeyConstraint(["empire_id", "universe_id"], ["empires.id", "empires.universe_id"]),
        CheckConstraint(
            "jsonb_typeof(permissions) = 'array' "
            "AND jsonb_array_length(permissions) > 0 "
            'AND permissions <@ \'["colony.read","colony.construct","colony.cancel"]\'::jsonb',
            name="binding_permissions",
        ),
    )
    membership_id: Mapped[UUID] = mapped_column(primary_key=True)
    empire_id: Mapped[UUID] = mapped_column(primary_key=True)
    universe_id: Mapped[UUID] = mapped_column()
    permissions: Mapped[list] = mapped_column(JSONB)


class ControlOperation(Base):
    __tablename__ = "control_operations"
    service_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    operation_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer)
