"""Frontier presence (13B, ruleset v0.9): passages, protocol periods, detections.

Revision ID: 0014_frontier
Revises: 0013_relations
Frozen DDL; independent of runtime ORM models. Additive: one new table, one nullable column and
its CHECK, the 'protocol' kind in the Fleet operation ledger, dated protocol periods,
frontier detections and the 'frontier' contact source (extension of a CHECK). No backfill: only missions launched in v0.9 Universes record passages, and no
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


SOURCES = "'combat','presence','diplomacy'"
DETECTION = [
    """
CREATE TABLE fleet_protocol_periods (
	fleet_id UUID NOT NULL, 
	empire_id UUID NOT NULL, 
	universe_id UUID NOT NULL, 
	system_id UUID NOT NULL, 
	protocol VARCHAR(20) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	ended_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_fleet_protocol_periods PRIMARY KEY (id), 
	CONSTRAINT fk_fleet_protocol_periods_fleet FOREIGN KEY(fleet_id, empire_id, universe_id) REFERENCES fleets (id, empire_id, universe_id), 
	CONSTRAINT fk_fleet_protocol_periods_system FOREIGN KEY(system_id, universe_id) REFERENCES galaxy_systems (system_id, universe_id), 
	CONSTRAINT ck_fleet_protocol_periods_protocol CHECK (protocol IN ('SURVEILLANCE','AMBUSH','INTERCEPTION','FRIENDLY_CONTACT')), 
	CONSTRAINT ck_fleet_protocol_periods_period CHECK (ended_at IS NULL OR ended_at >= started_at)
)
""",
    "CREATE UNIQUE INDEX uq_fleet_protocol_periods_open ON fleet_protocol_periods (fleet_id) WHERE ended_at IS NULL",
    "CREATE INDEX ix_fleet_protocol_periods_system ON fleet_protocol_periods (universe_id, system_id, started_at)",
    """
CREATE TABLE frontier_detections (
	universe_id UUID NOT NULL, 
	mission_id UUID NOT NULL, 
	sequence INTEGER NOT NULL, 
	watch_fleet_id UUID NOT NULL, 
	role VARCHAR(8) NOT NULL, 
	observer_empire_id UUID NOT NULL, 
	observed_empire_id UUID NOT NULL, 
	system_id UUID NOT NULL, 
	detected_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	identified BOOLEAN NOT NULL, 
	friendly BOOLEAN NOT NULL, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_frontier_detections PRIMARY KEY (id), 
	CONSTRAINT fk_frontier_detections_passage FOREIGN KEY(mission_id, sequence) REFERENCES fleet_mission_passages (mission_id, sequence), 
	CONSTRAINT fk_frontier_detections_watch_fleet FOREIGN KEY(watch_fleet_id) REFERENCES fleets (id), 
	CONSTRAINT fk_frontier_detections_observer FOREIGN KEY(observer_empire_id, universe_id) REFERENCES empires (id, universe_id), 
	CONSTRAINT fk_frontier_detections_observed FOREIGN KEY(observed_empire_id, universe_id) REFERENCES empires (id, universe_id), 
	CONSTRAINT uq_frontier_detections UNIQUE (mission_id, sequence, watch_fleet_id, role), 
	CONSTRAINT ck_frontier_detections_role CHECK (role IN ('watch','transit')), 
	CONSTRAINT ck_frontier_detections_sides CHECK (observer_empire_id <> observed_empire_id)
)
""",
    "CREATE INDEX ix_frontier_detections_observer ON frontier_detections (observer_empire_id, detected_at)",
]


def sources(kinds):
    op.execute("ALTER TABLE relation_contacts DROP CONSTRAINT ck_relation_contacts_source")
    op.execute(
        f"ALTER TABLE relation_contacts ADD CONSTRAINT ck_relation_contacts_source CHECK (first_source IN ({kinds}))"
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
    for ddl in DETECTION:
        op.execute(ddl)
    sources(SOURCES + ",'frontier'")


def downgrade():
    connection = op.get_bind()
    for check in [
        "SELECT EXISTS (SELECT 1 FROM fleet_mission_passages)",
        "SELECT EXISTS (SELECT 1 FROM fleets WHERE protocol IS NOT NULL)",
        "SELECT EXISTS (SELECT 1 FROM fleet_operations WHERE kind = 'protocol')",
        "SELECT EXISTS (SELECT 1 FROM fleet_protocol_periods)",
        "SELECT EXISTS (SELECT 1 FROM frontier_detections)",
        "SELECT EXISTS (SELECT 1 FROM relation_contacts WHERE first_source = 'frontier')",
    ]:
        if connection.execute(sa.text(check)).scalar():
            raise RuntimeError("Cannot downgrade live Frontier data; archive explicitly")
    sources(SOURCES)
    op.drop_table("frontier_detections")
    op.drop_table("fleet_protocol_periods")
    operations(OPERATIONS)
    op.execute("ALTER TABLE fleets DROP CONSTRAINT ck_fleets_protocol")
    op.drop_column("fleets", "protocol")
    op.drop_table("fleet_mission_passages")
