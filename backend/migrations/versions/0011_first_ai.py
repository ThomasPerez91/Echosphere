"""Durable AI controllers/decisions and explicit bootstrap receipts; no backfill.

Frozen DDL, independent of runtime metadata. Historical Universes and permissions unchanged.
"""
# ruff: noqa: E501
import sqlalchemy as sa
from alembic import op

revision = "0011_first_ai"
down_revision = "0010_colonization"
branch_labels = None
depends_on = None

DDL = [
    """
CREATE TABLE ai_controllers (
	universe_id UUID NOT NULL, 
	empire_id UUID NOT NULL, 
	profile VARCHAR(32) NOT NULL, 
	policy_version VARCHAR(64) NOT NULL, 
	policy_digest VARCHAR(64) NOT NULL, 
	state VARCHAR(12) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	next_decision_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	sequence BIGINT NOT NULL, 
	memory JSONB NOT NULL, 
	attempts INTEGER NOT NULL, 
	retry_at TIMESTAMP WITH TIME ZONE, 
	error_code VARCHAR(32), 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_ai_controllers PRIMARY KEY (id), 
	CONSTRAINT fk_ai_controllers_empire_id_empires FOREIGN KEY(empire_id, universe_id) REFERENCES empires (id, universe_id), 
	CONSTRAINT uq_ai_controllers_empire_id UNIQUE (empire_id), 
	CONSTRAINT uq_ai_controller_scope UNIQUE (id, empire_id, universe_id), 
	CONSTRAINT ck_ai_controllers_state CHECK (state IN ('enabled','paused','blocked')), 
	CONSTRAINT ck_ai_controllers_profile CHECK (profile IN ('economic_cautious','expansionist')), 
	CONSTRAINT ck_ai_controllers_counters CHECK (sequence > 0 AND attempts >= 0), 
	CONSTRAINT ck_ai_controllers_deadline CHECK (next_decision_at > started_at)
)

""",
    """CREATE INDEX ix_ai_controllers_due ON ai_controllers (state, next_decision_at)""",
    """
CREATE TABLE ai_decisions (
	controller_id UUID NOT NULL, 
	sequence BIGINT NOT NULL, 
	universe_id UUID NOT NULL, 
	empire_id UUID NOT NULL, 
	planned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	observed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	outcome VARCHAR(12) NOT NULL, 
	observation JSONB NOT NULL, 
	trace JSONB NOT NULL, 
	CONSTRAINT pk_ai_decisions PRIMARY KEY (controller_id, sequence), 
	CONSTRAINT fk_ai_decisions_controller_id_ai_controllers FOREIGN KEY(controller_id, empire_id, universe_id) REFERENCES ai_controllers (id, empire_id, universe_id), 
	CONSTRAINT ck_ai_decisions_sequence CHECK (sequence > 0), 
	CONSTRAINT ck_ai_decisions_outcome CHECK (outcome IN ('wait','accepted','refusal'))
)

""",
    """
CREATE TABLE ai_bootstraps (
	universe_id UUID NOT NULL, 
	request_digest VARCHAR(64) NOT NULL, 
	request JSONB NOT NULL, 
	result JSONB NOT NULL, 
	CONSTRAINT pk_ai_bootstraps PRIMARY KEY (universe_id), 
	CONSTRAINT fk_ai_bootstraps_universe_id_universes FOREIGN KEY(universe_id) REFERENCES universes (id)
)

""",
 ]


def upgrade():
    for statement in DDL:
        op.execute(statement)


def downgrade():
    connection = op.get_bind()
    for table in ("ai_decisions", "ai_controllers", "ai_bootstraps"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Cannot downgrade live AI data; archive explicitly")
    op.drop_table("ai_decisions")
    op.drop_table("ai_controllers")
    op.drop_table("ai_bootstraps")
