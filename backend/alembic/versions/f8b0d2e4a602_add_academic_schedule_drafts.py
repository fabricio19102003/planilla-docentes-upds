"""add academic schedule drafts and blocks

Revision ID: f8b0d2e4a602
Revises: e7a9c1d3f501
"""

from __future__ import annotations

from collections.abc import Iterable
import re

from alembic import op
import sqlalchemy as sa


revision = "f8b0d2e4a602"
down_revision = "e7a9c1d3f501"
branch_labels = None
depends_on = None

TARGET_TABLES = ("academic_schedule_drafts", "academic_schedule_blocks")


def _schema() -> tuple[sa.MetaData, dict[str, sa.Table]]:
    metadata = sa.MetaData()
    programs = sa.Table("academic_programs", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    offerings = sa.Table("subject_offerings", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    groups = sa.Table("academic_groups", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    classrooms = sa.Table("classrooms", metadata, sa.Column("id", sa.Integer(), primary_key=True))

    def timestamps() -> tuple[sa.Column, sa.Column]:
        return (
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    drafts = sa.Table(
        "academic_schedule_drafts", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey(programs.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_period", sa.String(30), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        *timestamps(),
        sa.CheckConstraint("status IN ('draft', 'archived')", name="ck_academic_schedule_draft_status"),
    )
    for column in (drafts.c.program_id, drafts.c.academic_period, drafts.c.normalized_name, drafts.c.status):
        sa.Index(f"ix_academic_schedule_drafts_{column.name}", column)

    blocks = sa.Table(
        "academic_schedule_blocks", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey(drafts.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("offering_id", sa.Integer(), sa.ForeignKey(offerings.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey(groups.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("classroom_id", sa.Integer(), sa.ForeignKey(classrooms.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("activity_type", sa.String(12), nullable=False),
        sa.Column("weekday", sa.String(12), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("activity_type IN ('theory', 'practice')", name="ck_academic_schedule_block_activity_type"),
        sa.CheckConstraint(
            "weekday IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday')",
            name="ck_academic_schedule_block_weekday",
        ),
        sa.CheckConstraint("start_time < end_time", name="ck_academic_schedule_block_time_order"),
    )
    for column in (blocks.c.draft_id, blocks.c.offering_id, blocks.c.group_id, blocks.c.classroom_id, blocks.c.weekday):
        sa.Index(f"ix_academic_schedule_blocks_{column.name}", column)

    return metadata, {table.name: table for table in (drafts, blocks)}


def _type_signature(type_: sa.types.TypeEngine) -> tuple[object, ...]:
    if isinstance(type_, sa.String):
        return ("string", type_.length)
    if isinstance(type_, sa.Integer):
        return ("integer",)
    if isinstance(type_, sa.DateTime):
        return ("datetime",)
    if isinstance(type_, sa.Time):
        return ("time",)
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
    expression = re.sub(r"::\s*(?:character varying|text)(?:\[\])?", "", expression)
    expression = re.sub(r"\s+", "", expression)
    expression = _strip_outer_parentheses(expression)

    literal_list = r"'(?:''|[^'])*'(?:,'(?:''|[^'])*')*"
    membership = re.fullmatch(
        rf"([a-z_][a-z0-9_]*)in\(({literal_list})\)", expression
    )
    if membership:
        values = tuple(sorted(re.findall(r"'((?:''|[^'])*)'", membership.group(2))))
        if values:
            return ("membership", membership.group(1), values)

    postgres_membership = re.fullmatch(
        rf"([a-z_][a-z0-9_]*)=any\(array\[({literal_list})\]\)", expression
    )
    if postgres_membership:
        values = tuple(sorted(re.findall(r"'((?:''|[^'])*)'", postgres_membership.group(2))))
        if values:
            return ("membership", postgres_membership.group(1), values)

    return ("expression", expression)


def _check_definitions(items: Iterable[dict[str, object]]) -> dict[str | None, tuple[object, ...]]:
    return {item.get("name"): _check_signature(item.get("sqltext")) for item in items}


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
    if _named_column_sets(inspector.get_unique_constraints(table.name)):
        errors.append("unique constraints differ")

    actual_indexes = {
        (item.get("name"), tuple(item.get("column_names") or ()), bool(item.get("unique", False)))
        for item in inspector.get_indexes(table.name)
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
    actual_checks = _check_definitions(inspector.get_check_constraints(table.name))
    if set(actual_checks) != set(expected_checks):
        errors.append("check constraint names differ")
    else:
        for name, expected_definition in expected_checks.items():
            actual_definition = actual_checks[name]
            forward_compatible_publication_status = (
                table.name == "academic_schedule_drafts"
                and name == "ck_academic_schedule_draft_status"
                and expected_definition == ("membership", "status", ("archived", "draft"))
                and actual_definition == (
                    "membership", "status", ("archived", "draft", "published")
                )
            )
            if actual_definition != expected_definition and not forward_compatible_publication_status:
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
    _metadata, tables = _schema()
    inspector = sa.inspect(bind)
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
            raise RuntimeError(f"Academic schedule schema validation failed for {name}: " + "; ".join(errors))


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; adopted academic schedule data is destructive to remove."
    )
