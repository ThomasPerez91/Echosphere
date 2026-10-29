"""Accounts-only entities; all dates are server UTC and no Game FK is involved."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from portal_app.persistence.models import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("status IN ('active', 'suspended')", name="user_status"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320))
    email_key: Mapped[str] = mapped_column(String(320), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordCredential(Base):
    __tablename__ = "password_credentials"
    __table_args__ = (CheckConstraint("password_hash LIKE '$argon2id$%'", name="argon2id_only"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AccountToken(Base):
    __tablename__ = "account_tokens"
    __table_args__ = (
        CheckConstraint("purpose = 'email_verification'", name="token_purpose"),
        CheckConstraint("expires_at > created_at", name="positive_lifetime"),
        CheckConstraint("expires_at <= created_at + interval '24 hours'", name="maximum_lifetime"),
        CheckConstraint(
            "(active AND consumed_at IS NULL AND revoked_at IS NULL) OR "
            "(NOT active AND ((consumed_at IS NOT NULL AND revoked_at IS NULL) OR "
            "(consumed_at IS NULL AND revoked_at IS NOT NULL)))",
            name="token_state",
        ),
        Index(
            "uq_account_tokens_active",
            "user_id",
            "purpose",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(32), default="email_verification")
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint("state IN ('pending', 'sent', 'cancelled')", name="outbox_state"),
        CheckConstraint("attempts >= 0", name="nonnegative_attempts"),
        CheckConstraint("expires_at > created_at", name="outbox_lifetime"),
        CheckConstraint(
            "state <> 'pending' OR payload_ciphertext IS NOT NULL", name="pending_payload"
        ),
        Index("ix_email_outbox_due", "state", "next_attempt_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_id: Mapped[UUID] = mapped_column(ForeignKey("account_tokens.id"), unique=True)
    payload_ciphertext: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AbuseCounter(Base):
    __tablename__ = "abuse_counters"
    __table_args__ = (CheckConstraint("count >= 0", name="nonnegative_count"),)

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
