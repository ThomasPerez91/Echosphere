"""Empire names, leaving a multi game and archiving a solo game (Q60)

Revision ID: p0008_game_life
Revises: p0007_invitations
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p0008_game_life"
down_revision = "p0007_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "universe_memberships", sa.Column("empire_name", sa.String(length=40), nullable=True)
    )
    op.add_column(
        "universe_memberships",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "universe_references",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "universe_references",
        sa.Column("left_seats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("universe_references", "left_seats")
    op.drop_column("universe_references", "archived_at")
    op.drop_column("universe_memberships", "left_at")
    op.drop_column("universe_memberships", "empire_name")
