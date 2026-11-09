"""Colony names chosen by the player (recette 09/11/2026).

Revision ID: 0018_colony_names
Revises: 0017_extraction
Frozen DDL; additive: NULL keeps the planet name.
"""

from alembic import op

revision = "0018_colony_names"
down_revision = "0017_extraction"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE colonies ADD COLUMN name VARCHAR(40)")


def downgrade():
    op.execute("ALTER TABLE colonies DROP COLUMN name")
