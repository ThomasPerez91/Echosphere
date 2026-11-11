"""Ship units delivered one at a time, deposit regeneration (user decisions 10/11/2026).

Revision ID: 0019_unit_delivery_regeneration
Revises: 0018_colony_names
Frozen DDL; additive. Orders accepted before keep their whole-batch delivery (their snapshot has
no "delivery" key); deposits regenerate only under rulesets that say so (v0.11).
"""

from alembic import op

revision = "0019_unit_delivery_regeneration"
down_revision = "0018_colony_names"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE ship_orders ADD COLUMN delivered INTEGER DEFAULT '0' NOT NULL")
    op.execute(
        "ALTER TABLE ship_orders ADD CONSTRAINT ck_ship_orders_delivered "
        "CHECK (delivered >= 0 AND delivered <= quantity)"
    )
    op.execute(
        "ALTER TABLE galaxy_opportunities ADD COLUMN regen_remainder BIGINT DEFAULT '0' NOT NULL"
    )


def downgrade():
    op.execute("ALTER TABLE galaxy_opportunities DROP COLUMN regen_remainder")
    op.execute("ALTER TABLE ship_orders DROP CONSTRAINT ck_ship_orders_delivered")
    op.execute("ALTER TABLE ship_orders DROP COLUMN delivered")
