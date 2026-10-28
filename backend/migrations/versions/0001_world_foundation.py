"""Persist the first five concepts; no seeded worlds and no gameplay defaults."""

import sqlalchemy as sa
from alembic import op

revision = "0001_world_foundation"
down_revision = None
branch_labels = None
depends_on = None


def record_columns():
    # Frozen migration definitions, intentionally independent from current ORM classes.
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def universe_column():
    return sa.Column("universe_id", sa.Uuid(), nullable=False)


def named_columns():
    return [sa.Column("name", sa.String(120), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "universes",
        *record_columns(),
        *named_columns(),
        sa.Column("seed", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_universes"),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_universes_name_not_blank")),
    )
    op.create_table(
        "empires",
        *record_columns(),
        universe_column(),
        *named_columns(),
        sa.Column("controller_type", sa.String(8), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_empires"),
        sa.UniqueConstraint("id", "universe_id", name="uq_empires_id_universe"),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], name="fk_empires_universe_id_universes"
        ),
        sa.CheckConstraint(
            "controller_type IN ('human', 'ai')", name=op.f("ck_empires_controller_type")
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_empires_name_not_blank")),
    )
    op.create_index("ix_empires_universe_id", "empires", ["universe_id"])
    op.create_table(
        "stellar_systems",
        *record_columns(),
        universe_column(),
        *named_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_stellar_systems"),
        sa.UniqueConstraint("id", "universe_id", name="uq_stellar_systems_id_universe"),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], name="fk_stellar_systems_universe_id_universes"
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_stellar_systems_name_not_blank")
        ),
    )
    op.create_index("ix_stellar_systems_universe_id", "stellar_systems", ["universe_id"])
    op.create_table(
        "planets",
        *record_columns(),
        universe_column(),
        *named_columns(),
        sa.Column("system_id", sa.Uuid(), nullable=False),
        sa.Column("sector_capacity", sa.Integer(), nullable=False),
        sa.Column("orbital_capacity", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_planets"),
        sa.UniqueConstraint("id", "universe_id", name="uq_planets_id_universe"),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], name="fk_planets_universe_id_universes"
        ),
        sa.ForeignKeyConstraint(
            ["system_id", "universe_id"],
            ["stellar_systems.id", "stellar_systems.universe_id"],
            name="fk_planets_system_universe",
        ),
        sa.CheckConstraint("sector_capacity > 0", name=op.f("ck_planets_positive_sectors")),
        sa.CheckConstraint("orbital_capacity >= 0", name=op.f("ck_planets_nonnegative_orbitals")),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_planets_name_not_blank")),
    )
    op.create_index("ix_planets_universe_id", "planets", ["universe_id"])
    op.create_index("ix_planets_system_id", "planets", ["system_id"])
    op.create_table(
        "colonies",
        *record_columns(),
        universe_column(),
        sa.Column("empire_id", sa.Uuid(), nullable=False),
        sa.Column("planet_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_colonies"),
        sa.UniqueConstraint("planet_id", name="uq_colonies_planet"),
        sa.ForeignKeyConstraint(
            ["universe_id"], ["universes.id"], name="fk_colonies_universe_id_universes"
        ),
        sa.ForeignKeyConstraint(
            ["empire_id", "universe_id"],
            ["empires.id", "empires.universe_id"],
            name="fk_colonies_empire_universe",
        ),
        sa.ForeignKeyConstraint(
            ["planet_id", "universe_id"],
            ["planets.id", "planets.universe_id"],
            name="fk_colonies_planet_universe",
        ),
    )
    op.create_index("ix_colonies_universe_id", "colonies", ["universe_id"])
    op.create_index("ix_colonies_empire_id", "colonies", ["empire_id"])


def downgrade() -> None:
    for table in ["colonies", "planets", "stellar_systems", "empires", "universes"]:
        op.drop_table(table)
