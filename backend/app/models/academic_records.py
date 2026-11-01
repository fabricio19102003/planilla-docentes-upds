"""Curriculum, academic terms, students and their per-subject history.

The legacy academic system remains the system of record: students and their
subject records are imported from its CSV exports and every import is
re-runnable. ``legacy_registration_id`` (the legacy ``RegistroMateriaID``) is
the stable identity of a subject record across imports.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.academic_management import AcademicProgram, AcademicSubject, TimestampedCatalog

TERM_KINDS = ("I", "II", "INV", "VER")
RECORD_STATUSES = ("aprobado", "reprobado", "retirado", "pendiente")


class CurriculumPlan(TimestampedCatalog, Base):
    __tablename__ = "curriculum_plans"
    __table_args__ = (
        UniqueConstraint("program_id", "code", name="uq_curriculum_plan_code"),
        CheckConstraint("total_semesters > 0", name="ck_curriculum_plan_semesters"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    total_semesters: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    program: Mapped[AcademicProgram] = relationship()
    subjects: Mapped[list["CurriculumSubject"]] = relationship(
        back_populates="plan", order_by="(CurriculumSubject.semester, CurriculumSubject.position)"
    )


class CurriculumSubject(TimestampedCatalog, Base):
    """One slot of the curriculum; electives are slots without a subject."""

    __tablename__ = "curriculum_subjects"
    __table_args__ = (
        UniqueConstraint("plan_id", "subject_id", name="uq_curriculum_subject_subject"),
        UniqueConstraint("plan_id", "semester", "slot_name", name="uq_curriculum_subject_slot"),
        CheckConstraint("semester > 0", name="ck_curriculum_subject_semester"),
        CheckConstraint(
            "theory_hours >= 0 AND practice_hours >= 0 AND credits >= 0",
            name="ck_curriculum_subject_load",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_subjects.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_name: Mapped[str] = mapped_column(String(200), nullable=False)
    theory_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    practice_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    is_elective: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plan: Mapped[CurriculumPlan] = relationship(back_populates="subjects")
    subject: Mapped[Optional[AcademicSubject]] = relationship()


class AcademicTerm(TimestampedCatalog, Base):
    """A normalized academic period: ``I/2026``, ``II/2026``, ``INV/2026``, ``VER/2026``."""

    __tablename__ = "academic_terms"
    __table_args__ = (
        UniqueConstraint("code", name="uq_academic_term_code"),
        UniqueConstraint("year", "kind", name="uq_academic_term_year_kind"),
        CheckConstraint("kind IN ('I', 'II', 'INV', 'VER')", name="ck_academic_term_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(4), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_intensive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legacy_names: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class AcademicHistoryImport(Base):
    """Receipt of one applied legacy CSV import."""

    __tablename__ = "academic_history_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    terms: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), nullable=False
    )


class Student(TimestampedCatalog, Base):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("document_number", name="uq_student_document_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(60), nullable=False)
    first_names: Mapped[str] = mapped_column(String(120), nullable=False)
    last_names: Mapped[str] = mapped_column(String(120), nullable=False)
    birth_date: Mapped[Optional[date]] = mapped_column(Date)
    gender: Mapped[Optional[str]] = mapped_column(String(20))
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    personal_email: Mapped[Optional[str]] = mapped_column(String(200))
    academic_email: Mapped[Optional[str]] = mapped_column(String(200))
    birth_country: Mapped[Optional[str]] = mapped_column(String(80))
    nationality: Mapped[Optional[str]] = mapped_column(String(80))
    is_foreign: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    school: Mapped[Optional[str]] = mapped_column(String(200))
    address: Mapped[Optional[str]] = mapped_column(Text)
    legacy_enrollment_status: Mapped[Optional[str]] = mapped_column(String(30), index=True)
    program_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    curriculum_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("curriculum_plans.id", ondelete="RESTRICT"), nullable=True
    )
    last_import_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_history_imports.id", ondelete="SET NULL"), nullable=True
    )

    records: Mapped[list["StudentSubjectRecord"]] = relationship(back_populates="student")

    @property
    def full_name(self) -> str:
        return f"{self.first_names} {self.last_names}".strip()


class StudentSubjectRecord(TimestampedCatalog, Base):
    """One subject a student took in one term (legacy ``RegistroMateriaID``)."""

    __tablename__ = "student_subject_records"
    __table_args__ = (
        UniqueConstraint("legacy_registration_id", name="uq_student_record_legacy_id"),
        CheckConstraint(
            "status IN ('aprobado', 'reprobado', 'retirado', 'pendiente')",
            name="ck_student_record_status",
        ),
        CheckConstraint(
            "grade IS NULL OR (grade >= 0 AND grade <= 100)", name="ck_student_record_grade"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    legacy_registration_id: Mapped[int] = mapped_column(Integer, nullable=False)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    term_id: Mapped[int] = mapped_column(
        ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("academic_subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    group_code: Mapped[Optional[str]] = mapped_column(String(20))
    shift: Mapped[Optional[str]] = mapped_column(String(20))
    teacher_document: Mapped[Optional[str]] = mapped_column(String(30))
    teacher_name: Mapped[Optional[str]] = mapped_column(String(200))
    teacher_ci: Mapped[Optional[str]] = mapped_column(
        ForeignKey("teachers.ci", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    grade: Mapped[Optional[int]] = mapped_column(Integer)
    last_import_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_history_imports.id", ondelete="SET NULL"), nullable=True
    )

    student: Mapped[Student] = relationship(back_populates="records")
    term: Mapped[AcademicTerm] = relationship()
    subject: Mapped[AcademicSubject] = relationship()
