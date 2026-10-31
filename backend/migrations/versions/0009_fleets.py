"""Fleets: production orders, stationed/moving fleets, missions, cargo and reports.

Revision ID: 0009_fleets
Revises: 0008_galaxy_exploration
Frozen DDL; independent of runtime ORM models. No backfill: only v0.4+ Universes get Fleets.
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0009_fleets"
down_revision = "0008_galaxy_exploration"
branch_labels = None
depends_on = None

TABLES = [
    [
        "ship_orders",
        """
CREATE TABLE ship_orders (
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
colony_id UUID NOT NULL,
ship_class VARCHAR(32) NOT NULL,
quantity INTEGER NOT NULL,
sequence BIGINT NOT NULL,
status VARCHAR(12) NOT NULL,
idempotency_key VARCHAR(160) NOT NULL,
snapshot JSONB NOT NULL,
refunded JSONB,
accepted_at TIMESTAMP WITH TIME ZONE NOT NULL,
started_at TIMESTAMP WITH TIME ZONE,
due_at TIMESTAMP WITH TIME ZONE,
completed_at TIMESTAMP WITH TIME ZONE,
cancelled_at TIMESTAMP WITH TIME ZONE,
id UUID DEFAULT gen_random_uuid() NOT NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
CONSTRAINT pk_ship_orders PRIMARY KEY (id),
CONSTRAINT fk_ship_orders_empire_id_empire_exploration FOREIGN KEY(empire_id, universe_id)
REFERENCES empire_exploration (empire_id, universe_id),
CONSTRAINT fk_ship_orders_colony_id_colonies FOREIGN KEY(colony_id, empire_id, universe_id)
REFERENCES colonies (id, empire_id, universe_id),
CONSTRAINT uq_ship_order_key UNIQUE (empire_id, idempotency_key),
CONSTRAINT uq_ship_order_sequence UNIQUE (colony_id, sequence),
CONSTRAINT ck_ship_orders_quantity CHECK (quantity > 0 AND sequence > 0),
CONSTRAINT ck_ship_orders_status CHECK (status IN ('queued','active','completed','cancelled')),
CONSTRAINT ck_ship_orders_queued CHECK (status <> 'queued' OR (started_at IS NULL AND due_at
IS NULL)),
CONSTRAINT ck_ship_orders_schedule CHECK (status NOT IN ('active','completed') OR (started_at
IS NOT NULL AND due_at > started_at)),
CONSTRAINT ck_ship_orders_completion CHECK ((status = 'completed') = (completed_at IS NOT
NULL)),
CONSTRAINT ck_ship_orders_cancellation CHECK ((status = 'cancelled') = (cancelled_at IS NOT
NULL AND refunded IS NOT NULL))
)
""",
    ],
    [
        "fleets",
        """
CREATE TABLE fleets (
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
home_colony_id UUID NOT NULL,
kind VARCHAR(12) NOT NULL,
status VARCHAR(12) NOT NULL,
system_id UUID,
active_mission_id UUID,
name VARCHAR(80) NOT NULL,
id UUID DEFAULT gen_random_uuid() NOT NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
CONSTRAINT pk_fleets PRIMARY KEY (id),
CONSTRAINT fk_fleets_empire_id_empire_exploration FOREIGN KEY(empire_id, universe_id)
REFERENCES empire_exploration (empire_id, universe_id),
CONSTRAINT fk_fleets_home_colony_id_colonies FOREIGN KEY(home_colony_id, empire_id,
universe_id) REFERENCES colonies (id, empire_id, universe_id),
CONSTRAINT fk_fleets_empire_id_system_knowledge FOREIGN KEY(empire_id, system_id, universe_id)
REFERENCES system_knowledge (empire_id, system_id, universe_id),
CONSTRAINT uq_fleet_scope UNIQUE (id, empire_id, universe_id),
CONSTRAINT uq_fleet_active_mission UNIQUE (active_mission_id),
CONSTRAINT ck_fleets_kind CHECK (kind IN ('GARRISON','TASK')),
CONSTRAINT ck_fleets_status CHECK (status IN ('STATIONED','MOVING')),
CONSTRAINT ck_fleets_location CHECK ((status = 'STATIONED') = (system_id IS NOT NULL)),
CONSTRAINT ck_fleets_engagement CHECK ((status = 'MOVING') = (active_mission_id IS NOT NULL)),
CONSTRAINT ck_fleets_garrison CHECK (kind <> 'GARRISON' OR status = 'STATIONED'),
CONSTRAINT ck_fleets_name CHECK (length(trim(name)) > 0)
)
""",
    ],
    [
        "fleet_stacks",
        """
