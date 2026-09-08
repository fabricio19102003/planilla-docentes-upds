"""Add historical resolution snapshots to detail requests.

Revision ID: e1f2a3b4c5d6
Revises: dd4e5f6a7b8c
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "dd4e5f6a7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("detail_requests", sa.Column("resolution_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("detail_requests", "resolution_snapshot")
