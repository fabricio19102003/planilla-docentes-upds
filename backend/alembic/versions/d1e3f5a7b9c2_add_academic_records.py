"""add academic records

Revision ID: d1e3f5a7b9c2
Revises: c5e7a9b1d3f4

Curriculum plans and their subject slots, normalized academic terms, students,
their per-subject history imported from the legacy academic system, and the
receipts of each applied legacy import.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d1e3f5a7b9c2"
down_revision: Union[str, None] = "c5e7a9b1d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    ]


def _tables(metadata: sa.MetaData) -> list[sa.Table]:
    sa.Table("academic_programs", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("academic_subjects", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))

    plans = sa.Table(
        "curriculum_plans",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "program_id", sa.Integer(),
            sa.ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=False, index=True,
        ),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("total_semesters", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("program_id", "code", name="uq_curriculum_plan_code"),
        sa.CheckConstraint("total_semesters > 0", name="ck_curriculum_plan_semesters"),
    )
    curriculum_subjects = sa.Table(
        "curriculum_subjects",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id", sa.Integer(),
            sa.ForeignKey("curriculum_plans.id", ondelete="RESTRICT"), nullable=False, index=True,
        ),
        sa.Column(
            "subject_id", sa.Integer(),
            sa.ForeignKey("academic_subjects.id", ondelete="RESTRICT"), nullable=True, index=True,
        ),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("slot_name", sa.String(200), nullable=False),
        sa.Column("theory_hours", sa.Integer(), nullable=False),
        sa.Column("practice_hours", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("is_elective", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("plan_id", "subject_id", name="uq_curriculum_subject_subject"),
        sa.UniqueConstraint("plan_id", "semester", "slot_name", name="uq_curriculum_subject_slot"),
        sa.CheckConstraint("semester > 0", name="ck_curriculum_subject_semester"),
        sa.CheckConstraint(
            "theory_hours >= 0 AND practice_hours >= 0 AND credits >= 0",
            name="ck_curriculum_subject_load",
        ),
    )
    terms = sa.Table(
        "academic_terms",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False, index=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(4), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("is_intensive", sa.Boolean(), nullable=False),
        sa.Column("legacy_names", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_academic_term_code"),
        sa.UniqueConstraint("year", "kind", name="uq_academic_term_year_kind"),
        sa.CheckConstraint("kind IN ('I', 'II', 'INV', 'VER')", name="ck_academic_term_kind"),
    )
    imports = sa.Table(
        "academic_history_imports",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False, index=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    students = sa.Table(
        "students",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_number", sa.String(30), nullable=False, index=True),
        sa.Column("document_type", sa.String(60), nullable=False),
        sa.Column("first_names", sa.String(120), nullable=False),
        sa.Column("last_names", sa.String(120), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("personal_email", sa.String(200), nullable=True),
        sa.Column("academic_email", sa.String(200), nullable=True),
        sa.Column("birth_country", sa.String(80), nullable=True),
        sa.Column("nationality", sa.String(80), nullable=True),
        sa.Column("is_foreign", sa.Boolean(), nullable=False, index=True),
        sa.Column("school", sa.String(200), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("legacy_enrollment_status", sa.String(30), nullable=True, index=True),
        sa.Column(
            "program_id", sa.Integer(),
            sa.ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=True, index=True,
        ),
        sa.Column(
            "curriculum_plan_id", sa.Integer(),
            sa.ForeignKey("curriculum_plans.id", ondelete="RESTRICT"), nullable=True,
        ),
        sa.Column(
            "last_import_id", sa.Integer(),
            sa.ForeignKey("academic_history_imports.id", ondelete="SET NULL"), nullable=True,
        ),
        *_timestamps(),
        sa.UniqueConstraint("document_number", name="uq_student_document_number"),
    )
    records = sa.Table(
        "student_subject_records",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("legacy_registration_id", sa.Integer(), nullable=False),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True,
        ),
        sa.Column(
            "term_id", sa.Integer(),
            sa.ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True,
        ),
        sa.Column(
            "subject_id", sa.Integer(),
            sa.ForeignKey("academic_subjects.id", ondelete="RESTRICT"), nullable=False, index=True,
        ),
        sa.Column("group_code", sa.String(20), nullable=True),
        sa.Column("shift", sa.String(20), nullable=True),
        sa.Column("teacher_document", sa.String(30), nullable=True),
        sa.Column("teacher_name", sa.String(200), nullable=True),
        sa.Column(
            "teacher_ci", sa.String(20),
            sa.ForeignKey("teachers.ci", ondelete="SET NULL"), nullable=True, index=True,
        ),
        sa.Column("status", sa.String(12), nullable=False, index=True),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column(
            "last_import_id", sa.Integer(),
            sa.ForeignKey("academic_history_imports.id", ondelete="SET NULL"), nullable=True,
        ),
        *_timestamps(),
        sa.UniqueConstraint("legacy_registration_id", name="uq_student_record_legacy_id"),
        sa.CheckConstraint(
            "status IN ('aprobado', 'reprobado', 'retirado', 'pendiente')",
            name="ck_student_record_status",
        ),
        sa.CheckConstraint(
            "grade IS NULL OR (grade >= 0 AND grade <= 100)", name="ck_student_record_grade"
        ),
    )
    # Creation order respects foreign keys.
    return [plans, curriculum_subjects, terms, imports, students, records]


def _validate(inspector: sa.Inspector, table: sa.Table) -> None:
    columns = {column["name"]: column for column in inspector.get_columns(table.name)}
    for expected in table.columns:
        column = columns.get(expected.name)
        if column is None or (not expected.primary_key and column["nullable"] is not expected.nullable):
            raise RuntimeError(f"Incompatible pre-existing {table.name}.{expected.name} column")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    tables = _tables(sa.MetaData())
    for table in tables:
        if table.name in existing:
            _validate(inspector, table)
    for table in tables:
        if table.name not in existing:
            table.create(bind)


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
