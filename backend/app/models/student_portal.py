"""Student portal accounts, separate from staff users so student and staff sessions never mix."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.academic_management import AcademicGroup, TimestampedCatalog
from app.models.academic_records import Student


class StudentAccount(TimestampedCatalog, Base):
    __tablename__ = "student_accounts"
    __table_args__ = (UniqueConstraint("student_id", name="uq_student_account_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Part of every student token: issuing a new temporary password bumps it and ends open sessions.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    temporary_issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    temporary_issued_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)

    student: Mapped[Student] = relationship()


REQUEST_STATUSES = ("pendiente", "realizada", "observada")
OBSERVATION_REASONS = ("documentos_migracion", "pago_pendiente", "otro")
ITEM_KINDS = ("recursado", "pendiente")


class ReenrollmentWindow(TimestampedCatalog, Base):
    """Dates during which students can request re-enrollment for one target term."""

    __tablename__ = "reenrollment_windows"
    __table_args__ = (
        UniqueConstraint("term_code", name="uq_reenrollment_window_term"),
        CheckConstraint("ends_on >= starts_on", name="ck_reenrollment_window_dates"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term_code: Mapped[str] = mapped_column(String(30), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class ReenrollmentRequest(TimestampedCatalog, Base):
    __tablename__ = "reenrollment_requests"
    __table_args__ = (
        UniqueConstraint("student_id", "window_id", name="uq_reenrollment_request_student_window"),
        CheckConstraint("status IN ('pendiente', 'realizada', 'observada')", name="ck_reenrollment_request_status"),
        CheckConstraint(
            "observation_reason IS NULL OR observation_reason IN ('documentos_migracion', 'pago_pendiente', 'otro')",
            name="ck_reenrollment_request_reason",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    window_id: Mapped[int] = mapped_column(
        ForeignKey("reenrollment_windows.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_semester: Mapped[int] = mapped_column(Integer, nullable=False)
    main_group_id: Mapped[int] = mapped_column(
        ForeignKey("academic_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, index=True, default="pendiente")
    observation_reason: Mapped[Optional[str]] = mapped_column(String(30))
    observation_message: Mapped[Optional[str]] = mapped_column(Text)
    # Scholarship, amounts and subject lists as shown to the student when they last submitted.
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    handled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    handled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    student: Mapped[Student] = relationship()
    window: Mapped[ReenrollmentWindow] = relationship()
    main_group: Mapped["AcademicGroup"] = relationship()
    items: Mapped[list["ReenrollmentRequestItem"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="ReenrollmentRequestItem.id"
    )


class ReenrollmentRequestItem(Base):
    """A recursado or pending subject of a request, with the group chosen for it."""

    __tablename__ = "reenrollment_request_items"
    __table_args__ = (
        UniqueConstraint("request_id", "subject_code", name="uq_reenrollment_item_subject"),
        CheckConstraint("kind IN ('recursado', 'pendiente')", name="ck_reenrollment_item_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("reenrollment_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    subject_code: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(200), nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("academic_groups.id", ondelete="RESTRICT"), nullable=False, index=True)

    request: Mapped[ReenrollmentRequest] = relationship(back_populates="items")
    group: Mapped["AcademicGroup"] = relationship()
