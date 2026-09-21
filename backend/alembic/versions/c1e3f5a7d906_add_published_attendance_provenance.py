"""add published schedule provenance to regular attendance

Revision ID: c1e3f5a7d906
Revises: b0d2e4f6c804
"""

from __future__ import annotations

from collections.abc import Iterable
import re

from alembic import op
import sqlalchemy as sa


revision = "c1e3f5a7d906"
down_revision = "b0d2e4f6c804"
branch_labels = None
depends_on = None

TABLE = "attendance_records"
PUBLISHED_ASSIGNMENT_COLUMN = "published_schedule_assignment_id"


def _schema(target: bool) -> tuple[sa.MetaData, sa.Table]:
    metadata = sa.MetaData()
    teachers = sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    designations = sa.Table("designations", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    biometrics = sa.Table("biometric_records", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    published_assignments = sa.Table(
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
            PUBLISHED_ASSIGNMENT_COLUMN,
            sa.Integer(),
            sa.ForeignKey(published_assignments.c.id, ondelete="RESTRICT"),
            nullable=True,
        ))
    columns.extend([
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("scheduled_start", sa.Time(), nullable=False),
        sa.Column("scheduled_end", sa.Time(), nullable=False),
        sa.Column("actual_entry", sa.Time()),
        sa.Column("actual_exit", sa.Time()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("academic_hours", sa.Integer(), nullable=False),
        sa.Column("late_minutes", sa.Integer(), nullable=False),
        sa.Column("observation", sa.Text()),
        sa.Column(
            "biometric_record_id",
            sa.Integer(),
            sa.ForeignKey(biometrics.c.id, ondelete="SET NULL"),
        ),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    ])
    constraints: list[sa.SchemaItem] = []
    if target:
        constraints.append(sa.CheckConstraint(
            "(designation_id IS NOT NULL AND published_schedule_assignment_id IS NULL) OR "
            "(designation_id IS NULL AND published_schedule_assignment_id IS NOT NULL)",
            name="ck_attendance_record_exactly_one_source",
        ))
    else:
        constraints.append(sa.UniqueConstraint(
            "teacher_ci", "designation_id", "date", "scheduled_start",
            name="uq_attendance_record",
        ))
    table = sa.Table(TABLE, metadata, *columns, *constraints)
    sa.Index("ix_attendance_records_teacher_ci", table.c.teacher_ci)
    sa.Index("ix_attendance_records_designation_id", table.c.designation_id)
    sa.Index("ix_attendance_records_date", table.c.date)
    if target:
        published_column = table.c[PUBLISHED_ASSIGNMENT_COLUMN]
        sa.Index("ix_attendance_records_published_schedule_assignment_id", published_column)
        sa.Index(
            "uq_attendance_record_legacy_source",
            table.c.teacher_ci,
            table.c.designation_id,
            table.c.date,
            table.c.scheduled_start,
            unique=True,
            postgresql_where=sa.text("designation_id IS NOT NULL"),
            sqlite_where=sa.text("designation_id IS NOT NULL"),
        )
        sa.Index(
            "uq_attendance_record_published_source",
            table.c.teacher_ci,
            published_column,
            table.c.date,
            table.c.scheduled_start,
            unique=True,
            postgresql_where=sa.text("published_schedule_assignment_id IS NOT NULL"),
            sqlite_where=sa.text("published_schedule_assignment_id IS NOT NULL"),
        )
    return metadata, table


def _type_signature(type_: sa.types.TypeEngine) -> tuple[object, ...]:
    if isinstance(type_, sa.String):
        return ("string", type_.length)
    if isinstance(type_, sa.Integer):
        return ("integer",)
    if isinstance(type_, sa.DateTime):
        return ("datetime",)
    if isinstance(type_, sa.Date):
        return ("date",)
    if isinstance(type_, sa.Time):
        return ("time",)
    if isinstance(type_, sa.Text):
        return ("text",)
    return (type(type_).__name__.lower(),)


def _strip_outer_parentheses(value: str) -> str:
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        for index, character in enumerate(value):
            depth += character == "("
            depth -= character == ")"
            if depth == 0 and index != len(value) - 1:
                return value
        if depth != 0:
            return value
        value = value[1:-1]
    return value


def _expression(value: object) -> str:
    result = str(value if value is not None else "").lower().replace('"', "")
    result = re.sub(r"::\s*(?:character varying|text|date|timestamp(?: without time zone)?)(?:\[\])?", "", result)
    return _strip_outer_parentheses(re.sub(r"\s+", "", result))


def _default_signature(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    expression = _expression(value)
    if expression in {
        "now()", "pg_catalog.now()", "current_timestamp", "current_timestamp()",
        "transaction_timestamp()", "pg_catalog.transaction_timestamp()",
    }:
        return ("current_timestamp",)
    return ("expression", expression)


def _postgres_autoincrement_signature(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    expression = re.sub(r"\s+", "", str(value).lower().replace('"', ""))
    match = re.fullmatch(r"nextval\('(?:[^']*\.)?([^']+)'::regclass\)", expression)
    return ("postgres_sequence", match.group(1)) if match else _default_signature(value)


def _check_signature(value: object) -> str:
    return re.sub(r"[()]", "", _expression(value))


def _named_columns(items: Iterable[dict[str, object]]) -> set[tuple[str | None, tuple[str, ...]]]:
    return {(item.get("name"), tuple(item.get("column_names") or ())) for item in items}


def _index_where_from_expected(index: sa.Index, dialect: str) -> object:
    return index.dialect_options[dialect].get("where") if dialect in {"postgresql", "sqlite"} else None


def _index_where_from_actual(item: dict[str, object], dialect: str) -> object:
    options = item.get("dialect_options") or {}
    return options.get(f"{dialect}_where") if isinstance(options, dict) else None


def _validate_table(inspector: sa.Inspector, table: sa.Table) -> list[str]:
    errors: list[str] = []
    dialect = inspector.bind.dialect.name
    actual_columns = {item["name"]: item for item in inspector.get_columns(table.name)}
    if set(actual_columns) != set(table.c.keys()):
        errors.append("columns differ")
    else:
        for expected in table.columns:
            actual = actual_columns[expected.name]
            if _type_signature(actual["type"]) != _type_signature(expected.type):
                errors.append(f"column {expected.name} type differs")
            if not expected.primary_key and bool(actual["nullable"]) != bool(expected.nullable):
                errors.append(f"column {expected.name} nullability differs")
            if (
                dialect == "postgresql"
                and expected.primary_key
                and isinstance(expected.type, sa.Integer)
                and expected.server_default is None
            ):
                expected_default = ("postgres_sequence", f"{table.name}_{expected.name}_seq")
                actual_default = _postgres_autoincrement_signature(actual.get("default"))
            else:
                expected_default = _default_signature(
                    expected.server_default.arg if expected.server_default is not None else None
                )
                actual_default = _default_signature(actual.get("default"))
            if actual_default != expected_default:
                errors.append(f"column {expected.name} server default differs")
    expected_pk = tuple(item.name for item in table.primary_key.columns)
    actual_pk = tuple(inspector.get_pk_constraint(table.name).get("constrained_columns") or ())
    if actual_pk != expected_pk:
        errors.append("primary key differs")
    expected_unique = {
        (item.name, tuple(column.name for column in item.columns))
        for item in table.constraints if isinstance(item, sa.UniqueConstraint)
    }
    if _named_columns(inspector.get_unique_constraints(table.name)) != expected_unique:
        errors.append("unique constraints differ")
    unique_names = {name for name, _columns in expected_unique}
    actual_indexes = {
        (
            item.get("name"),
            tuple(item.get("column_names") or ()),
            bool(item.get("unique", False)),
            _expression(_index_where_from_actual(item, dialect)),
        )
        for item in inspector.get_indexes(table.name)
        if item.get("duplicates_constraint") not in unique_names
    }
    expected_indexes = {
        (
            item.name,
            tuple(column.name for column in item.columns),
            bool(item.unique),
            _expression(_index_where_from_expected(item, dialect)),
        )
        for item in table.indexes
    }
    if actual_indexes != expected_indexes:
        errors.append("indexes differ")
    expected_checks = {
        item.name: _check_signature(item.sqltext)
        for item in table.constraints if isinstance(item, sa.CheckConstraint)
    }
    actual_checks = {
        item.get("name"): _check_signature(item.get("sqltext"))
        for item in inspector.get_check_constraints(table.name)
    }
    if actual_checks != expected_checks:
        errors.append("check constraints differ")
    expected_fks = {
        (
            tuple(element.parent.name for element in item.elements),
            tuple(element.column.table.name for element in item.elements),
            tuple(element.column.name for element in item.elements),
            (item.ondelete or "").upper(),
        )
        for item in table.foreign_key_constraints
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


def _migrate_legacy() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint("uq_attendance_record", type_="unique")
        batch.alter_column("designation_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column(PUBLISHED_ASSIGNMENT_COLUMN, sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_attendance_records_published_schedule_assignment",
            "academic_schedule_published_assignments",
            [PUBLISHED_ASSIGNMENT_COLUMN],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_attendance_record_exactly_one_source",
            "(designation_id IS NOT NULL AND published_schedule_assignment_id IS NULL) OR "
            "(designation_id IS NULL AND published_schedule_assignment_id IS NOT NULL)",
        )
    op.create_index(
        "ix_attendance_records_published_schedule_assignment_id",
        TABLE,
        [PUBLISHED_ASSIGNMENT_COLUMN],
        unique=False,
    )
    op.create_index(
        "uq_attendance_record_legacy_source",
        TABLE,
        ["teacher_ci", "designation_id", "date", "scheduled_start"],
        unique=True,
        postgresql_where=sa.text("designation_id IS NOT NULL"),
        sqlite_where=sa.text("designation_id IS NOT NULL"),
    )
    op.create_index(
        "uq_attendance_record_published_source",
        TABLE,
        ["teacher_ci", PUBLISHED_ASSIGNMENT_COLUMN, "date", "scheduled_start"],
        unique=True,
        postgresql_where=sa.text("published_schedule_assignment_id IS NOT NULL"),
        sqlite_where=sa.text("published_schedule_assignment_id IS NOT NULL"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    _old_metadata, old_table = _schema(target=False)
    _target_metadata, target_table = _schema(target=True)
    inspector = sa.inspect(bind)
    target_errors = _validate_table(inspector, target_table)
    if not target_errors:
        return
    old_errors = _validate_table(inspector, old_table)
    if old_errors:
        raise RuntimeError(
            "Incompatible pre-existing attendance_records table: "
            + "; ".join(sorted(set(old_errors + target_errors)))
        )
    _migrate_legacy()
    errors = _validate_table(sa.inspect(bind), target_table)
    if errors:
        raise RuntimeError("Attendance provenance schema validation failed: " + "; ".join(errors))


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; published attendance provenance is destructive to remove."
    )
