"""Research state and explicit Research permissions; no ruleset adoption/backfill.

Revision ID: 0007_empire_research
Revises: 0006_game_sessions
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_empire_research"
down_revision = "0006_game_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_colonies_research_scope", "colonies", ["id", "empire_id", "universe_id"]
    )
    op.execute(
        """
        CREATE TABLE empire_research (
        empire_id UUID NOT NULL,
        universe_id UUID NOT NULL,
        stream_id UUID NOT NULL,
        next_sequence BIGINT NOT NULL,
        CONSTRAINT pk_empire_research PRIMARY KEY (empire_id),
        CONSTRAINT fk_empire_research_empire_id_empires FOREIGN KEY(empire_id, universe_id)
        REFERENCES empires (id, universe_id),
        CONSTRAINT fk_empire_research_stream_id_event_streams FOREIGN KEY(stream_id,
        universe_id) REFERENCES event_streams (id, universe_id),
        CONSTRAINT uq_research_scope UNIQUE (empire_id, universe_id),
        CONSTRAINT uq_research_stream UNIQUE (stream_id),
        CONSTRAINT ck_empire_research_sequence CHECK (next_sequence > 0)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE research_orders (
        empire_id UUID NOT NULL,
        universe_id UUID NOT NULL,
        colony_id UUID NOT NULL,
        sequence BIGINT NOT NULL,
        idempotency_key VARCHAR(160) NOT NULL,
        technology_id VARCHAR(64) NOT NULL,
        status VARCHAR(12) NOT NULL,
        snapshot JSONB NOT NULL,
        blocked_reason VARCHAR(64),
        started_at TIMESTAMP WITH TIME ZONE,
        due_at TIMESTAMP WITH TIME ZONE,
        completed_at TIMESTAMP WITH TIME ZONE,
        cancelled_at TIMESTAMP WITH TIME ZONE,
        refunded JSONB,
        id UUID DEFAULT gen_random_uuid() NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_research_orders PRIMARY KEY (id),
        CONSTRAINT fk_research_orders_empire_id_empire_research FOREIGN KEY(empire_id,
        universe_id) REFERENCES empire_research (empire_id, universe_id),
        CONSTRAINT fk_research_orders_colony_id_colonies FOREIGN KEY(colony_id, empire_id,
        universe_id) REFERENCES colonies (id, empire_id, universe_id),
        CONSTRAINT uq_research_key UNIQUE (empire_id, idempotency_key),
        CONSTRAINT uq_research_sequence UNIQUE (empire_id, sequence),
        CONSTRAINT ck_research_orders_sequence CHECK (sequence > 0),
        CONSTRAINT ck_research_orders_status CHECK (status IN
        ('queued','active','blocked','completed','cancelled')),
        CONSTRAINT ck_research_orders_completion CHECK ((status = 'completed') = (completed_at
        IS NOT NULL)),
        CONSTRAINT ck_research_orders_cancellation CHECK ((status = 'cancelled') = (cancelled_at
        IS NOT NULL)),
        CONSTRAINT ck_research_orders_schedule CHECK ((started_at IS NULL) = (due_at IS NULL)),
        CONSTRAINT ck_research_orders_active_start CHECK (status != 'active' OR started_at IS
        NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_research_active ON research_orders (empire"
        "_id) WHERE status = 'active'"
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_research_technology ON research_orders (em"
        "pire_id, technology_id) WHERE status != 'cancelled'"
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_research_waiting ON research_orders (empir"
        "e_id) WHERE status IN ('queued','blocked')"
    )
    op.execute(
        """
        CREATE TABLE acquired_technologies (
        empire_id UUID NOT NULL,
        technology_id VARCHAR(64) NOT NULL,
        universe_id UUID NOT NULL,
        acquired_at TIMESTAMP WITH TIME ZONE NOT NULL,
        effect VARCHAR(32) NOT NULL,
        reduction_bps INTEGER NOT NULL,
        CONSTRAINT pk_acquired_technologies PRIMARY KEY (empire_id, technology_id),
        CONSTRAINT fk_acquired_technologies_empire_id_empire_research FOREIGN KEY(empire_id,
        universe_id) REFERENCES empire_research (empire_id, universe_id),
        CONSTRAINT ck_acquired_technologies_reduction CHECK (reduction_bps >= 0 AND
        reduction_bps < 10000)
        )
        """
    )
    op.drop_constraint(
        op.f("ck_empire_bindings_binding_permissions"), "empire_bindings", type_="check"
    )
    op.create_check_constraint(
        "binding_permissions",
        "empire_bindings",
        "jsonb_typeof(permissions) = 'array' AND jsonb_array_length(permis"
        'sions) > 0 AND permissions <@ \'["colony.read","colony.construct",'
        '"colony.cancel","research.read","research.start","research.cancel'
        "\"]'::jsonb",
    )


def downgrade():
    connection = op.get_bind()
    for table in ["research_orders", "acquired_technologies", "empire_research"]:
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Cannot downgrade populated Research; archive explicitly")
    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM empire_bindings WHERE permissions ?|"
            " array['research.read','research.start','research.cancel'])"
        )
    ).scalar():
        raise RuntimeError("Cannot downgrade live Research grants; revoke explicitly")
    op.drop_table("acquired_technologies")
    op.drop_table("research_orders")
    op.drop_table("empire_research")
    op.drop_constraint("uq_colonies_research_scope", "colonies", type_="unique")
    op.drop_constraint(
        op.f("ck_empire_bindings_binding_permissions"), "empire_bindings", type_="check"
    )
    op.create_check_constraint(
        "binding_permissions",
        "empire_bindings",
        "jsonb_typeof(permissions) = 'array' AND jsonb_array_length(permis"
        'sions) > 0 AND permissions <@ \'["colony.read","colony.construct",'
        '"colony.cancel"]\'::jsonb',
    )
