"""normalize teacher specialty to text

Revision ID: b8c4d2e6f901
Revises: f7a1b2c3d4e5
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c4d2e6f901"
down_revision = "f7a1b2c3d4e5"
branch_labels = None
depends_on = None


def _alter_specialty(type_: sa.types.TypeEngine, existing_type: sa.types.TypeEngine) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("teachers") as batch_op:
            batch_op.alter_column(
                "specialty",
                existing_type=existing_type,
                type_=type_,
                existing_nullable=True,
            )
        return
    op.alter_column(
        "teachers",
        "specialty",
        existing_type=existing_type,
        type_=type_,
        existing_nullable=True,
    )


def upgrade() -> None:
    _alter_specialty(sa.Text(), sa.String(length=200))


def downgrade() -> None:
    bind = op.get_bind()
    teachers = sa.table("teachers", sa.column("specialty", sa.Text()))
    length = sa.func.length if bind.dialect.name == "sqlite" else sa.func.char_length
    over_limit = bind.scalar(
        sa.select(sa.func.count()).select_from(teachers).where(length(teachers.c.specialty) > 200)
    )
    if over_limit:
        raise RuntimeError(
            "Cannot downgrade teachers.specialty to VARCHAR(200): values exceed 200 characters"
        )
    _alter_specialty(sa.String(length=200), sa.Text())
