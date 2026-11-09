"""Self-service universe creation (UX-API-02)

Revision ID: p0006_creation
Revises: p0005_control
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p0006_creation"
down_revision = "p0005_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable additions only: operator-provisioned universes keep every field null.
    op.add_column("universe_references", sa.Column("created_by", sa.Uuid(), nullable=True))
    op.add_column("universe_references", sa.Column("creation_request_id", sa.Uuid(), nullable=True))
    op.add_column(
        "universe_references",
        sa.Column("start_request", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("universe_references", sa.Column("human_empire_id", sa.Uuid(), nullable=True))
    op.add_column(
        "universe_references", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_universe_references_created_by_users"),
        "universe_references",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_index(
        op.f("ix_universe_references_created_by"),
        "universe_references",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        "uq_universe_creation_request",
        "universe_references",
        ["created_by", "creation_request_id"],
        unique=True,
        postgresql_where=sa.text("creation_request_id IS NOT NULL"),
    )
    op.create_check_constraint(
        op.f("ck_universe_references_universe_creation_fields"),
        "universe_references",
        "(created_by IS NULL) = (creation_request_id IS NULL) "
        "AND (created_by IS NULL) = (start_request IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_universe_references_universe_creation_fields"), "universe_references", "check"
    )
    op.drop_index(
        "uq_universe_creation_request",
        table_name="universe_references",
        postgresql_where=sa.text("creation_request_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_universe_references_created_by"), table_name="universe_references")
    op.drop_constraint(
        op.f("fk_universe_references_created_by_users"), "universe_references", "foreignkey"
    )
    for column in ("started_at", "human_empire_id", "start_request", "creation_request_id",
                   "created_by"):
        op.drop_column("universe_references", column)
