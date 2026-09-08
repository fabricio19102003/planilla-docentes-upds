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
    op.add_column(
        "billing_notification_capacity_windows",
        sa.Column("worker_heartbeat_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("billing_notification_capacity_windows", "worker_heartbeat_at")
