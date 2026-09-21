from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date, time
from typing import Optional

from app.database import Base


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    __table_args__ = (
        CheckConstraint(
            "(designation_id IS NOT NULL AND published_schedule_assignment_id IS NULL) OR "
            "(designation_id IS NULL AND published_schedule_assignment_id IS NOT NULL)",
            name="ck_attendance_record_exactly_one_source",
        ),
        Index(
            "uq_attendance_record_legacy_source",
            "teacher_ci", "designation_id", "date", "scheduled_start",
            unique=True,
            postgresql_where=text("designation_id IS NOT NULL"),
            sqlite_where=text("designation_id IS NOT NULL"),
        ),
        Index(
            "uq_attendance_record_published_source",
            "teacher_ci", "published_schedule_assignment_id", "date", "scheduled_start",
            unique=True,
            postgresql_where=text("published_schedule_assignment_id IS NOT NULL"),
            sqlite_where=text("published_schedule_assignment_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False, index=True
    )
    designation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("designations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    published_schedule_assignment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("academic_schedule_published_assignments.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_start: Mapped[time] = mapped_column(Time, nullable=False)
    scheduled_end: Mapped[time] = mapped_column(Time, nullable=False)
    actual_entry: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_exit: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # ATTENDED, LATE, ABSENT
    academic_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    observation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    biometric_record_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("biometric_records.id", ondelete="SET NULL"), nullable=True
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    teacher: Mapped["Teacher"] = relationship(  # noqa: F821
        "Teacher", back_populates="attendance_records"
    )
    designation: Mapped[Optional["Designation"]] = relationship(  # noqa: F821
        "Designation", back_populates="attendance_records"
    )
    published_schedule_assignment: Mapped[Optional["AcademicSchedulePublishedAssignment"]] = relationship(  # noqa: F821
        "AcademicSchedulePublishedAssignment", back_populates="attendance_records"
    )
    biometric_record: Mapped[Optional["BiometricRecord"]] = relationship(  # noqa: F821
        "BiometricRecord", back_populates="attendance_records"
    )

    @property
    def source_kind(self) -> str:
        return "legacy" if self.designation_id is not None else "published"

    @property
    def source_id(self) -> int:
        source_id = self.designation_id or self.published_schedule_assignment_id
        if source_id is None:  # pragma: no cover - database CHECK invariant
            raise ValueError("Attendance source identity is missing")
        return source_id

    @property
    def source_key(self) -> str:
        return f"{self.source_kind}:{self.source_id}"

    def __repr__(self) -> str:
        return f"<AttendanceRecord ci={self.teacher_ci} date={self.date} status={self.status}>"
