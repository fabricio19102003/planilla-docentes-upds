"""add outbound notification attempts

Revision ID: a1b2c3d4e5f6
Revises: c9d0e1f2a3b4
"""

import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "outbound_notification_attempts" in inspector.get_table_names():
        _validate_existing_table(inspector)
        return

    op.create_table(
        "outbound_notification_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("publication_id", sa.Integer(), nullable=False),
        sa.Column("publication_version", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider_message_id", sa.String(length=100), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["billing_publications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_outbound_notification_attempt_key"),
    )
    op.create_index(
        op.f("ix_outbound_notification_attempts_publication_id"),
        "outbound_notification_attempts",
        ["publication_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outbound_notification_attempts_user_id"),
        "outbound_notification_attempts",
        ["user_id"],
        unique=False,
    )


def _validate_existing_table(inspector: Inspector) -> None:
    table = "outbound_notification_attempts"
    dialect_name = inspector.bind.dialect.name
    default_schema = inspector.default_schema_name
    id_default = (
        ("postgresql_sequence", default_schema, f"{table}_id_seq")
        if dialect_name == "postgresql"
        else None
    )
    expected_columns = {
        "id": (("integer",), False, id_default),
        "idempotency_key": (("string", 64), False, None),
        "publication_id": (("integer",), False, None),
        "publication_version": (("integer",), False, None),
        "user_id": (("integer",), True, None),
        "channel": (("string", 20), False, None),
        "provider": (("string", 32), False, None),
        "mode": (("string", 20), False, None),
        "status": (("string", 20), False, None),
        "provider_message_id": (("string", 100), True, None),
        "error_code": (("text",), True, None),
        "created_at": (("datetime",), False, None),
        "updated_at": (("datetime",), False, None),
    }
    actual_columns = {
        column["name"]: (
            _type_signature(column["type"]),
            bool(column["nullable"]),
            _default_signature(
                column.get("default"),
                dialect_name=dialect_name,
                column_name=column["name"],
                default_schema=default_schema,
            ),
        )
        for column in inspector.get_columns(table)
    }
    if actual_columns != expected_columns:
        raise RuntimeError("incompatible precreated outbound_notification_attempts columns")

    primary_key = inspector.get_pk_constraint(table)
    if tuple(primary_key.get("constrained_columns") or ()) != ("id",):
        raise RuntimeError("incompatible precreated outbound_notification_attempts primary key")

    unique_constraints = {
        (constraint.get("name"), tuple(constraint.get("column_names") or ()))
        for constraint in inspector.get_unique_constraints(table)
    }
    if unique_constraints != {
        ("uq_outbound_notification_attempt_key", ("idempotency_key",))
    }:
        raise RuntimeError("incompatible precreated outbound_notification_attempts unique constraints")

    foreign_keys = {
        (
            tuple(foreign_key.get("constrained_columns") or ()),
            foreign_key.get("referred_table"),
            tuple(foreign_key.get("referred_columns") or ()),
            (foreign_key.get("options") or {}).get("ondelete"),
        )
        for foreign_key in inspector.get_foreign_keys(table)
    }
    if foreign_keys != {
        (("publication_id",), "billing_publications", ("id",), "CASCADE"),
        (("user_id",), "users", ("id",), "SET NULL"),
    }:
        raise RuntimeError("incompatible precreated outbound_notification_attempts foreign keys")

    indexes = {
        (index.get("name"), tuple(index.get("column_names") or ()), bool(index.get("unique")))
        for index in inspector.get_indexes(table)
        if not index.get("duplicates_constraint")
    }
    if indexes != {
        ("ix_outbound_notification_attempts_publication_id", ("publication_id",), False),
        ("ix_outbound_notification_attempts_user_id", ("user_id",), False),
    }:
        raise RuntimeError("incompatible precreated outbound_notification_attempts indexes")


def _type_signature(column_type: sa.types.TypeEngine) -> tuple[object, ...]:
    if isinstance(column_type, sa.Text):
        return ("text",)
    if isinstance(column_type, sa.String):
        return ("string", column_type.length)
    if isinstance(column_type, sa.Integer):
        return ("integer",)
    if isinstance(column_type, sa.DateTime):
        return ("datetime",)
    return (column_type.__class__.__name__.lower(),)


_POSTGRES_NEXTVAL_RE = re.compile(
    r"^nextval\('(?:(?P<schema>[a-z_][a-z0-9_$]*)\.)?"
    r"(?P<sequence>[a-z_][a-z0-9_$]*)'::regclass\)$"
)


def _default_signature(
    value: object,
    *,
    dialect_name: str,
    column_name: str,
    default_schema: str | None,
) -> object:
    if value is None:
        return None
    normalized = str(value).strip()
    if dialect_name == "postgresql" and column_name == "id":
        match = _POSTGRES_NEXTVAL_RE.fullmatch(normalized)
        if match is not None:
            schema = match.group("schema") or default_schema
            sequence = match.group("sequence")
            if (
                schema == default_schema
                and sequence == "outbound_notification_attempts_id_seq"
            ):
                return ("postgresql_sequence", schema, sequence)
    return normalized


def downgrade() -> None:
    raise RuntimeError(
        "Destructive downgrade is disabled. Restore an explicitly approved backup instead."
    )
