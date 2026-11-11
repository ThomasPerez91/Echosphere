"""Galaxy shapes (ruleset v0.12, recette 11/11/2026): the density layout a shaped world was drawn
from, kept for the map backdrop.

Revision ID: 0022_galaxy_shapes
Revises: 0021_contested_extraction
Frozen DDL; additive: every existing world is a lattice blob without layout.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_galaxy_shapes"
down_revision = "0021_contested_extraction"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "universe_galaxies", sa.Column("layout", postgresql.JSONB(), nullable=True)
    )


def downgrade():
    op.drop_column("universe_galaxies", "layout")
