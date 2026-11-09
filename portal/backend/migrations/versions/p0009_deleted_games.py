"""Games deleted by their creator (recette 09/11/2026)

Revision ID: p0009_deleted_games
Revises: p0008_game_life
"""

import sqlalchemy as sa
from alembic import op

revision = "p0009_deleted_games"
down_revision = "p0008_game_life"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "universe_references",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("universe_references", "deleted_at")
