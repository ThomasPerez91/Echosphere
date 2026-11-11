"""Extraction missions (EXP-02b, ruleset v0.10).

Revision ID: 0017_extraction
Revises: 0016_prospect_study
Frozen DDL; independent of runtime ORM models. Additive: the EXTRACT mission kind (target
opportunity, analysis-like deadline, 0-hop route, automatic way back without recall), the settlement cursor of a deposit and the
claims table. No backfill: no existing mission has this kind, every deposit starts unsettled.
"""

# ruff: noqa: E501
import sqlalchemy as sa
from alembic import op

revision = "0017_extraction"
down_revision = "0016_prospect_study"
branch_labels = None
depends_on = None

OLD_KINDS = "'DEPLOY','SURVEY','RETURN','COLONIZE','ATTACK','PROSPECT','STUDY'"
NEW_KINDS = OLD_KINDS + ",'EXTRACT'"
OLD_OPPORTUNITY = "(kind = 'STUDY') = (target_opportunity_id IS NOT NULL)"
NEW_OPPORTUNITY = "(kind IN ('STUDY','EXTRACT')) = (target_opportunity_id IS NOT NULL)"
OLD_ROUTE = "origin_id <> destination_id OR kind IN ('COLONIZE','ATTACK','PROSPECT','STUDY')"
NEW_ROUTE = "origin_id <> destination_id OR kind IN ('COLONIZE','ATTACK','PROSPECT','STUDY','EXTRACT')"
OLD_DEADLINE = (
    "(kind IN ('SURVEY','PROSPECT','STUDY') AND due_at > travel_arrival_at) "
    "OR (kind = 'ATTACK' AND due_at >= travel_arrival_at AND due_at > started_at) "
    "OR (kind NOT IN ('SURVEY','PROSPECT','STUDY','ATTACK') AND due_at = travel_arrival_at)"
)
NEW_DEADLINE = (
    "(kind IN ('SURVEY','PROSPECT','STUDY','EXTRACT') AND due_at > travel_arrival_at) "
    "OR (kind = 'ATTACK' AND due_at >= travel_arrival_at AND due_at > started_at) "
    "OR (kind NOT IN ('SURVEY','PROSPECT','STUDY','EXTRACT','ATTACK') AND due_at = travel_arrival_at)"
)
OLD_RECALL_PAIR = (
    "(recalled_at IS NULL) = (return_at IS NULL) "
    "OR (kind = 'ATTACK' AND recalled_at IS NULL AND return_at IS NOT NULL)"
)
NEW_RECALL_PAIR = (
    "(recalled_at IS NULL) = (return_at IS NULL) "
    "OR (kind IN ('ATTACK','EXTRACT') AND recalled_at IS NULL AND return_at IS NOT NULL)"
)
OLD_RETURNING = (
    "status <> 'returning' OR recalled_at IS NOT NULL OR (kind = 'ATTACK' AND return_at IS NOT NULL)"
)
NEW_RETURNING = (
    "status <> 'returning' OR recalled_at IS NOT NULL "
    "OR (kind IN ('ATTACK','EXTRACT') AND return_at IS NOT NULL)"
)


def checks(kinds, opportunity, route, deadline, recall_pair, returning):
    for name, body in (
        ("kind", f"kind IN ({kinds})"),
        ("opportunity", opportunity),
        ("route", route),
        ("deadline", deadline),
        ("recall_pair", recall_pair),
        ("returning", returning),
    ):
        op.execute(f"ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_{name}")
        op.execute(f"ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_{name} CHECK ({body})")


def upgrade():
    checks(NEW_KINDS, NEW_OPPORTUNITY, NEW_ROUTE, NEW_DEADLINE, NEW_RECALL_PAIR, NEW_RETURNING)
    op.execute("ALTER TABLE galaxy_opportunities ADD COLUMN settled_at TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE galaxy_opportunities ADD COLUMN settle_remainder BIGINT DEFAULT '0' NOT NULL")
    op.execute(
        "ALTER TABLE galaxy_opportunities ADD CONSTRAINT ck_galaxy_opportunities_settle_remainder "
        "CHECK (settle_remainder >= 0)"
    )
    op.execute("""
CREATE TABLE deposit_claims (
	mission_id UUID NOT NULL,
	empire_id UUID NOT NULL,
	universe_id UUID NOT NULL,
	opportunity_id UUID NOT NULL,
	extractors INTEGER NOT NULL,
	room BIGINT NOT NULL,
	active_from TIMESTAMP WITH TIME ZONE NOT NULL,
	active_until TIMESTAMP WITH TIME ZONE NOT NULL,
	credited BIGINT NOT NULL,
	CONSTRAINT pk_deposit_claims PRIMARY KEY (mission_id),
	CONSTRAINT fk_deposit_claims_empire_id_empire_exploration FOREIGN KEY(empire_id, universe_id) REFERENCES empire_exploration (empire_id, universe_id),
	CONSTRAINT fk_deposit_claims_opportunity_id_galaxy_opportunities FOREIGN KEY(opportunity_id, universe_id) REFERENCES galaxy_opportunities (id, universe_id),
	CONSTRAINT fk_deposit_claims_mission_id_fleet_missions FOREIGN KEY(mission_id) REFERENCES fleet_missions (id),
	CONSTRAINT ck_deposit_claims_extractors CHECK (extractors > 0),
	CONSTRAINT ck_deposit_claims_credited CHECK (room >= 0 AND credited >= 0 AND credited <= room),
	CONSTRAINT ck_deposit_claims_window CHECK (active_until >= active_from)
)
""")
    op.execute(
        "CREATE INDEX ix_deposit_claims_opportunity ON deposit_claims (opportunity_id, active_until)"
    )


def downgrade():
    connection = op.get_bind()
    for check in [
        "SELECT EXISTS (SELECT 1 FROM deposit_claims)",
        "SELECT EXISTS (SELECT 1 FROM fleet_missions WHERE kind = 'EXTRACT')",
    ]:
        if connection.execute(sa.text(check)).scalar():
            raise RuntimeError("Cannot downgrade live extraction data; archive explicitly")
    op.execute("DROP TABLE deposit_claims")
    op.execute("ALTER TABLE galaxy_opportunities DROP CONSTRAINT ck_galaxy_opportunities_settle_remainder")
    op.execute("ALTER TABLE galaxy_opportunities DROP COLUMN settle_remainder")
    op.execute("ALTER TABLE galaxy_opportunities DROP COLUMN settled_at")
    checks(OLD_KINDS, OLD_OPPORTUNITY, OLD_ROUTE, OLD_DEADLINE, OLD_RECALL_PAIR, OLD_RETURNING)
