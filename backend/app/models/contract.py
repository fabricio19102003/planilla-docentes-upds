from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ContractDocument(Base):
    """An issued, immutable teacher contract or amendment."""

    __tablename__ = "contract_documents"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_contract_document_public_id"),
        UniqueConstraint(
            "teacher_ci", "academic_period", "amendment_sequence",
            name="uq_contract_document_teacher_period_sequence",
        ),
        UniqueConstraint(
            "teacher_ci", "academic_period", "source_digest",
            name="uq_contract_document_teacher_period_digest",
        ),
        UniqueConstraint(
            "id", "teacher_ci", "academic_period",
            name="uq_contract_document_lineage_identity",
        ),
        ForeignKeyConstraint(
            ["root_contract_id", "teacher_ci", "academic_period"],
            [
                "contract_documents.id",
                "contract_documents.teacher_ci",
                "contract_documents.academic_period",
            ],
            name="fk_contract_document_root_owner",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["predecessor_contract_id", "teacher_ci", "academic_period"],
            [
                "contract_documents.id",
                "contract_documents.teacher_ci",
                "contract_documents.academic_period",
            ],
            name="fk_contract_document_predecessor_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "document_kind IN ('original', 'amendment')",
            name="ck_contract_document_kind",
        ),
        CheckConstraint("status = 'issued'", name="ck_contract_document_status"),
        CheckConstraint(
            "(document_kind = 'original' AND amendment_sequence = 0 "
            "AND root_contract_id IS NULL AND predecessor_contract_id IS NULL) OR "
            "(document_kind = 'amendment' AND amendment_sequence > 0 "
            "AND root_contract_id IS NOT NULL AND predecessor_contract_id IS NOT NULL)",
            name="ck_contract_document_lineage_shape",
        ),
        CheckConstraint("artifact_size > 0", name="ck_contract_document_artifact_size"),
        Index(
            "ix_contract_documents_teacher_period_issued",
            "teacher_ci", "academic_period", "issued_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="RESTRICT"), nullable=False
    )
    teacher_name: Mapped[str] = mapped_column(String(200), nullable=False)
    teacher_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    academic_period: Mapped[str] = mapped_column(String(30), nullable=False)
    period_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    document_kind: Mapped[str] = mapped_column(String(12), nullable=False)
    root_contract_id: Mapped[Optional[int]] = mapped_column(Integer)
    predecessor_contract_id: Mapped[Optional[int]] = mapped_column(Integer)
    amendment_sequence: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(12), default="issued", server_default=text("'issued'"), nullable=False
    )
    department: Mapped[str] = mapped_column(String(30), nullable=False)
    full_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    artifact_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_size: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    lines: Mapped[list["ContractLine"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="ContractLine.line_number",
    )


class ContractLine(Base):
    """Immutable legal workload evidence attached to one issued document."""

    __tablename__ = "contract_lines"
    __table_args__ = (
        UniqueConstraint("contract_id", "line_number", name="uq_contract_line_number"),
        CheckConstraint(
            "activity_kind IN ('theory', 'practice')",
            name="ck_contract_line_activity_kind",
        ),
        CheckConstraint(
            "rate_class IN ('regular', 'practice')",
            name="ck_contract_line_rate_class",
        ),
        CheckConstraint(
            "hour_basis IN ('weekly', 'payable')",
            name="ck_contract_line_hour_basis",
        ),
        CheckConstraint(
            "change_kind IN ('full', 'added', 'removed', 'changed')",
            name="ck_contract_line_change_kind",
        ),
        CheckConstraint("hours >= 0", name="ck_contract_line_hours_nonnegative"),
        CheckConstraint("hourly_rate > 0", name="ck_contract_line_rate_positive"),
        CheckConstraint(
            "effective_to >= effective_from",
            name="ck_contract_line_date_order",
        ),
        CheckConstraint(
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
        Index("ix_contract_lines_contract_activity", "contract_id", "activity_kind"),
        Index("ix_contract_lines_source", "source_kind", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contract_documents.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_kind: Mapped[str] = mapped_column(String(12), nullable=False)
    rate_class: Mapped[str] = mapped_column(String(12), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hour_basis: Mapped[str] = mapped_column(String(12), nullable=False)
    subject_label: Mapped[str] = mapped_column(String(200), nullable=False)
    group_label: Mapped[str] = mapped_column(String(50), nullable=False)
    semester_label: Mapped[str] = mapped_column(String(50), nullable=False)
    schedule_label: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(12), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    designation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("designations.id", ondelete="RESTRICT")
    )
    publication_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_schedule_publications.id", ondelete="RESTRICT")
    )
    publication_sequence: Mapped[Optional[int]] = mapped_column(Integer)
    publication_program_id: Mapped[Optional[int]] = mapped_column(Integer)
    authority_effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    published_block_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_schedule_published_blocks.id", ondelete="RESTRICT")
    )
    published_assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_schedule_published_assignments.id", ondelete="RESTRICT")
    )
    change_kind: Mapped[str] = mapped_column(String(12), nullable=False)
    previous_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    previous_hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    previous_source_key: Mapped[Optional[str]] = mapped_column(String(80))

    contract: Mapped[ContractDocument] = relationship(back_populates="lines")
