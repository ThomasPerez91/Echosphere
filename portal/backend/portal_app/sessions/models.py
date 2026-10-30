"""Portal sessions and profile bindings; no Game connection or credentials."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from portal_app.persistence.models import Base


class BrowserProfile(Base):
    __tablename__ = "browser_profiles"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountDevice(Base):
    __tablename__ = "account_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "profile_id"),
        UniqueConstraint("id", "user_id"),
        CheckConstraint("revocation_epoch >= 0", name="device_epoch_nonnegative"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("browser_profiles.id"))
    revocation_epoch: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PortalSession(Base):
    __tablename__ = "portal_sessions"
    __table_args__ = (
        UniqueConstraint("id", "device_id", "user_id"),
        ForeignKeyConstraint(
            ["device_id", "user_id"], ["account_devices.id", "account_devices.user_id"]
        ),
        CheckConstraint(
            "expires_at = created_at + interval '7 days'", name="session_absolute_limit"
        ),
        CheckConstraint(
            "last_activity_at >= created_at AND last_activity_at < expires_at",
            name="session_activity",
        ),
        Index(
            "uq_portal_sessions_active_device",
            "device_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[UUID] = mapped_column()
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginChallenge(Base):
    __tablename__ = "login_challenges"
    __table_args__ = (
        CheckConstraint(
            "expires_at = created_at + interval '5 minutes'", name="login_challenge_lifetime"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LogoutRequest(Base):
    __tablename__ = "logout_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["portal_session_id", "device_id", "user_id"],
            ["portal_sessions.id", "portal_sessions.device_id", "portal_sessions.user_id"],
        ),
        ForeignKeyConstraint(
            ["device_id", "user_id"], ["account_devices.id", "account_devices.user_id"]
        ),
        CheckConstraint("state IN ('pending', 'acknowledged')", name="logout_request_state"),
        CheckConstraint("device_epoch > 0", name="logout_positive_epoch"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[UUID] = mapped_column()
    portal_session_id: Mapped[UUID] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), default="pending")
    device_epoch: Mapped[int] = mapped_column(Integer)
