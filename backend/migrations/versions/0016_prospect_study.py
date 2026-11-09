"""Prospection and study missions (EXP-02a, ruleset v0.10).

Revision ID: 0016_prospect_study
Revises: 0015_opportunities
Frozen DDL; independent of runtime ORM models. Additive: two mission kinds, a nullable target
opportunity on missions (with its CHECK and scoped FK), the analysis deadline and 0-hop route
extended to them, and the studies table. No backfill: no existing mission has these kinds.
"""

# ruff: noqa: E501
import sqlalchemy as sa
from alembic import op

revision = "0016_prospect_study"
down_revision = "0015_opportunities"
branch_labels = None
depends_on = None

OLD_KINDS = "'DEPLOY','SURVEY','RETURN','COLONIZE','ATTACK'"
NEW_KINDS = OLD_KINDS + ",'PROSPECT','STUDY'"
OLD_ROUTE = "origin_id <> destination_id OR kind IN ('COLONIZE','ATTACK')"
NEW_ROUTE = "origin_id <> destination_id OR kind IN ('COLONIZE','ATTACK','PROSPECT','STUDY')"
OLD_DEADLINE = (
    "(kind = 'SURVEY' AND due_at > travel_arrival_at) "
    "OR (kind = 'ATTACK' AND due_at >= travel_arrival_at AND due_at > started_at) "
    "OR (kind NOT IN ('SURVEY','ATTACK') AND due_at = travel_arrival_at)"
)
NEW_DEADLINE = (
    "(kind IN ('SURVEY','PROSPECT','STUDY') AND due_at > travel_arrival_at) "
    "OR (kind = 'ATTACK' AND due_at >= travel_arrival_at AND due_at > started_at) "
    "OR (kind NOT IN ('SURVEY','PROSPECT','STUDY','ATTACK') AND due_at = travel_arrival_at)"
)


def checks(kinds, route, deadline):
    for name, body in (("kind", f"kind IN ({kinds})"), ("route", route), ("deadline", deadline)):
        op.execute(f"ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_{name}")
        op.execute(f"ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_{name} CHECK ({body})")


def upgrade():
    op.execute("ALTER TABLE fleet_missions ADD COLUMN target_opportunity_id UUID")
    op.execute(
        "ALTER TABLE fleet_missions ADD CONSTRAINT fk_fleet_missions_target_opportunity "
        "FOREIGN KEY(target_opportunity_id, universe_id) REFERENCES galaxy_opportunities (id, universe_id)"
    )
    op.execute(
        "ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_opportunity "
        "CHECK ((kind = 'STUDY') = (target_opportunity_id IS NOT NULL))"
    )
    checks(NEW_KINDS, NEW_ROUTE, NEW_DEADLINE)
    op.execute("""
CREATE TABLE opportunity_studies (
	empire_id UUID NOT NULL, 
	opportunity_id UUID NOT NULL, 
	universe_id UUID NOT NULL, 
	mission_id UUID NOT NULL, 
	studied_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	data_credited BIGINT NOT NULL, 
	CONSTRAINT pk_opportunity_studies PRIMARY KEY (empire_id, opportunity_id), 
	CONSTRAINT fk_opportunity_studies_empire_id_empire_exploration FOREIGN KEY(empire_id, universe_id) REFERENCES empire_exploration (empire_id, universe_id), 
	CONSTRAINT fk_opportunity_studies_opportunity_id_galaxy_opportunities FOREIGN KEY(opportunity_id, universe_id) REFERENCES galaxy_opportunities (id, universe_id), 
	CONSTRAINT fk_opportunity_studies_mission_id_fleet_missions FOREIGN KEY(mission_id) REFERENCES fleet_missions (id), 
	CONSTRAINT uq_opportunity_studies_mission_id UNIQUE (mission_id), 
	CONSTRAINT ck_opportunity_studies_credited CHECK (data_credited >= 0)
)
""")


def downgrade():
    connection = op.get_bind()
    for check in [
        "SELECT EXISTS (SELECT 1 FROM opportunity_studies)",
        "SELECT EXISTS (SELECT 1 FROM fleet_missions WHERE kind IN ('PROSPECT','STUDY'))",
    ]:
        if connection.execute(sa.text(check)).scalar():
            raise RuntimeError("Cannot downgrade live prospection data; archive explicitly")
    op.execute("DROP TABLE opportunity_studies")
    checks(OLD_KINDS, OLD_ROUTE, OLD_DEADLINE)
    op.execute("ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_opportunity")
    op.execute("ALTER TABLE fleet_missions DROP CONSTRAINT fk_fleet_missions_target_opportunity")
    op.execute("ALTER TABLE fleet_missions DROP COLUMN target_opportunity_id")
