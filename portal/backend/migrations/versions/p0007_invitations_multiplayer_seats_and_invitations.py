"""Multiplayer seats and invitations (UX-API-03)

Revision ID: p0007_invitations
Revises: p0006_creation
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "p0007_invitations"
down_revision = "p0006_creation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "universe_references",
        sa.Column("seats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "universe_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("universe_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_by", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mode IN ('link', 'email')", name=op.f("ck_universe_invitations_invitation_mode")
        ),
        sa.CheckConstraint(
            "state IN ('open', 'accepted', 'declined', 'revoked')",
            name=op.f("ck_universe_invitations_invitation_state"),
        ),
        sa.CheckConstraint(
            "(mode = 'email') = (email IS NOT NULL)",
            name=op.f("ck_universe_invitations_invitation_email"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_universe_invitations_invitation_lifetime")
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by"], ["users.id"], name=op.f("fk_universe_invitations_accepted_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_universe_invitations_created_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["universe_id"],
            ["universe_references.id"],
            name=op.f("fk_universe_invitations_universe_id_universe_references"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_universe_invitations")),
        sa.UniqueConstraint("token_digest", name=op.f("uq_universe_invitations_token_digest")),
    )
    op.create_index(
        op.f("ix_universe_invitations_email"), "universe_invitations", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_universe_invitations_universe_id"),
        "universe_invitations",
        ["universe_id"],
        unique=False,
    )
    op.create_index(
        "uq_invitation_open_link",
        "universe_invitations",
        ["universe_id"],
        unique=True,
        postgresql_where=sa.text("mode = 'link' AND state = 'open'"),
    )
    op.create_index(
        "uq_invitation_open_email",
        "universe_invitations",
        ["universe_id", "email"],
        unique=True,
        postgresql_where=sa.text("mode = 'email' AND state = 'open'"),
    )
    op.create_table(
        "invitation_email_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('pending', 'sent', 'cancelled')",
            name=op.f("ck_invitation_email_outbox_invitation_mail_state"),
        ),
        sa.CheckConstraint(
            "state <> 'pending' OR payload_ciphertext IS NOT NULL",
            name=op.f("ck_invitation_email_outbox_invitation_mail_payload"),
        ),
        sa.ForeignKeyConstraint(
            ["invitation_id"],
            ["universe_invitations.id"],
            name=op.f("fk_invitation_email_outbox_invitation_id_universe_invitations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitation_email_outbox")),
        sa.UniqueConstraint(
            "invitation_id", name=op.f("uq_invitation_email_outbox_invitation_id")
        ),
    )
    op.create_index(
        "ix_invitation_email_outbox_due",
        "invitation_email_outbox",
        ["state", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invitation_email_outbox_due", table_name="invitation_email_outbox")
    op.drop_table("invitation_email_outbox")
    op.drop_index(
        "uq_invitation_open_email",
        table_name="universe_invitations",
        postgresql_where=sa.text("mode = 'email' AND state = 'open'"),
    )
    op.drop_index(
        "uq_invitation_open_link",
        table_name="universe_invitations",
        postgresql_where=sa.text("mode = 'link' AND state = 'open'"),
    )
    op.drop_index(op.f("ix_universe_invitations_universe_id"), table_name="universe_invitations")
    op.drop_index(op.f("ix_universe_invitations_email"), table_name="universe_invitations")
    op.drop_table("universe_invitations")
    op.drop_column("universe_references", "seats")
