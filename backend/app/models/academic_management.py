from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampedCatalog:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AcademicProgram(TimestampedCatalog, Base):
    __tablename__ = "academic_programs"
    __table_args__ = (UniqueConstraint("code", name="uq_academic_program_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    offerings: Mapped[list["SubjectOffering"]] = relationship(back_populates="program")
    groups: Mapped[list["AcademicGroup"]] = relationship(back_populates="program")
    schedule_drafts: Mapped[list["AcademicScheduleDraft"]] = relationship(back_populates="program")


class AcademicSubject(TimestampedCatalog, Base):
    __tablename__ = "academic_subjects"
    __table_args__ = (UniqueConstraint("code", name="uq_academic_subject_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    offerings: Mapped[list["SubjectOffering"]] = relationship(back_populates="subject")


class SubjectOffering(TimestampedCatalog, Base):
    __tablename__ = "subject_offerings"
    __table_args__ = (
        UniqueConstraint(
            "subject_id", "program_id", "academic_period", "semester",
            name="uq_subject_offering_identity",
        ),
        CheckConstraint("semester > 0", name="ck_subject_offering_semester_positive"),
        CheckConstraint("theory_hours >= 0", name="ck_subject_offering_theory_hours"),
        CheckConstraint("practice_hours >= 0", name="ck_subject_offering_practice_hours"),
        CheckConstraint(
            "theory_hours > 0 OR practice_hours > 0", name="ck_subject_offering_has_hours"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("academic_subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_period: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    theory_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    practice_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    subject: Mapped[AcademicSubject] = relationship(back_populates="offerings")
    program: Mapped[AcademicProgram] = relationship(back_populates="offerings")


class AcademicGroup(TimestampedCatalog, Base):
    __tablename__ = "academic_groups"
    __table_args__ = (
        UniqueConstraint(
            "program_id", "academic_period", "semester", "code",
            name="uq_academic_group_identity",
        ),
        CheckConstraint("semester > 0", name="ck_academic_group_semester_positive"),
        CheckConstraint(
            "expected_size IS NULL OR expected_size > 0", name="ck_academic_group_expected_size"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_period: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    shift: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    expected_size: Mapped[Optional[int]] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    program: Mapped[AcademicProgram] = relationship(back_populates="groups")


class Classroom(TimestampedCatalog, Base):
    __tablename__ = "classrooms"
    __table_args__ = (
        UniqueConstraint("code", name="uq_classroom_code"),
        CheckConstraint(
            "(classroom_type IN ('classroom', 'laboratory') AND capacity IS NOT NULL AND capacity > 0) "
            "OR (classroom_type IN ('virtual', 'other') AND (capacity IS NULL OR capacity > 0))",
            name="ck_classroom_capacity_by_type",
        ),
        CheckConstraint(
            "classroom_type IN ('classroom', 'laboratory', 'virtual', 'other')",
            name="ck_classroom_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    campus: Mapped[str] = mapped_column(String(120), nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(Integer)
    classroom_type: Mapped[str] = mapped_column(String(20), nullable=False)
    resources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class TeacherAvailability(TimestampedCatalog, Base):
    __tablename__ = "teacher_availability"
    __table_args__ = (
        CheckConstraint(
            "weekday IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')",
            name="ck_teacher_availability_weekday",
        ),
        CheckConstraint("start_time < end_time", name="ck_teacher_availability_time_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_period: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    weekday: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    teacher: Mapped[Any] = relationship("Teacher")


class AcademicScheduleDraft(TimestampedCatalog, Base):
    __tablename__ = "academic_schedule_drafts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'archived', 'published')",
            name="ck_academic_schedule_draft_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_period: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", nullable=False, index=True)

    program: Mapped[AcademicProgram] = relationship(back_populates="schedule_drafts")
    blocks: Mapped[list["AcademicScheduleBlock"]] = relationship(
        back_populates="draft", cascade="all, delete-orphan"
    )


class AcademicScheduleBlock(TimestampedCatalog, Base):
    __tablename__ = "academic_schedule_blocks"
    __table_args__ = (
        CheckConstraint(
            "activity_type IN ('theory', 'practice')",
            name="ck_academic_schedule_block_activity_type",
        ),
        CheckConstraint(
            "weekday IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday')",
            name="ck_academic_schedule_block_weekday",
        ),
        CheckConstraint("start_time < end_time", name="ck_academic_schedule_block_time_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("academic_schedule_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("subject_offerings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("academic_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    classroom_id: Mapped[int] = mapped_column(
        ForeignKey("classrooms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    activity_type: Mapped[str] = mapped_column(String(12), nullable=False)
    weekday: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    draft: Mapped[AcademicScheduleDraft] = relationship(back_populates="blocks")
    offering: Mapped[SubjectOffering] = relationship()
    group: Mapped[AcademicGroup] = relationship()
    classroom: Mapped[Classroom] = relationship()
    assignments: Mapped[list["AcademicScheduleAssignment"]] = relationship(
        back_populates="block", cascade="all, delete-orphan"
    )


class AcademicScheduleAssignment(TimestampedCatalog, Base):
    __tablename__ = "academic_schedule_assignments"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_academic_schedule_assignment_date_order",
        ),
        Index(
            "ix_academic_schedule_assignments_block_dates",
            "block_id", "effective_from", "effective_to",
        ),
        Index(
            "ix_academic_schedule_assignments_teacher_dates",
            "teacher_ci", "effective_from", "effective_to",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_id: Mapped[int] = mapped_column(
        ForeignKey("academic_schedule_blocks.id", ondelete="CASCADE"), nullable=False
    )
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="RESTRICT"), nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)

    block: Mapped[AcademicScheduleBlock] = relationship(back_populates="assignments")
    teacher: Mapped[Any] = relationship("Teacher")


class AcademicSchedulePublication(Base):
    __tablename__ = "academic_schedule_publications"
    __table_args__ = (
        UniqueConstraint(
            "program_id", "academic_period", "effective_from", "sequence",
            name="uq_academic_schedule_publication_revision",
        ),
        UniqueConstraint("source_draft_id", name="uq_academic_schedule_publication_source_draft"),
        CheckConstraint("sequence > 0", name="ck_academic_schedule_publication_sequence"),
        Index(
            "ix_academic_schedule_publications_scope_effective",
            "program_id", "academic_period", "effective_from", "sequence",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("academic_programs.id", ondelete="RESTRICT"), nullable=False
    )
    academic_period: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_draft_id: Mapped[int] = mapped_column(
        ForeignKey("academic_schedule_drafts.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    program: Mapped[AcademicProgram] = relationship()
    source_draft: Mapped[AcademicScheduleDraft] = relationship()
    blocks: Mapped[list["AcademicSchedulePublishedBlock"]] = relationship(
        back_populates="publication", cascade="all, delete-orphan"
    )


class AcademicSchedulePublishedBlock(Base):
    __tablename__ = "academic_schedule_published_blocks"
    __table_args__ = (
        UniqueConstraint(
            "publication_id", "source_block_id",
            name="uq_academic_schedule_published_block_source",
        ),
        CheckConstraint(
            "activity_type IN ('theory', 'practice')",
            name="ck_academic_schedule_published_block_activity",
        ),
        CheckConstraint(
            "weekday IN ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday')",
            name="ck_academic_schedule_published_block_weekday",
        ),
        CheckConstraint(
            "start_time < end_time", name="ck_academic_schedule_published_block_time_order"
        ),
        Index(
            "ix_academic_schedule_published_blocks_publication_day",
            "publication_id", "weekday", "start_time",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publication_id: Mapped[int] = mapped_column(
        ForeignKey("academic_schedule_publications.id", ondelete="CASCADE"), nullable=False
    )
    source_block_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_offering_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_classroom_id: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_code: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_name: Mapped[str] = mapped_column(String(200), nullable=False)
    group_code: Mapped[str] = mapped_column(String(30), nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    classroom_code: Mapped[str] = mapped_column(String(30), nullable=False)
    classroom_name: Mapped[str] = mapped_column(String(200), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(12), nullable=False)
    weekday: Mapped[str] = mapped_column(String(12), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    publication: Mapped[AcademicSchedulePublication] = relationship(back_populates="blocks")
    assignments: Mapped[list["AcademicSchedulePublishedAssignment"]] = relationship(
        back_populates="block", cascade="all, delete-orphan"
    )


class AcademicSchedulePublishedAssignment(Base):
    __tablename__ = "academic_schedule_published_assignments"
    __table_args__ = (
        UniqueConstraint(
            "publication_block_id", "source_assignment_id",
            name="uq_academic_schedule_published_assignment_source",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_academic_schedule_published_assignment_date_order",
        ),
        Index(
            "ix_academic_schedule_published_assignments_block_dates",
            "publication_block_id", "effective_from", "effective_to",
        ),
        Index(
            "ix_academic_schedule_published_assignments_teacher_dates",
            "teacher_ci", "effective_from", "effective_to",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publication_block_id: Mapped[int] = mapped_column(
        ForeignKey("academic_schedule_published_blocks.id", ondelete="CASCADE"), nullable=False
    )
    source_assignment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    teacher_ci: Mapped[str] = mapped_column(String(20), nullable=False)
    teacher_name: Mapped[str] = mapped_column(String(200), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)

    block: Mapped[AcademicSchedulePublishedBlock] = relationship(back_populates="assignments")
    attendance_records: Mapped[list[Any]] = relationship(
        "AttendanceRecord", back_populates="published_schedule_assignment"
    )
    practice_attendance_logs: Mapped[list[Any]] = relationship(
        "PracticeAttendanceLog", back_populates="published_schedule_assignment"
    )


class HistoricalScheduleImport(Base):
    """Durable receipt for a privileged, digest-bound historical import."""

    __tablename__ = "historical_schedule_imports"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_historical_schedule_import_key"),
        UniqueConstraint("preview_digest", name="uq_historical_schedule_import_digest"),
        CheckConstraint(
            "policy = 'historical_availability_not_recorded'",
            name="ck_historical_schedule_import_policy",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    preview_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    pre_state_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    applied_state_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    academic_period: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    policy: Mapped[str] = mapped_column(String(80), nullable=False)
    source_hashes: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
