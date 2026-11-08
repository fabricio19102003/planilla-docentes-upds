"""add classroom reservations

Revision ID: b5c7d9e1f3a6
Revises: a4b6c8d0e2f5

One-off reservations of a classroom or laboratory made by teachers from the portal,
confirmed on creation. The table starts empty.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b5c7d9e1f3a6"
down_revision: Union[str, None] = "a4b6c8d0e2f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classroom_reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey("classrooms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("teacher_ci", sa.String(20), sa.ForeignKey("teachers.ci", ondelete="RESTRICT"), nullable=False),
        sa.Column("reservation_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("academic_periods", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("start_time < end_time", name="ck_classroom_reservation_time_order"),
        sa.CheckConstraint("academic_periods >= 1", name="ck_classroom_reservation_periods"),
        sa.CheckConstraint("status IN ('confirmed', 'cancelled')", name="ck_classroom_reservation_status"),
    )
    for column in ("classroom_id", "teacher_ci", "reservation_date", "status"):
        op.create_index(f"ix_classroom_reservations_{column}", "classroom_reservations", [column])
    op.create_index("ix_classroom_reservations_room_date", "classroom_reservations",
                    ["classroom_id", "reservation_date"])


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
