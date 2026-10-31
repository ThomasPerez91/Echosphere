"""Persist generated worlds, Empire knowledge and expeditions; no world backfill.

Revision ID: 0008_galaxy_exploration
Revises: 0007_empire_research
Frozen DDL; independent of runtime ORM models.
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0008_galaxy_exploration"
down_revision = "0007_empire_research"
branch_labels = None
depends_on = None

TABLES = [
    [
        "universe_galaxies",
        """
CREATE TABLE universe_galaxies (
universe_id UUID NOT NULL,
generator_version VARCHAR(32) NOT NULL,
inputs JSONB NOT NULL,
digest VARCHAR(64) NOT NULL,
CONSTRAINT pk_universe_galaxies PRIMARY KEY (universe_id),
CONSTRAINT fk_universe_galaxies_universe_id_universes FOREIGN KEY(universe_id)
REFERENCES universes (id)
)
""",
    ],
    [
        "empire_exploration",
        """
CREATE TABLE empire_exploration (
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
stream_id UUID NOT NULL,
CONSTRAINT pk_empire_exploration PRIMARY KEY (empire_id),
CONSTRAINT fk_empire_exploration_empire_id_empires FOREIGN KEY(empire_id, universe_id)
REFERENCES empires (id, universe_id),
CONSTRAINT fk_empire_exploration_stream_id_event_streams FOREIGN KEY(stream_id,
universe_id) REFERENCES event_streams (id, universe_id),
CONSTRAINT uq_exploration_scope UNIQUE (empire_id, universe_id),
CONSTRAINT uq_exploration_stream UNIQUE (stream_id),
CONSTRAINT fk_empire_exploration_universe_id_universe_galaxies FOREIGN KEY(universe_id)
REFERENCES universe_galaxies (universe_id)
)
""",
    ],
    [
        "galaxy_systems",
        """
CREATE TABLE galaxy_systems (
system_id UUID NOT NULL,
universe_id UUID NOT NULL,
ordinal INTEGER NOT NULL,
x INTEGER NOT NULL,
y INTEGER NOT NULL,
CONSTRAINT pk_galaxy_systems PRIMARY KEY (system_id),
CONSTRAINT fk_galaxy_systems_system_id_stellar_systems FOREIGN KEY(system_id,
universe_id) REFERENCES stellar_systems (id, universe_id),
CONSTRAINT uq_galaxy_system_scope UNIQUE (system_id, universe_id),
CONSTRAINT uq_galaxy_system_ordinal UNIQUE (universe_id, ordinal),
CONSTRAINT ck_galaxy_systems_coordinates CHECK (ordinal >= 0 AND x >= 0 AND y >= 0),
CONSTRAINT fk_galaxy_systems_universe_id_universe_galaxies FOREIGN KEY(universe_id)
REFERENCES universe_galaxies (universe_id)
)
""",
    ],
    [
        "galaxy_planets",
        """
CREATE TABLE galaxy_planets (
planet_id UUID NOT NULL,
universe_id UUID NOT NULL,
system_id UUID NOT NULL,
ordinal INTEGER NOT NULL,
CONSTRAINT pk_galaxy_planets PRIMARY KEY (planet_id),
CONSTRAINT fk_galaxy_planets_planet_id_planets FOREIGN KEY(planet_id, system_id,
universe_id) REFERENCES planets (id, system_id, universe_id),
CONSTRAINT fk_galaxy_planets_system_id_galaxy_systems FOREIGN KEY(system_id,
universe_id) REFERENCES galaxy_systems (system_id, universe_id),
CONSTRAINT uq_galaxy_planet_scope UNIQUE (planet_id, universe_id),
CONSTRAINT uq_galaxy_planet_parent UNIQUE (planet_id, system_id, universe_id),
CONSTRAINT uq_galaxy_planet_ordinal UNIQUE (system_id, ordinal),
CONSTRAINT ck_galaxy_planets_ordinal CHECK (ordinal >= 0)
)
""",
    ],
    [
        "galaxy_routes",
        """
CREATE TABLE galaxy_routes (
universe_id UUID NOT NULL,
a_id UUID NOT NULL,
b_id UUID NOT NULL,
id UUID DEFAULT gen_random_uuid() NOT NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
CONSTRAINT pk_galaxy_routes PRIMARY KEY (id),
CONSTRAINT fk_galaxy_routes_a_id_galaxy_systems FOREIGN KEY(a_id, universe_id)
REFERENCES galaxy_systems (system_id, universe_id),
CONSTRAINT fk_galaxy_routes_b_id_galaxy_systems FOREIGN KEY(b_id, universe_id)
REFERENCES galaxy_systems (system_id, universe_id),
CONSTRAINT uq_galaxy_route_scope UNIQUE (id, universe_id),
CONSTRAINT uq_galaxy_route_endpoints UNIQUE (id, a_id, b_id, universe_id),
CONSTRAINT uq_galaxy_route_pair UNIQUE (a_id, b_id),
CONSTRAINT ck_galaxy_routes_ordered_endpoints CHECK (a_id < b_id)
)
""",
    ],
    [
        "system_knowledge",
        """
