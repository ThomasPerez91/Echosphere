"""Versioned colony economy, infrastructure and construction orders.

Revision ID: 0004_colony_economy
Revises: 0003_generic_event_streams
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_colony_economy"
down_revision = "0003_generic_event_streams"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "universe_economies",
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("ruleset_version", sa.String(length=32), nullable=False),
        sa.Column("ruleset_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["universe_id"],
            ["universes.id"],
            name=op.f("fk_universe_economies_universe_id_universes"),
        ),
        sa.PrimaryKeyConstraint("universe_id", name=op.f("pk_universe_economies")),
    )
    op.create_table(
        "colony_economies",
        sa.Column("colony_id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("next_order_sequence", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "next_order_sequence > 0", name=op.f("ck_colony_economies_positive_sequence")
        ),
        sa.ForeignKeyConstraint(
            ["colony_id", "universe_id"],
            ["colonies.id", "colonies.universe_id"],
            name="fk_economies_colony_universe",
        ),
        sa.ForeignKeyConstraint(
            ["colony_id"],
            ["colony_timelines.colony_id"],
            name=op.f("fk_colony_economies_colony_id_colony_timelines"),
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"],
            ["universe_economies.universe_id"],
            name=op.f("fk_colony_economies_universe_id_universe_economies"),
        ),
        sa.PrimaryKeyConstraint("colony_id", name=op.f("pk_colony_economies")),
        sa.UniqueConstraint("colony_id", "universe_id", name="uq_colony_economies_scope"),
    )
    op.create_table(
        "colony_infrastructures",
        sa.Column("colony_id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("sector_index", sa.Integer(), nullable=False),
        sa.Column("infrastructure_type", sa.String(length=64), nullable=False),
        sa.Column("level", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sector_index > 0 AND level >= 1", name=op.f("ck_colony_infrastructures_sector_level")
        ),
        sa.ForeignKeyConstraint(
            ["colony_id", "universe_id"],
            ["colony_economies.colony_id", "colony_economies.universe_id"],
            name="fk_infrastructures_economy_scope",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_colony_infrastructures")),
        sa.UniqueConstraint("colony_id", "sector_index", name="uq_infrastructures_sector"),
    )
    op.create_index(
        op.f("ix_colony_infrastructures_colony_id"),
        "colony_infrastructures",
        ["colony_id"],
        unique=False,
    )
    op.create_table(
        "construction_orders",
        sa.Column("colony_id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("infrastructure_type", sa.String(length=64), nullable=False),
        sa.Column("sector_index", sa.Integer(), nullable=False),
        sa.Column("target_level", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("applied_bonus_bps", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)",
            name=op.f("ck_construction_orders_cancellation"),
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name=op.f("ck_construction_orders_completion"),
        ),
        sa.CheckConstraint(
            "status != 'active' OR started_at IS NOT NULL",
            name=op.f("ck_construction_orders_active_start"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'active', 'completed', 'cancelled')",
            name=op.f("ck_construction_orders_status"),
        ),
        sa.CheckConstraint(
            "(started_at IS NULL) = (due_at IS NULL)", name=op.f("ck_construction_orders_schedule")
        ),
        sa.CheckConstraint(
            "sector_index > 0 AND target_level > 0 AND sequence > 0",
            name=op.f("ck_construction_orders_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["colony_id", "universe_id"],
            ["colony_economies.colony_id", "colony_economies.universe_id"],
            name="fk_orders_economy_scope",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_orders")),
        sa.UniqueConstraint("colony_id", "idempotency_key", name="uq_orders_key"),
        sa.UniqueConstraint("colony_id", "sequence", name="uq_orders_sequence"),
    )
    op.create_index(
        "ix_orders_one_active",
        "construction_orders",
        ["colony_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_orders_queue", "construction_orders", ["colony_id", "status", "sequence"], unique=False
    )


def downgrade() -> None:
    connection = op.get_bind()
    for table in [
        "construction_orders",
        "colony_infrastructures",
        "colony_economies",
        "universe_economies",
    ]:
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Cannot downgrade populated colony economy; archive it explicitly")
    op.drop_table("construction_orders")
    op.drop_table("colony_infrastructures")
    op.drop_table("colony_economies")
    op.drop_table("universe_economies")
