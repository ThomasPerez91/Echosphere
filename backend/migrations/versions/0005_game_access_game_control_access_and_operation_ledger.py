"""Game control access and operation ledger

Revision ID: 0005_game_access
Revises: 0004_colony_economy
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_game_access"
down_revision = "0004_colony_economy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "control_operations",
        sa.Column("service_id", sa.String(length=40), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("service_id", "operation_id", name=op.f("pk_control_operations")),
    )
    op.create_table(
        "game_principals",
        sa.Column("global_user_id", sa.Uuid(), nullable=False),
        sa.Column("account_epoch", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("account_epoch >= 0", name=op.f("ck_game_principals_principal_epoch")),
        sa.PrimaryKeyConstraint("global_user_id", name=op.f("pk_game_principals")),
    )
    op.create_table(
        "game_accesses",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("global_user_id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("access_epoch", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("portal_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_digest", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'revoked')",
            name=op.f("ck_game_accesses_access_status"),
        ),
        sa.CheckConstraint(
            "valid_until > portal_confirmed_at "
            "AND valid_until <= portal_confirmed_at + interval '8 hours'",
            name=op.f("ck_game_accesses_access_lifetime"),
        ),
        sa.CheckConstraint(
            "revision >= 1 AND access_epoch >= 1", name=op.f("ck_game_accesses_access_revision")
        ),
        sa.ForeignKeyConstraint(
            ["global_user_id"],
            ["game_principals.global_user_id"],
            name=op.f("fk_game_accesses_global_user_id_game_principals"),
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], name=op.f("fk_game_accesses_universe_id_universes")
        ),
        sa.PrimaryKeyConstraint("membership_id", name=op.f("pk_game_accesses")),
        sa.UniqueConstraint(
            "global_user_id", "universe_id", name=op.f("uq_game_accesses_global_user_id")
        ),
        sa.UniqueConstraint(
            "membership_id", "universe_id", name=op.f("uq_game_accesses_membership_id")
        ),
    )
    op.create_index(
        op.f("ix_game_accesses_global_user_id"), "game_accesses", ["global_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_game_accesses_universe_id"), "game_accesses", ["universe_id"], unique=False
    )
    op.create_table(
        "game_devices",
        sa.Column("global_user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("device_epoch", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("device_epoch >= 0", name=op.f("ck_game_devices_device_epoch")),
        sa.ForeignKeyConstraint(
            ["global_user_id"],
            ["game_principals.global_user_id"],
            name=op.f("fk_game_devices_global_user_id_game_principals"),
        ),
        sa.PrimaryKeyConstraint("global_user_id", "device_id", name=op.f("pk_game_devices")),
    )
    op.create_table(
        "empire_bindings",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("empire_id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(permissions) = 'array' "
            "AND jsonb_array_length(permissions) > 0 "
            'AND permissions <@ \'["colony.read","colony.construct","colony.cancel"]\'::jsonb',
            name=op.f("ck_empire_bindings_binding_permissions"),
        ),
        sa.ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name=op.f("fk_empire_bindings_empire_id_empires"),
        ),
        sa.ForeignKeyConstraint(
            ["membership_id", "universe_id"],
            ["game_accesses.membership_id", "game_accesses.universe_id"],
            name=op.f("fk_empire_bindings_membership_id_game_accesses"),
        ),
        sa.PrimaryKeyConstraint("membership_id", "empire_id", name=op.f("pk_empire_bindings")),
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "control_operations",
        "empire_bindings",
        "game_accesses",
        "game_devices",
        "game_principals",
    ):
        if connection.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError("Refusing populated control-plane downgrade")
    op.drop_table("empire_bindings")
    op.drop_table("game_devices")
    op.drop_index(op.f("ix_game_accesses_universe_id"), table_name="game_accesses")
    op.drop_index(op.f("ix_game_accesses_global_user_id"), table_name="game_accesses")
    op.drop_table("game_accesses")
    op.drop_table("game_principals")
    op.drop_table("control_operations")
