"""MFA factors and limited recovery

Revision ID: p0004_mfa
Revises: p0003_account_security
"""

import sqlalchemy as sa
from alembic import op

revision = "p0004_mfa"
down_revision = "p0003_account_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_failures",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_auth_failures")),
    )
    op.create_table(
        "mfa_backup_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_mfa_backup_codes_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_backup_codes")),
        sa.UniqueConstraint("digest", name=op.f("uq_mfa_backup_codes_digest")),
    )
    op.create_index(
        op.f("ix_mfa_backup_codes_user_id"), "mfa_backup_codes", ["user_id"], unique=False
    )
    op.create_table(
        "mfa_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("context_digest", sa.String(length=64), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("challenge", sa.LargeBinary(), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=True),
        sa.Column("replace_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at AND expires_at <= created_at + interval '5 minutes'",
            name=op.f("ck_mfa_challenges_mfa_lifetime"),
        ),
        sa.CheckConstraint(
            "purpose IN ('assert', 'enroll_totp', 'enroll_webauthn')",
            name=op.f("ck_mfa_challenges_mfa_purpose"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_mfa_challenges_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_challenges")),
    )
    op.create_index(op.f("ix_mfa_challenges_user_id"), "mfa_challenges", ["user_id"], unique=False)
    op.create_table(
        "mfa_recovery_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at = created_at + interval '15 minutes'",
            name=op.f("ck_mfa_recovery_sessions_mfa_recovery_lifetime"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_mfa_recovery_sessions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_recovery_sessions")),
        sa.UniqueConstraint("digest", name=op.f("uq_mfa_recovery_sessions_digest")),
    )
    op.create_index(
        op.f("ix_mfa_recovery_sessions_user_id"), "mfa_recovery_sessions", ["user_id"], unique=False
    )
    op.create_table(
        "totp_credentials",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("last_step", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_totp_credentials_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_totp_credentials")),
    )
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sign_count >= 0", name=op.f("ck_webauthn_credentials_webauthn_count")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_webauthn_credentials_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webauthn_credentials")),
        sa.UniqueConstraint("credential_id", name=op.f("uq_webauthn_credentials_credential_id")),
    )
    op.create_index(
        op.f("ix_webauthn_credentials_user_id"), "webauthn_credentials", ["user_id"], unique=False
    )
    op.add_column(
        "step_up_grants",
        sa.Column("assurance", sa.String(length=16), server_default="password", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "privilege_recovery_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.add_column(
        "email_change_requests",
        sa.Column("assurance", sa.String(16), nullable=False, server_default="password"),
    )
    op.drop_constraint(op.f("ck_step_up_grants_stepup_action"), "step_up_grants", type_="check")
    op.create_check_constraint(
        op.f("ck_step_up_grants_stepup_action"),
        "step_up_grants",
        "action IN ('password_change', 'email_change', 'logout_all', 'mfa_enroll', "
        "'mfa_remove', 'mfa_disable', 'mfa_backup_codes')",
    )
    op.drop_constraint(
        op.f("ck_account_revocations_account_revoke_reason"), "account_revocations", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_account_revocations_account_revoke_reason"),
        "account_revocations",
        "reason IN ('password_reset', 'password_change', 'email_change', 'logout_all', "
        "'mfa_activate', 'mfa_change', 'mfa_disable', 'mfa_recovery')",
    )
    op.drop_constraint(
        op.f("ck_security_email_outbox_security_mail_kind"), "security_email_outbox", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_security_email_outbox_security_mail_kind"),
        "security_email_outbox",
        "kind IN ('password_reset', 'email_old', 'email_new', 'password_changed', "
        "'email_changed_old', 'email_changed_new', 'mfa_changed')",
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "users",
        "auth_failures",
        "mfa_backup_codes",
        "mfa_challenges",
        "mfa_recovery_sessions",
        "totp_credentials",
        "webauthn_credentials",
    ):
        if connection.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError("Refusing populated MFA downgrade")
    op.drop_constraint(op.f("ck_step_up_grants_stepup_action"), "step_up_grants", type_="check")
    op.create_check_constraint(
        op.f("ck_step_up_grants_stepup_action"),
        "step_up_grants",
        "action IN ('password_change', 'email_change', 'logout_all')",
    )
    op.drop_constraint(
        op.f("ck_account_revocations_account_revoke_reason"), "account_revocations", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_account_revocations_account_revoke_reason"),
        "account_revocations",
        "reason IN ('password_reset', 'password_change', 'email_change', 'logout_all')",
    )
    op.drop_constraint(
        op.f("ck_security_email_outbox_security_mail_kind"), "security_email_outbox", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_security_email_outbox_security_mail_kind"),
        "security_email_outbox",
        "kind IN ('password_reset', 'email_old', 'email_new', 'password_changed', "
        "'email_changed_old', 'email_changed_new')",
    )
    op.drop_column("email_change_requests", "assurance")
    op.drop_column("users", "privilege_recovery_required")
    op.drop_column("step_up_grants", "assurance")
    op.drop_index(op.f("ix_webauthn_credentials_user_id"), table_name="webauthn_credentials")
    op.drop_table("webauthn_credentials")
    op.drop_table("totp_credentials")
    op.drop_index(op.f("ix_mfa_recovery_sessions_user_id"), table_name="mfa_recovery_sessions")
    op.drop_table("mfa_recovery_sessions")
    op.drop_index(op.f("ix_mfa_challenges_user_id"), table_name="mfa_challenges")
    op.drop_table("mfa_challenges")
    op.drop_index(op.f("ix_mfa_backup_codes_user_id"), table_name="mfa_backup_codes")
    op.drop_table("mfa_backup_codes")
    op.drop_table("auth_failures")
