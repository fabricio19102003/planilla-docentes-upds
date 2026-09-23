"""add historical schedule import receipts

Revision ID: f4b6d8e0a219
Revises: e3a5c7f9b128
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "f4b6d8e0a219"
down_revision = "e3a5c7f9b128"
branch_labels = None
depends_on = None

TABLE = "historical_schedule_imports"
CLASSROOMS = "classrooms"
CAPACITY_CHECK = (
    "(classroom_type IN ('classroom', 'laboratory') AND capacity IS NOT NULL AND capacity > 0) "
    "OR (classroom_type IN ('virtual', 'other') AND (capacity IS NULL OR capacity > 0))"
)
# PostgreSQL reflection deparses IN predicates to ANY arrays and strips the
# outer CHECK parenthesis. Keep that exact representation for adoption checks.
POSTGRES_REFLECTED_CAPACITY_CHECK = (
    "classroom_type::text = ANY (ARRAY['classroom'::character varying, "
    "'laboratory'::character varying]::text[])) AND capacity IS NOT NULL AND capacity > 0 OR "
    "(classroom_type::text = ANY (ARRAY['virtual'::character varying, "
    "'other'::character varying]::text[])) AND (capacity IS NULL OR capacity > 0"
)


def _schema() -> tuple[sa.MetaData, sa.Table]:
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    table = sa.Table(
        TABLE,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("preview_digest", sa.String(64), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("pre_state_digest", sa.String(64), nullable=False),
        sa.Column("applied_state_digest", sa.String(64), nullable=False),
        sa.Column("academic_period", sa.String(30), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey(users.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("policy", sa.String(80), nullable=False),
        sa.Column("source_hashes", sa.JSON(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_historical_schedule_import_key"),
        sa.UniqueConstraint("preview_digest", name="uq_historical_schedule_import_digest"),
        sa.CheckConstraint(
            "policy = 'historical_availability_not_recorded'",
            name="ck_historical_schedule_import_policy",
        ),
    )
    sa.Index("ix_historical_schedule_imports_idempotency_key", table.c.idempotency_key)
    sa.Index("ix_historical_schedule_imports_academic_period", table.c.academic_period)
    return metadata, table


def _validation_helper():
    path = Path(__file__).with_name("b0d2e4f6c804_add_academic_schedule_publications.py")
    spec = importlib.util.spec_from_file_location("historical_import_schema_validation", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError("Schema validation helpers are unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _academic_catalog_helper():
    path = Path(__file__).with_name("e7a9c1d3f501_add_academic_management_catalogs.py")
    spec = importlib.util.spec_from_file_location("historical_import_academic_catalog_schema", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError("Academic catalog schema helpers are unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _classroom_schema(*, target: bool, dialect_name: str | None = None) -> sa.Table:
    _metadata, tables = _academic_catalog_helper()._schema()
    table = tables[CLASSROOMS]
    if dialect_name == "sqlite":
        table.c.active.server_default = sa.DefaultClause(sa.text("1"))
    if not target:
        return table
    table.c.capacity.nullable = True
    for constraint in list(table.constraints):
        if constraint.name == "ck_classroom_capacity_positive":
            table.constraints.remove(constraint)
    table.append_constraint(sa.CheckConstraint(
        POSTGRES_REFLECTED_CAPACITY_CHECK if dialect_name == "postgresql" else CAPACITY_CHECK,
        name="ck_classroom_capacity_by_type",
    ))
    return table


def _validate_receipt(inspector: sa.Inspector, table: sa.Table) -> list[str]:
    return _validation_helper()._validate_table(inspector, table)


def _validate_classroom(inspector: sa.Inspector, table: sa.Table) -> list[str]:
    return _validation_helper()._validate_table(inspector, table)


def _classroom_state(inspector: sa.Inspector) -> str:
    dialect_name = inspector.bind.dialect.name
    legacy_errors = _validate_classroom(
        inspector, _classroom_schema(target=False, dialect_name=dialect_name)
    )
    if not legacy_errors:
        return "legacy"
    target_errors = _validate_classroom(
        inspector, _classroom_schema(target=True, dialect_name=dialect_name)
    )
    if not target_errors:
        return "target"
    raise RuntimeError(
        "Incompatible pre-existing classrooms table: "
        + "; ".join(sorted(set(legacy_errors + target_errors)))
    )


def _upgrade_classroom_capacity(bind: sa.Connection) -> None:
    recreate = "always" if bind.dialect.name == "sqlite" else "auto"
    with op.batch_alter_table(CLASSROOMS, recreate=recreate) as batch:
        batch.drop_constraint("ck_classroom_capacity_positive", type_="check")
        batch.alter_column("capacity", existing_type=sa.Integer(), nullable=True)
        batch.create_check_constraint("ck_classroom_capacity_by_type", CAPACITY_CHECK)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _metadata, receipt = _schema()

    # Adoption is validated completely before any schema mutation.
    receipt_exists = inspector.has_table(TABLE)
    if receipt_exists:
        errors = _validate_receipt(inspector, receipt)
        if errors:
            raise RuntimeError(
                "Incompatible pre-existing historical_schedule_imports table: "
                + "; ".join(errors)
            )

    classroom_state = _classroom_state(inspector)
    if classroom_state == "legacy":
        _upgrade_classroom_capacity(bind)
    classroom_errors = _validate_classroom(
        sa.inspect(bind), _classroom_schema(target=True, dialect_name=bind.dialect.name)
    )
    if classroom_errors:
        raise RuntimeError(
            "Classroom capacity schema validation failed: " + "; ".join(classroom_errors)
        )

    if not receipt_exists:
        receipt.create(bind)

    errors = _validate_receipt(sa.inspect(bind), receipt)
    if errors:
        raise RuntimeError("Historical import receipt schema validation failed: " + "; ".join(errors))


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; historical import receipts are audit evidence."
    )
