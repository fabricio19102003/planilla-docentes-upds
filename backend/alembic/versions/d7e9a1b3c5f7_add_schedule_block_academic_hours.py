"""add academic hours to schedule blocks

Revision ID: d7e9a1b3c5f7
Revises: c6e8f0a2b431

Draft and published schedule blocks store the academic hours payroll pays per
occurrence. Existing rows stay NULL and keep the previous max(1, minutes // 45) rule.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d7e9a1b3c5f7"
down_revision: Union[str, None] = "c6e8f0a2b431"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("academic_schedule_blocks", "academic_schedule_published_blocks")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in TABLES:
        existing = {column["name"]: column for column in inspector.get_columns(table)}.get("academic_hours")
        if existing is not None:
            if not isinstance(existing["type"], sa.Integer) or existing["nullable"] is not True:
                raise RuntimeError(f"Incompatible pre-existing {table}.academic_hours column")
            continue
        op.add_column(table, sa.Column("academic_hours", sa.Integer(), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
