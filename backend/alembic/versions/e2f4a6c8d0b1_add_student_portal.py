"""add student portal

Revision ID: e2f4a6c8d0b1
Revises: d1e3f5a7b9c2

Student portal accounts (temporary password from registration staff, changed on
first login), re-enrollment windows per target term, and the students'
re-enrollment requests with the groups they chose.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e2f4a6c8d0b1"
down_revision: Union[str, None] = "d1e3f5a7b9c2"
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
    for name in ("students", "users", "academic_groups"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer(), primary_key=True))
    accounts = sa.Table(
        "student_accounts", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        _fk("student_id", "students.id", "RESTRICT"),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("temporary_issued_at", sa.DateTime(), nullable=True),
        _fk("temporary_issued_by", "users.id", "SET NULL", nullable=True, index=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("student_id", name="uq_student_account_student"),
    )
    windows = sa.Table(
        "reenrollment_windows", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("term_code", sa.String(30), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        _fk("created_by", "users.id", "SET NULL", nullable=True, index=False),
        *_timestamps(),
        sa.UniqueConstraint("term_code", name="uq_reenrollment_window_term"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_reenrollment_window_dates"),
    )
    requests = sa.Table(
        "reenrollment_requests", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        _fk("student_id", "students.id", "RESTRICT"),
        _fk("window_id", "reenrollment_windows.id", "RESTRICT"),
        sa.Column("target_semester", sa.Integer(), nullable=False),
        _fk("main_group_id", "academic_groups.id", "RESTRICT"),
        sa.Column("status", sa.String(12), nullable=False, index=True),
        sa.Column("observation_reason", sa.String(30), nullable=True),
        sa.Column("observation_message", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        _fk("handled_by", "users.id", "SET NULL", nullable=True, index=False),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "window_id", name="uq_reenrollment_request_student_window"),
        sa.CheckConstraint("status IN ('pendiente', 'realizada', 'observada')", name="ck_reenrollment_request_status"),
        sa.CheckConstraint(
            "observation_reason IS NULL OR observation_reason IN ('documentos_migracion', 'pago_pendiente', 'otro')",
            name="ck_reenrollment_request_reason",
        ),
    )
    items = sa.Table(
        "reenrollment_request_items", metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        _fk("request_id", "reenrollment_requests.id", "CASCADE"),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("subject_code", sa.String(30), nullable=False),
        sa.Column("subject_name", sa.String(200), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        _fk("group_id", "academic_groups.id", "RESTRICT"),
        sa.UniqueConstraint("request_id", "subject_code", name="uq_reenrollment_item_subject"),
        sa.CheckConstraint("kind IN ('recursado', 'pendiente')", name="ck_reenrollment_item_kind"),
    )
    # Creation order respects foreign keys.
    return [accounts, windows, requests, items]


def upgrade() -> None:
    bind = op.get_bind()
    for table in _tables(sa.MetaData()):
        table.create(bind)


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
