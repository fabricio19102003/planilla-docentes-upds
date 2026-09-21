"""add effective-dated academic schedule assignments

Revision ID: a9c1e3f5b703
Revises: f8b0d2e4a602
"""

from __future__ import annotations

from collections.abc import Iterable
import re

from alembic import op
import sqlalchemy as sa


revision = "a9c1e3f5b703"
down_revision = "f8b0d2e4a602"
branch_labels = None
depends_on = None

TABLE_NAME = "academic_schedule_assignments"


def _schema() -> tuple[sa.MetaData, sa.Table]:
    metadata = sa.MetaData()
    blocks = sa.Table("academic_schedule_blocks", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    teachers = sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    assignments = sa.Table(
        TABLE_NAME,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("block_id", sa.Integer(), sa.ForeignKey(blocks.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_ci", sa.String(20), sa.ForeignKey(teachers.c.ci, ondelete="RESTRICT"), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_academic_schedule_assignment_date_order",
        ),
    )
    sa.Index(
        "ix_academic_schedule_assignments_block_dates",
        assignments.c.block_id,
        assignments.c.effective_from,
        assignments.c.effective_to,
    )
    sa.Index(
        "ix_academic_schedule_assignments_teacher_dates",
        assignments.c.teacher_ci,
        assignments.c.effective_from,
        assignments.c.effective_to,
    )
    return metadata, assignments


def _type_signature(type_: sa.types.TypeEngine) -> tuple[object, ...]:
    if isinstance(type_, sa.String):
        return ("string", type_.length)
    if isinstance(type_, sa.Integer):
        return ("integer",)
    if isinstance(type_, sa.DateTime):
        return ("datetime",)
    if isinstance(type_, sa.Date):
        return ("date",)
    return (type(type_).__name__.lower(),)


def _named_column_sets(items: Iterable[dict[str, object]]) -> set[tuple[str | None, tuple[str, ...]]]:
    return {(item.get("name"), tuple(item.get("column_names") or ())) for item in items}


def _strip_outer_parentheses(value: str) -> str:
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        encloses_expression = True
        for index, character in enumerate(value):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0 and index != len(value) - 1:
                    encloses_expression = False
                    break
        if not encloses_expression or depth != 0:
            break
        value = value[1:-1]
    return value


def _check_signature(sqltext: object) -> tuple[object, ...]:
    expression = str(sqltext if sqltext is not None else "").lower().replace('"', "")
    expression = re.sub(r"::\s*(?:character varying|text|date)(?:\[\])?", "", expression)
    expression = re.sub(r"\s+", "", expression)
    expression = _strip_outer_parentheses(expression)
    return ("expression", expression.replace("(", "").replace(")", ""))


def _server_default_signature(default: object) -> tuple[object, ...] | None:
    if default is None:
        return None
    expression = str(default).strip().lower().replace('"', "")
    expression = re.sub(r"\s+", "", expression)
    expression = _strip_outer_parentheses(expression)
    expression = re.sub(
        r"::(?:timestamp(?:withouttimezone)?|datetime)$", "", expression
    )
    expression = _strip_outer_parentheses(expression)
    if expression in {
        "now()",
        "pg_catalog.now()",
        "current_timestamp",
        "current_timestamp()",
        "transaction_timestamp()",
        "pg_catalog.transaction_timestamp()",
    }:
        return ("current_timestamp",)
    return ("expression", expression)


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
            if expected.server_default is not None:
                expected_default = _server_default_signature(expected.server_default.arg)
                actual_default = _server_default_signature(actual.get("default"))
                if actual_default != expected_default:
                    errors.append(f"column {expected.name} has incompatible server default")

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
        constraint.name: _check_signature(constraint.sqltext)
        for constraint in table.constraints if isinstance(constraint, sa.CheckConstraint)
    }
    actual_checks = {
        item.get("name"): _check_signature(item.get("sqltext"))
        for item in inspector.get_check_constraints(table.name)
    }
    if set(actual_checks) != set(expected_checks):
        errors.append("check constraint names differ")
    else:
        for name, definition in expected_checks.items():
            if actual_checks[name] != definition:
                errors.append(f"check constraint {name} definition differs")

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
    _metadata, table = _schema()
    inspector = sa.inspect(bind)
    if inspector.has_table(TABLE_NAME):
        errors = _validate_table(inspector, table)
        if errors:
            raise RuntimeError(f"Incompatible pre-existing table {TABLE_NAME}: " + "; ".join(errors))
    else:
        table.create(bind)
    errors = _validate_table(sa.inspect(bind), table)
    if errors:
        raise RuntimeError(f"Academic schedule assignment schema validation failed: " + "; ".join(errors))


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; adopted academic schedule assignment history is destructive to remove."
    )
