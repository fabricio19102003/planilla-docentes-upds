"""add migration documents

Revision ID: a4b6c8d0e2f5
Revises: f3a5b7c9d1e3

The configurable list of documents foreign students must present (name, whether it
expires) and the documents each foreign student has presented, with the expiry date
when it applies. Both tables start empty: staff define the list.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a4b6c8d0e2f5"
down_revision: Union[str, None] = "f3a5b7c9d1e3"
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
    for name in ("students", "users"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer(), primary_key=True))
    types = sa.Table(
        "migration_document_types", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("requires_expiry", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("name", name="uq_migration_document_type_name"),
        sa.CheckConstraint("length(name) >= 1 AND length(name) <= 120", name="ck_migration_document_type_name"),
        sa.CheckConstraint("position >= 0", name="ck_migration_document_type_position"),
    )
    documents = sa.Table(
        "student_migration_documents", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        _fk("student_id", "students.id", "RESTRICT"),
        _fk("document_type_id", "migration_document_types.id", "RESTRICT"),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _fk("recorded_by", "users.id", "SET NULL", nullable=True, index=False),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "document_type_id", name="uq_student_migration_document"),
    )
    # Creation order respects foreign keys.
    return [types, documents]


def upgrade() -> None:
    bind = op.get_bind()
    for table in _tables(sa.MetaData()):
        table.create(bind)


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
