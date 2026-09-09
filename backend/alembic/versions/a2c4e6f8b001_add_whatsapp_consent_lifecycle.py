"""add WhatsApp consent lifecycle persistence

Revision ID: a2c4e6f8b001
Revises: f1a2b3c4d5e6
"""

from alembic import op
import sqlalchemy as sa


revision = "a2c4e6f8b001"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("whatsapp_preferences")
    }
    additions = {
        "consent_source": sa.String(32),
        "consented_at": sa.DateTime(),
    }
    for name, column_type in additions.items():
        existing = columns.get(name)
        if existing is None:
            op.add_column(
                "whatsapp_preferences",
                sa.Column(name, column_type, nullable=True),
            )
        elif not _column_matches(
            existing,
            nullable=True,
            type_family="string" if isinstance(column_type, sa.String) else "datetime",
            length=getattr(column_type, "length", None),
        ):
            raise RuntimeError(
                f"Incompatible pre-existing whatsapp_preferences.{name} column"
            )

    expected_preference_check = "consent_revision >= 0"
    existing_preference_check = next((check.get("sqltext") for check in inspector.get_check_constraints("whatsapp_preferences") if check["name"] == "ck_whatsapp_preference_revision_nonnegative"), None)
    if existing_preference_check is None:
        with op.batch_alter_table("whatsapp_preferences") as batch:
            batch.create_check_constraint(
                "ck_whatsapp_preference_revision_nonnegative", expected_preference_check
            )
    elif _normalize_check_expression(existing_preference_check) != _normalize_check_expression(
        expected_preference_check
    ):
        raise RuntimeError(
            "Incompatible pre-existing whatsapp_preferences check constraint expression"
        )

    if "whatsapp_consent_revisions" not in inspector.get_table_names():
        op.create_table(
            "whatsapp_consent_revisions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "teacher_ci",
                sa.String(20),
                sa.ForeignKey("teachers.ci", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(24), nullable=False),
            sa.Column("phone_e164", sa.String(16), nullable=False),
            sa.Column("is_verified", sa.Boolean(), nullable=False),
            sa.Column("consent_evidence", sa.Text(), nullable=True),
            sa.Column("consent_source", sa.String(32), nullable=True),
            sa.Column("consented_at", sa.DateTime(), nullable=True),
            sa.Column("opt_out_evidence", sa.Text(), nullable=True),
            sa.Column("opted_out_at", sa.DateTime(), nullable=True),
            sa.Column(
                "actor_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint("revision > 0", name="ck_whatsapp_consent_revision_positive"),
            sa.UniqueConstraint(
                "teacher_ci",
                "revision",
                name="uq_whatsapp_consent_teacher_revision",
            ),
        )
        op.create_index(
            "ix_whatsapp_consent_revisions_teacher_ci",
            "whatsapp_consent_revisions",
            ["teacher_ci"],
        )
    else:
        _validate_existing_history(inspector)


def _normalize_check_expression(expression: str) -> str:
    normalized = "".join(expression.split()).casefold()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1]
    return normalized


def _column_matches(column, *, nullable: bool, type_family: str, length=None) -> bool:
    column_type = column["type"]
    matches_type = {
        "integer": isinstance(column_type, sa.Integer),
        "string": isinstance(column_type, sa.String) and not isinstance(column_type, sa.Text),
        "text": isinstance(column_type, sa.Text),
        "boolean": isinstance(column_type, sa.Boolean),
        # PostgreSQL reflects this as TIMESTAMP while SQLite uses DATETIME.
        "datetime": isinstance(column_type, sa.DateTime),
    }[type_family]
    return (
        matches_type
        and bool(column["nullable"]) is nullable
        and getattr(column_type, "length", None) == length
    )


def _validate_existing_history(inspector) -> None:
    expected = {
        # SQLite reports INTEGER PRIMARY KEY as nullable; PostgreSQL truthfully
        # reflects the migration-created primary key as non-null.
        "id": (inspector.bind.dialect.name == "sqlite", "integer", None),
        "teacher_ci": (False, "string", 20),
        "revision": (False, "integer", None),
        "event_type": (False, "string", 24),
        "phone_e164": (False, "string", 16),
        "is_verified": (False, "boolean", None),
        "consent_evidence": (True, "text", None),
        "consent_source": (True, "string", 32),
        "consented_at": (True, "datetime", None),
        "opt_out_evidence": (True, "text", None),
        "opted_out_at": (True, "datetime", None),
        "actor_user_id": (True, "integer", None),
        "created_at": (False, "datetime", None),
    }
    columns = {
        column["name"]: column
        for column in inspector.get_columns("whatsapp_consent_revisions")
    }
    if set(columns) != set(expected) or any(
        not _column_matches(
            columns[name], nullable=nullable, type_family=type_family, length=length
        )
        for name, (nullable, type_family, length) in expected.items()
    ):
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions columns")
    if tuple(inspector.get_pk_constraint("whatsapp_consent_revisions").get("constrained_columns") or ()) != ("id",):
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions primary key")
    if {tuple(item.get("column_names") or ()) for item in inspector.get_unique_constraints("whatsapp_consent_revisions")} != {("teacher_ci", "revision")}:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions unique constraint")
    checks = {
        item["name"]: _normalize_check_expression(item.get("sqltext") or "")
        for item in inspector.get_check_constraints("whatsapp_consent_revisions")
    }
    if checks != {
        "ck_whatsapp_consent_revision_positive": _normalize_check_expression("revision > 0")
    }:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions check constraint")
    if {(item["name"], tuple(item.get("column_names") or ())) for item in inspector.get_indexes("whatsapp_consent_revisions")} != {("ix_whatsapp_consent_revisions_teacher_ci", ("teacher_ci",))}:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions index")
    if inspector.bind.dialect.name == "sqlite":
        raise RuntimeError(
            "Cannot prove pre-existing whatsapp_consent_revisions foreign-key actions on SQLite"
        )
    foreign_keys = {(tuple(item.get("constrained_columns") or ()), item.get("referred_table"), tuple(item.get("referred_columns") or ()), (item.get("options") or {}).get("ondelete")) for item in inspector.get_foreign_keys("whatsapp_consent_revisions")}
    expected_foreign_keys = {(("teacher_ci",), "teachers", ("ci",), "CASCADE"), (("actor_user_id",), "users", ("id",), "RESTRICT")}
    if foreign_keys != expected_foreign_keys:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions foreign keys")


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
