"""add outbound notification attempts

Revision ID: a1b2c3d4e5f6
Revises: c9d0e1f2a3b4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "outbound_notification_attempts" in inspector.get_table_names():
        expected = {
            "id", "idempotency_key", "publication_id", "publication_version",
            "user_id", "channel", "provider", "mode", "status",
            "provider_message_id", "error_code", "created_at", "updated_at",
        }
        actual = {column["name"] for column in inspector.get_columns("outbound_notification_attempts")}
        if actual != expected:
            raise RuntimeError("incompatible precreated outbound_notification_attempts table")
        return

    op.create_table(
        "outbound_notification_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("publication_id", sa.Integer(), nullable=False),
        sa.Column("publication_version", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider_message_id", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["billing_publications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_outbound_notification_attempt_key"),
    )
    op.create_index(
        op.f("ix_outbound_notification_attempts_publication_id"),
        "outbound_notification_attempts",
        ["publication_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_notification_attempts_user_id"),
        "outbound_notification_attempts",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    raise RuntimeError(
        "Destructive downgrade is disabled. Restore an explicitly approved backup instead."
    )
