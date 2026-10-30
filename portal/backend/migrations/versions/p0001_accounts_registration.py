"""Accounts registration, verification and durable encrypted delivery.

No sessions/MFA or Game references are introduced. C03 owns session tables.
"""

import sqlalchemy as sa
from alembic import op

revision = "p0001_accounts_registration"
down_revision = "p0000_portal_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("email_key", sa.String(320), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="user_status"),
    )
    op.create_table(
        "password_credentials",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("password_hash LIKE '$argon2id$%'", name="argon2id_only"),
    )
    op.create_table(
        "account_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("purpose = 'email_verification'", name="token_purpose"),
        sa.CheckConstraint("expires_at > created_at", name="positive_lifetime"),
        sa.CheckConstraint(
            "expires_at <= created_at + interval '24 hours'", name="maximum_lifetime"
        ),
        sa.CheckConstraint(
            "(active AND consumed_at IS NULL AND revoked_at IS NULL) OR "
            "(NOT active AND ((consumed_at IS NOT NULL AND revoked_at IS NULL) OR "
            "(consumed_at IS NULL AND revoked_at IS NOT NULL)))",
            name="token_state",
        ),
    )
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])
    op.create_index(
        "uq_account_tokens_active",
        "account_tokens",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "token_id", sa.Uuid(), sa.ForeignKey("account_tokens.id"), nullable=False, unique=True
        ),
        sa.Column("payload_ciphertext", sa.Text()),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("state IN ('pending', 'sent', 'cancelled')", name="outbox_state"),
        sa.CheckConstraint("attempts >= 0", name="nonnegative_attempts"),
        sa.CheckConstraint("expires_at > created_at", name="outbox_lifetime"),
        sa.CheckConstraint(
            "state <> 'pending' OR payload_ciphertext IS NOT NULL", name="pending_payload"
        ),
    )
    op.create_index("ix_email_outbox_user_id", "email_outbox", ["user_id"])
    op.create_index("ix_email_outbox_due", "email_outbox", ["state", "next_attempt_at"])
    op.create_table(
        "abuse_counters",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("window_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.CheckConstraint("count >= 0", name="nonnegative_count"),
    )
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"])
    op.create_index("ix_security_events_created_at", "security_events", ["created_at"])


def downgrade() -> None:
    # A rollback must never silently delete accounts or pending verification/delivery data.
    connection = op.get_bind()
    for table in ("users", "account_tokens", "email_outbox", "abuse_counters", "security_events"):
        if connection.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError("Refusing populated Accounts downgrade; preserve account data")
    for table in (
        "security_events",
        "abuse_counters",
        "email_outbox",
        "account_tokens",
        "password_credentials",
        "users",
    ):
        op.drop_table(table)
