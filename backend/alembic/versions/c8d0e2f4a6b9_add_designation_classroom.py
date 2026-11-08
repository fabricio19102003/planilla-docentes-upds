"""add classroom to designations

Revision ID: c8d0e2f4a6b9
Revises: b5c7d9e1f3a6

A designation stores the classroom where its theory classes are held, only to mark that room as
occupied in classroom reservations. Payroll, attendance, contracts and billing never read it.
Existing rows stay NULL (no classroom).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c8d0e2f4a6b9"
down_revision: Union[str, None] = "b5c7d9e1f3a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "designations"
COLUMN = "classroom_id"
INDEX = "ix_designations_classroom_id"
FOREIGN_KEY = "fk_designations_classroom_id_classrooms"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"]: column for column in inspector.get_columns(TABLE)}.get(COLUMN)
    if existing is None and bind.dialect.name == "sqlite":
        # SQLite cannot add a constraint afterwards; ADD COLUMN accepts an inline REFERENCES.
        op.execute(sa.text(
            f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} INTEGER REFERENCES classrooms(id) ON DELETE SET NULL"
        ))
    elif existing is None:
        op.add_column(TABLE, sa.Column(
            COLUMN, sa.Integer(), sa.ForeignKey("classrooms.id", ondelete="SET NULL", name=FOREIGN_KEY),
            nullable=True,
        ))
    else:
        if not isinstance(existing["type"], sa.Integer) or existing["nullable"] is not True:
            raise RuntimeError(f"Incompatible pre-existing {TABLE}.{COLUMN} column")
        has_key = any(
            key["constrained_columns"] == [COLUMN] and key["referred_table"] == "classrooms"
            for key in inspector.get_foreign_keys(TABLE)
        )
        if not has_key and bind.dialect.name != "sqlite":
            op.create_foreign_key(FOREIGN_KEY, TABLE, "classrooms", [COLUMN], ["id"], ondelete="SET NULL")
    if not any(index["column_names"] == [COLUMN] for index in inspector.get_indexes(TABLE)):
        op.create_index(INDEX, TABLE, [COLUMN])


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
