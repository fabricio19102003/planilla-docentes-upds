"""add intensive courses

Revision ID: f3a5b7c9d1e3
Revises: e2f4a6c8d0b1

Summer/winter intensive courses (term VER/YYYY or INV/YYYY) opened by registration
staff, the students enrolled in them, and the single-row settings with the rates,
margin and price limits used to estimate the price per student. The settings start
without rates: until staff configure them no course can be opened.
"""
from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f3a5b7c9d1e3"
down_revision: Union[str, None] = "e2f4a6c8d0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    ]


def _fk(column: str, target: str, ondelete: str, nullable: bool = False, index: bool = True) -> sa.Column:
    return sa.Column(column, sa.Integer(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable, index=index)


def _tables(metadata: sa.MetaData) -> list[sa.Table]:
    for name in ("students", "users", "academic_subjects"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    settings = sa.Table(
        "intensive_course_settings", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("theory_hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("practice_hourly_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("margin_factor", sa.Numeric(6, 3), nullable=False),
        sa.Column("min_price", sa.Integer(), nullable=False),
        sa.Column("max_price", sa.Integer(), nullable=False),
        _fk("updated_by", "users.id", "SET NULL", nullable=True, index=False),
        *_timestamps(),
        sa.CheckConstraint("id = 1", name="ck_intensive_settings_single_row"),
        sa.CheckConstraint("theory_hourly_rate IS NULL OR theory_hourly_rate > 0", name="ck_intensive_settings_theory"),
        sa.CheckConstraint("practice_hourly_rate IS NULL OR practice_hourly_rate > 0",
                           name="ck_intensive_settings_practice"),
        sa.CheckConstraint("margin_factor >= 1", name="ck_intensive_settings_factor"),
        sa.CheckConstraint("min_price > 0 AND min_price <= max_price", name="ck_intensive_settings_prices"),
    )
    courses = sa.Table(
        "intensive_courses", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("term_code", sa.String(30), nullable=False, index=True),
        _fk("subject_id", "academic_subjects.id", "RESTRICT"),
        sa.Column("teacher_ci", sa.String(20), sa.ForeignKey("teachers.ci", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("enrollment_starts_on", sa.Date(), nullable=False),
        sa.Column("enrollment_ends_on", sa.Date(), nullable=False),
        sa.Column("theory_hours", sa.Integer(), nullable=False),
        sa.Column("practice_hours", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, index=True),
        sa.Column("final_enrolled", sa.Integer(), nullable=True),
        sa.Column("final_price", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        _fk("closed_by", "users.id", "SET NULL", nullable=True, index=False),
        _fk("created_by", "users.id", "SET NULL", nullable=True, index=False),
        *_timestamps(),
        sa.UniqueConstraint("term_code", "subject_id", name="uq_intensive_course_term_subject"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_intensive_course_status"),
        sa.CheckConstraint("capacity >= 1", name="ck_intensive_course_capacity"),
        sa.CheckConstraint("enrollment_ends_on >= enrollment_starts_on", name="ck_intensive_course_dates"),
        sa.CheckConstraint("theory_hours >= 0 AND practice_hours >= 0", name="ck_intensive_course_hours"),
        sa.CheckConstraint("theory_hours > 0 OR practice_hours > 0", name="ck_intensive_course_has_hours"),
        sa.CheckConstraint(
            "status = 'open' OR (final_enrolled IS NOT NULL AND final_price IS NOT NULL)",
            name="ck_intensive_course_closed_price",
        ),
    )
    enrollments = sa.Table(
        "intensive_enrollments", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        _fk("course_id", "intensive_courses.id", "CASCADE"),
        _fk("student_id", "students.id", "RESTRICT"),
        sa.Column("enrolled_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("course_id", "student_id", name="uq_intensive_enrollment_student"),
    )
    # Creation order respects foreign keys.
    return [settings, courses, enrollments]


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables(sa.MetaData())
    for table in tables:
        table.create(bind)
    bind.execute(tables[0].insert().values(id=1, margin_factor=Decimal("1.10"), min_price=1200, max_price=1600))


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
