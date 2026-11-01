"""Colonization: COLONIZE missions on a known planet, SETTLED fleets, founded colonies.

Revision ID: 0010_colonization
Revises: 0009_fleets
Frozen DDL; independent of runtime ORM models. No backfill: only v0.5+ Universes colonize, and
every existing row already satisfies the widened constraints.
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0010_colonization"
down_revision = "0009_fleets"
branch_labels = None
depends_on = None

UPGRADE = [
    "ALTER TABLE fleets DROP CONSTRAINT ck_fleets_status",
    "ALTER TABLE fleets ADD CONSTRAINT ck_fleets_status "
    "CHECK (status IN ('STATIONED','MOVING','MERGED','SETTLED'))",
    "ALTER TABLE fleets ADD CONSTRAINT ck_fleets_settled "
    "CHECK (status <> 'SETTLED' OR kind = 'TASK')",
    "ALTER TABLE fleet_missions ADD COLUMN target_planet_id UUID",
    "ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_kind",
    "ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_route",
    "ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_travel",
    "ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_kind "
    "CHECK (kind IN ('DEPLOY','SURVEY','RETURN','COLONIZE'))",
    "ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_target "
    "CHECK ((kind = 'COLONIZE') = (target_planet_id IS NOT NULL))",
    "ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_route "
    "CHECK (origin_id <> destination_id OR kind = 'COLONIZE')",
    "ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_travel "
    "CHECK ((origin_id <> destination_id AND travel_arrival_at > started_at) "
    "OR (origin_id = destination_id AND travel_arrival_at = started_at))",
    "ALTER TABLE fleet_missions ADD CONSTRAINT fk_fleet_missions_target_planet_knowledge "
    "FOREIGN KEY(empire_id, target_planet_id) REFERENCES planet_knowledge (empire_id, planet_id)",
    "ALTER TABLE fleet_missions ADD CONSTRAINT fk_fleet_missions_target_planet_system "
    "FOREIGN KEY(target_planet_id, destination_id, universe_id) "
    "REFERENCES planets (id, system_id, universe_id)",
    "CREATE UNIQUE INDEX ix_fleet_mission_colonize_active ON fleet_missions (empire_id) "
    "WHERE kind = 'COLONIZE' AND status = 'active'",
    "CREATE INDEX ix_fleet_mission_colonize_target ON fleet_missions "
    "(universe_id, target_planet_id) WHERE kind = 'COLONIZE' AND status = 'active'",
    "ALTER TABLE colonies ADD COLUMN founded_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE colonies ADD COLUMN founding_mission_id UUID",
    "ALTER TABLE colonies ADD CONSTRAINT uq_colonies_founding_mission UNIQUE (founding_mission_id)",
    "ALTER TABLE colonies ADD CONSTRAINT ck_colonies_founding "
    "CHECK ((founded_at IS NULL) = (founding_mission_id IS NULL))",
    "ALTER TABLE colonies ADD CONSTRAINT fk_colonies_founding_mission_fleet_missions "
    "FOREIGN KEY(founding_mission_id, empire_id, universe_id) "
    "REFERENCES fleet_missions (id, empire_id, universe_id)",
]
DOWNGRADE = [
    "ALTER TABLE colonies DROP CONSTRAINT fk_colonies_founding_mission_fleet_missions",
    "ALTER TABLE colonies DROP CONSTRAINT ck_colonies_founding",
    "ALTER TABLE colonies DROP CONSTRAINT uq_colonies_founding_mission",
    "ALTER TABLE colonies DROP COLUMN founding_mission_id",
    "ALTER TABLE colonies DROP COLUMN founded_at",
    "DROP INDEX ix_fleet_mission_colonize_target",
    "DROP INDEX ix_fleet_mission_colonize_active",
    "ALTER TABLE fleet_missions DROP CONSTRAINT fk_fleet_missions_target_planet_system",
    "ALTER TABLE fleet_missions DROP CONSTRAINT fk_fleet_missions_target_planet_knowledge",
    "ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_travel",
    "ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_route",
    "ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_target",
    "ALTER TABLE fleet_missions DROP CONSTRAINT ck_fleet_missions_kind",
    "ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_kind "
    "CHECK (kind IN ('DEPLOY','SURVEY','RETURN'))",
    "ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_route "
    "CHECK (origin_id <> destination_id)",
    "ALTER TABLE fleet_missions ADD CONSTRAINT ck_fleet_missions_travel "
    "CHECK (travel_arrival_at > started_at)",
    "ALTER TABLE fleet_missions DROP COLUMN target_planet_id",
    "ALTER TABLE fleets DROP CONSTRAINT ck_fleets_settled",
    "ALTER TABLE fleets DROP CONSTRAINT ck_fleets_status",
    "ALTER TABLE fleets ADD CONSTRAINT ck_fleets_status "
    "CHECK (status IN ('STATIONED','MOVING','MERGED'))",
]
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
]


def permissions(include_expansion):
    op.drop_constraint(
        op.f("ck_empire_bindings_binding_permissions"), "empire_bindings", type_="check"
    )
    allowed = PERMISSIONS + (["colony.expand"] if include_expansion else [])
    op.create_check_constraint(
        "binding_permissions",
        "empire_bindings",
        "jsonb_typeof(permissions) = 'array' AND jsonb_array_length(permissions) > 0 "
        "AND permissions <@ '" + json.dumps(allowed) + "'::jsonb",
    )


def upgrade():
    for ddl in UPGRADE:
        op.execute(ddl)
    permissions(True)


def downgrade():
    connection = op.get_bind()
    for check in [
        "SELECT EXISTS (SELECT 1 FROM fleet_missions WHERE kind = 'COLONIZE')",
        "SELECT EXISTS (SELECT 1 FROM fleets WHERE status = 'SETTLED')",
        "SELECT EXISTS (SELECT 1 FROM colonies WHERE founding_mission_id IS NOT NULL)",
    ]:
        if connection.execute(sa.text(check)).scalar():
            raise RuntimeError("Cannot downgrade live Colonization data; archive explicitly")
    if connection.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM empire_bindings WHERE permissions ? 'colony.expand')")
    ).scalar():
        raise RuntimeError("Cannot downgrade live colony.expand grants; revoke explicitly")
    permissions(False)
    for ddl in DOWNGRADE:
        op.execute(ddl)
