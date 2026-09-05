"""bind billing media tokens to their notification job

Revision ID: dd4e5f6a7b8c
Revises: cc3d4e5f6a7b
"""
from alembic import op
import sqlalchemy as sa

revision = "dd4e5f6a7b8c"
down_revision = "cc3d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "job_id" in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("billing_media_tokens")}:
        return
    with op.batch_alter_table("billing_media_tokens") as batch:
        batch.add_column(sa.Column("job_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_billing_media_tokens_job_id", "billing_notification_jobs", ["job_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_billing_media_tokens_job_id", ["job_id"])


def downgrade() -> None:
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("billing_media_tokens")
    if not any(key.get("name") == "fk_billing_media_tokens_job_id" for key in foreign_keys):
        raise RuntimeError("Restore an explicitly approved backup instead.")
    with op.batch_alter_table("billing_media_tokens") as batch:
        batch.drop_index("ix_billing_media_tokens_job_id")
        batch.drop_constraint("fk_billing_media_tokens_job_id", type_="foreignkey")
        batch.drop_column("job_id")
