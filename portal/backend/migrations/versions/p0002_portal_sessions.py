"""Portal profile bindings, login challenges, sessions and durable logout intentions."""

import sqlalchemy as sa
from alembic import op

revision = "p0002_portal_sessions"
down_revision = "p0001_accounts_registration"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "browser_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("digest", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "account_devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("browser_profiles.id"), nullable=False),
        sa.Column("revocation_epoch", sa.Integer(), nullable=False),
        sa.CheckConstraint("revocation_epoch >= 0", name="device_epoch_nonnegative"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "profile_id"),
        sa.UniqueConstraint("id", "user_id"),
    )
    op.create_index("ix_account_devices_user_id", "account_devices", ["user_id"])
    op.create_table(
        "portal_sessions",
        sa.UniqueConstraint("id", "device_id", "user_id"),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["device_id", "user_id"], ["account_devices.id", "account_devices.user_id"]
        ),
        sa.CheckConstraint(
            "expires_at = created_at + interval '7 days'", name="session_absolute_limit"
        ),
        sa.CheckConstraint(
            "last_activity_at >= created_at AND last_activity_at < expires_at",
            name="session_activity",
        ),
    )
    op.create_index("ix_portal_sessions_user_id", "portal_sessions", ["user_id"])
    op.create_index(
        "uq_portal_sessions_active_device",
        "portal_sessions",
        ["device_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_table(
        "login_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("digest", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "expires_at = created_at + interval '5 minutes'", name="login_challenge_lifetime"
        ),
    )
    op.create_index("ix_login_challenges_expires_at", "login_challenges", ["expires_at"])
    op.create_table(
        "logout_requests",
        sa.ForeignKeyConstraint(
            ["portal_session_id", "device_id", "user_id"],
            ["portal_sessions.id", "portal_sessions.device_id", "portal_sessions.user_id"],
        ),
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("portal_session_id", sa.Uuid(), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("device_epoch", sa.Integer(), nullable=False),
        sa.CheckConstraint("device_epoch > 0", name="logout_positive_epoch"),
        sa.ForeignKeyConstraint(
            ["device_id", "user_id"], ["account_devices.id", "account_devices.user_id"]
        ),
        sa.CheckConstraint("state IN ('pending', 'acknowledged')", name="logout_request_state"),
    )
    op.create_index("ix_logout_requests_user_id", "logout_requests", ["user_id"])


def downgrade():
    connection = op.get_bind()
    for table in (
        "browser_profiles",
        "account_devices",
        "portal_sessions",
        "login_challenges",
        "logout_requests",
    ):
        if connection.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError("Refusing populated Portal sessions downgrade")
    for table in (
        "logout_requests",
        "login_challenges",
        "portal_sessions",
        "account_devices",
        "browser_profiles",
    ):
        op.drop_table(table)
