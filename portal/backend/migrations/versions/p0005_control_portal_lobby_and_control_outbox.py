"""Portal lobby and control outbox

Revision ID: p0005_control
Revises: p0004_mfa
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p0005_control"
down_revision = "p0004_mfa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "universe_references",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("backend_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provisioned", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_universe_references")),
    )
    op.create_table(
        "universe_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("access_epoch", sa.BigInteger(), nullable=False),
        sa.Column("desired_status", sa.String(length=16), nullable=False),
        sa.Column("portal_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bindings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("desired_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("applied_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reconciliation_pending", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "desired_status IN ('active', 'suspended', 'revoked')",
            name=op.f("ck_universe_memberships_membership_status"),
        ),
        sa.CheckConstraint(
            "valid_until > portal_confirmed_at "
            "AND valid_until <= portal_confirmed_at + interval '8 hours'",
            name=op.f("ck_universe_memberships_membership_lifetime"),
        ),
        sa.CheckConstraint(
            "revision >= 1 AND access_epoch >= 1",
            name=op.f("ck_universe_memberships_membership_revision"),
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"],
            ["universe_references.id"],
            name=op.f("fk_universe_memberships_universe_id_universe_references"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_universe_memberships_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_universe_memberships")),
        sa.UniqueConstraint("user_id", "universe_id", name=op.f("uq_universe_memberships_user_id")),
    )
    op.create_index(
        op.f("ix_universe_memberships_next_check_at"),
        "universe_memberships",
        ["next_check_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_universe_memberships_universe_id"),
        "universe_memberships",
        ["universe_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_universe_memberships_user_id"), "universe_memberships", ["user_id"], unique=False
    )
    op.create_table(
        "control_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("backend_id", sa.String(length=40), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=True),
        sa.Column("membership_id", sa.Uuid(), nullable=True),
        sa.Column("logout_request_id", sa.Uuid(), nullable=True),
        sa.Column("account_revocation_id", sa.Uuid(), nullable=True),
        sa.Column("envelope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('pending', 'acknowledged')",
            name=op.f("ck_control_outbox_control_delivery_state"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_control_outbox_control_attempts")),
        sa.ForeignKeyConstraint(
            ["account_revocation_id"],
            ["account_revocations.id"],
            name=op.f("fk_control_outbox_account_revocation_id_account_revocations"),
        ),
        sa.ForeignKeyConstraint(
            ["logout_request_id"],
            ["logout_requests.id"],
            name=op.f("fk_control_outbox_logout_request_id_logout_requests"),
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["universe_memberships.id"],
            name=op.f("fk_control_outbox_membership_id_universe_memberships"),
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"],
            ["universe_references.id"],
            name=op.f("fk_control_outbox_universe_id_universe_references"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_outbox")),
    )
    op.create_index(
        op.f("ix_control_outbox_next_attempt_at"),
        "control_outbox",
        ["next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "uq_control_logout_target",
        "control_outbox",
        ["logout_request_id", "backend_id"],
        unique=True,
        postgresql_where=sa.text("logout_request_id IS NOT NULL"),
    )
    op.create_index(
        "uq_control_revocation_target",
        "control_outbox",
        ["account_revocation_id", "backend_id"],
        unique=True,
        postgresql_where=sa.text("account_revocation_id IS NOT NULL"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("control_outbox", "universe_memberships", "universe_references"):
        if connection.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError("Refusing populated control-plane downgrade")
    op.drop_index(
        "uq_control_revocation_target",
        table_name="control_outbox",
        postgresql_where=sa.text("account_revocation_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_control_logout_target",
        table_name="control_outbox",
        postgresql_where=sa.text("logout_request_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_control_outbox_next_attempt_at"), table_name="control_outbox")
    op.drop_table("control_outbox")
    op.drop_index(op.f("ix_universe_memberships_user_id"), table_name="universe_memberships")
    op.drop_index(op.f("ix_universe_memberships_universe_id"), table_name="universe_memberships")
    op.drop_index(op.f("ix_universe_memberships_next_check_at"), table_name="universe_memberships")
    op.drop_table("universe_memberships")
    op.drop_table("universe_references")
