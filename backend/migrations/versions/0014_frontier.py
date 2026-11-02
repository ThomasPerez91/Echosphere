"""Frontier presence (13B, ruleset v0.9): passages, protocol periods, detections.

Revision ID: 0014_frontier
Revises: 0013_relations
Frozen DDL; independent of runtime ORM models. Additive: one new table, one nullable column and
its CHECK, the 'protocol' kind in the Fleet operation ledger, dated protocol periods,
frontier detections, the 'frontier' contact source (extension of a CHECK) and automatic
frontier encounters (B05 engagements, B06 retreats). No backfill: only missions launched in v0.9 Universes record passages, and no
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


ENCOUNTERS = [
    """
CREATE TABLE frontier_encounters (
	universe_id UUID NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	mission_id UUID NOT NULL, 
	sequence INTEGER NOT NULL, 
	period_id UUID NOT NULL, 
	watch_fleet_id UUID NOT NULL, 
	protocol VARCHAR(20) NOT NULL, 
	watcher_empire_id UUID NOT NULL, 
	mover_empire_id UUID NOT NULL, 
	system_id UUID NOT NULL, 
	encounter_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	state VARCHAR(12) NOT NULL, 
	attempts INTEGER NOT NULL, 
	retry_at TIMESTAMP WITH TIME ZONE, 
	error_code VARCHAR(32), 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	outcome VARCHAR(24), 
	result JSONB, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_frontier_encounters PRIMARY KEY (id), 
	CONSTRAINT fk_frontier_encounters_passage FOREIGN KEY(mission_id, sequence) REFERENCES fleet_mission_passages (mission_id, sequence), 
	CONSTRAINT fk_frontier_encounters_period FOREIGN KEY(period_id) REFERENCES fleet_protocol_periods (id), 
	CONSTRAINT fk_frontier_encounters_watch_fleet FOREIGN KEY(watch_fleet_id) REFERENCES fleets (id), 
	CONSTRAINT fk_frontier_encounters_watcher FOREIGN KEY(watcher_empire_id, universe_id) REFERENCES empires (id, universe_id), 
	CONSTRAINT fk_frontier_encounters_mover FOREIGN KEY(mover_empire_id, universe_id) REFERENCES empires (id, universe_id), 
	CONSTRAINT uq_frontier_encounters UNIQUE (mission_id, sequence, watch_fleet_id, kind), 
	CONSTRAINT ck_frontier_encounters_kind CHECK (kind IN ('engagement','retreat')), 
	CONSTRAINT ck_frontier_encounters_protocol CHECK ((kind = 'engagement' AND protocol IN ('AMBUSH','INTERCEPTION')) OR (kind = 'retreat' AND protocol = 'FRIENDLY_CONTACT')), 
	CONSTRAINT ck_frontier_encounters_state CHECK (state IN ('pending','resolved','cancelled','blocked')), 
	CONSTRAINT ck_frontier_encounters_sides CHECK (watcher_empire_id <> mover_empire_id), 
	CONSTRAINT ck_frontier_encounters_resolution CHECK ((state = 'resolved') = (processed_at IS NOT NULL AND outcome IS NOT NULL)), 
	CONSTRAINT ck_frontier_encounters_cancellation CHECK ((state = 'cancelled') = (cancelled_at IS NOT NULL)), 
	CONSTRAINT ck_frontier_encounters_attempts CHECK (attempts >= 0)
)
""",
    "CREATE INDEX ix_frontier_encounters_due ON frontier_encounters (encounter_at, id) WHERE state = 'pending'",
    "CREATE INDEX ix_frontier_encounters_watcher ON frontier_encounters (watcher_empire_id, encounter_at)",
    "CREATE INDEX ix_frontier_encounters_mover ON frontier_encounters (mover_empire_id, encounter_at)",
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
	CONSTRAINT ck_fleet_mission_passages_cancellation CHECK (cancelled_at IS NULL OR cancelled_at < entered_at)
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
    for ddl in ENCOUNTERS:
        op.execute(ddl)


def downgrade():
    connection = op.get_bind()
    for check in [
        "SELECT EXISTS (SELECT 1 FROM fleet_mission_passages)",
        "SELECT EXISTS (SELECT 1 FROM fleets WHERE protocol IS NOT NULL)",
        "SELECT EXISTS (SELECT 1 FROM fleet_operations WHERE kind = 'protocol')",
        "SELECT EXISTS (SELECT 1 FROM fleet_protocol_periods)",
        "SELECT EXISTS (SELECT 1 FROM frontier_detections)",
        "SELECT EXISTS (SELECT 1 FROM relation_contacts WHERE first_source = 'frontier')",
        "SELECT EXISTS (SELECT 1 FROM frontier_encounters)",
    ]:
        if connection.execute(sa.text(check)).scalar():
            raise RuntimeError("Cannot downgrade live Frontier data; archive explicitly")
    op.drop_table("frontier_encounters")
    sources(SOURCES)
    op.drop_table("frontier_detections")
    op.drop_table("fleet_protocol_periods")
    operations(OPERATIONS)
    op.execute("ALTER TABLE fleets DROP CONSTRAINT ck_fleets_protocol")
    op.drop_column("fleets", "protocol")
    op.drop_table("fleet_mission_passages")
