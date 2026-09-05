"""add official WhatsApp billing persistence

Revision ID: bb2c3d4e5f6a
Revises: aa1b2c3d4e5f
"""

from alembic import op
import sqlalchemy as sa

revision = "bb2c3d4e5f6a"
down_revision = "aa1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "billing_notification_batches" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "billing_notification_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("billing_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("publication_version", sa.Integer(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("readiness_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("digest", name="uq_billing_notification_batch_digest"),
    )
    op.create_index("ix_billing_notification_batches_publication_id", "billing_notification_batches", ["publication_id"])
    op.create_table(
        "billing_notification_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("billing_notification_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_ci", sa.String(20), sa.ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("content_sid", sa.String(34)),
        sa.Column("media_snapshot", sa.JSON()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_expires_at", sa.DateTime()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("provider_sid", sa.String(34)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("batch_id", "teacher_ci", "channel", name="uq_billing_notification_job_intent"),
    )
    op.create_index("ix_billing_notification_job_claim", "billing_notification_jobs", ["status", "lease_expires_at"])
    op.create_index("ix_billing_notification_job_provider_sid", "billing_notification_jobs", ["provider_sid"])
    op.create_table(
        "whatsapp_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("billing_notification_jobs.id", ondelete="SET NULL")),
        sa.Column("provider_sid", sa.String(34)),
        sa.Column("dedupe_key", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_whatsapp_event_dedupe_key"),
    )
    op.create_index("ix_whatsapp_event_provider_sid", "whatsapp_events", ["provider_sid"])
    op.create_table(
        "billing_media_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("billing_notification_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_ci", sa.String(20), sa.ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("artifact_size", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_billing_media_token_hash"),
    )
    op.create_index("ix_billing_media_tokens_batch_id", "billing_media_tokens", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_billing_media_tokens_batch_id", table_name="billing_media_tokens")
    op.drop_table("billing_media_tokens")
    op.drop_index("ix_whatsapp_event_provider_sid", table_name="whatsapp_events")
    op.drop_table("whatsapp_events")
    op.drop_index("ix_billing_notification_job_provider_sid", table_name="billing_notification_jobs")
    op.drop_index("ix_billing_notification_job_claim", table_name="billing_notification_jobs")
    op.drop_table("billing_notification_jobs")
    op.drop_index("ix_billing_notification_batches_publication_id", table_name="billing_notification_batches")
    op.drop_table("billing_notification_batches")
