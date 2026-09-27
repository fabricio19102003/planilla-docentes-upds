"""add designation bootstrap receipts

Revision ID: c6e8f0a2b431
Revises: f4b6d8e0a219
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "c6e8f0a2b431"
down_revision = "f4b6d8e0a219"
branch_labels = None
depends_on = None
TABLE = "designation_bootstrap_receipts"


def _schema() -> tuple[sa.MetaData, sa.Table]:
    metadata = sa.MetaData()
    programs = sa.Table("academic_programs", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    drafts = sa.Table("academic_schedule_drafts", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    receipt = sa.Table(
        TABLE,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_key", sa.String(64), nullable=False),
        sa.Column("preview_digest", sa.String(64), nullable=False),
        sa.Column("official_sha256", sa.String(64), nullable=False),
        sa.Column("salary_sha256", sa.String(64), nullable=False),
        sa.Column("alias_sha256", sa.String(64), nullable=True),
        sa.Column("database_state_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "program_id", sa.Integer(), sa.ForeignKey(programs.c.id, ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("academic_period", sa.String(30), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "draft_id", sa.Integer(), sa.ForeignKey(drafts.c.id, ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_id", sa.Integer(), sa.ForeignKey(users.c.id, ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("theory_block_count", sa.Integer(), nullable=False),
        sa.Column("practice_block_count", sa.Integer(), nullable=False),
        sa.Column("theory_assignment_count", sa.Integer(), nullable=False),
        sa.Column("practice_assignment_count", sa.Integer(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("plan_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "operation_key", name="uq_designation_bootstrap_receipt_operation",
        ),
        sa.UniqueConstraint(
            "preview_digest", name="uq_designation_bootstrap_receipt_digest",
        ),
        sa.UniqueConstraint("draft_id", name="uq_designation_bootstrap_receipt_draft"),
        sa.CheckConstraint(
            "theory_block_count >= 0 AND practice_block_count >= 0 "
            "AND theory_assignment_count >= 0 AND practice_assignment_count >= 0",
            name="ck_designation_bootstrap_receipt_counts_nonnegative",
        ),
    )
    sa.Index(
        "ix_designation_bootstrap_receipts_operation_key",
        receipt.c.operation_key,
    )
    sa.Index(
        "ix_designation_bootstrap_receipts_academic_period",
        receipt.c.academic_period,
    )
    return metadata, receipt


def _validation_helper():
    path = Path(__file__).with_name("b0d2e4f6c804_add_academic_schedule_publications.py")
    spec = importlib.util.spec_from_file_location("designation_bootstrap_schema_validation", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError("Schema validation helpers are unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_receipt(inspector: sa.Inspector, receipt: sa.Table) -> list[str]:
    return _validation_helper()._validate_table(inspector, receipt)


def upgrade() -> None:
    bind = op.get_bind()
    _metadata, receipt = _schema()
    inspector = sa.inspect(bind)
    if inspector.has_table(TABLE):
        errors = _validate_receipt(inspector, receipt)
        if errors:
            raise RuntimeError(
                f"Incompatible pre-existing {TABLE} table: " + "; ".join(errors)
            )
    else:
        receipt.create(bind)

    errors = _validate_receipt(sa.inspect(bind), receipt)
    if errors:
        raise RuntimeError(
            "Designation bootstrap receipt schema validation failed: " + "; ".join(errors)
        )


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; designation bootstrap receipts are audit evidence."
    )
