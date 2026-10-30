"""Game browser handoff and sessions

Revision ID: 0006_game_sessions
Revises: 0005_game_access
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_game_sessions"
down_revision = "0005_game_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_game_access_session_scope",
        "game_accesses",
        ["membership_id", "global_user_id", "universe_id"],
    )
    op.create_table(
        "game_pre_auths",
        sa.Column("peer_digest", sa.String(64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at = created_at + interval '5 minutes'",
            name=op.f("ck_game_pre_auths_pre_auth_lifetime"),
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], name=op.f("fk_game_pre_auths_universe_id_universes")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_pre_auths")),
        sa.UniqueConstraint("digest", name=op.f("uq_game_pre_auths_digest")),
    )
    op.create_index(
        "ix_game_pre_auths_peer_digest", "game_pre_auths", ["peer_digest"], unique=False
    )
    op.create_index(
        op.f("ix_game_pre_auths_expires_at"), "game_pre_auths", ["expires_at"], unique=False
    )
    op.create_table(
        "game_consumed_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pre_auth_id", sa.Uuid(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["pre_auth_id"],
            ["game_pre_auths.id"],
            name=op.f("fk_game_consumed_tickets_pre_auth_id_game_pre_auths"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_consumed_tickets")),
        sa.UniqueConstraint("pre_auth_id", name=op.f("uq_game_consumed_tickets_pre_auth_id")),
    )
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("global_user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("key_id", sa.String(length=64), nullable=False),
        sa.Column("account_epoch", sa.BigInteger(), nullable=False),
        sa.Column("device_epoch", sa.BigInteger(), nullable=False),
        sa.Column("access_epoch", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("logout_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at AND expires_at <= created_at + interval '8 hours' "
            "AND expires_at <= access_valid_until",
            name=op.f("ck_game_sessions_game_session_lifetime"),
        ),
        sa.CheckConstraint(
            "account_epoch >= 0 AND device_epoch >= 0 AND access_epoch >= 1",
            name=op.f("ck_game_sessions_game_session_epochs"),
        ),
        sa.CheckConstraint(
            "last_activity_at >= created_at AND last_activity_at < expires_at",
            name=op.f("ck_game_sessions_game_session_activity"),
        ),
        sa.ForeignKeyConstraint(
            ["global_user_id", "device_id"],
            ["game_devices.global_user_id", "game_devices.device_id"],
            name=op.f("fk_game_sessions_global_user_id_game_devices"),
        ),
        sa.ForeignKeyConstraint(
            ["global_user_id"],
            ["game_principals.global_user_id"],
            name=op.f("fk_game_sessions_global_user_id_game_principals"),
        ),
        sa.ForeignKeyConstraint(
            ["membership_id", "global_user_id", "universe_id"],
            [
                "game_accesses.membership_id",
                "game_accesses.global_user_id",
                "game_accesses.universe_id",
            ],
            name=op.f("fk_game_sessions_membership_id_game_accesses"),
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], name=op.f("fk_game_sessions_universe_id_universes")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_sessions")),
        sa.UniqueConstraint("digest", name=op.f("uq_game_sessions_digest")),
    )
    op.create_index(
        "uq_game_session_active_slot",
        "game_sessions",
        ["global_user_id", "device_id", "universe_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("game_sessions", "game_consumed_tickets", "game_pre_auths"):
        if connection.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError("Refusing populated Game session downgrade")
    op.drop_index(
        "uq_game_session_active_slot",
        table_name="game_sessions",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_table("game_sessions")
    op.drop_table("game_consumed_tickets")
    op.drop_index(op.f("ix_game_pre_auths_expires_at"), table_name="game_pre_auths")
    op.drop_index("ix_game_pre_auths_peer_digest", table_name="game_pre_auths")
    op.drop_table("game_pre_auths")
    op.drop_constraint("uq_game_access_session_scope", "game_accesses", type_="unique")
