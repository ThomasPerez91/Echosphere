"""Initialize the independent Accounts migration history, without account tables.

Account entities and their constraints belong to C02/P0001. This baseline only
establishes portal_alembic_version in Accounts DB; Game revisions stay untouched.
"""

revision = "p0000_portal_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
