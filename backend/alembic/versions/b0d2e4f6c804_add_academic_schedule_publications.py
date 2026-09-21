"""add immutable academic schedule publications

Revision ID: b0d2e4f6c804
Revises: a9c1e3f5b703
"""

from __future__ import annotations

from collections.abc import Iterable
import re

from alembic import op
import sqlalchemy as sa


revision = "b0d2e4f6c804"
down_revision = "a9c1e3f5b703"
branch_labels = None
depends_on = None

PUBLICATIONS = "academic_schedule_publications"
BLOCKS = "academic_schedule_published_blocks"
ASSIGNMENTS = "academic_schedule_published_assignments"


def _schema() -> tuple[sa.MetaData, tuple[sa.Table, ...]]:
    metadata = sa.MetaData()
    programs = sa.Table("academic_programs", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    drafts = sa.Table("academic_schedule_drafts", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    publications = sa.Table(
        PUBLICATIONS,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey(programs.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("academic_period", sa.String(30), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("source_draft_id", sa.Integer(), sa.ForeignKey(drafts.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey(users.c.id, ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "program_id", "academic_period", "effective_from", "sequence",
            name="uq_academic_schedule_publication_revision",
        ),
        sa.UniqueConstraint("source_draft_id", name="uq_academic_schedule_publication_source_draft"),
        sa.CheckConstraint("sequence > 0", name="ck_academic_schedule_publication_sequence"),
    )
    sa.Index(
        "ix_academic_schedule_publications_scope_effective",
        publications.c.program_id,
        publications.c.academic_period,
        publications.c.effective_from,
        publications.c.sequence,
    )
    blocks = sa.Table(
        BLOCKS,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey(publications.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("source_block_id", sa.Integer(), nullable=False),
        sa.Column("source_offering_id", sa.Integer(), nullable=False),
        sa.Column("source_subject_id", sa.Integer(), nullable=False),
        sa.Column("source_group_id", sa.Integer(), nullable=False),
        sa.Column("source_classroom_id", sa.Integer(), nullable=False),
        sa.Column("subject_code", sa.String(30), nullable=False),
        sa.Column("subject_name", sa.String(200), nullable=False),
        sa.Column("group_code", sa.String(30), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("classroom_code", sa.String(30), nullable=False),
        sa.Column("classroom_name", sa.String(200), nullable=False),
        sa.Column("activity_type", sa.String(12), nullable=False),
        sa.Column("weekday", sa.String(12), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint(
            "publication_id", "source_block_id",
            name="uq_academic_schedule_published_block_source",
        ),
        sa.CheckConstraint(
            "activity_type IN ('theory', 'practice')",
            name="ck_academic_schedule_published_block_activity",
        ),
        sa.CheckConstraint(
            "weekday IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday')",
            name="ck_academic_schedule_published_block_weekday",
        ),
        sa.CheckConstraint(
            "start_time < end_time", name="ck_academic_schedule_published_block_time_order"
        ),
    )
    sa.Index(
        "ix_academic_schedule_published_blocks_publication_day",
        blocks.c.publication_id,
        blocks.c.weekday,
        blocks.c.start_time,
    )
    assignments = sa.Table(
        ASSIGNMENTS,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("publication_block_id", sa.Integer(), sa.ForeignKey(blocks.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("source_assignment_id", sa.Integer(), nullable=False),
        sa.Column("teacher_ci", sa.String(20), nullable=False),
        sa.Column("teacher_name", sa.String(200), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.UniqueConstraint(
            "publication_block_id", "source_assignment_id",
            name="uq_academic_schedule_published_assignment_source",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_academic_schedule_published_assignment_date_order",
        ),
    )
    sa.Index(
        "ix_academic_schedule_published_assignments_block_dates",
        assignments.c.publication_block_id,
        assignments.c.effective_from,
        assignments.c.effective_to,
    )
    sa.Index(
        "ix_academic_schedule_published_assignments_teacher_dates",
        assignments.c.teacher_ci,
        assignments.c.effective_from,
        assignments.c.effective_to,
    )
    return metadata, (publications, blocks, assignments)


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
    expression = str(value).lower().replace('"', "")
    expression = re.sub(r"\s+", "", expression)
    match = re.fullmatch(r"nextval\('(?:[^']*\.)?([^']+)'::regclass\)", expression)
    return ("postgres_sequence", match.group(1)) if match else _default_signature(value)


def _check_signature(value: object) -> tuple[object, ...]:
    expression = _expression(value)
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


def _named_columns(items: Iterable[dict[str, object]]) -> set[tuple[str | None, tuple[str, ...]]]:
    return {(item.get("name"), tuple(item.get("column_names") or ())) for item in items}


def _validate_table(inspector: sa.Inspector, table: sa.Table) -> list[str]:
    errors: list[str] = []
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
                inspector.bind.dialect.name == "postgresql"
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
    if tuple(inspector.get_pk_constraint(table.name).get("constrained_columns") or ()) != expected_pk:
        errors.append("primary key differs")
    expected_unique = {
        (item.name, tuple(column.name for column in item.columns))
        for item in table.constraints if isinstance(item, sa.UniqueConstraint)
    }
    if _named_columns(inspector.get_unique_constraints(table.name)) != expected_unique:
        errors.append("unique constraints differ")
    unique_names = {name for name, _columns in expected_unique}
    actual_indexes = {
        (item.get("name"), tuple(item.get("column_names") or ()), bool(item.get("unique", False)))
        for item in inspector.get_indexes(table.name)
        if item.get("duplicates_constraint") not in unique_names
    }
    expected_indexes = {
        (item.name, tuple(column.name for column in item.columns), bool(item.unique))
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


def _replace_draft_status_check(bind: sa.Connection) -> None:
    with op.batch_alter_table("academic_schedule_drafts") as batch:
        batch.drop_constraint("ck_academic_schedule_draft_status", type_="check")
        batch.create_check_constraint(
            "ck_academic_schedule_draft_status",
            "status IN ('draft', 'archived', 'published')",
        )


def upgrade() -> None:
    bind = op.get_bind()
    _metadata, tables = _schema()
    inspector = sa.inspect(bind)
    for table in tables:
        if inspector.has_table(table.name):
            errors = _validate_table(inspector, table)
            if errors:
                raise RuntimeError(
                    f"Incompatible pre-existing table {table.name}: " + "; ".join(errors)
                )
    _replace_draft_status_check(bind)
    for table in tables:
        if not sa.inspect(bind).has_table(table.name):
            table.create(bind)
    inspector = sa.inspect(bind)
    for table in tables:
        errors = _validate_table(inspector, table)
        if errors:
            raise RuntimeError(f"Publication schema validation failed for {table.name}: " + "; ".join(errors))


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; immutable schedule publications are destructive to remove."
    )
