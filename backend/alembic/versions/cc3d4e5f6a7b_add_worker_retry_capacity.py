"""add official worker retry and moving-capacity persistence

Revision ID: cc3d4e5f6a7b
Revises: bb2c3d4e5f6a
"""

from alembic import op
import sqlalchemy as sa

revision = "cc3d4e5f6a7b"
down_revision = "bb2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "billing_notification_capacity_windows" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.add_column("billing_notification_jobs", sa.Column("next_attempt_at", sa.DateTime()))
    op.add_column("billing_notification_jobs", sa.Column("last_error_code", sa.String(64)))
    op.create_index("ix_billing_notification_job_due", "billing_notification_jobs", ["status", "next_attempt_at"])
    op.create_table(
        "billing_notification_capacity_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("next_dispatch_at", sa.DateTime()),
    )
    op.bulk_insert(sa.table("billing_notification_capacity_windows", sa.column("id", sa.Integer()), sa.column("revision", sa.Integer())), [{"id": 1, "revision": 0}])
    op.create_table(
        "billing_notification_capacity_reservations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("recipient_key", sa.String(64), nullable=False),
        sa.Column("reserved_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_billing_notification_capacity_job"),
    )
    op.create_index("ix_billing_notification_capacity_reserved_at", "billing_notification_capacity_reservations", ["reserved_at"])


def downgrade() -> None:
    op.drop_index("ix_billing_notification_capacity_reserved_at", table_name="billing_notification_capacity_reservations")
    op.drop_table("billing_notification_capacity_reservations")
    op.drop_table("billing_notification_capacity_windows")
    op.drop_index("ix_billing_notification_job_due", table_name="billing_notification_jobs")
    op.drop_column("billing_notification_jobs", "last_error_code")
    op.drop_column("billing_notification_jobs", "next_attempt_at")
