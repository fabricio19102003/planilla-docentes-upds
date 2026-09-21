"""add immutable contract ledger

Revision ID: e3a5c7f9b128
Revises: d2f4a6b8e017
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re

from alembic import op
import sqlalchemy as sa


revision = "e3a5c7f9b128"
down_revision = "d2f4a6b8e017"
branch_labels = None
depends_on = None

DOCUMENTS = "contract_documents"
LINES = "contract_lines"


def _schema() -> tuple[sa.MetaData, tuple[sa.Table, sa.Table]]:
    metadata = sa.MetaData()
    teachers = sa.Table("teachers", metadata, sa.Column("ci", sa.String(20), primary_key=True))
    designations = sa.Table("designations", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    publications = sa.Table(
        "academic_schedule_publications", metadata, sa.Column("id", sa.Integer(), primary_key=True)
    )
    blocks = sa.Table(
        "academic_schedule_published_blocks", metadata, sa.Column("id", sa.Integer(), primary_key=True)
    )
    assignments = sa.Table(
        "academic_schedule_published_assignments", metadata, sa.Column("id", sa.Integer(), primary_key=True)
    )
    documents = sa.Table(
        DOCUMENTS,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(36), nullable=False),
        sa.Column("teacher_ci", sa.String(20), sa.ForeignKey(teachers.c.ci, ondelete="RESTRICT"), nullable=False),
        sa.Column("teacher_name", sa.String(200), nullable=False),
        sa.Column("teacher_snapshot", sa.JSON(), nullable=False),
        sa.Column("academic_period", sa.String(30), nullable=False),
        sa.Column("period_snapshot", sa.JSON(), nullable=False),
        sa.Column("document_kind", sa.String(12), nullable=False),
        sa.Column("root_contract_id", sa.Integer()),
        sa.Column("predecessor_contract_id", sa.Integer()),
        sa.Column("amendment_sequence", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("issued_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("source_digest", sa.String(64), nullable=False),
        sa.Column("template_version", sa.String(30), nullable=False),
        sa.Column("status", sa.String(12), server_default=sa.text("'issued'"), nullable=False),
        sa.Column("department", sa.String(30), nullable=False),
        sa.Column("full_snapshot", sa.JSON(), nullable=False),
        sa.Column("artifact_filename", sa.String(255), nullable=False),
        sa.Column("artifact_media_type", sa.String(100), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("artifact_size", sa.Integer(), nullable=False),
        sa.Column("artifact_content", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("public_id", name="uq_contract_document_public_id"),
        sa.UniqueConstraint(
            "teacher_ci", "academic_period", "amendment_sequence",
            name="uq_contract_document_teacher_period_sequence",
        ),
        sa.UniqueConstraint(
            "teacher_ci", "academic_period", "source_digest",
            name="uq_contract_document_teacher_period_digest",
        ),
        sa.UniqueConstraint(
            "id", "teacher_ci", "academic_period",
            name="uq_contract_document_lineage_identity",
        ),
        sa.ForeignKeyConstraint(
            ["root_contract_id", "teacher_ci", "academic_period"],
            [
                "contract_documents.id",
                "contract_documents.teacher_ci",
                "contract_documents.academic_period",
            ],
            name="fk_contract_document_root_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_contract_id", "teacher_ci", "academic_period"],
            [
                "contract_documents.id",
                "contract_documents.teacher_ci",
                "contract_documents.academic_period",
            ],
            name="fk_contract_document_predecessor_owner",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("document_kind IN ('original', 'amendment')", name="ck_contract_document_kind"),
        sa.CheckConstraint("status = 'issued'", name="ck_contract_document_status"),
        sa.CheckConstraint(
            "(document_kind = 'original' AND amendment_sequence = 0 "
            "AND root_contract_id IS NULL AND predecessor_contract_id IS NULL) OR "
            "(document_kind = 'amendment' AND amendment_sequence > 0 "
            "AND root_contract_id IS NOT NULL AND predecessor_contract_id IS NOT NULL)",
            name="ck_contract_document_lineage_shape",
        ),
        sa.CheckConstraint("artifact_size > 0", name="ck_contract_document_artifact_size"),
    )
    sa.Index(
        "ix_contract_documents_teacher_period_issued",
        documents.c.teacher_ci,
        documents.c.academic_period,
        documents.c.issued_at,
    )
    lines = sa.Table(
        LINES,
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey(documents.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("activity_kind", sa.String(12), nullable=False),
        sa.Column("rate_class", sa.String(12), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("hours", sa.Numeric(12, 2), nullable=False),
        sa.Column("hour_basis", sa.String(12), nullable=False),
        sa.Column("subject_label", sa.String(200), nullable=False),
        sa.Column("group_label", sa.String(50), nullable=False),
        sa.Column("semester_label", sa.String(50), nullable=False),
        sa.Column("schedule_label", sa.String(500), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=False),
        sa.Column("source_kind", sa.String(12), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("designation_id", sa.Integer(), sa.ForeignKey(designations.c.id, ondelete="RESTRICT")),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey(publications.c.id, ondelete="RESTRICT")),
        sa.Column("publication_sequence", sa.Integer()),
        sa.Column("publication_program_id", sa.Integer()),
        sa.Column("authority_effective_from", sa.Date(), nullable=False),
        sa.Column("published_block_id", sa.Integer(), sa.ForeignKey(blocks.c.id, ondelete="RESTRICT")),
        sa.Column("published_assignment_id", sa.Integer(), sa.ForeignKey(assignments.c.id, ondelete="RESTRICT")),
        sa.Column("change_kind", sa.String(12), nullable=False),
        sa.Column("previous_hours", sa.Numeric(12, 2)),
        sa.Column("previous_hourly_rate", sa.Numeric(12, 2)),
        sa.Column("previous_source_key", sa.String(80)),
        sa.UniqueConstraint("contract_id", "line_number", name="uq_contract_line_number"),
        sa.CheckConstraint("activity_kind IN ('theory', 'practice')", name="ck_contract_line_activity_kind"),
        sa.CheckConstraint("rate_class IN ('regular', 'practice')", name="ck_contract_line_rate_class"),
        sa.CheckConstraint("hour_basis IN ('weekly', 'payable')", name="ck_contract_line_hour_basis"),
        sa.CheckConstraint(
            "change_kind IN ('full', 'added', 'removed', 'changed')",
            name="ck_contract_line_change_kind",
        ),
        sa.CheckConstraint("hours >= 0", name="ck_contract_line_hours_nonnegative"),
        sa.CheckConstraint("hourly_rate > 0", name="ck_contract_line_rate_positive"),
        sa.CheckConstraint("effective_to >= effective_from", name="ck_contract_line_date_order"),
        sa.CheckConstraint(
            "(source_kind = 'legacy' AND designation_id IS NOT NULL "
            "AND publication_id IS NULL AND publication_sequence IS NULL AND publication_program_id IS NULL "
            "AND published_block_id IS NULL "
            "AND published_assignment_id IS NULL) OR "
            "(source_kind = 'published' AND designation_id IS NULL "
            "AND publication_id IS NOT NULL AND publication_sequence IS NOT NULL "
            "AND publication_program_id IS NOT NULL AND published_block_id IS NOT NULL "
            "AND published_assignment_id IS NOT NULL)",
            name="ck_contract_line_source_provenance",
        ),
    )
    sa.Index("ix_contract_lines_contract_activity", lines.c.contract_id, lines.c.activity_kind)
    sa.Index("ix_contract_lines_source", lines.c.source_kind, lines.c.source_id)
    return metadata, (documents, lines)


def _validation_helpers():
    path = Path(__file__).with_name("b0d2e4f6c804_add_academic_schedule_publications.py")
    spec = importlib.util.spec_from_file_location("contract_schema_validation", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError("Contract schema validation helpers are unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module._type_signature
    original_check = module._check_signature

    def type_signature(type_):
        if isinstance(type_, sa.LargeBinary):
            return ("binary", type_.length)
        if isinstance(type_, sa.Numeric):
            return ("numeric", type_.precision, type_.scale)
        if isinstance(type_, sa.JSON):
            return ("json",)
        return original(type_)

    module._type_signature = type_signature

    def check_signature(value):
        signature = original_check(value)
        if signature[0] != "expression":
            return signature
        expression = re.sub(r"::numeric", "", str(signature[1]))
        return ("expression", expression.replace("(", "").replace(")", ""))

    module._check_signature = check_signature
    return module


def _validate_table(inspector: sa.Inspector, table: sa.Table, helpers=None) -> list[str]:
    helpers = helpers or _validation_helpers()
    errors = helpers._validate_table(inspector, table)
    if "foreign keys differ" not in errors:
        return errors
    expected = {
        (
            tuple(element.parent.name for element in item.elements),
            tuple(element.column.table.name for element in item.elements),
            tuple(element.column.name for element in item.elements),
            (item.ondelete or "").upper(),
        )
        for item in table.foreign_key_constraints
    }
    actual = set()
    for item in inspector.get_foreign_keys(table.name):
        constrained = tuple(item.get("constrained_columns") or ())
        referred_table = str(item.get("referred_table"))
        actual.add((
            constrained,
            tuple(referred_table for _ in constrained),
            tuple(item.get("referred_columns") or ()),
            str((item.get("options") or {}).get("ondelete") or "").upper(),
        ))
    if actual == expected:
        errors.remove("foreign keys differ")
    return errors


def _install_immutability_guards(bind: sa.Connection) -> None:
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(
            "CREATE OR REPLACE FUNCTION reject_issued_contract_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'issued contracts are immutable'; END; $$"
        ))
        for table in (DOCUMENTS, LINES):
            op.execute(sa.text(
                "DO $$ BEGIN "
                f"IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_{table}_immutable') THEN "
                f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION reject_issued_contract_mutation(); "
                "END IF; END $$"
            ))
    elif bind.dialect.name == "sqlite":
        for table in (DOCUMENTS, LINES):
            for operation in ("UPDATE", "DELETE"):
                op.execute(sa.text(
                    f"CREATE TRIGGER IF NOT EXISTS trg_{table}_{operation.lower()}_immutable "
                    f"BEFORE {operation} ON {table} BEGIN "
                    "SELECT RAISE(ABORT, 'issued contracts are immutable'); END"
                ))


def _install_integrity_guards(bind: sa.Connection) -> None:
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("""
            CREATE OR REPLACE FUNCTION validate_contract_document_lineage() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.document_kind = 'amendment' AND NOT EXISTS (
                    SELECT 1
                    FROM contract_documents root
                    JOIN contract_documents predecessor
                      ON predecessor.id = NEW.predecessor_contract_id
                    WHERE root.id = NEW.root_contract_id
                      AND root.teacher_ci = NEW.teacher_ci
                      AND root.academic_period = NEW.academic_period
                      AND root.document_kind = 'original'
                      AND root.amendment_sequence = 0
                      AND root.root_contract_id IS NULL
                      AND root.predecessor_contract_id IS NULL
                      AND predecessor.teacher_ci = NEW.teacher_ci
                      AND predecessor.academic_period = NEW.academic_period
                      AND predecessor.amendment_sequence = NEW.amendment_sequence - 1
                      AND (
                          (NEW.amendment_sequence = 1 AND predecessor.id = root.id)
                          OR
                          (NEW.amendment_sequence > 1
                           AND predecessor.document_kind = 'amendment'
                           AND predecessor.root_contract_id = root.id)
                      )
                ) THEN
                    RAISE EXCEPTION 'invalid contract amendment lineage';
                END IF;
                RETURN NEW;
            END;
            $$
        """))
        op.execute(sa.text("""
            CREATE OR REPLACE FUNCTION validate_contract_line_provenance() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.source_kind = 'legacy' AND NOT EXISTS (
                    SELECT 1
                    FROM designations designation
                    JOIN contract_documents document ON document.id = NEW.contract_id
                    WHERE designation.id = NEW.designation_id
                      AND NEW.source_id = designation.id
                      AND designation.teacher_ci = document.teacher_ci
                ) THEN
                    RAISE EXCEPTION 'invalid legacy contract-line provenance';
                ELSIF NEW.source_kind = 'published' AND NOT EXISTS (
                    SELECT 1
                    FROM academic_schedule_published_assignments assignment
                    JOIN academic_schedule_published_blocks block
                      ON block.id = assignment.publication_block_id
                    JOIN academic_schedule_publications publication
                      ON publication.id = block.publication_id
                    JOIN contract_documents document ON document.id = NEW.contract_id
                    WHERE assignment.id = NEW.published_assignment_id
                      AND NEW.source_id = assignment.id
                      AND assignment.teacher_ci = document.teacher_ci
                      AND block.id = NEW.published_block_id
                      AND publication.id = NEW.publication_id
                      AND publication.sequence = NEW.publication_sequence
                      AND publication.program_id = NEW.publication_program_id
                      AND publication.effective_from = NEW.authority_effective_from
                      AND publication.academic_period = document.academic_period
                ) THEN
                    RAISE EXCEPTION 'invalid published contract-line provenance';
                END IF;
                RETURN NEW;
            END;
            $$
        """))
        for trigger, table, function in (
            ("trg_contract_documents_lineage_insert", DOCUMENTS, "validate_contract_document_lineage"),
            ("trg_contract_lines_provenance_insert", LINES, "validate_contract_line_provenance"),
        ):
            op.execute(sa.text(
                "DO $$ BEGIN "
                f"IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = '{trigger}') THEN "
                f"CREATE TRIGGER {trigger} BEFORE INSERT ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {function}(); "
                "END IF; END $$"
            ))
    elif bind.dialect.name == "sqlite":
        op.execute(sa.text("""
            CREATE TRIGGER IF NOT EXISTS trg_contract_documents_lineage_insert
            BEFORE INSERT ON contract_documents
            WHEN NEW.document_kind = 'amendment'
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1
                    FROM contract_documents root
                    JOIN contract_documents predecessor
                      ON predecessor.id = NEW.predecessor_contract_id
                    WHERE root.id = NEW.root_contract_id
                      AND root.teacher_ci = NEW.teacher_ci
                      AND root.academic_period = NEW.academic_period
                      AND root.document_kind = 'original'
                      AND root.amendment_sequence = 0
                      AND root.root_contract_id IS NULL
                      AND root.predecessor_contract_id IS NULL
                      AND predecessor.teacher_ci = NEW.teacher_ci
                      AND predecessor.academic_period = NEW.academic_period
                      AND predecessor.amendment_sequence = NEW.amendment_sequence - 1
                      AND (
                          (NEW.amendment_sequence = 1 AND predecessor.id = root.id)
                          OR
                          (NEW.amendment_sequence > 1
                           AND predecessor.document_kind = 'amendment'
                           AND predecessor.root_contract_id = root.id)
                      )
                ) THEN RAISE(ABORT, 'invalid contract amendment lineage') END;
            END
        """))
        op.execute(sa.text("""
            CREATE TRIGGER IF NOT EXISTS trg_contract_lines_provenance_insert
            BEFORE INSERT ON contract_lines
            BEGIN
                SELECT CASE WHEN NEW.source_kind = 'legacy' AND NOT EXISTS (
                    SELECT 1
                    FROM designations designation
                    JOIN contract_documents document ON document.id = NEW.contract_id
                    WHERE designation.id = NEW.designation_id
                      AND NEW.source_id = designation.id
                      AND designation.teacher_ci = document.teacher_ci
                ) THEN RAISE(ABORT, 'invalid legacy contract-line provenance') END;
                SELECT CASE WHEN NEW.source_kind = 'published' AND NOT EXISTS (
                    SELECT 1
                    FROM academic_schedule_published_assignments assignment
                    JOIN academic_schedule_published_blocks block
                      ON block.id = assignment.publication_block_id
                    JOIN academic_schedule_publications publication
                      ON publication.id = block.publication_id
                    JOIN contract_documents document ON document.id = NEW.contract_id
                    WHERE assignment.id = NEW.published_assignment_id
                      AND NEW.source_id = assignment.id
                      AND assignment.teacher_ci = document.teacher_ci
                      AND block.id = NEW.published_block_id
                      AND publication.id = NEW.publication_id
                      AND publication.sequence = NEW.publication_sequence
                      AND publication.program_id = NEW.publication_program_id
                      AND publication.effective_from = NEW.authority_effective_from
                      AND publication.academic_period = document.academic_period
                ) THEN RAISE(ABORT, 'invalid published contract-line provenance') END;
            END
        """))


def upgrade() -> None:
    bind = op.get_bind()
    _metadata, tables = _schema()
    inspector = sa.inspect(bind)
    present = {table.name for table in tables if inspector.has_table(table.name)}
    if present and present != {DOCUMENTS, LINES}:
        raise RuntimeError(
            "Partial contract-ledger adoption detected; restore the database before retrying."
        )
    helpers = _validation_helpers()
    if present:
        errors = [
            f"{table.name}: {error}"
            for table in tables
            for error in _validate_table(inspector, table, helpers)
        ]
        if errors:
            raise RuntimeError("Incompatible pre-existing contract ledger: " + "; ".join(errors))
        _install_immutability_guards(bind)
        _install_integrity_guards(bind)
        return
    for table in tables:
        table.create(bind)
    errors = [
        f"{table.name}: {error}"
        for table in tables
        for error in _validate_table(sa.inspect(bind), table, helpers)
    ]
    if errors:
        raise RuntimeError("Contract ledger validation failed: " + "; ".join(errors))
    _install_immutability_guards(bind)
    _install_integrity_guards(bind)


def downgrade() -> None:
    raise RuntimeError(
        "Restore an explicitly approved backup instead; issued contract documents cannot be destroyed."
    )
