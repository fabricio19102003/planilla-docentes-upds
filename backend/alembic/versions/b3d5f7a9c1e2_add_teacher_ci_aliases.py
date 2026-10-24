"""add teacher CI aliases

Revision ID: b3d5f7a9c1e2
Revises: d7e9a1b3c5f7

Published billing snapshots keep the CI that was current when they were
published. Record each corrected CI so the portal can still match those
snapshots. Backfills aliases from the update_teacher activity log entries.
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b3d5f7a9c1e2"
down_revision: Union[str, None] = "d7e9a1b3c5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "teacher_ci_aliases"


def _table(metadata: sa.MetaData) -> sa.Table:
    sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    return sa.Table(
        TABLE,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("previous_ci", sa.String(20), nullable=False, index=True),
        sa.Column(
            "teacher_ci",
            sa.String(20),
            sa.ForeignKey("teachers.ci", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def _ci_changes(bind) -> list[tuple[str, str, object]]:
    rows = bind.execute(
        sa.text(
            "SELECT details, created_at FROM activity_logs "
            "WHERE action = 'update_teacher' ORDER BY created_at, id"
        )
    ).all()
    changes = []
    for details, created_at in rows:
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except ValueError:
                continue
        if not isinstance(details, dict):
            continue
        old_ci, new_ci = details.get("old_ci"), details.get("new_ci")
        if isinstance(old_ci, str) and isinstance(new_ci, str) and old_ci and new_ci and old_ci != new_ci:
            changes.append((old_ci, new_ci, created_at))
    return changes


def backfill(bind) -> int:
    """Insert one alias per logged CI change, pointing at the teacher's current CI."""
    changes = _ci_changes(bind)
    teachers = {ci for (ci,) in bind.execute(sa.text("SELECT ci FROM teachers")).all()}
    existing = {
        (previous, teacher)
        for previous, teacher in bind.execute(sa.text(f"SELECT previous_ci, teacher_ci FROM {TABLE}")).all()
    }
    inserted = 0
    for index, (old_ci, new_ci, created_at) in enumerate(changes):
        current = new_ci
        # Follow later corrections of the same teacher (A -> B, then B -> C).
        for later_old, later_new, _ in changes[index + 1:]:
            if later_old == current:
                current = later_new
        if current not in teachers or current == old_ci or (old_ci, current) in existing:
            continue
        bind.execute(
            sa.text(
                f"INSERT INTO {TABLE} (previous_ci, teacher_ci, changed_at) "
                "VALUES (:previous_ci, :teacher_ci, :changed_at)"
            ),
            {"previous_ci": old_ci, "teacher_ci": current, "changed_at": created_at},
        )
        existing.add((old_ci, current))
        inserted += 1
    return inserted


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE in inspector.get_table_names():
        columns = {column["name"]: column for column in inspector.get_columns(TABLE)}
        for name, kind in (("previous_ci", sa.String), ("teacher_ci", sa.String), ("changed_at", sa.DateTime)):
            column = columns.get(name)
            if column is None or not isinstance(column["type"], kind) or column["nullable"] is not False:
                raise RuntimeError(f"Incompatible pre-existing {TABLE}.{name} column")
    else:
        _table(sa.MetaData()).create(bind)
    backfill(bind)


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
