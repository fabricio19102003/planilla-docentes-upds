"""add_teacher_profile_photos

Revision ID: 7d52c8e1a4f3
Revises: 1b96ed18cd96
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7d52c8e1a4f3"
down_revision: Union[str, None] = "1b96ed18cd96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("teachers", sa.Column("photo_filename", sa.String(length=255), nullable=True))
    op.add_column("teachers", sa.Column("photo_content_type", sa.String(length=100), nullable=True))
    op.add_column("teachers", sa.Column("photo_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("teachers", "photo_updated_at")
    op.drop_column("teachers", "photo_content_type")
    op.drop_column("teachers", "photo_filename")
