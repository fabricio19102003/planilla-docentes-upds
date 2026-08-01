"""add practice attendance unique constraint

Revision ID: c4a8d7e2f901
Revises: 7d52c8e1a4f3
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a8d7e2f901"
down_revision: Union[str, None] = "7d52c8e1a4f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    if not sa.inspect(connection).has_table("practice_attendance_logs"):
        # The application creates newer model tables with Base.metadata.create_all.
        # When Alembic runs first on a clean database, the later create_all call
        # will create this table with the model's unique constraint already present.
        return
    duplicates = connection.execute(
        sa.text(
            """
            SELECT teacher_ci, designation_id, date, scheduled_start, count(*) AS duplicate_count
            FROM practice_attendance_logs
            GROUP BY teacher_ci, designation_id, date, scheduled_start
            HAVING count(*) > 1
            ORDER BY teacher_ci, designation_id, date, scheduled_start
            LIMIT 10
            """
        )
    ).mappings().all()
    if duplicates:
        sample = "; ".join(
            f"CI {row['teacher_ci']}, designación {row['designation_id']}, "
            f"{row['date']} {row['scheduled_start']} ({row['duplicate_count']} registros)"
            for row in duplicates
        )
        raise RuntimeError(
            "No se puede crear uq_practice_attendance_log porque existen registros "
            f"duplicados. Sanealos explícitamente y reintentá la migración. Ejemplos: {sample}"
        )

    with op.batch_alter_table("practice_attendance_logs") as batch_op:
        batch_op.create_unique_constraint(
            "uq_practice_attendance_log",
            ["teacher_ci", "designation_id", "date", "scheduled_start"],
        )


def downgrade() -> None:
    with op.batch_alter_table("practice_attendance_logs") as batch_op:
        batch_op.drop_constraint(
            "uq_practice_attendance_log",
            type_="unique",
        )
