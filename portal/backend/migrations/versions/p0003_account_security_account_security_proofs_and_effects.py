"""account security proofs and effects

Revision ID: p0003_account_security
Revises: p0002_portal_sessions
"""

import sqlalchemy as sa
from alembic import op

revision = "p0003_account_security"
down_revision = "p0002_portal_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_revocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("account_epoch", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reason IN ('password_reset', 'password_change', 'email_change', 'logout_all')",
            name=op.f("ck_account_revocations_account_revoke_reason"),
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'acknowledged')",
            name=op.f("ck_account_revocations_account_revoke_state"),
        ),
        sa.CheckConstraint(
            "account_epoch > 0", name=op.f("ck_account_revocations_account_epoch_positive")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_account_revocations_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_revocations")),
        sa.UniqueConstraint(
            "user_id", "account_epoch", name=op.f("uq_account_revocations_user_id")
        ),
    )
    op.create_index(
        op.f("ix_account_revocations_user_id"), "account_revocations", ["user_id"], unique=False
    )
    op.create_table(
        "password_reset_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at = created_at + interval '30 minutes'",
            name=op.f("ck_password_reset_requests_reset_lifetime"),
        ),
        sa.CheckConstraint(
            "(active AND consumed_at IS NULL AND revoked_at IS NULL) OR "
            "(NOT active AND ((consumed_at IS NOT NULL AND revoked_at IS NULL) OR "
            "(consumed_at IS NULL AND revoked_at IS NOT NULL)))",
            name=op.f("ck_password_reset_requests_reset_state"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_password_reset_requests_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_requests")),
        sa.UniqueConstraint("digest", name=op.f("uq_password_reset_requests_digest")),
    )
    op.create_index(
        op.f("ix_password_reset_requests_user_id"),
        "password_reset_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "uq_password_reset_active",
        "password_reset_requests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "email_change_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("old_email", sa.String(length=320), nullable=False),
        sa.Column("new_email", sa.String(length=320), nullable=False),
        sa.Column("new_email_key", sa.String(length=320), nullable=False),
        sa.Column("old_digest", sa.String(length=64), nullable=False),
        sa.Column("new_digest", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("old_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at = created_at + interval '1 hour'",
            name=op.f("ck_email_change_requests_email_change_lifetime"),
        ),
        sa.CheckConstraint(
            "NOT active OR (completed_at IS NULL AND revoked_at IS NULL)",
            name=op.f("ck_email_change_requests_email_change_state"),
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "device_id", "user_id"],
            ["portal_sessions.id", "portal_sessions.device_id", "portal_sessions.user_id"],
            name=op.f("fk_email_change_requests_session_id_portal_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_email_change_requests_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_change_requests")),
        sa.UniqueConstraint("new_digest", name=op.f("uq_email_change_requests_new_digest")),
        sa.UniqueConstraint("old_digest", name=op.f("uq_email_change_requests_old_digest")),
    )
    op.create_index(
        op.f("ix_email_change_requests_user_id"), "email_change_requests", ["user_id"], unique=False
    )
    op.create_index(
        "uq_email_change_active",
        "email_change_requests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.create_table(
        "step_up_grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("parameters_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "action IN ('password_change', 'email_change', 'logout_all')",
            name=op.f("ck_step_up_grants_stepup_action"),
        ),
        sa.CheckConstraint(
            "expires_at = created_at + interval '5 minutes'",
            name=op.f("ck_step_up_grants_stepup_lifetime"),
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR revoked_at IS NULL", name=op.f("ck_step_up_grants_stepup_state")
        ),
        sa.ForeignKeyConstraint(
            ["session_id", "device_id", "user_id"],
            ["portal_sessions.id", "portal_sessions.device_id", "portal_sessions.user_id"],
            name=op.f("fk_step_up_grants_session_id_portal_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_step_up_grants_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_step_up_grants")),
        sa.UniqueConstraint("digest", name=op.f("uq_step_up_grants_digest")),
    )
    op.create_index(op.f("ix_step_up_grants_user_id"), "step_up_grants", ["user_id"], unique=False)
    op.create_table(
        "security_email_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reset_id", sa.Uuid(), nullable=True),
        sa.Column("email_change_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("recipient_digest", sa.String(length=64), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=True),
        sa.Column("payload_ciphertext", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('password_reset', 'email_old', 'email_new', 'password_changed', "
            "'email_changed_old', 'email_changed_new')",
            name=op.f("ck_security_email_outbox_security_mail_kind"),
        ),
        sa.CheckConstraint(
            "state <> 'pending' OR payload_ciphertext IS NOT NULL",
            name=op.f("ck_security_email_outbox_security_mail_payload"),
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'sent', 'cancelled')",
            name=op.f("ck_security_email_outbox_security_mail_state"),
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND expires_at > created_at",
            name=op.f("ck_security_email_outbox_security_mail_bounds"),
        ),
        sa.ForeignKeyConstraint(
            ["email_change_id"],
            ["email_change_requests.id"],
            name=op.f("fk_security_email_outbox_email_change_id_email_change_requests"),
        ),
        sa.ForeignKeyConstraint(
            ["reset_id"],
            ["password_reset_requests.id"],
            name=op.f("fk_security_email_outbox_reset_id_password_reset_requests"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_security_email_outbox_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_email_outbox")),
    )
    op.create_index(
        "ix_security_email_due", "security_email_outbox", ["state", "next_attempt_at"], unique=False
    )
    op.create_index(
        op.f("ix_security_email_outbox_user_id"), "security_email_outbox", ["user_id"], unique=False
    )
    op.add_column(
        "users", sa.Column("security_epoch", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "platform_privileged", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )

    op.create_check_constraint(
        op.f("ck_users_user_epoch_nonnegative"), "users", "security_epoch >= 0"
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "users",
        "account_revocations",
        "email_change_requests",
        "password_reset_requests",
        "security_email_outbox",
        "step_up_grants",
    ):
        if connection.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError("Refusing populated account security downgrade")
    op.drop_constraint(op.f("ck_users_user_epoch_nonnegative"), "users", type_="check")
    op.drop_column("users", "platform_privileged")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "security_epoch")
    op.drop_index(op.f("ix_security_email_outbox_user_id"), table_name="security_email_outbox")
    op.drop_index("ix_security_email_due", table_name="security_email_outbox")
    op.drop_table("security_email_outbox")
    op.drop_index(op.f("ix_step_up_grants_user_id"), table_name="step_up_grants")
    op.drop_table("step_up_grants")
    op.drop_index(
        "uq_email_change_active",
        table_name="email_change_requests",
        postgresql_where=sa.text("active"),
    )
    op.drop_index(op.f("ix_email_change_requests_user_id"), table_name="email_change_requests")
    op.drop_table("email_change_requests")
    op.drop_index(
        "uq_password_reset_active",
        table_name="password_reset_requests",
        postgresql_where=sa.text("active"),
    )
    op.drop_index(op.f("ix_password_reset_requests_user_id"), table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
    op.drop_index(op.f("ix_account_revocations_user_id"), table_name="account_revocations")
    op.drop_table("account_revocations")
