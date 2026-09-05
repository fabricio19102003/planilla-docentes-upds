"""add append-only billing publication revisions

Revision ID: f7a1b2c3d4e5
Revises: e5f2a7c9d301
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a1b2c3d4e5"
down_revision = "e5f2a7c9d301"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    # Older development deployments relied on Base.metadata.create_all(), so
    # the parent table may already exist. A genuinely fresh Alembic chain does
    # not create it until the later runtime-schema baseline revision. Defer both
    # tables to that revision instead of failing midway through a fresh upgrade.
    if not inspector.has_table("billing_publications"):
        return
    if inspector.has_table("billing_publication_revisions"):
        return

    op.create_table(
        "billing_publication_revisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("publication_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("calculation_digest", sa.String(length=64), nullable=False),
        sa.Column("billing_digest", sa.String(length=64), nullable=False),
        sa.Column("calculation_snapshot", sa.JSON(), nullable=False),
        sa.Column("billing_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["billing_publications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("publication_id", "version", name="uq_billing_revision_version"),
        sa.UniqueConstraint(
            "publication_id", "calculation_digest",
            name="uq_billing_revision_calculation_digest",
        ),
    )
    op.create_index(
        "ix_billing_publication_revisions_publication_id",
        "billing_publication_revisions", ["publication_id"], unique=False,
    )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("billing_publication_revisions"):
        return
    op.drop_index(
        "ix_billing_publication_revisions_publication_id",
        table_name="billing_publication_revisions",
    )
    op.drop_table("billing_publication_revisions")
