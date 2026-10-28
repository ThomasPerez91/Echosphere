"""Colony timelines, exact resource anchors and recoverable events."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_colony_time"
down_revision = "0001_world_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "colony_timelines",
        sa.Column("colony_id", sa.Uuid(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_sequence", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("colony_id", name="pk_colony_timelines"),
        sa.ForeignKeyConstraint(
            ["colony_id"], ["colonies.id"], name="fk_colony_timelines_colony_id_colonies"
        ),
        sa.CheckConstraint("next_sequence > 0", name=op.f("ck_colony_timelines_positive_sequence")),
    )
    op.create_table(
        "resource_balances",
        sa.Column("colony_id", sa.Uuid(), nullable=False),
        sa.Column("resource", sa.String(8), nullable=False),
        sa.Column("stock", sa.BigInteger(), nullable=False),
        sa.Column("rate_per_hour", sa.BigInteger(), nullable=False),
        sa.Column("remainder", sa.BigInteger(), nullable=False),
        sa.Column("capacity", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("colony_id", "resource", name="pk_resource_balances"),
        sa.ForeignKeyConstraint(
            ["colony_id"],
            ["colony_timelines.colony_id"],
            name="fk_resource_balances_colony_id_colony_timelines",
        ),
        sa.CheckConstraint(
            "resource IN ('alloys', 'flux', 'data')",
            name=op.f("ck_resource_balances_resource_kind"),
        ),
        sa.CheckConstraint(
            "stock >= 0 AND rate_per_hour >= 0",
            name=op.f("ck_resource_balances_nonnegative_amounts"),
        ),
        sa.CheckConstraint(
            "remainder >= 0 AND remainder < 3600000000",
            name=op.f("ck_resource_balances_valid_remainder"),
        ),
        sa.CheckConstraint(
            "capacity IS NULL OR (capacity >= 0 AND stock <= capacity)",
            name=op.f("ck_resource_balances_capacity"),
        ),
    )
    op.create_table(
        "scheduled_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("colony_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_scheduled_events"),
        sa.ForeignKeyConstraint(
            ["colony_id"],
            ["colony_timelines.colony_id"],
            name="fk_scheduled_events_colony_id_colony_timelines",
        ),
        sa.UniqueConstraint("colony_id", "sequence", name="uq_events_colony_sequence"),
        sa.UniqueConstraint("colony_id", "idempotency_key", name="uq_events_colony_key"),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'blocked')", name=op.f("ck_scheduled_events_status")
        ),
        sa.CheckConstraint(
            "sequence > 0 AND attempts >= 0", name=op.f("ck_scheduled_events_counters")
        ),
        sa.CheckConstraint(
            "(status = 'completed') = (completed_at IS NOT NULL)",
            name=op.f("ck_scheduled_events_completion"),
        ),
    )
    op.create_index(
        "ix_events_colony_order", "scheduled_events", ["colony_id", "due_at", "sequence"]
    )
    op.create_index(
        "ix_events_pending", "scheduled_events", ["status", "due_at", "next_attempt_at"]
    )


def downgrade() -> None:
    op.drop_table("scheduled_events")
    op.drop_table("resource_balances")
    op.drop_table("colony_timelines")
