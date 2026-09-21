"""add academic management catalogs and teacher availability

Revision ID: e7a9c1d3f501
Revises: a2c4e6f8b003
"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa


revision = "e7a9c1d3f501"
down_revision = "a2c4e6f8b003"
branch_labels = None
depends_on = None

TARGET_TABLES = (
    "academic_programs",
    "academic_subjects",
    "subject_offerings",
    "academic_groups",
    "classrooms",
    "teacher_availability",
)


def _schema() -> tuple[sa.MetaData, dict[str, sa.Table]]:
    metadata = sa.MetaData()
    teachers = sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))

    def timestamps() -> tuple[sa.Column, sa.Column]:
        return (
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    programs = sa.Table(
        "academic_programs", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.UniqueConstraint("code", name="uq_academic_program_code"),
    )
    sa.Index("ix_academic_programs_code", programs.c.code)
    sa.Index("ix_academic_programs_active", programs.c.active)

    subjects = sa.Table(
        "academic_subjects", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.UniqueConstraint("code", name="uq_academic_subject_code"),
    )
    sa.Index("ix_academic_subjects_code", subjects.c.code)
    sa.Index("ix_academic_subjects_active", subjects.c.active)

    offerings = sa.Table(
        "subject_offerings", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey(subjects.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey(programs.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_period", sa.String(30), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("theory_hours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("practice_hours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.UniqueConstraint("subject_id", "program_id", "academic_period", "semester", name="uq_subject_offering_identity"),
        sa.CheckConstraint("semester > 0", name="ck_subject_offering_semester_positive"),
        sa.CheckConstraint("theory_hours >= 0", name="ck_subject_offering_theory_hours"),
        sa.CheckConstraint("practice_hours >= 0", name="ck_subject_offering_practice_hours"),
        sa.CheckConstraint("theory_hours > 0 OR practice_hours > 0", name="ck_subject_offering_has_hours"),
    )
    for column in (offerings.c.subject_id, offerings.c.program_id, offerings.c.academic_period, offerings.c.active):
        sa.Index(f"ix_subject_offerings_{column.name}", column)

    groups = sa.Table(
        "academic_groups", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey(programs.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_period", sa.String(30), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("shift", sa.String(30), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("expected_size", sa.Integer()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.UniqueConstraint("program_id", "academic_period", "semester", "code", name="uq_academic_group_identity"),
        sa.CheckConstraint("semester > 0", name="ck_academic_group_semester_positive"),
        sa.CheckConstraint("expected_size IS NULL OR expected_size > 0", name="ck_academic_group_expected_size"),
    )
    for column in (groups.c.program_id, groups.c.academic_period, groups.c.active):
        sa.Index(f"ix_academic_groups_{column.name}", column)

    classrooms = sa.Table(
        "classrooms", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("campus", sa.String(120), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("classroom_type", sa.String(20), nullable=False),
        sa.Column("resources", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.UniqueConstraint("code", name="uq_classroom_code"),
        sa.CheckConstraint("capacity > 0", name="ck_classroom_capacity_positive"),
        sa.CheckConstraint("classroom_type IN ('classroom', 'laboratory', 'virtual', 'other')", name="ck_classroom_type"),
    )
    sa.Index("ix_classrooms_code", classrooms.c.code)
    sa.Index("ix_classrooms_active", classrooms.c.active)

    availability = sa.Table(
        "teacher_availability", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_ci", sa.String(20), sa.ForeignKey(teachers.c.ci, ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_period", sa.String(30), nullable=False),
        sa.Column("weekday", sa.String(12), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.CheckConstraint("weekday IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')", name="ck_teacher_availability_weekday"),
        sa.CheckConstraint("start_time < end_time", name="ck_teacher_availability_time_order"),
    )
    for column in (availability.c.teacher_ci, availability.c.academic_period, availability.c.weekday, availability.c.active):
        sa.Index(f"ix_teacher_availability_{column.name}", column)

    return metadata, {table.name: table for table in (programs, subjects, offerings, groups, classrooms, availability)}


def _type_signature(type_: sa.types.TypeEngine) -> tuple[object, ...]:
    if isinstance(type_, sa.Text):
        return ("text",)
    if isinstance(type_, sa.String):
        return ("string", type_.length)
    if isinstance(type_, sa.Boolean):
        return ("boolean",)
    if isinstance(type_, sa.Integer):
        return ("integer",)
    if isinstance(type_, sa.DateTime):
        return ("datetime",)
    if isinstance(type_, sa.Time):
        return ("time",)
    if isinstance(type_, sa.JSON):
        return ("json",)
    return (type(type_).__name__.lower(),)


def _named_column_sets(items: Iterable[dict[str, object]]) -> set[tuple[str | None, tuple[str, ...]]]:
    return {(item.get("name"), tuple(item.get("column_names") or ())) for item in items}


def _validate_table(inspector: sa.Inspector, table: sa.Table) -> list[str]:
    errors: list[str] = []
    actual_columns = {column["name"]: column for column in inspector.get_columns(table.name)}
    if set(actual_columns) != set(table.c.keys()):
        errors.append("columns differ")
    else:
        for expected in table.columns:
            actual = actual_columns[expected.name]
            if _type_signature(actual["type"]) != _type_signature(expected.type):
                errors.append(f"column {expected.name} has incompatible type")
            if not expected.primary_key and bool(actual["nullable"]) != bool(expected.nullable):
                errors.append(f"column {expected.name} has incompatible nullability")

    expected_pk = tuple(column.name for column in table.primary_key.columns)
    actual_pk = tuple(inspector.get_pk_constraint(table.name).get("constrained_columns") or ())
    if actual_pk != expected_pk:
        errors.append("primary key differs")

    expected_unique = {
        (constraint.name, tuple(column.name for column in constraint.columns))
        for constraint in table.constraints if isinstance(constraint, sa.UniqueConstraint)
    }
    if _named_column_sets(inspector.get_unique_constraints(table.name)) != expected_unique:
        errors.append("unique constraints differ")

    unique_names = {name for name, _columns in expected_unique}
    actual_indexes = {
        (item.get("name"), tuple(item.get("column_names") or ()), bool(item.get("unique", False)))
        for item in inspector.get_indexes(table.name)
        if item.get("duplicates_constraint") not in unique_names
    }
    expected_indexes = {
        (index.name, tuple(column.name for column in index.columns), bool(index.unique))
        for index in table.indexes
    }
    if actual_indexes != expected_indexes:
        errors.append("indexes differ")

    expected_checks = {
        constraint.name for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    }
    actual_checks = {item.get("name") for item in inspector.get_check_constraints(table.name)}
    if actual_checks != expected_checks:
        errors.append("check constraints differ")

    expected_fks = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.column.table.name for element in constraint.elements),
            tuple(element.column.name for element in constraint.elements),
            (constraint.ondelete or "").upper(),
        )
        for constraint in table.foreign_key_constraints
    }
    actual_fks = {
        (
            tuple(item.get("constrained_columns") or ()),
            (str(item.get("referred_table")),),
            tuple(item.get("referred_columns") or ()),
            str((item.get("options") or {}).get("ondelete") or "").upper(),
        )
        for item in inspector.get_foreign_keys(table.name)
    }
    if actual_fks != expected_fks:
        errors.append("foreign keys differ")
    return errors


def upgrade() -> None:
    bind = op.get_bind()
    _metadata, tables = _schema()
    inspector = sa.inspect(bind)

    # Validate every adopted table before creating anything. This prevents a
    # partial schema when a pre-created table is incompatible.
    for name in TARGET_TABLES:
        if inspector.has_table(name):
            errors = _validate_table(inspector, tables[name])
            if errors:
                raise RuntimeError(f"Incompatible pre-existing table {name}: " + "; ".join(errors))

    for name in TARGET_TABLES:
        if not sa.inspect(bind).has_table(name):
            tables[name].create(bind)

    inspector = sa.inspect(bind)
    for name in TARGET_TABLES:
        errors = _validate_table(inspector, tables[name])
        if errors:
            raise RuntimeError(f"Academic management schema validation failed for {name}: " + "; ".join(errors))


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; adopted academic management data is destructive to remove."
    )
