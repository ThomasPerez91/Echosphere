"""Account proofs and durable security effects, owned only by Accounts DB."""

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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from portal_app.persistence.models import Base


class StepUpGrant(Base):
    __tablename__ = "step_up_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "device_id", "user_id"],
            ["portal_sessions.id", "portal_sessions.device_id", "portal_sessions.user_id"],
        ),
        CheckConstraint(
            "action IN ('password_change', 'email_change', 'logout_all')", name="stepup_action"
        ),
        CheckConstraint("expires_at = created_at + interval '5 minutes'", name="stepup_lifetime"),
        CheckConstraint("consumed_at IS NULL OR revoked_at IS NULL", name="stepup_state"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[UUID] = mapped_column()
    device_id: Mapped[UUID] = mapped_column()
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    action: Mapped[str] = mapped_column(String(32))
    parameters_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetRequest(Base):
    __tablename__ = "password_reset_requests"
    __table_args__ = (
        CheckConstraint("expires_at = created_at + interval '30 minutes'", name="reset_lifetime"),
        Index("uq_password_reset_active", "user_id", unique=True, postgresql_where=text("active")),
        CheckConstraint(
            "(active AND consumed_at IS NULL AND revoked_at IS NULL) OR "
            "(NOT active AND ((consumed_at IS NOT NULL AND revoked_at IS NULL) OR "
            "(consumed_at IS NULL AND revoked_at IS NOT NULL)))",
            name="reset_state",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailChangeRequest(Base):
    __tablename__ = "email_change_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "device_id", "user_id"],
            ["portal_sessions.id", "portal_sessions.device_id", "portal_sessions.user_id"],
        ),
        CheckConstraint(
            "expires_at = created_at + interval '1 hour'", name="email_change_lifetime"
        ),
        Index("uq_email_change_active", "user_id", unique=True, postgresql_where=text("active")),
        CheckConstraint(
            "NOT active OR (completed_at IS NULL AND revoked_at IS NULL)", name="email_change_state"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[UUID] = mapped_column()
    device_id: Mapped[UUID] = mapped_column()
    old_email: Mapped[str] = mapped_column(String(320))
    new_email: Mapped[str] = mapped_column(String(320))
    new_email_key: Mapped[str] = mapped_column(String(320))
    old_digest: Mapped[str] = mapped_column(String(64), unique=True)
    new_digest: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    old_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountRevocation(Base):
    __tablename__ = "account_revocations"
    __table_args__ = (
        UniqueConstraint("user_id", "account_epoch"),
        CheckConstraint("account_epoch > 0", name="account_epoch_positive"),
        CheckConstraint(
            "reason IN ('password_reset', 'password_change', 'email_change', 'logout_all')",
            name="account_revoke_reason",
        ),
        CheckConstraint("state IN ('pending', 'acknowledged')", name="account_revoke_state"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    account_epoch: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SecurityEmail(Base):
    __tablename__ = "security_email_outbox"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('password_reset', 'email_old', 'email_new', 'password_changed', "
            "'email_changed_old', 'email_changed_new')",
            name="security_mail_kind",
        ),
        CheckConstraint("state IN ('pending', 'sent', 'cancelled')", name="security_mail_state"),
        CheckConstraint("attempts >= 0 AND expires_at > created_at", name="security_mail_bounds"),
        CheckConstraint(
            "state <> 'pending' OR payload_ciphertext IS NOT NULL", name="security_mail_payload"
        ),
        Index("ix_security_email_due", "state", "next_attempt_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    reset_id: Mapped[UUID | None] = mapped_column(ForeignKey("password_reset_requests.id"))
    email_change_id: Mapped[UUID | None] = mapped_column(ForeignKey("email_change_requests.id"))
    kind: Mapped[str] = mapped_column(String(32))
    recipient_digest: Mapped[str] = mapped_column(String(64))
    token_digest: Mapped[str | None] = mapped_column(String(64))
    payload_ciphertext: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