CREATE TABLE fleet_stacks (
fleet_id UUID NOT NULL,
ship_class VARCHAR(32) NOT NULL,
count INTEGER NOT NULL,
CONSTRAINT pk_fleet_stacks PRIMARY KEY (fleet_id, ship_class),
CONSTRAINT ck_fleet_stacks_count CHECK (count > 0),
CONSTRAINT fk_fleet_stacks_fleet_id_fleets FOREIGN KEY(fleet_id) REFERENCES fleets (id)
)
""",
    ],
    [
        "fleet_cargo",
        """
CREATE TABLE fleet_cargo (
fleet_id UUID NOT NULL,
resource VARCHAR(8) NOT NULL,
amount BIGINT NOT NULL,
CONSTRAINT pk_fleet_cargo PRIMARY KEY (fleet_id, resource),
CONSTRAINT ck_fleet_cargo_resource CHECK (resource IN ('alloys','flux','data')),
CONSTRAINT ck_fleet_cargo_amount CHECK (amount > 0),
CONSTRAINT fk_fleet_cargo_fleet_id_fleets FOREIGN KEY(fleet_id) REFERENCES fleets (id)
)
""",
    ],
    [
        "fleet_missions",
        """
CREATE TABLE fleet_missions (
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
fleet_id UUID NOT NULL,
kind VARCHAR(12) NOT NULL,
status VARCHAR(12) NOT NULL,
origin_id UUID NOT NULL,
destination_id UUID NOT NULL,
payer_colony_id UUID NOT NULL,
idempotency_key VARCHAR(160) NOT NULL,
snapshot JSONB NOT NULL,
started_at TIMESTAMP WITH TIME ZONE NOT NULL,
travel_arrival_at TIMESTAMP WITH TIME ZONE NOT NULL,
due_at TIMESTAMP WITH TIME ZONE NOT NULL,
recalled_at TIMESTAMP WITH TIME ZONE,
return_at TIMESTAMP WITH TIME ZONE,
completed_at TIMESTAMP WITH TIME ZONE,
id UUID DEFAULT gen_random_uuid() NOT NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
CONSTRAINT pk_fleet_missions PRIMARY KEY (id),
CONSTRAINT fk_fleet_missions_fleet_id_fleets FOREIGN KEY(fleet_id, empire_id, universe_id)
REFERENCES fleets (id, empire_id, universe_id),
CONSTRAINT fk_fleet_missions_origin_system_knowledge FOREIGN KEY(empire_id, origin_id,
universe_id) REFERENCES system_knowledge (empire_id, system_id, universe_id),
CONSTRAINT fk_fleet_missions_destination_system_knowledge FOREIGN KEY(empire_id,
destination_id, universe_id) REFERENCES system_knowledge (empire_id, system_id, universe_id),
CONSTRAINT fk_fleet_missions_payer_colony_id_colonies FOREIGN KEY(payer_colony_id, empire_id,
universe_id) REFERENCES colonies (id, empire_id, universe_id),
CONSTRAINT uq_fleet_mission_fleet UNIQUE (id, fleet_id),
CONSTRAINT uq_fleet_mission_scope UNIQUE (id, empire_id, universe_id),
CONSTRAINT uq_fleet_mission_key UNIQUE (empire_id, idempotency_key),
CONSTRAINT ck_fleet_missions_kind CHECK (kind IN ('DEPLOY','SURVEY','RETURN')),
CONSTRAINT ck_fleet_missions_status CHECK (status IN ('active','returning','completed')),
CONSTRAINT ck_fleet_missions_route CHECK (origin_id <> destination_id),
CONSTRAINT ck_fleet_missions_travel CHECK (travel_arrival_at > started_at),
CONSTRAINT ck_fleet_missions_deadline CHECK ((kind = 'SURVEY' AND due_at > travel_arrival_at)
OR (kind <> 'SURVEY' AND due_at = travel_arrival_at)),
CONSTRAINT ck_fleet_missions_recall_pair CHECK ((recalled_at IS NULL) = (return_at IS NULL)),
CONSTRAINT ck_fleet_missions_recall CHECK (recalled_at IS NULL OR (kind <> 'RETURN' AND
recalled_at >= started_at AND recalled_at < travel_arrival_at AND return_at = recalled_at +
(recalled_at - started_at))),
CONSTRAINT ck_fleet_missions_returning CHECK (status <> 'returning' OR recalled_at IS NOT
NULL),
CONSTRAINT ck_fleet_missions_completion CHECK ((status = 'completed') = (completed_at IS NOT
NULL))
)
""",
    ],
    [
        "fleet_mission_legs",
        """