CREATE TABLE system_knowledge (
empire_id UUID NOT NULL,
system_id UUID NOT NULL,
universe_id UUID NOT NULL,
state VARCHAR(12) NOT NULL,
approximate_x INTEGER NOT NULL,
approximate_y INTEGER NOT NULL,
discovered_at TIMESTAMP WITH TIME ZONE NOT NULL,
mapped_at TIMESTAMP WITH TIME ZONE,
last_seen_at TIMESTAMP WITH TIME ZONE,
observation JSONB,
known_name VARCHAR(120),
known_x INTEGER,
known_y INTEGER,
CONSTRAINT pk_system_knowledge PRIMARY KEY (empire_id, system_id),
CONSTRAINT fk_system_knowledge_empire_id_empire_exploration FOREIGN KEY(empire_id,
universe_id) REFERENCES empire_exploration (empire_id, universe_id),
CONSTRAINT fk_system_knowledge_system_id_galaxy_systems FOREIGN KEY(system_id,
universe_id) REFERENCES galaxy_systems (system_id, universe_id),
CONSTRAINT uq_knowledge_scope UNIQUE (empire_id, system_id, universe_id),
CONSTRAINT ck_system_knowledge_state CHECK (state IN ('DETECTED','MAPPED','MONITORED')),
CONSTRAINT ck_system_knowledge_structure CHECK ((state = 'DETECTED' AND mapped_at IS NULL
AND known_name IS NULL AND known_x IS NULL AND known_y IS NULL AND last_seen_at IS NULL
AND observation IS NULL) OR (state <> 'DETECTED' AND mapped_at IS NOT NULL
AND known_name IS NOT NULL AND known_x IS NOT NULL AND known_y IS NOT NULL)),
CONSTRAINT ck_system_knowledge_monitoring CHECK (state <> 'MONITORED' OR
(last_seen_at IS NOT NULL AND observation IS NOT NULL))
)
""",
    ],
    [
        "exploration_missions",
        """
CREATE TABLE exploration_missions (
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
colony_id UUID NOT NULL,
destination_id UUID NOT NULL,
idempotency_key VARCHAR(160) NOT NULL,
status VARCHAR(12) NOT NULL,
snapshot JSONB NOT NULL,
started_at TIMESTAMP WITH TIME ZONE NOT NULL,
due_at TIMESTAMP WITH TIME ZONE NOT NULL,
completed_at TIMESTAMP WITH TIME ZONE,
id UUID DEFAULT gen_random_uuid() NOT NULL,
created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
CONSTRAINT pk_exploration_missions PRIMARY KEY (id),
CONSTRAINT fk_exploration_missions_empire_id_empire_exploration FOREIGN KEY(empire_id,
universe_id) REFERENCES empire_exploration (empire_id, universe_id),
CONSTRAINT fk_exploration_missions_colony_id_colonies FOREIGN KEY(colony_id, empire_id,
universe_id) REFERENCES colonies (id, empire_id, universe_id),
CONSTRAINT fk_exploration_missions_destination_id_galaxy_systems FOREIGN
KEY(destination_id, universe_id) REFERENCES galaxy_systems (system_id, universe_id),
CONSTRAINT uq_exploration_mission_scope UNIQUE (id, empire_id, universe_id),
CONSTRAINT uq_exploration_key UNIQUE (empire_id, idempotency_key),
CONSTRAINT ck_exploration_missions_status CHECK (status IN ('active','completed')),
CONSTRAINT ck_exploration_missions_completion CHECK ((status = 'completed') =
(completed_at IS NOT NULL)),
CONSTRAINT ck_exploration_missions_deadline CHECK (due_at > started_at)
)
""",
    ],
    [
        "galaxy_starting_sites",
        """
CREATE TABLE galaxy_starting_sites (
planet_id UUID NOT NULL,
universe_id UUID NOT NULL,
system_id UUID NOT NULL,
CONSTRAINT pk_galaxy_starting_sites PRIMARY KEY (planet_id),
CONSTRAINT fk_galaxy_starting_sites_planet_id_galaxy_planets FOREIGN KEY(planet_id,
system_id, universe_id) REFERENCES galaxy_planets (planet_id, system_id, universe_id)
)
""",
    ],
    [
        "planet_knowledge",
        """
