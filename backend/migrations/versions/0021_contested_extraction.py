"""Contested extraction (EXP-02c, ruleset v0.12): an ATTACK may target a deposit.

Revision ID: 0021_contested_extraction
Revises: 0020_sandbox_games
Frozen DDL; additive: every existing ATTACK and engagement targets a planet.
"""

# ruff: noqa: E501
import sqlalchemy as sa
from alembic import op

revision = "0021_contested_extraction"
down_revision = "0020_sandbox_games"
branch_labels = None
depends_on = None

TARGET_OLD = "(kind IN ('COLONIZE','ATTACK')) = (target_planet_id IS NOT NULL)"
TARGET_NEW = "(kind = 'COLONIZE' AND target_planet_id IS NOT NULL) OR (kind = 'ATTACK' AND (target_planet_id IS NULL) <> (target_opportunity_id IS NULL)) OR (kind NOT IN ('COLONIZE','ATTACK') AND target_planet_id IS NULL)"
OPP_OLD = "(kind IN ('STUDY','EXTRACT')) = (target_opportunity_id IS NOT NULL)"
OPP_NEW = "(kind IN ('STUDY','EXTRACT') AND target_opportunity_id IS NOT NULL) OR kind = 'ATTACK' OR (kind NOT IN ('STUDY','EXTRACT','ATTACK') AND target_opportunity_id IS NULL)"


def checks(target, opportunity):
    for name, body in (("target", target), ("opportunity", opportunity)):
        op.execute(f"ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_{name}")
        op.execute(f"ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_{name} CHECK ({body})")


def upgrade():
    checks(TARGET_NEW, OPP_NEW)
    op.execute("ALTER TABLE combat_engagements ALTER COLUMN target_planet_id DROP NOT NULL")
    op.execute("ALTER TABLE combat_engagements ADD COLUMN target_opportunity_id UUID")
    op.execute(
        "ALTER TABLE combat_engagements ADD CONSTRAINT fk_combat_engagements_opportunity "
        "FOREIGN KEY (target_opportunity_id, universe_id) "
        "REFERENCES galaxy_opportunities (id, universe_id)"
    )
    op.execute(
        "ALTER TABLE combat_engagements ADD CONSTRAINT ck_combat_engagements_target "
        "CHECK ((target_planet_id IS NULL) <> (target_opportunity_id IS NULL))"
    )


def downgrade():
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM combat_engagements WHERE target_opportunity_id IS NOT NULL)")
    ).scalar():
        raise RuntimeError("Cannot downgrade live deposit attacks; archive explicitly")
    op.execute("ALTER TABLE combat_engagements DROP CONSTRAINT ck_combat_engagements_target")
    op.execute("ALTER TABLE combat_engagements DROP CONSTRAINT fk_combat_engagements_opportunity")
    op.execute("ALTER TABLE combat_engagements DROP COLUMN target_opportunity_id")
    op.execute("ALTER TABLE combat_engagements ALTER COLUMN target_planet_id SET NOT NULL")
    checks(TARGET_OLD, OPP_OLD)
