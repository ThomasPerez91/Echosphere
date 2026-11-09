"""Galaxy opportunities (EXP-01, ruleset v0.10): deposits, curiosities, Empire knowledge.

Revision ID: 0015_opportunities
Revises: 0014_frontier
Frozen DDL; independent of runtime ORM models. Additive: two new tables. No backfill: only
Universes generated with a v0.10 ruleset receive opportunities, at world generation.
"""

# ruff: noqa: E501
import sqlalchemy as sa
from alembic import op

revision = "0015_opportunities"
down_revision = "0014_frontier"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE galaxy_opportunities (
	universe_id UUID NOT NULL, 
	system_id UUID NOT NULL, 
	ordinal INTEGER NOT NULL, 
	family VARCHAR(10) NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	tier VARCHAR(12) NOT NULL, 
	resource VARCHAR(8), 
	reserve_total BIGINT, 
	reserve_remaining BIGINT, 
	throughput_per_hour BIGINT, 
	study_seconds INTEGER, 
	data_reward BIGINT, 
	dossier INTEGER, 
	clue INTEGER, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_galaxy_opportunities PRIMARY KEY (id), 
	CONSTRAINT fk_galaxy_opportunities_system_id_galaxy_systems FOREIGN KEY(system_id, universe_id) REFERENCES galaxy_systems (system_id, universe_id), 
	CONSTRAINT uq_galaxy_opportunity_scope UNIQUE (id, universe_id), 
	CONSTRAINT uq_galaxy_opportunity_ordinal UNIQUE (system_id, ordinal), 
	CONSTRAINT ck_galaxy_opportunities_ordinal CHECK (ordinal >= 0), 
	CONSTRAINT ck_galaxy_opportunities_family CHECK (family IN ('deposit','curiosity')), 
	CONSTRAINT ck_galaxy_opportunities_tier CHECK (tier IN ('common','remarkable')), 
	CONSTRAINT ck_galaxy_opportunities_shape CHECK ((family = 'deposit' AND resource IN ('alloys','flux','data') AND reserve_total > 0 AND reserve_remaining >= 0 AND reserve_remaining <= reserve_total AND throughput_per_hour > 0 AND study_seconds IS NULL AND data_reward IS NULL) OR (family = 'curiosity' AND resource IS NULL AND reserve_total IS NULL AND reserve_remaining IS NULL AND throughput_per_hour IS NULL AND study_seconds > 0 AND data_reward > 0)), 
	CONSTRAINT ck_galaxy_opportunities_dossier CHECK ((dossier IS NULL AND clue IS NULL) OR (family = 'curiosity' AND dossier >= 0 AND clue >= 0))
)
""")
    op.execute(
        "CREATE INDEX ix_galaxy_opportunities_system ON galaxy_opportunities (universe_id, system_id)"
    )
    op.execute("""
CREATE TABLE opportunity_knowledge (
	empire_id UUID NOT NULL, 
	opportunity_id UUID NOT NULL, 
	universe_id UUID NOT NULL, 
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	observed_reserve BIGINT, 
	CONSTRAINT pk_opportunity_knowledge PRIMARY KEY (empire_id, opportunity_id), 
	CONSTRAINT fk_opportunity_knowledge_empire_id_empire_exploration FOREIGN KEY(empire_id, universe_id) REFERENCES empire_exploration (empire_id, universe_id), 
	CONSTRAINT fk_opportunity_knowledge_opportunity_id_galaxy_opportunities FOREIGN KEY(opportunity_id, universe_id) REFERENCES galaxy_opportunities (id, universe_id), 
	CONSTRAINT ck_opportunity_knowledge_observed CHECK (observed_reserve IS NULL OR observed_reserve >= 0)
)
""")


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM galaxy_opportunities)")).scalar():
        raise RuntimeError("Cannot downgrade live opportunities; archive explicitly")
    op.execute("DROP TABLE opportunity_knowledge")
    op.execute("DROP TABLE galaxy_opportunities")
