"""Combat MVP v0.7: stream fences, engagements, reports, ATTACK missions, DESTROYED fleets.

Revision ID: 0012_combat
Revises: 0011_first_ai
Frozen DDL; independent of runtime ORM models. No backfill: only v0.7+ Universes fight, and
every existing row already satisfies the widened constraints.
"""

# ruff: noqa: E501
import json

import sqlalchemy as sa
from alembic import op

revision = "0012_combat"
down_revision = "0011_first_ai"
branch_labels = None
depends_on = None

TABLES = [
    """
CREATE TABLE stream_fences (
	stream_id UUID NOT NULL, 
	universe_id UUID NOT NULL, 
	fence_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	owner VARCHAR(160) NOT NULL, 
	released_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_stream_fences PRIMARY KEY (id), 
	CONSTRAINT fk_stream_fences_stream_universe FOREIGN KEY(stream_id, universe_id) REFERENCES event_streams (id, universe_id), 
	CONSTRAINT uq_stream_fences_owner UNIQUE (stream_id, owner), 
	CONSTRAINT ck_stream_fences_owner CHECK (length(owner) BETWEEN 1 AND 160)
)
""",
    'CREATE INDEX ix_stream_fences_open ON stream_fences (stream_id, fence_at) WHERE released_at IS NULL',
    """
CREATE TABLE combat_engagements (
	universe_id UUID NOT NULL, 
	mission_id UUID NOT NULL, 
	attacker_empire_id UUID NOT NULL, 
	defender_empire_id UUID, 
	target_planet_id UUID NOT NULL, 
	target_system_id UUID NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	travel_arrival_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	battle_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	state VARCHAR(12) NOT NULL, 
	attempts INTEGER NOT NULL, 
	retry_at TIMESTAMP WITH TIME ZONE, 
	error_code VARCHAR(32), 
	cancelled_at TIMESTAMP WITH TIME ZONE, 
	snapshot JSONB, 
	result JSONB, 
	processed_at TIMESTAMP WITH TIME ZONE, 
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_combat_engagements PRIMARY KEY (id), 
	CONSTRAINT fk_combat_engagements_mission_id_fleet_missions FOREIGN KEY(mission_id, attacker_empire_id, universe_id) REFERENCES fleet_missions (id, empire_id, universe_id), 
	CONSTRAINT fk_combat_engagements_defender FOREIGN KEY(defender_empire_id, universe_id) REFERENCES empires (id, universe_id), 
	CONSTRAINT fk_combat_engagements_target_planet_id_planets FOREIGN KEY(target_planet_id, target_system_id, universe_id) REFERENCES planets (id, system_id, universe_id), 
	CONSTRAINT uq_combat_engagements_mission UNIQUE (mission_id), 
	CONSTRAINT uq_combat_engagements_scope UNIQUE (id, universe_id), 
	CONSTRAINT ck_combat_engagements_state CHECK (state IN ('pending','resolved','cancelled','blocked')), 
	CONSTRAINT ck_combat_engagements_timeline CHECK (travel_arrival_at >= started_at AND battle_at >= travel_arrival_at AND battle_at > started_at), 
	CONSTRAINT ck_combat_engagements_sides CHECK (defender_empire_id IS NULL OR defender_empire_id <> attacker_empire_id), 
	CONSTRAINT ck_combat_engagements_resolution CHECK ((state = 'resolved') = (processed_at IS NOT NULL AND result IS NOT NULL AND snapshot IS NOT NULL)), 
	CONSTRAINT ck_combat_engagements_attempts CHECK (attempts >= 0)
)
""",
    "CREATE INDEX ix_combat_engagements_due ON combat_engagements (battle_at, started_at, id) WHERE state = 'pending'",
    'CREATE INDEX ix_combat_engagements_defender ON combat_engagements (defender_empire_id, battle_at)',
    "CREATE INDEX ix_combat_engagements_system ON combat_engagements (universe_id, target_system_id) WHERE state IN ('pending','blocked')",
    """
CREATE TABLE combat_reports (
	engagement_id UUID NOT NULL, 
	empire_id UUID NOT NULL, 
	universe_id UUID NOT NULL, 
	role VARCHAR(12) NOT NULL, 
	battle_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	processed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	result JSONB NOT NULL, 
	CONSTRAINT pk_combat_reports PRIMARY KEY (engagement_id, empire_id), 
	CONSTRAINT fk_combat_reports_engagement_id_combat_engagements FOREIGN KEY(engagement_id, universe_id) REFERENCES combat_engagements (id, universe_id), 
	CONSTRAINT fk_combat_reports_empire_id_empires FOREIGN KEY(empire_id, universe_id) REFERENCES empires (id, universe_id), 
	CONSTRAINT ck_combat_reports_role CHECK (role IN ('attacker','defender')), 
	CONSTRAINT ck_combat_reports_processing CHECK (processed_at >= battle_at)
)
""",
    'CREATE INDEX ix_combat_reports_empire ON combat_reports (empire_id, battle_at)',
]
MISSION_CHECKS = {
    "kind": "kind IN ('DEPLOY','SURVEY','RETURN','COLONIZE','ATTACK')",
    "target": "(kind IN ('COLONIZE','ATTACK')) = (target_planet_id IS NOT NULL)",
    "route": "origin_id <> destination_id OR kind IN ('COLONIZE','ATTACK')",
    "deadline": "(kind = 'SURVEY' AND due_at > travel_arrival_at) "
    "OR (kind = 'ATTACK' AND due_at >= travel_arrival_at AND due_at > started_at) "
    "OR (kind NOT IN ('SURVEY','ATTACK') AND due_at = travel_arrival_at)",
    "recall_pair": "(recalled_at IS NULL) = (return_at IS NULL) "
    "OR (kind = 'ATTACK' AND recalled_at IS NULL AND return_at IS NOT NULL)",
    "recall": "recalled_at IS NULL OR (kind NOT IN ('RETURN','ATTACK') "
    "AND recalled_at >= started_at AND recalled_at < travel_arrival_at "
    "AND return_at = recalled_at + (recalled_at - started_at)) "
    "OR (kind = 'ATTACK' AND recalled_at >= started_at AND recalled_at < due_at "
    "AND return_at = CASE WHEN recalled_at < travel_arrival_at "
    "THEN recalled_at + (recalled_at - started_at) "
    "ELSE recalled_at + (travel_arrival_at - started_at) END)",
    "returning": "status <> 'returning' OR recalled_at IS NOT NULL "
    "OR (kind = 'ATTACK' AND return_at IS NOT NULL)",
}
PREVIOUS_MISSION_CHECKS = {
    "kind": "kind IN ('DEPLOY','SURVEY','RETURN','COLONIZE')",
    "target": "(kind = 'COLONIZE') = (target_planet_id IS NOT NULL)",
    "route": "origin_id <> destination_id OR kind = 'COLONIZE'",
    "deadline": "(kind = 'SURVEY' AND due_at > travel_arrival_at) "
    "OR (kind <> 'SURVEY' AND due_at = travel_arrival_at)",
    "recall_pair": "(recalled_at IS NULL) = (return_at IS NULL)",
    "recall": "recalled_at IS NULL OR (kind <> 'RETURN' AND recalled_at >= started_at "
    "AND recalled_at < travel_arrival_at "
    "AND return_at = recalled_at + (recalled_at - started_at))",
    "returning": "status <> 'returning' OR recalled_at IS NOT NULL",
}
ATTACK_RETURN = (
    "kind <> 'ATTACK' OR recalled_at IS NOT NULL OR return_at IS NULL "
    "OR return_at = due_at + (travel_arrival_at - started_at)"
)
PERMISSIONS = [
    "colony.read",
    "colony.construct",
    "colony.cancel",
    "research.read",
    "research.start",
    "research.cancel",
    "galaxy.read",
    "exploration.read",
    "exploration.start",
    "fleet.read",
    "fleet.build",
    "fleet.command",
    "colony.expand",
]


