"""add_designation_unique_constraint

Revision ID: b7c3d07d4a21
Revises: 96f8fee1d58e
Create Date: 2026-03-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7c3d07d4a21"
down_revision: Union[str, None] = "96f8fee1d58e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM designations
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT id,
                           row_number() OVER (
                               PARTITION BY teacher_ci, subject, semester, group_code
                               ORDER BY id DESC
                           ) AS row_num
                    FROM designations
                ) ranked
                WHERE ranked.row_num > 1
            )
            """
        )
    )
    op.create_unique_constraint(
        "uq_designation_teacher_subject_semester_group",
        "designations",
        ["teacher_ci", "subject", "semester", "group_code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_designation_teacher_subject_semester_group",
        "designations",
        type_="unique",
    )
