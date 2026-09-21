"""add published schedule provenance to practice attendance

Revision ID: d2f4a6b8e017
Revises: c1e3f5a7d906
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "d2f4a6b8e017"
down_revision = "c1e3f5a7d906"
branch_labels = None
depends_on = None

TABLE = "practice_attendance_logs"
PUBLISHED_COLUMN = "published_schedule_assignment_id"


def _validation_helpers():
    path = Path(__file__).with_name("c1e3f5a7d906_add_published_attendance_provenance.py")
    spec = importlib.util.spec_from_file_location("attendance_provenance_validation", path)
    if spec is None or spec.loader is None:  # pragma: no cover - deployment invariant
        raise RuntimeError("Attendance provenance validation helpers are unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema(target: bool) -> tuple[sa.MetaData, sa.Table]:
    metadata = sa.MetaData()
    teachers = sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    designations = sa.Table("designations", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    users = sa.Table("users", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    published = sa.Table(
        "academic_schedule_published_assignments",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("teacher_ci", sa.String(20), sa.ForeignKey(teachers.c.ci, ondelete="CASCADE"), nullable=False),
        sa.Column(
            "designation_id",
            sa.Integer(),
            sa.ForeignKey(designations.c.id, ondelete="CASCADE"),
            nullable=target,
        ),
    ]
    if target:
        columns.append(sa.Column(
            PUBLISHED_COLUMN,
            sa.Integer(),
            sa.ForeignKey(published.c.id, ondelete="RESTRICT"),
        ))
    columns.extend([
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("scheduled_start", sa.Time(), nullable=False),
        sa.Column("scheduled_end", sa.Time(), nullable=False),
        sa.Column("actual_start", sa.Time()),
        sa.Column("actual_end", sa.Time()),
        sa.Column("academic_hours", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("observation", sa.Text()),
        sa.Column("registered_by", sa.String(20), sa.ForeignKey(users.c.ci)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ])
    constraints: list[sa.SchemaItem] = []
    if target:
        constraints.append(sa.CheckConstraint(
            "(designation_id IS NOT NULL AND published_schedule_assignment_id IS NULL) OR "
            "(designation_id IS NULL AND published_schedule_assignment_id IS NOT NULL)",
            name="ck_practice_attendance_log_exactly_one_source",
        ))
    else:
        constraints.append(sa.UniqueConstraint(
            "teacher_ci", "designation_id", "date", "scheduled_start",
            name="uq_practice_attendance_log",
        ))
    table = sa.Table(TABLE, metadata, *columns, *constraints)
    sa.Index("ix_practice_attendance_logs_teacher_ci", table.c.teacher_ci)
    sa.Index("ix_practice_attendance_logs_designation_id", table.c.designation_id)
    sa.Index("ix_practice_attendance_logs_date", table.c.date)
    if target:
        published_column = table.c[PUBLISHED_COLUMN]
        sa.Index("ix_practice_attendance_logs_published_schedule_assignment_id", published_column)
        sa.Index(
            "uq_practice_attendance_log_legacy_source",
            table.c.teacher_ci, table.c.designation_id, table.c.date, table.c.scheduled_start,
            unique=True,
            postgresql_where=sa.text("designation_id IS NOT NULL"),
            sqlite_where=sa.text("designation_id IS NOT NULL"),
        )
        sa.Index(
            "uq_practice_attendance_log_published_source",
            table.c.teacher_ci, published_column, table.c.date, table.c.scheduled_start,
            unique=True,
            postgresql_where=sa.text("published_schedule_assignment_id IS NOT NULL"),
            sqlite_where=sa.text("published_schedule_assignment_id IS NOT NULL"),
        )
    return metadata, table


def _migrate_legacy() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint("uq_practice_attendance_log", type_="unique")
        batch.alter_column("designation_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column(PUBLISHED_COLUMN, sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_practice_attendance_logs_published_schedule_assignment",
            "academic_schedule_published_assignments",
            [PUBLISHED_COLUMN],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_practice_attendance_log_exactly_one_source",
            "(designation_id IS NOT NULL AND published_schedule_assignment_id IS NULL) OR "
            "(designation_id IS NULL AND published_schedule_assignment_id IS NOT NULL)",
        )
    op.create_index(
        "ix_practice_attendance_logs_published_schedule_assignment_id",
        TABLE,
        [PUBLISHED_COLUMN],
    )
    op.create_index(
        "uq_practice_attendance_log_legacy_source",
        TABLE,
        ["teacher_ci", "designation_id", "date", "scheduled_start"],
        unique=True,
        postgresql_where=sa.text("designation_id IS NOT NULL"),
        sqlite_where=sa.text("designation_id IS NOT NULL"),
    )
    op.create_index(
        "uq_practice_attendance_log_published_source",
        TABLE,
        ["teacher_ci", PUBLISHED_COLUMN, "date", "scheduled_start"],
        unique=True,
        postgresql_where=sa.text("published_schedule_assignment_id IS NOT NULL"),
        sqlite_where=sa.text("published_schedule_assignment_id IS NOT NULL"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    helpers = _validation_helpers()
    _old_metadata, old_table = _schema(target=False)
    _target_metadata, target_table = _schema(target=True)
    inspector = sa.inspect(bind)
    target_errors = helpers._validate_table(inspector, target_table)
    if not target_errors:
        return
    old_errors = helpers._validate_table(inspector, old_table)
    if old_errors:
        raise RuntimeError(
            "Incompatible pre-existing practice_attendance_logs table: "
            + "; ".join(sorted(set(old_errors + target_errors)))
        )
    _migrate_legacy()
    errors = helpers._validate_table(sa.inspect(bind), target_table)
    if errors:
        raise RuntimeError("Practice attendance provenance validation failed: " + "; ".join(errors))


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; published practice attendance provenance is destructive to remove."
    )
