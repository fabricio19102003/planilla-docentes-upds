"""add WhatsApp consent lifecycle persistence

Revision ID: a2c4e6f8b001
Revises: f1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa


revision = "a2c4e6f8b001"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("whatsapp_preferences")
    }
    additions = {
        "consent_source": sa.String(32),
        "consented_at": sa.DateTime(),
    }
    for name, column_type in additions.items():
        existing = columns.get(name)
        if existing is None:
            op.add_column(
                "whatsapp_preferences",
                sa.Column(name, column_type, nullable=True),
            )
        elif not isinstance(existing["type"], type(column_type)):
            raise RuntimeError(
                f"Incompatible pre-existing whatsapp_preferences.{name} column"
            )

    if "whatsapp_consent_revisions" not in inspector.get_table_names():
        op.create_table(
            "whatsapp_consent_revisions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "teacher_ci",
                sa.String(20),
                sa.ForeignKey("teachers.ci", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(24), nullable=False),
            sa.Column("phone_e164", sa.String(16), nullable=False),
            sa.Column("is_verified", sa.Boolean(), nullable=False),
            sa.Column("consent_evidence", sa.Text(), nullable=True),
            sa.Column("consent_source", sa.String(32), nullable=True),
            sa.Column("consented_at", sa.DateTime(), nullable=True),
            sa.Column("opt_out_evidence", sa.Text(), nullable=True),
            sa.Column("opted_out_at", sa.DateTime(), nullable=True),
            sa.Column(
                "actor_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint("revision > 0", name="ck_whatsapp_consent_revision_positive"),
            sa.UniqueConstraint(
                "teacher_ci",
                "revision",
                name="uq_whatsapp_consent_teacher_revision",
            ),
        )
        op.create_index(
            "ix_whatsapp_consent_revisions_teacher_ci",
            "whatsapp_consent_revisions",
            ["teacher_ci"],
        )


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
