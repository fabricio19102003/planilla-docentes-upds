"""add chat

Revision ID: c5e7a9b1d3f4
Revises: c4e6a8b0d2f4

Shared inbox between each docente and Administración: one conversation per
teacher, its messages, and the private attachments stored on disk.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c5e7a9b1d3f4"
down_revision: Union[str, None] = "c4e6a8b0d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONVERSATIONS = "chat_conversations"
MESSAGES = "chat_messages"
ATTACHMENTS = "chat_attachments"


def _tables(metadata: sa.MetaData) -> list[sa.Table]:
    sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    conversations = sa.Table(
        CONVERSATIONS,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "teacher_ci",
            sa.String(20),
            sa.ForeignKey("teachers.ci", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("admin_last_read_message_id", sa.Integer(), nullable=True),
        sa.Column("docente_last_read_message_id", sa.Integer(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    messages = sa.Table(
        MESSAGES,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey(f"{CONVERSATIONS}.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_role", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("sender_role IN ('admin', 'docente')", name="ck_chat_message_sender_role"),
    )
    attachments = sa.Table(
        ATTACHMENTS,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey(f"{MESSAGES}.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("stored_filename", sa.String(100), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    return [conversations, messages, attachments]


def _validate(inspector: sa.Inspector, table: sa.Table) -> None:
    columns = {column["name"]: column for column in inspector.get_columns(table.name)}
    for expected in table.columns:
        column = columns.get(expected.name)
        kind = sa.Integer if isinstance(expected.type, sa.Integer) else (
            sa.DateTime if isinstance(expected.type, sa.DateTime) else sa.String
        )
        if (
            column is None
            or not isinstance(column["type"], kind)
            or column["nullable"] is not expected.nullable
        ):
            raise RuntimeError(f"Incompatible pre-existing {table.name}.{expected.name} column")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for table in _tables(sa.MetaData()):
        if table.name in existing:
            _validate(inspector, table)
        else:
            table.create(bind)


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
