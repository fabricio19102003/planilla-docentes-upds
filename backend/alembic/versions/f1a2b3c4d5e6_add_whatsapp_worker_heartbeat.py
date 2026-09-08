"""add official WhatsApp worker heartbeat

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
"""
from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns(
            "billing_notification_capacity_windows"
        )
    }
    existing = columns.get("worker_heartbeat_at")
    if existing is not None:
        if not isinstance(existing["type"], sa.DateTime) or existing["nullable"] is not True:
            raise RuntimeError(
                "Incompatible pre-existing "
                "billing_notification_capacity_windows.worker_heartbeat_at column"
            )
        return
    op.add_column(
        "billing_notification_capacity_windows",
        sa.Column("worker_heartbeat_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
