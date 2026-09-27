from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String,
    UniqueConstraint, event, func,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base


class DesignationBootstrapReceipt(Base):
    """Append-only evidence for one digest-bound designation bootstrap draft."""

    __tablename__ = "designation_bootstrap_receipts"
    __table_args__ = (
        UniqueConstraint("operation_key", name="uq_designation_bootstrap_receipt_operation"),
        UniqueConstraint("preview_digest", name="uq_designation_bootstrap_receipt_digest"),
        UniqueConstraint("draft_id", name="uq_designation_bootstrap_receipt_draft"),
        CheckConstraint(
            "theory_block_count >= 0 AND practice_block_count >= 0 "
            "AND theory_assignment_count >= 0 AND practice_assignment_count >= 0",
            name="ck_designation_bootstrap_receipt_counts_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    preview_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    official_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    salary_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    alias_sha256: Mapped[str | None] = mapped_column(String(64))
    database_state_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=False,
    )
    academic_period: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("academic_schedule_drafts.id", ondelete="RESTRICT"), nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
    )
    theory_block_count: Mapped[int] = mapped_column(Integer, nullable=False)
    practice_block_count: Mapped[int] = mapped_column(Integer, nullable=False)
    theory_assignment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    practice_assignment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )

    draft: Mapped[Any] = relationship("AcademicScheduleDraft")
    actor: Mapped[Any] = relationship("User")


@event.listens_for(DesignationBootstrapReceipt, "before_update")
@event.listens_for(DesignationBootstrapReceipt, "before_delete")
def _prevent_designation_bootstrap_receipt_mutation(mapper, connection, target):
    raise TypeError("Designation bootstrap receipts are append-only")


@event.listens_for(Session, "do_orm_execute")
def _prevent_bulk_designation_bootstrap_receipt_mutation(execute_state):
    if (
        (execute_state.is_update or execute_state.is_delete)
        and execute_state.bind_mapper is DesignationBootstrapReceipt.__mapper__
    ):
        raise TypeError("Designation bootstrap receipts are append-only")