CREATE TABLE fleet_mission_legs (
mission_id UUID NOT NULL,
ordinal INTEGER NOT NULL,
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
route_id UUID NOT NULL,
CONSTRAINT pk_fleet_mission_legs PRIMARY KEY (mission_id, ordinal),
CONSTRAINT fk_fleet_mission_legs_mission_id_fleet_missions FOREIGN KEY(mission_id, empire_id,
universe_id) REFERENCES fleet_missions (id, empire_id, universe_id),
CONSTRAINT fk_fleet_mission_legs_empire_id_route_knowledge FOREIGN KEY(empire_id, route_id)
REFERENCES route_knowledge (empire_id, route_id),
CONSTRAINT ck_fleet_mission_legs_ordinal CHECK (ordinal >= 0)
)
""",
    ],
    [
        "fleet_reports",
        """
CREATE TABLE fleet_reports (
mission_id UUID NOT NULL,
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
processed_at TIMESTAMP WITH TIME ZONE NOT NULL,
result JSONB NOT NULL,
CONSTRAINT pk_fleet_reports PRIMARY KEY (mission_id),
CONSTRAINT fk_fleet_reports_mission_id_fleet_missions FOREIGN KEY(mission_id, empire_id,
universe_id) REFERENCES fleet_missions (id, empire_id, universe_id),
CONSTRAINT ck_fleet_reports_processing CHECK (processed_at >= observed_at)
)
""",
    ],
    [
        "fleet_operations",
        """
CREATE TABLE fleet_operations (
empire_id UUID NOT NULL,
idempotency_key VARCHAR(160) NOT NULL,
universe_id UUID NOT NULL,
kind VARCHAR(12) NOT NULL,
request JSONB NOT NULL,
result JSONB NOT NULL,
accepted_at TIMESTAMP WITH TIME ZONE NOT NULL,
CONSTRAINT pk_fleet_operations PRIMARY KEY (empire_id, idempotency_key),
CONSTRAINT fk_fleet_operations_empire_id_empire_exploration FOREIGN KEY(empire_id,
universe_id) REFERENCES empire_exploration (empire_id, universe_id),
CONSTRAINT ck_fleet_operations_kind CHECK (kind IN ('split','merge','load','unload','recall'))
)
""",
    ],
]
INDEXES = [
    "CREATE UNIQUE INDEX ix_ship_order_active ON ship_orders (colony_id) WHERE status = 'active'",
    "CREATE UNIQUE INDEX ix_fleet_garrison ON fleets (home_colony_id) WHERE kind = 'GARRISON'",
    "CREATE UNIQUE INDEX ix_fleet_mission_open ON fleet_missions (fleet_id) "
    "WHERE status IN ('active','returning')",
]
# Circular reference fleets ↔ fleet_missions: added once both tables exist.
ENGAGEMENT = (
    "ALTER TABLE fleets ADD CONSTRAINT fk_fleets_active_mission_id_fleet_missions "
    "FOREIGN KEY(active_mission_id, id) REFERENCES fleet_missions (id, fleet_id)"
)
FLEET_RIGHTS = ["fleet.read", "fleet.build", "fleet.command"]


def permissions(include_fleets):
    op.drop_constraint(
        op.f("ck_empire_bindings_binding_permissions"), "empire_bindings", type_="check"
    )
    allowed = [
        "colony.read",
        "colony.construct",
        "colony.cancel",
        "research.read",
        "research.start",
        "research.cancel",
        "galaxy.read",
        "exploration.read",
        "exploration.start",
    ]
    if include_fleets:
        allowed += FLEET_RIGHTS
    op.create_check_constraint(
        "binding_permissions",
        "empire_bindings",
        "jsonb_typeof(permissions) = 'array' AND jsonb_array_length(permissions) > 0 "
        "AND permissions <@ '" + json.dumps(allowed) + "'::jsonb",
    )


def upgrade():
    for _, ddl in TABLES:
        op.execute(ddl)
    for ddl in INDEXES:
        op.execute(ddl)
    op.execute(ENGAGEMENT)
    permissions(True)


def downgrade():
    connection = op.get_bind()
    for name, _ in TABLES:
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {name})")).scalar():
            raise RuntimeError("Cannot downgrade populated Fleets; archive explicitly")
    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM empire_bindings WHERE permissions ?| "
            "array['fleet.read','fleet.build','fleet.command'])"
        )
    ).scalar():
        raise RuntimeError("Cannot downgrade live Fleet grants; revoke explicitly")
    permissions(False)
    op.drop_constraint("fk_fleets_active_mission_id_fleet_missions", "fleets", type_="foreignkey")
    for name, _ in reversed(TABLES):
        op.drop_table(name)