CREATE TABLE planet_knowledge (
empire_id UUID NOT NULL,
planet_id UUID NOT NULL,
universe_id UUID NOT NULL,
system_id UUID NOT NULL,
discovered_at TIMESTAMP WITH TIME ZONE NOT NULL,
known_name VARCHAR(120) NOT NULL,
sector_capacity INTEGER NOT NULL,
orbital_capacity INTEGER NOT NULL,
CONSTRAINT pk_planet_knowledge PRIMARY KEY (empire_id, planet_id),
CONSTRAINT fk_planet_knowledge_planet_id_galaxy_planets FOREIGN KEY(planet_id,
system_id, universe_id) REFERENCES galaxy_planets (planet_id, system_id, universe_id),
CONSTRAINT fk_planet_knowledge_empire_id_system_knowledge FOREIGN KEY(empire_id,
system_id, universe_id) REFERENCES system_knowledge (empire_id, system_id, universe_id),
CONSTRAINT ck_planet_knowledge_capacities CHECK (sector_capacity > 0 AND orbital_capacity >= 0)
)
""",
    ],
    [
        "route_knowledge",
        """
CREATE TABLE route_knowledge (
empire_id UUID NOT NULL,
route_id UUID NOT NULL,
universe_id UUID NOT NULL,
a_id UUID NOT NULL,
b_id UUID NOT NULL,
discovered_at TIMESTAMP WITH TIME ZONE NOT NULL,
CONSTRAINT pk_route_knowledge PRIMARY KEY (empire_id, route_id),
CONSTRAINT fk_route_knowledge_route_id_galaxy_routes FOREIGN KEY(route_id, a_id, b_id,
universe_id) REFERENCES galaxy_routes (id, a_id, b_id, universe_id),
CONSTRAINT fk_route_knowledge_a_id FOREIGN KEY(empire_id, a_id, universe_id) REFERENCES
system_knowledge (empire_id, system_id, universe_id),
CONSTRAINT fk_route_knowledge_b_id FOREIGN KEY(empire_id, b_id, universe_id) REFERENCES
system_knowledge (empire_id, system_id, universe_id)
)
""",
    ],
    [
        "exploration_mission_legs",
        """
CREATE TABLE exploration_mission_legs (
mission_id UUID NOT NULL,
ordinal INTEGER NOT NULL,
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
route_id UUID NOT NULL,
CONSTRAINT pk_exploration_mission_legs PRIMARY KEY (mission_id, ordinal),
CONSTRAINT fk_exploration_mission_legs_mission_id_exploration_missions FOREIGN
KEY(mission_id, empire_id, universe_id) REFERENCES exploration_missions (id, empire_id,
universe_id),
CONSTRAINT fk_exploration_mission_legs_route_id_galaxy_routes FOREIGN KEY(route_id,
universe_id) REFERENCES galaxy_routes (id, universe_id),
CONSTRAINT ck_exploration_mission_legs_ordinal CHECK (ordinal >= 0)
)
""",
    ],
    [
        "exploration_reports",
        """
CREATE TABLE exploration_reports (
mission_id UUID NOT NULL,
empire_id UUID NOT NULL,
universe_id UUID NOT NULL,
observed_at TIMESTAMP WITH TIME ZONE NOT NULL,
processed_at TIMESTAMP WITH TIME ZONE NOT NULL,
discoveries JSONB NOT NULL,
CONSTRAINT pk_exploration_reports PRIMARY KEY (mission_id),
CONSTRAINT fk_exploration_reports_mission_id_exploration_missions FOREIGN
KEY(mission_id, empire_id, universe_id) REFERENCES exploration_missions (id, empire_id,
universe_id),
CONSTRAINT ck_exploration_reports_processing CHECK (processed_at >= observed_at)
)
""",
    ],
]
INDEXES = [
    "CREATE UNIQUE INDEX ix_exploration_active ON exploration_missions (empire_id) "
    "WHERE status = 'active'"
]


def permissions(include_exploration):
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
    ]
    if include_exploration:
        allowed += ["galaxy.read", "exploration.read", "exploration.start"]
    op.create_check_constraint(
        "binding_permissions",
        "empire_bindings",
        "jsonb_typeof(permissions) = 'array' AND jsonb_array_length(permissions) > 0 "
        "AND permissions <@ '" + json.dumps(allowed) + "'::jsonb",
    )


def upgrade():
    op.create_unique_constraint(
        "uq_planets_galaxy_parent", "planets", ["id", "system_id", "universe_id"]
    )
    for _, ddl in TABLES:
        op.execute(ddl)
    for ddl in INDEXES:
        op.execute(ddl)
    permissions(True)


def downgrade():
    connection = op.get_bind()
    for name, _ in TABLES:
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {name})")).scalar():
            raise RuntimeError("Cannot downgrade populated Galaxy/Exploration; archive explicitly")
    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM empire_bindings WHERE permissions ?| "
            "array['galaxy.read','exploration.read','exploration.start'])"
        )
    ).scalar():
        raise RuntimeError("Cannot downgrade live Galaxy/Exploration grants; revoke explicitly")
    permissions(False)
    for name, _ in reversed(TABLES):
        op.drop_table(name)
    op.drop_constraint("uq_planets_galaxy_parent", "planets", type_="unique")
