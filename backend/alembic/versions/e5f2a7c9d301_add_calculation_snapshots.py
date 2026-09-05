"""add immutable payroll calculation snapshots

Revision ID: e5f2a7c9d301
Revises: d9e4a1b6c2f0
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f2a7c9d301"
down_revision = "d9e4a1b6c2f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ("planilla_outputs", "practice_planilla_outputs"):
        if inspector.has_table(table):
            op.add_column(table, sa.Column("calculation_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ("practice_planilla_outputs", "planilla_outputs"):
        if inspector.has_table(table):
            op.drop_column(table, "calculation_snapshot")
