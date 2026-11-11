"""Planetary defense (ruleset v0.13, DEF-01 validated on 11/11/2026): the condition of a defense
module (operational, disabled for lack of Flux, damaged in battle).

Revision ID: 0023_planetary_defense
Revises: 0022_galaxy_shapes
Frozen DDL; additive: every existing infrastructure keeps a NULL condition.
"""

import sqlalchemy as sa
from alembic import op

revision = "0023_planetary_defense"
down_revision = "0022_galaxy_shapes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "colony_infrastructures", sa.Column("condition", sa.String(16), nullable=True)
    )
    op.create_check_constraint(
        "defense_condition",
        "colony_infrastructures",
        "condition IS NULL OR condition IN ('operational', 'disabled', 'damaged')",
    )


def downgrade():
    op.drop_constraint(
        op.f("ck_colony_infrastructures_defense_condition"), "colony_infrastructures", type_="check"
    )
    op.drop_column("colony_infrastructures", "condition")
