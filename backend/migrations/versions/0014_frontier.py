"""Frontier presence (13B, ruleset v0.9): per-hop passages and a stationed Fleet protocol.

Revision ID: 0014_frontier
Revises: 0013_relations
Frozen DDL; independent of runtime ORM models. Additive: one new table, one nullable column and
its CHECK, plus the 'protocol' kind in the Fleet operation ledger. No backfill: only missions launched in v0.9 Universes record passages, and no
existing Fleet has a protocol. No right is added (protocols use fleet.command).
"""

# ruff: noqa: E501
import sqlalchemy as sa
from alembic import op

revision = "0014_frontier"
down_revision = "0013_relations"
branch_labels = None
depends_on = None

PROTOCOL = (
    "protocol IS NULL OR (kind = 'TASK' AND status = 'STATIONED' AND protocol IN "
    "('SURVEILLANCE','AMBUSH','INTERCEPTION','FRIENDLY_CONTACT'))"
)


OPERATIONS = "'split','merge','load','unload','recall'"


def operations(kinds):
    op.execute("ALTER TABLE fleet_operations DROP CONSTRAINT ck_fleet_operations_kind")
    op.execute(
        f"ALTER TABLE fleet_operations ADD CONSTRAINT ck_fleet_operations_kind CHECK (kind IN ({kinds}))"
    )


def upgrade():
    op.execute("""
CREATE TABLE fleet_mission_passages (
	mission_id UUID NOT NULL, 
	sequence INTEGER NOT NULL, 
	empire_id UUID NOT NULL, 
	universe_id UUID NOT NULL, 
	system_id UUID NOT NULL, 
	entered_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	direction VARCHAR(8) NOT NULL, 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT pk_fleet_mission_passages PRIMARY KEY (mission_id, sequence), 
	CONSTRAINT fk_fleet_mission_passages_mission FOREIGN KEY(mission_id, empire_id, universe_id) REFERENCES fleet_missions (id, empire_id, universe_id), 
	CONSTRAINT fk_fleet_mission_passages_system FOREIGN KEY(system_id, universe_id) REFERENCES galaxy_systems (system_id, universe_id), 
	CONSTRAINT ck_fleet_mission_passages_sequence CHECK (sequence >= 0), 
	CONSTRAINT ck_fleet_mission_passages_direction CHECK (direction IN ('outbound','return')), 
	CONSTRAINT ck_fleet_mission_passages_cancellation CHECK (cancelled_at IS NULL OR (direction = 'outbound' AND cancelled_at < entered_at))
)
""")
    op.execute(
        "CREATE INDEX ix_fleet_mission_passages_system ON fleet_mission_passages "
        "(universe_id, system_id, entered_at) WHERE cancelled_at IS NULL"
    )
    op.add_column("fleets", sa.Column("protocol", sa.String(length=20), nullable=True))
    op.execute(f"ALTER TABLE fleets ADD CONSTRAINT ck_fleets_protocol CHECK ({PROTOCOL})")
    operations(OPERATIONS + ",'protocol'")


def downgrade():
    connection = op.get_bind()
    for check in [
        "SELECT EXISTS (SELECT 1 FROM fleet_mission_passages)",
        "SELECT EXISTS (SELECT 1 FROM fleets WHERE protocol IS NOT NULL)",
        "SELECT EXISTS (SELECT 1 FROM fleet_operations WHERE kind = 'protocol')",
    ]:
        if connection.execute(sa.text(check)).scalar():
            raise RuntimeError("Cannot downgrade live Frontier data; archive explicitly")
    operations(OPERATIONS)
    op.execute("ALTER TABLE fleets DROP CONSTRAINT ck_fleets_protocol")
    op.drop_column("fleets", "protocol")
    op.drop_table("fleet_mission_passages")