def missions(checks):
    for name, condition in checks.items():
        op.execute(f"ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_{name}")
        op.execute(f"ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_{name} CHECK ({condition})")


def fleets(statuses):
    op.execute("ALTER TABLE fleets DROP CONSTRAINT ck_fleets_status")
    op.execute(f"ALTER TABLE fleets ADD CONSTRAINT ck_fleets_status CHECK (status IN ({statuses}))")


def permissions(include_combat):
    op.drop_constraint(
        op.f("ck_empire_bindings_binding_permissions"), "empire_bindings", type_="check"
    )
    allowed = PERMISSIONS + (["combat.read", "combat.attack"] if include_combat else [])
    op.create_check_constraint(
        "binding_permissions",
        "empire_bindings",
        "jsonb_typeof(permissions) = 'array' AND jsonb_array_length(permissions) > 0 "
        "AND permissions <@ '" + json.dumps(allowed) + "'::jsonb",
    )


def upgrade():
    for ddl in TABLES:
        op.execute(ddl)
    fleets("'STATIONED','MOVING','MERGED','SETTLED','DESTROYED'")
    op.execute(
        "ALTER TABLE fleets ADD CONSTRAINT ck_fleets_destroyed "
        "CHECK (status <> 'DESTROYED' OR kind = 'TASK')"
    )
    missions(MISSION_CHECKS)
    op.execute(f"ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_attack_return CHECK ({ATTACK_RETURN})")
    permissions(True)


def downgrade():
    connection = op.get_bind()
    for check in [
        "SELECT EXISTS (SELECT 1 FROM combat_engagements)",
        "SELECT EXISTS (SELECT 1 FROM stream_fences)",
        "SELECT EXISTS (SELECT 1 FROM fleet_missions WHERE kind = 'ATTACK')",
        "SELECT EXISTS (SELECT 1 FROM fleets WHERE status = 'DESTROYED')",
    ]:
        if connection.execute(sa.text(check)).scalar():
            raise RuntimeError("Cannot downgrade live Combat data; archive explicitly")
    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM empire_bindings "
            "WHERE permissions ?| array['combat.read','combat.attack'])"
        )
    ).scalar():
        raise RuntimeError("Cannot downgrade live combat grants; revoke explicitly")
    permissions(False)
    op.execute("ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_attack_return")
    missions(PREVIOUS_MISSION_CHECKS)
    op.execute("ALTER TABLE fleets DROP CONSTRAINT ck_fleets_destroyed")
    fleets("'STATIONED','MOVING','MERGED','SETTLED'")
    for table in ("combat_reports", "combat_engagements", "stream_fences"):
        op.drop_table(table)
