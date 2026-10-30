"""Portal intentions, immutable deliveries and acknowledged snapshots, never Game ORM."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from portal_app.account_security import models as security_models  # noqa: F401
from portal_app.persistence.models import Base
from portal_app.sessions import models as session_models  # noqa: F401


class UniverseReference(Base):
    __tablename__ = "universe_references"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    backend_id: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    provisioned: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UniverseMembership(Base):
    __tablename__ = "universe_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "universe_id"),
        CheckConstraint("revision >= 1 AND access_epoch >= 1", name="membership_revision"),
        CheckConstraint(
            "desired_status IN ('active', 'suspended', 'revoked')", name="membership_status"
        ),
        CheckConstraint(
            "valid_until > portal_confirmed_at "
            "AND valid_until <= portal_confirmed_at + interval '8 hours'",
            name="membership_lifetime",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universe_references.id"), index=True)
    revision: Mapped[int] = mapped_column(BigInteger)
    access_epoch: Mapped[int] = mapped_column(BigInteger)
    desired_status: Mapped[str] = mapped_column(String(16))
    portal_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bindings: Mapped[list] = mapped_column(JSONB)
    desired_snapshot: Mapped[dict] = mapped_column(JSONB)
    applied_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reconciliation_pending: Mapped[bool] = mapped_column(default=True)


class ControlOutbox(Base):
    __tablename__ = "control_outbox"
    __table_args__ = (
        CheckConstraint("state IN ('pending', 'acknowledged')", name="control_delivery_state"),
        CheckConstraint("attempts >= 0", name="control_attempts"),
        Index(
            "uq_control_logout_target",
            "logout_request_id",
            "backend_id",
            unique=True,
            postgresql_where=text("logout_request_id IS NOT NULL"),
        ),
        Index(
            "uq_control_revocation_target",
            "account_revocation_id",
            "backend_id",
            unique=True,
            postgresql_where=text("account_revocation_id IS NOT NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    backend_id: Mapped[str] = mapped_column(String(40))
    universe_id: Mapped[UUID | None] = mapped_column(ForeignKey("universe_references.id"))
    membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("universe_memberships.id"))
    logout_request_id: Mapped[UUID | None] = mapped_column(ForeignKey("logout_requests.id"))
    account_revocation_id: Mapped[UUID | None] = mapped_column(ForeignKey("account_revocations.id"))
    envelope: Mapped[dict] = mapped_column(JSONB)
    request_digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
