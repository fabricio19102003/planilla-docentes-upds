"""add WhatsApp dispatch authorization persistence

Revision ID: a2c4e6f8b003
Revises: a2c4e6f8b002
"""

from alembic import op
import sqlalchemy as sa


revision = "a2c4e6f8b003"
down_revision = "a2c4e6f8b002"
branch_labels = None
depends_on = None

_TABLE = "billing_whatsapp_dispatch_authorizations"
_CHECKS = (
    ("ck_whatsapp_dispatch_authorization_state", "state IN ('pending', 'authorized', 'consumed', 'cancelled', 'expired', 'revoked')"),
    ("ck_whatsapp_dispatch_authorization_expiry", "expires_at > created_at"),
    ("ck_whatsapp_dispatch_authorization_attestation", "attestation_code IS NULL OR attestation_code = 'dispatch_reviewed_and_authorized_v1'"),
    ("ck_whatsapp_dispatch_authorization_reason", "terminal_reason IS NULL OR terminal_reason IN ('migration_reauthorization_required', 'creator_cancelled', 'authorization_expired', 'pre_provider_rejected', 'provider_outcome_ambiguous')"),
    ("ck_whatsapp_dispatch_authorization_release", "(released_at IS NULL) = (attestation_code IS NULL AND release_actor_user_id IS NULL AND release_key_hash IS NULL AND release_request_digest IS NULL)"),
    ("ck_whatsapp_dispatch_authorization_consumed", "consumed_at IS NULL OR released_at IS NOT NULL"),
    ("ck_whatsapp_dispatch_authorization_cancel", "(cancelled_at IS NULL) = (cancel_key_hash IS NULL AND cancel_request_digest IS NULL)"),
    ("ck_whatsapp_dispatch_authorization_pending_lifecycle", "state != 'pending' OR (released_at IS NULL AND consumed_at IS NULL AND cancelled_at IS NULL AND revoked_at IS NULL)"),
    ("ck_whatsapp_dispatch_authorization_authorized_lifecycle", "state != 'authorized' OR (released_at IS NOT NULL AND consumed_at IS NULL AND cancelled_at IS NULL AND revoked_at IS NULL)"),
    ("ck_whatsapp_dispatch_authorization_consumed_lifecycle", "state != 'consumed' OR (released_at IS NOT NULL AND consumed_at IS NOT NULL AND cancelled_at IS NULL)"),
    ("ck_whatsapp_dispatch_authorization_cancelled_lifecycle", "state != 'cancelled' OR (cancelled_at IS NOT NULL AND revoked_at IS NOT NULL)"),
    ("ck_whatsapp_dispatch_authorization_revoked_lifecycle", "state NOT IN ('expired', 'revoked') OR revoked_at IS NOT NULL"),
)


def _schema_metadata() -> sa.MetaData:
    metadata = sa.MetaData()
    for name in ("users", "billing_notification_jobs", "billing_whatsapp_activation_tests"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
    return metadata


def authorization_table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        _TABLE, metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("activation_id", sa.Integer, sa.ForeignKey("billing_whatsapp_activation_tests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("billing_notification_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("creator_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("attestation_code", sa.String(48)),
        sa.Column("release_actor_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("release_key_hash", sa.String(64)),
        sa.Column("release_request_digest", sa.String(64)),
        sa.Column("released_at", sa.DateTime), sa.Column("consumed_at", sa.DateTime),
        sa.Column("cancel_key_hash", sa.String(64)), sa.Column("cancel_request_digest", sa.String(64)),
        sa.Column("cancelled_at", sa.DateTime), sa.Column("revoked_at", sa.DateTime),
        sa.Column("terminal_reason", sa.String(64)),
        sa.Column("created_at", sa.DateTime, nullable=False), sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("activation_id", name="uq_whatsapp_dispatch_authorization_activation"),
        sa.UniqueConstraint("job_id", name="uq_whatsapp_dispatch_authorization_job"),
        *(sa.CheckConstraint(expression, name=name) for name, expression in _CHECKS),
        sa.Index("ix_whatsapp_dispatch_authorization_claim", "state", "expires_at", "job_id"),
    )


def _normalize(expression: str) -> str:
    return "".join(expression.split()).casefold().strip("()")


def _column_matches(actual, expected) -> bool:
    actual_type, expected_type = actual["type"], expected.type
    return (
        (actual["nullable"] is expected.nullable or (expected.primary_key and actual["nullable"] is True))
        and actual_type._type_affinity is expected_type._type_affinity
        and getattr(actual_type, "length", None) == getattr(expected_type, "length", None)
    )


def _validate_authorization_table(inspector) -> None:
    table = authorization_table(_schema_metadata())
    columns = {item["name"]: item for item in inspector.get_columns(_TABLE)}
    if set(columns) != set(table.c.keys()) or any(not _column_matches(columns[name], column) for name, column in table.c.items()):
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_dispatch_authorizations columns")
    if tuple(inspector.get_pk_constraint(_TABLE).get("constrained_columns") or ()) != ("id",):
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_dispatch_authorizations primary key")
    unique = {(item.get("name"), tuple(item.get("column_names") or ())) for item in inspector.get_unique_constraints(_TABLE)}
    expected_unique = {("uq_whatsapp_dispatch_authorization_activation", ("activation_id",)), ("uq_whatsapp_dispatch_authorization_job", ("job_id",))}
    if unique != expected_unique:
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_dispatch_authorizations unique constraint")
    checks = {item["name"]: _normalize(item.get("sqltext") or "") for item in inspector.get_check_constraints(_TABLE)}
    if checks != {name: _normalize(expression) for name, expression in _CHECKS}:
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_dispatch_authorizations check constraint")
    foreign_keys = {(tuple(item["constrained_columns"]), item["referred_table"], tuple(item["referred_columns"]), (item.get("options") or {}).get("ondelete")) for item in inspector.get_foreign_keys(_TABLE)}
    expected_foreign_keys = {((item.parent.name,), item.column.table.name, (item.column.name,), item.ondelete) for item in table.foreign_keys}
    if foreign_keys != expected_foreign_keys:
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_dispatch_authorizations foreign keys")
    indexes = {(item.get("name"), tuple(item.get("column_names") or ()), bool(item.get("unique", False))) for item in inspector.get_indexes(_TABLE) if not (item.get("duplicates_constraint") in {name for name, _columns in expected_unique})}
    if indexes != {("ix_whatsapp_dispatch_authorization_claim", ("state", "expires_at", "job_id"), False)}:
        raise RuntimeError("Incompatible pre-existing billing_whatsapp_dispatch_authorizations index")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE in inspector.get_table_names():
        _validate_authorization_table(inspector)
    else:
        authorization_table(_schema_metadata()).create(bind)


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead; this authorization history is destructive to remove.")
