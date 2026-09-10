"""add WhatsApp activation persistence

Revision ID: a2c4e6f8b002
Revises: a2c4e6f8b001
"""

from alembic import op
import sqlalchemy as sa


revision = "a2c4e6f8b002"
down_revision = "a2c4e6f8b001"
branch_labels = None
depends_on = None


_ACTIVATION_STATUS = "status IN ('queued', 'leased', 'sending', 'accepted', 'ambiguous', 'sent', 'delivered', 'read', 'failed', 'undelivered', 'cancelled')"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    job_columns = {column["name"]: column for column in inspector.get_columns("billing_notification_jobs")}
    intent_type = job_columns.get("intent_type")
    if intent_type is None:
        op.add_column(
            "billing_notification_jobs",
            sa.Column("intent_type", sa.String(24), nullable=False, server_default="ordinary"),
        )
    elif not _column_matches(intent_type, nullable=False, type_family="string", length=24):
        raise RuntimeError("Incompatible pre-existing billing_notification_jobs.intent_type column")
    op.execute(sa.text("UPDATE billing_notification_jobs SET intent_type = 'ordinary' WHERE intent_type IS NULL"))
    _adopt_or_create_check(
        inspector,
        "billing_notification_jobs",
        "ck_billing_notification_job_intent_type",
        "intent_type IN ('ordinary', 'activation_test')",
    )
    _replace_legacy_claim_index(inspector)

    if "billing_whatsapp_activation_tests" not in inspector.get_table_names():
        op.create_table(
            "billing_whatsapp_activation_tests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("actor_ci", sa.String(20), nullable=False),
            sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
            sa.Column("request_digest", sa.String(64), nullable=False),
            sa.Column("teacher_ci_at_creation", sa.String(20), nullable=False),
            sa.Column("recipient_hmac", sa.String(64), nullable=False),
            sa.Column("recipient_masked", sa.String(20), nullable=False),
            sa.Column("consent_revision", sa.Integer(), nullable=False),
            sa.Column("publication_id", sa.Integer(), sa.ForeignKey("billing_publications.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("publication_revision_id", sa.Integer(), sa.ForeignKey("billing_publication_revisions.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("publication_version", sa.Integer(), nullable=False),
            sa.Column("billing_digest", sa.String(64), nullable=False),
            sa.Column("content_sid", sa.String(34), nullable=False),
            sa.Column("batch_id", sa.Integer(), sa.ForeignKey("billing_notification_batches.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("billing_notification_jobs.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("media_token_id", sa.Integer(), sa.ForeignKey("billing_media_tokens.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("artifact_hash", sa.String(64), nullable=False),
            sa.Column("artifact_size", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(24), nullable=False),
            sa.Column("terminal_reason", sa.String(64)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("consent_revision > 0", name="ck_whatsapp_activation_consent_revision_positive"),
            sa.CheckConstraint("artifact_size > 0", name="ck_whatsapp_activation_artifact_size_positive"),
            sa.CheckConstraint(_ACTIVATION_STATUS, name="ck_whatsapp_activation_status"),
            sa.UniqueConstraint("actor_user_id", "idempotency_key_hash", name="uq_whatsapp_activation_actor_key"),
            sa.UniqueConstraint("batch_id", name="uq_whatsapp_activation_batch"),
            sa.UniqueConstraint("job_id", name="uq_whatsapp_activation_job"),
            sa.UniqueConstraint("media_token_id", name="uq_whatsapp_activation_media_token"),
        )
        op.create_index(
            "ix_whatsapp_activation_status",
            "billing_whatsapp_activation_tests",
            ["status"],
        )
    else:
        _validate_activation_table(inspector)


def _column_matches(column, *, nullable: bool | None, type_family: str, length=None) -> bool:
    column_type = column["type"]
    matches = {
        "integer": isinstance(column_type, sa.Integer),
        "string": isinstance(column_type, sa.String) and not isinstance(column_type, sa.Text),
        "datetime": isinstance(column_type, sa.DateTime),
    }[type_family]
    return matches and (nullable is None or bool(column["nullable"]) is nullable) and getattr(column_type, "length", None) == length


def _foreign_key_signatures(inspector):
    if inspector.bind.dialect.name == "sqlite":
        statement = "PRAGMA foreign_key_list('billing_whatsapp_activation_tests')"
        if hasattr(inspector.bind, "exec_driver_sql"):
            rows = list(inspector.bind.exec_driver_sql(statement).mappings())
        else:
            with inspector.bind.connect() as connection:
                rows = list(connection.exec_driver_sql(statement).mappings())
        return {
            ((row["from"],), row["table"], (row["to"],), row["on_delete"])
            for row in rows
        }
    return {
        (
            tuple(item.get("constrained_columns") or ()),
            item.get("referred_table"),
            tuple(item.get("referred_columns") or ()),
            (item.get("options") or {}).get("ondelete"),
        )
        for item in inspector.get_foreign_keys("billing_whatsapp_activation_tests")
    }


def _normalize(expression: str) -> str:
    return "".join(expression.split()).casefold().strip("()")


def _adopt_or_create_check(inspector, table: str, name: str, expression: str) -> None:
    existing = next((item.get("sqltext") for item in inspector.get_check_constraints(table) if item.get("name") == name), None)
    if existing is None:
        with op.batch_alter_table(table) as batch:
            batch.create_check_constraint(name, expression)
    elif _normalize(existing) != _normalize(expression):
        raise RuntimeError(f"Incompatible pre-existing {table} check constraint")


def _replace_legacy_claim_index(inspector) -> None:
    expected = ("intent_type", "status", "lease_expires_at")
    existing = next((item for item in inspector.get_indexes("billing_notification_jobs") if item.get("name") == "ix_billing_notification_job_claim"), None)
    if existing is not None and tuple(existing.get("column_names") or ()) not in {expected, ("status", "lease_expires_at")}:
        raise RuntimeError("Incompatible pre-existing billing_notification_jobs claim index")
    if existing is None or tuple(existing.get("column_names") or ()) != expected:
        if existing is not None:
            op.drop_index("ix_billing_notification_job_claim", table_name="billing_notification_jobs")
        op.create_index("ix_billing_notification_job_claim", "billing_notification_jobs", list(expected))


def _validate_activation_table(inspector) -> None:
    expected = {
        "id": (None if inspector.bind.dialect.name == "sqlite" else False, "integer", None),
        "actor_user_id": (False, "integer", None), "actor_ci": (False, "string", 20),
        "idempotency_key_hash": (False, "string", 64), "request_digest": (False, "string", 64),
        "teacher_ci_at_creation": (False, "string", 20), "recipient_hmac": (False, "string", 64),
        "recipient_masked": (False, "string", 20), "consent_revision": (False, "integer", None),
        "publication_id": (False, "integer", None), "publication_revision_id": (False, "integer", None),
        "publication_version": (False, "integer", None), "billing_digest": (False, "string", 64),
        "content_sid": (False, "string", 34), "batch_id": (False, "integer", None),
        "job_id": (False, "integer", None), "media_token_id": (False, "integer", None),
        "artifact_hash": (False, "string", 64), "artifact_size": (False, "integer", None),
        "status": (False, "string", 24), "terminal_reason": (True, "string", 64),
        "created_at": (False, "datetime", None), "updated_at": (False, "datetime", None),
    }
    columns = {column["name"]: column for column in inspector.get_columns("billing_whatsapp_activation_tests")}
    if set(columns) != set(expected) or any(not _column_matches(columns[name], nullable=nullable, type_family=kind, length=length) for name, (nullable, kind, length) in expected.items()):
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_activation_tests columns")
    if tuple(inspector.get_pk_constraint("billing_whatsapp_activation_tests").get("constrained_columns") or ()) != ("id",):
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_activation_tests primary key")
    unique = {(item.get("name"), tuple(item.get("column_names") or ())) for item in inspector.get_unique_constraints("billing_whatsapp_activation_tests")}
    expected_unique = {
        ("uq_whatsapp_activation_actor_key", ("actor_user_id", "idempotency_key_hash")),
        ("uq_whatsapp_activation_batch", ("batch_id",)),
        ("uq_whatsapp_activation_job", ("job_id",)),
        ("uq_whatsapp_activation_media_token", ("media_token_id",)),
    }
    if unique != expected_unique:
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_activation_tests unique constraint")
    checks = {item["name"]: _normalize(item.get("sqltext") or "") for item in inspector.get_check_constraints("billing_whatsapp_activation_tests")}
    expected_checks = {
        "ck_whatsapp_activation_consent_revision_positive": _normalize("consent_revision > 0"),
        "ck_whatsapp_activation_artifact_size_positive": _normalize("artifact_size > 0"),
        "ck_whatsapp_activation_status": _normalize(_ACTIVATION_STATUS),
    }
    if checks != expected_checks:
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_activation_tests check constraint")
    foreign_keys = _foreign_key_signatures(inspector)
    expected_foreign_keys = {
        (("actor_user_id",), "users", ("id",), "RESTRICT"),
        (("publication_id",), "billing_publications", ("id",), "RESTRICT"),
        (("publication_revision_id",), "billing_publication_revisions", ("id",), "RESTRICT"),
        (("batch_id",), "billing_notification_batches", ("id",), "RESTRICT"),
        (("job_id",), "billing_notification_jobs", ("id",), "RESTRICT"),
        (("media_token_id",), "billing_media_tokens", ("id",), "RESTRICT"),
    }
    if foreign_keys != expected_foreign_keys:
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_activation_tests foreign keys")
    indexes = {(item.get("name"), tuple(item.get("column_names") or ()), bool(item.get("unique", False))) for item in inspector.get_indexes("billing_whatsapp_activation_tests") if not (item.get("duplicates_constraint") in {name for name, _columns in expected_unique})}
    if indexes != {("ix_whatsapp_activation_status", ("status",), False)}:
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_activation_tests index")


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
