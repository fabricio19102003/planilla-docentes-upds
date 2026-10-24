"""allow issued contracts to follow a CI correction

Revision ID: c4e6a8b0d2f4
Revises: b3d5f7a9c1e2

Issued contracts stay immutable, with one narrow exception: an UPDATE that changes only
teacher_ci, covered by a contract_ci_corrections grant for that (old, new) pair created in
the same transaction. DELETE and every other change are still rejected, contract_lines stay
fully immutable, and correction records themselves cannot be edited or deleted.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4e6a8b0d2f4"
down_revision: Union[str, None] = "b3d5f7a9c1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "contract_ci_corrections"
SQLITE_TRIGGER = "trg_contract_documents_update_immutable"


def _create_table(bind) -> None:
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        TABLE,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("old_ci", sa.String(20), nullable=False, index=True),
        sa.Column("new_ci", sa.String(20), nullable=False, index=True),
        sa.Column("contract_count", sa.Integer(), nullable=False),
        sa.Column("corrected_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("corrected_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("txid", sa.BigInteger(), nullable=True),
    ).create(bind)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns(TABLE)}
        missing = {"old_ci", "new_ci", "contract_count", "corrected_by", "corrected_at", "txid"} - columns
        if missing:
            raise RuntimeError(f"Incompatible pre-existing {TABLE} table: missing {sorted(missing)}")
    else:
        _create_table(bind)

    if bind.dialect.name == "postgresql":
        # JSON columns are compared as text: jsonb equality would accept rewritten snapshots.
        op.execute(sa.text("""
            CREATE OR REPLACE FUNCTION reject_issued_contract_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'contract_documents' THEN
                    IF NEW.teacher_ci IS DISTINCT FROM OLD.teacher_ci
                       AND (to_jsonb(NEW) - 'teacher_ci' - 'teacher_snapshot' - 'period_snapshot' - 'full_snapshot')
                           = (to_jsonb(OLD) - 'teacher_ci' - 'teacher_snapshot' - 'period_snapshot' - 'full_snapshot')
                       AND NEW.teacher_snapshot::text IS NOT DISTINCT FROM OLD.teacher_snapshot::text
                       AND NEW.period_snapshot::text IS NOT DISTINCT FROM OLD.period_snapshot::text
                       AND NEW.full_snapshot::text IS NOT DISTINCT FROM OLD.full_snapshot::text
                       AND EXISTS (
                           SELECT 1 FROM contract_ci_corrections grant_row
                           WHERE grant_row.old_ci = OLD.teacher_ci
                             AND grant_row.new_ci = NEW.teacher_ci
                             AND grant_row.txid = txid_current()
                       )
                    THEN
                        RETURN NEW;
                    END IF;
                END IF;
                RAISE EXCEPTION 'issued contracts are immutable';
            END;
            $$
        """))
        op.execute(sa.text(
            "CREATE OR REPLACE FUNCTION reject_contract_ci_correction_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'contract CI corrections are immutable'; END; $$"
        ))
        op.execute(sa.text(
            "DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_{TABLE}_immutable') THEN "
            f"CREATE TRIGGER trg_{TABLE}_immutable BEFORE UPDATE OR DELETE ON {TABLE} "
            "FOR EACH ROW EXECUTE FUNCTION reject_contract_ci_correction_mutation(); "
            "END IF; END $$"
        ))
    elif bind.dialect.name == "sqlite":
        others = [
            column["name"]
            for column in sa.inspect(bind).get_columns("contract_documents")
            if column["name"] != "teacher_ci"
        ]
        unchanged = " AND ".join(f"NEW.{name} IS OLD.{name}" for name in others)
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {SQLITE_TRIGGER}"))
        op.execute(sa.text(
            f"CREATE TRIGGER {SQLITE_TRIGGER} BEFORE UPDATE ON contract_documents "
            "WHEN NOT (NEW.teacher_ci IS NOT OLD.teacher_ci "
            f"AND {unchanged} "
            f"AND EXISTS (SELECT 1 FROM {TABLE} grant_row "
            "WHERE grant_row.old_ci = OLD.teacher_ci AND grant_row.new_ci = NEW.teacher_ci)) "
            "BEGIN SELECT RAISE(ABORT, 'issued contracts are immutable'); END"
        ))
        for operation in ("UPDATE", "DELETE"):
            op.execute(sa.text(
                f"CREATE TRIGGER IF NOT EXISTS trg_{TABLE}_{operation.lower()}_immutable "
                f"BEFORE {operation} ON {TABLE} BEGIN "
                "SELECT RAISE(ABORT, 'contract CI corrections are immutable'); END"
            ))


def downgrade() -> None:
    raise RuntimeError("Restore an explicitly approved backup instead.")
