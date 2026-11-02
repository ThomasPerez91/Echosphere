"""Relations (step 13, ruleset v0.8): contacts, pairs, pacts, journal and two new rights.

Revision ID: 0013_relations
Revises: 0012_combat
Frozen DDL; independent of runtime ORM models. Business migration, non-destructive and without
any transformation of historical data, with a controlled extension of the existing permission
constraint (17 rights). No backfill and no automatic human grant: only v0.8 Universes relate.
"""

# ruff: noqa: E501
import json

import sqlalchemy as sa
from alembic import op

revision = "0013_relations"
down_revision = "0012_combat"
branch_labels = None
depends_on = None

TABLES = [
    """
CREATE TABLE relation_contacts (
	observer_empire_id UUID NOT NULL,
	observed_empire_id UUID NOT NULL,
	universe_id UUID NOT NULL,
	first_source VARCHAR(12) NOT NULL,
	first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
	presence_planet_id UUID,
	presence_observed_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT pk_relation_contacts PRIMARY KEY (observer_empire_id, observed_empire_id),
	CONSTRAINT fk_relation_contacts_observer FOREIGN KEY(observer_empire_id, universe_id) REFERENCES empires (id, universe_id),
	CONSTRAINT fk_relation_contacts_observed FOREIGN KEY(observed_empire_id, universe_id) REFERENCES empires (id, universe_id),
	CONSTRAINT fk_relation_contacts_presence_planet FOREIGN KEY(presence_planet_id, universe_id) REFERENCES planets (id, universe_id),
	CONSTRAINT ck_relation_contacts_sides CHECK (observer_empire_id <> observed_empire_id),
	CONSTRAINT ck_relation_contacts_source CHECK (first_source IN ('combat','presence')),
	CONSTRAINT ck_relation_contacts_seen CHECK (last_seen_at >= first_seen_at),
	CONSTRAINT ck_relation_contacts_presence CHECK ((presence_planet_id IS NULL) = (presence_observed_at IS NULL))
)
""",
    "CREATE INDEX ix_relation_contacts_observed ON relation_contacts (observed_empire_id)",
    """
CREATE TABLE relation_pairs (
	low_empire_id UUID NOT NULL,
	high_empire_id UUID NOT NULL,
	universe_id UUID NOT NULL,
	proposal_by_empire_id UUID,
	proposed_at TIMESTAMP WITH TIME ZONE,
	proposal_expires_at TIMESTAMP WITH TIME ZONE,
	low_cooldown_until TIMESTAMP WITH TIME ZONE,
	high_cooldown_until TIMESTAMP WITH TIME ZONE,
	last_hostile_by_low_at TIMESTAMP WITH TIME ZONE,
	last_hostile_by_high_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT pk_relation_pairs PRIMARY KEY (low_empire_id, high_empire_id),
	CONSTRAINT fk_relation_pairs_low FOREIGN KEY(low_empire_id, universe_id) REFERENCES empires (id, universe_id),
	CONSTRAINT fk_relation_pairs_high FOREIGN KEY(high_empire_id, universe_id) REFERENCES empires (id, universe_id),
	CONSTRAINT uq_relation_pairs_scope UNIQUE (low_empire_id, high_empire_id, universe_id),
	CONSTRAINT ck_relation_pairs_order CHECK (low_empire_id < high_empire_id),
	CONSTRAINT ck_relation_pairs_proposal CHECK ((proposal_by_empire_id IS NULL) = (proposed_at IS NULL) AND (proposed_at IS NULL) = (proposal_expires_at IS NULL)),
	CONSTRAINT ck_relation_pairs_proposal_side CHECK (proposal_by_empire_id IS NULL OR proposal_by_empire_id IN (low_empire_id, high_empire_id)),
	CONSTRAINT ck_relation_pairs_proposal_window CHECK (proposal_expires_at IS NULL OR proposal_expires_at > proposed_at)
)
""",
    "CREATE INDEX ix_relation_pairs_high ON relation_pairs (high_empire_id)",
    """
CREATE TABLE relation_pacts (
	universe_id UUID NOT NULL,
	low_empire_id UUID NOT NULL,
	high_empire_id UUID NOT NULL,
	proposed_by_empire_id UUID NOT NULL,
	accepted_by_empire_id UUID NOT NULL,
	accepted_at TIMESTAMP WITH TIME ZONE NOT NULL,
	notice_by_empire_id UUID,
	notice_at TIMESTAMP WITH TIME ZONE,
	ends_at TIMESTAMP WITH TIME ZONE,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_relation_pacts PRIMARY KEY (id),
	CONSTRAINT fk_relation_pacts_pair FOREIGN KEY(low_empire_id, high_empire_id, universe_id) REFERENCES relation_pairs (low_empire_id, high_empire_id, universe_id),
	CONSTRAINT ck_relation_pacts_signatories CHECK (proposed_by_empire_id IN (low_empire_id, high_empire_id) AND accepted_by_empire_id IN (low_empire_id, high_empire_id) AND proposed_by_empire_id <> accepted_by_empire_id),
	CONSTRAINT ck_relation_pacts_notice CHECK ((notice_by_empire_id IS NULL) = (notice_at IS NULL) AND (notice_at IS NULL) = (ends_at IS NULL)),
	CONSTRAINT ck_relation_pacts_notice_side CHECK (notice_by_empire_id IS NULL OR notice_by_empire_id IN (low_empire_id, high_empire_id)),
	CONSTRAINT ck_relation_pacts_notice_window CHECK (notice_at IS NULL OR (notice_at >= accepted_at AND ends_at > notice_at))
)
""",
    "CREATE UNIQUE INDEX uq_relation_pacts_open ON relation_pacts (low_empire_id, high_empire_id) WHERE ends_at IS NULL",
    "CREATE INDEX ix_relation_pacts_pair ON relation_pacts (low_empire_id, high_empire_id, accepted_at)",
    """
CREATE TABLE relation_events (
	universe_id UUID NOT NULL,
	low_empire_id UUID NOT NULL,
	high_empire_id UUID NOT NULL,
	actor_empire_id UUID NOT NULL,
	kind VARCHAR(12) NOT NULL,
	at TIMESTAMP WITH TIME ZONE NOT NULL,
	idempotency_key VARCHAR(160) NOT NULL,
	details JSONB NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_relation_events PRIMARY KEY (id),
	CONSTRAINT fk_relation_events_pair FOREIGN KEY(low_empire_id, high_empire_id, universe_id) REFERENCES relation_pairs (low_empire_id, high_empire_id, universe_id),
	CONSTRAINT fk_relation_events_actor FOREIGN KEY(actor_empire_id, universe_id) REFERENCES empires (id, universe_id),
	CONSTRAINT uq_relation_events_intent UNIQUE (actor_empire_id, idempotency_key),
	CONSTRAINT ck_relation_events_kind CHECK (kind IN ('proposed','withdrawn','accepted','refused','notice')),
	CONSTRAINT ck_relation_events_actor CHECK (actor_empire_id IN (low_empire_id, high_empire_id)),
	CONSTRAINT ck_relation_events_key CHECK (length(idempotency_key) BETWEEN 1 AND 160)
)
""",
    "CREATE INDEX ix_relation_events_pair ON relation_events (low_empire_id, high_empire_id, at)",
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
    "colony.expand",
    "combat.read",
    "combat.attack",
]


def permissions(include_relations):
    """Controlled extension: every existing binding already satisfies the widened list."""
    op.drop_constraint(
        op.f("ck_empire_bindings_binding_permissions"), "empire_bindings", type_="check"
    )
    allowed = PERMISSIONS + (["relations.read", "relations.negotiate"] if include_relations else [])
    op.create_check_constraint(
        "binding_permissions",
        "empire_bindings",
        "jsonb_typeof(permissions) = 'array' AND jsonb_array_length(permissions) > 0 "
        "AND permissions <@ '" + json.dumps(allowed) + "'::jsonb",
    )


def upgrade():
    for ddl in TABLES:
        op.execute(ddl)
    permissions(True)


def downgrade():
    connection = op.get_bind()
    for table in ("relation_events", "relation_pacts", "relation_pairs", "relation_contacts"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Cannot downgrade live Relations data; archive explicitly")
    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM empire_bindings "
            "WHERE permissions ?| array['relations.read','relations.negotiate'])"
        )
    ).scalar():
        raise RuntimeError("Cannot downgrade live relations grants; revoke explicitly")
    permissions(False)
    for table in ("relation_events", "relation_pacts", "relation_pairs", "relation_contacts"):
        op.drop_table(table)
