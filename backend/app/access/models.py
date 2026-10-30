"""Game session proofs; never credentials for an Accounts identity."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.models import Base


class PreAuth(Base):
    __tablename__ = "game_pre_auths"
    __table_args__ = (
        CheckConstraint("expires_at = created_at + interval '5 minutes'", name="pre_auth_lifetime"),
    )
    peer_digest: Mapped[str] = mapped_column(String(64), index=True)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsumedTicket(Base):
    __tablename__ = "game_consumed_tickets"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    pre_auth_id: Mapped[UUID] = mapped_column(ForeignKey("game_pre_auths.id"), unique=True)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GameSession(Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["global_user_id", "device_id"],
            ["game_devices.global_user_id", "game_devices.device_id"],
        ),
        ForeignKeyConstraint(
            ["membership_id", "global_user_id", "universe_id"],
            [
                "game_accesses.membership_id",
                "game_accesses.global_user_id",
                "game_accesses.universe_id",
            ],
        ),
        CheckConstraint(
            "expires_at > created_at AND expires_at <= created_at + interval '8 hours' "
            "AND expires_at <= access_valid_until",
            name="game_session_lifetime",
        ),
        CheckConstraint(
            "last_activity_at >= created_at AND last_activity_at < expires_at",
            name="game_session_activity",
        ),
        CheckConstraint(
            "account_epoch >= 0 AND device_epoch >= 0 AND access_epoch >= 1",
            name="game_session_epochs",
        ),
        Index(
            "uq_game_session_active_slot",
            "global_user_id",
            "device_id",
            "universe_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    global_user_id: Mapped[UUID] = mapped_column(ForeignKey("game_principals.global_user_id"))
    device_id: Mapped[UUID] = mapped_column()
    membership_id: Mapped[UUID] = mapped_column()
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universes.id"))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    key_id: Mapped[str] = mapped_column(String(64))
    account_epoch: Mapped[int] = mapped_column(BigInteger)
    device_epoch: Mapped[int] = mapped_column(BigInteger)
    access_epoch: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    access_valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    logout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
