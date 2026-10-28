"""Move event ownership to universe-scoped streams without losing the 0002 history."""

import sqlalchemy as sa
from alembic import op

revision = "0003_generic_event_streams"
down_revision = "0002_colony_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_colonies_id_universe", "colonies", ["id", "universe_id"])
    op.create_table(
        "event_streams",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("cursor_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_sequence", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_event_streams"),
        sa.UniqueConstraint("id", "universe_id", name="uq_streams_id_universe"),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], name="fk_event_streams_universe_id_universes"
        ),
        sa.CheckConstraint("next_sequence > 0", name=op.f("ck_event_streams_positive_sequence")),
    )
    op.create_index("ix_streams_universe_id", "event_streams", ["universe_id"])
    op.add_column("colony_timelines", sa.Column("stream_id", sa.Uuid(), nullable=True))
    op.add_column("colony_timelines", sa.Column("universe_id", sa.Uuid(), nullable=True))
    # Legacy colony UUIDs provide a deterministic one-to-one backfill only. New streams use UUIDs
    # independent of the colony. No runtime code assumes these IDs are equal.
    op.execute("""
        INSERT INTO event_streams (id, universe_id, cursor_at, next_sequence)
        SELECT t.colony_id, c.universe_id, t.settled_at, t.next_sequence
        FROM colony_timelines t JOIN colonies c ON c.id = t.colony_id
    """)
    op.execute("""
        UPDATE colony_timelines t SET stream_id = t.colony_id, universe_id = c.universe_id
        FROM colonies c WHERE c.id = t.colony_id
    """)
    for column in ["stream_id", "universe_id"]:
        op.alter_column("colony_timelines", column, nullable=False)
    op.create_unique_constraint("uq_colony_timelines_stream", "colony_timelines", ["stream_id"])
    op.create_foreign_key(
        "fk_colony_timeline_colony_universe",
        "colony_timelines",
        "colonies",
        ["colony_id", "universe_id"],
        ["id", "universe_id"],
    )
    op.create_foreign_key(
        "fk_colony_timeline_stream_universe",
        "colony_timelines",
        "event_streams",
        ["stream_id", "universe_id"],
        ["id", "universe_id"],
    )
    op.add_column("scheduled_events", sa.Column("stream_id", sa.Uuid(), nullable=True))
    op.add_column("scheduled_events", sa.Column("universe_id", sa.Uuid(), nullable=True))
    op.execute("""
        UPDATE scheduled_events e SET stream_id = t.stream_id, universe_id = t.universe_id
        FROM colony_timelines t WHERE t.colony_id = e.colony_id
    """)
    for column in ["stream_id", "universe_id"]:
        op.alter_column("scheduled_events", column, nullable=False)
    op.create_foreign_key(
        "fk_events_stream_universe",
        "scheduled_events",
        "event_streams",
        ["stream_id", "universe_id"],
        ["id", "universe_id"],
    )
    op.drop_constraint(
        "fk_scheduled_events_colony_id_colony_timelines", "scheduled_events", type_="foreignkey"
    )
    op.drop_constraint("uq_events_colony_sequence", "scheduled_events", type_="unique")
    op.drop_constraint("uq_events_colony_key", "scheduled_events", type_="unique")
    op.drop_index("ix_events_colony_order", table_name="scheduled_events")
    op.create_unique_constraint(
        "uq_events_stream_sequence", "scheduled_events", ["stream_id", "sequence"]
    )
    op.create_unique_constraint(
        "uq_events_stream_key", "scheduled_events", ["stream_id", "idempotency_key"]
    )
    op.create_index(
        "ix_events_stream_order", "scheduled_events", ["stream_id", "due_at", "sequence"]
    )
    op.drop_column("scheduled_events", "colony_id")
    op.drop_constraint(
        "fk_colony_timelines_colony_id_colonies", "colony_timelines", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("ck_colony_timelines_positive_sequence"), "colony_timelines", type_="check"
    )
    op.drop_column("colony_timelines", "next_sequence")


def downgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("Downgrade requires an online representability check")
    connection = op.get_bind()
    unrepresentable = connection.execute(
        sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM event_streams s LEFT JOIN colony_timelines t ON t.stream_id = s.id
            WHERE t.colony_id IS NULL OR s.cursor_at <> t.settled_at
        )
    """)
    ).scalar_one()
    if unrepresentable:
        raise RuntimeError("Cannot downgrade: non-colony stream or unsettled economic cursor")
    # Refuse incompatible data before any DDL. Never delete generic events to force a downgrade.
    op.add_column("colony_timelines", sa.Column("next_sequence", sa.BigInteger(), nullable=True))
    op.execute("""
        UPDATE colony_timelines t SET next_sequence = s.next_sequence
        FROM event_streams s WHERE s.id = t.stream_id
    """)
    op.alter_column("colony_timelines", "next_sequence", nullable=False)
    op.create_check_constraint(
        op.f("ck_colony_timelines_positive_sequence"), "colony_timelines", "next_sequence > 0"
    )
    op.create_foreign_key(
        "fk_colony_timelines_colony_id_colonies",
        "colony_timelines",
        "colonies",
        ["colony_id"],
        ["id"],
    )
    op.add_column("scheduled_events", sa.Column("colony_id", sa.Uuid(), nullable=True))
    op.execute("""
        UPDATE scheduled_events e SET colony_id = t.colony_id
        FROM colony_timelines t WHERE t.stream_id = e.stream_id
    """)
    op.alter_column("scheduled_events", "colony_id", nullable=False)
    op.create_foreign_key(
        "fk_scheduled_events_colony_id_colony_timelines",
        "scheduled_events",
        "colony_timelines",
        ["colony_id"],
        ["colony_id"],
    )
    op.drop_constraint("fk_events_stream_universe", "scheduled_events", type_="foreignkey")
    op.drop_constraint("uq_events_stream_sequence", "scheduled_events", type_="unique")
    op.drop_constraint("uq_events_stream_key", "scheduled_events", type_="unique")
    op.drop_index("ix_events_stream_order", table_name="scheduled_events")
    op.create_unique_constraint(
        "uq_events_colony_sequence", "scheduled_events", ["colony_id", "sequence"]
    )
    op.create_unique_constraint(
        "uq_events_colony_key", "scheduled_events", ["colony_id", "idempotency_key"]
    )
    op.create_index(
        "ix_events_colony_order", "scheduled_events", ["colony_id", "due_at", "sequence"]
    )
    op.drop_column("scheduled_events", "stream_id")
    op.drop_column("scheduled_events", "universe_id")
    op.drop_constraint("fk_colony_timeline_stream_universe", "colony_timelines", type_="foreignkey")
    op.drop_constraint("fk_colony_timeline_colony_universe", "colony_timelines", type_="foreignkey")
    op.drop_constraint("uq_colony_timelines_stream", "colony_timelines", type_="unique")
    op.drop_column("colony_timelines", "stream_id")
    op.drop_column("colony_timelines", "universe_id")
    op.drop_table("event_streams")
    op.drop_constraint("uq_colonies_id_universe", "colonies", type_="unique")
