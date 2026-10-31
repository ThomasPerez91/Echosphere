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
        "CREATE TABLE empire_research (\n\tempire_id UUID NOT NULL, \n\tuniver"
        "se_id UUID NOT NULL, \n\tstream_id UUID NOT NULL, \n\tnext_sequence B"
        "IGINT NOT NULL, \n\tCONSTRAINT pk_empire_research PRIMARY KEY (empi"
        "re_id), \n\tCONSTRAINT fk_empire_research_empire_id_empires FOREIGN"
        " KEY(empire_id, universe_id) REFERENCES empires (id, universe_id)"
        ", \n\tCONSTRAINT fk_empire_research_stream_id_event_streams FOREIGN"
        " KEY(stream_id, universe_id) REFERENCES event_streams (id, univer"
        "se_id), \n\tCONSTRAINT uq_research_scope UNIQUE (empire_id, univers"
        "e_id), \n\tCONSTRAINT uq_research_stream UNIQUE (stream_id), \n\tCONS"
        "TRAINT ck_empire_research_sequence CHECK (next_sequence > 0)\n)"
    )
    op.execute(
        "CREATE TABLE research_orders (\n\tempire_id UUID NOT NULL, \n\tuniver"
        "se_id UUID NOT NULL, \n\tcolony_id UUID NOT NULL, \n\tsequence BIGINT"
        " NOT NULL, \n\tidempotency_key VARCHAR(160) NOT NULL, \n\ttechnology_"
        "id VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(12) NOT NULL, \n\tsnapsho"
        "t JSONB NOT NULL, \n\tblocked_reason VARCHAR(64), \n\tstarted_at TIME"
        "STAMP WITH TIME ZONE, \n\tdue_at TIMESTAMP WITH TIME ZONE, \n\tcomple"
        "ted_at TIMESTAMP WITH TIME ZONE, \n\tcancelled_at TIMESTAMP WITH TI"
        "ME ZONE, \n\trefunded JSONB, \n\tid UUID DEFAULT gen_random_uuid() NO"
        "T NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT N"
        "ULL, \n\tCONSTRAINT pk_research_orders PRIMARY KEY (id), \n\tCONSTRAI"
        "NT fk_research_orders_empire_id_empire_research FOREIGN KEY(empir"
        "e_id, universe_id) REFERENCES empire_research (empire_id, univers"
        "e_id), \n\tCONSTRAINT fk_research_orders_colony_id_colonies FOREIGN"
        " KEY(colony_id, empire_id, universe_id) REFERENCES colonies (id, "
        "empire_id, universe_id), \n\tCONSTRAINT uq_research_key UNIQUE (emp"
        "ire_id, idempotency_key), \n\tCONSTRAINT uq_research_sequence UNIQU"
        "E (empire_id, sequence), \n\tCONSTRAINT ck_research_orders_sequence"
        " CHECK (sequence > 0), \n\tCONSTRAINT ck_research_orders_status CHE"
        "CK (status IN ('queued','active','blocked','completed','cancelled"
        "')), \n\tCONSTRAINT ck_research_orders_completion CHECK ((status = "
        "'completed') = (completed_at IS NOT NULL)), \n\tCONSTRAINT ck_resea"
        "rch_orders_cancellation CHECK ((status = 'cancelled') = (cancelle"
        "d_at IS NOT NULL)), \n\tCONSTRAINT ck_research_orders_schedule CHEC"
        "K ((started_at IS NULL) = (due_at IS NULL)), \n\tCONSTRAINT ck_rese"
        "arch_orders_active_start CHECK (status != 'active' OR started_at "
        "IS NOT NULL)\n)"
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
        "CREATE TABLE acquired_technologies (\n\tempire_id UUID NOT NULL, \n\t"
        "technology_id VARCHAR(64) NOT NULL, \n\tuniverse_id UUID NOT NULL, "
        "\n\tacquired_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\teffect VARCHAR"
        "(32) NOT NULL, \n\treduction_bps INTEGER NOT NULL, \n\tCONSTRAINT pk_"
        "acquired_technologies PRIMARY KEY (empire_id, technology_id), \n\tC"
        "ONSTRAINT fk_acquired_technologies_empire_id_empire_research FORE"
        "IGN KEY(empire_id, universe_id) REFERENCES empire_research (empir"
        "e_id, universe_id), \n\tCONSTRAINT ck_acquired_technologies_reducti"
        "on CHECK (reduction_bps >= 0 AND reduction_bps < 10000)\n)"
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
