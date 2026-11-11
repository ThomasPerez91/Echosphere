"""Test games (sandbox) chosen at creation (recette 10/11/2026).

Revision ID: 0020_sandbox_games
Revises: 0019_unit_delivery_regeneration
Frozen DDL; additive: every existing universe is a normal game.
"""

from alembic import op

revision = "0020_sandbox_games"
down_revision = "0019_unit_delivery_regeneration"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE universes ADD COLUMN sandbox BOOLEAN DEFAULT false NOT NULL")


def downgrade():
    op.execute("ALTER TABLE universes DROP COLUMN sandbox")
