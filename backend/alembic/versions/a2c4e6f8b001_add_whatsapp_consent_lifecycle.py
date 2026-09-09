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
        elif (
            not isinstance(existing["type"], type(column_type))
            or existing["nullable"] is not True
            or getattr(existing["type"], "length", None) != getattr(column_type, "length", None)
        ):
            raise RuntimeError(
                f"Incompatible pre-existing whatsapp_preferences.{name} column"
            )

    preference_checks = {
        check["name"] for check in inspector.get_check_constraints("whatsapp_preferences")
    }
    if "ck_whatsapp_preference_revision_nonnegative" not in preference_checks:
        with op.batch_alter_table("whatsapp_preferences") as batch:
            batch.create_check_constraint(
                "ck_whatsapp_preference_revision_nonnegative", "consent_revision >= 0"
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


def _validate_existing_history(inspector) -> None:
    expected = {
        "id": ("INTEGER", False), "teacher_ci": ("VARCHAR", False, 20),
        "revision": ("INTEGER", False), "event_type": ("VARCHAR", False, 24),
        "phone_e164": ("VARCHAR", False, 16), "is_verified": ("BOOLEAN", False),
        "consent_evidence": ("TEXT", True), "consent_source": ("VARCHAR", True, 32),
        "consented_at": ("DATETIME", True), "opt_out_evidence": ("TEXT", True),
        "opted_out_at": ("DATETIME", True), "actor_user_id": ("INTEGER", True),
        "created_at": ("DATETIME", False),
    }
    actual = {
        column["name"]: (column["type"].__class__.__name__.upper(), bool(column["nullable"]), getattr(column["type"], "length", None))
        for column in inspector.get_columns("whatsapp_consent_revisions")
    }
    normalized = {name: values[:2] if len(values) == 2 else values for name, values in actual.items()}
    if normalized != expected:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions columns")
    if tuple(inspector.get_pk_constraint("whatsapp_consent_revisions").get("constrained_columns") or ()) != ("id",):
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions primary key")
    if {tuple(item.get("column_names") or ()) for item in inspector.get_unique_constraints("whatsapp_consent_revisions")} != {("teacher_ci", "revision")}:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions unique constraint")
    if {item["name"] for item in inspector.get_check_constraints("whatsapp_consent_revisions")} != {"ck_whatsapp_consent_revision_positive"}:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions check constraint")
    if {(item["name"], tuple(item.get("column_names") or ())) for item in inspector.get_indexes("whatsapp_consent_revisions")} != {("ix_whatsapp_consent_revisions_teacher_ci", ("teacher_ci",))}:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions index")
    foreign_keys = {(tuple(item.get("constrained_columns") or ()), item.get("referred_table"), tuple(item.get("referred_columns") or ()), (item.get("options") or {}).get("ondelete")) for item in inspector.get_foreign_keys("whatsapp_consent_revisions")}
    if foreign_keys != {(("teacher_ci",), "teachers", ("ci",), "CASCADE"), (("actor_user_id",), "users", ("id",), "RESTRICT")}:
        raise RuntimeError("Incompatible pre-existing whatsapp_consent_revisions foreign keys")


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
