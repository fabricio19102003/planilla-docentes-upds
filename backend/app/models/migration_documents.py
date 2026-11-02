"""Required migration documents of foreign students and the ones each student has presented."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.academic_management import TimestampedCatalog


class MigrationDocumentType(TimestampedCatalog, Base):
    """A document every foreign student must present; deactivated instead of deleted once recorded."""

    __tablename__ = "migration_document_types"
    __table_args__ = (
        UniqueConstraint("name", name="uq_migration_document_type_name"),
        CheckConstraint("length(name) >= 1 AND length(name) <= 120", name="ck_migration_document_type_name"),
        CheckConstraint("position >= 0", name="ck_migration_document_type_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    requires_expiry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StudentMigrationDocument(TimestampedCatalog, Base):
    __tablename__ = "student_migration_documents"
    __table_args__ = (
        UniqueConstraint("student_id", "document_type_id", name="uq_student_migration_document"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_type_id: Mapped[int] = mapped_column(
        ForeignKey("migration_document_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    expires_on: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    recorded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
