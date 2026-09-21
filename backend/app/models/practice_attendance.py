from sqlalchemy import CheckConstraint, String, Integer, Text, DateTime, Date, Time, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date, time
from typing import Optional
from app.database import Base


class PracticeAttendanceLog(Base):
    """Manual attendance log for practice (asistencial) teachers.

    Unlike regular teachers whose attendance is derived from biometric
    records, practice teachers have their attendance entered manually by
    an admin from physical sign-in sheets.

    Each row represents one scheduled class for one teacher on one date.
    """

    __tablename__ = "practice_attendance_logs"

    __table_args__ = (
        CheckConstraint(
            "(designation_id IS NOT NULL AND published_schedule_assignment_id IS NULL) OR "
            "(designation_id IS NULL AND published_schedule_assignment_id IS NOT NULL)",
            name="ck_practice_attendance_log_exactly_one_source",
        ),
        Index(
            "uq_practice_attendance_log_legacy_source",
            "teacher_ci",
            "designation_id",
            "date",
            "scheduled_start",
            unique=True,
            postgresql_where=text("designation_id IS NOT NULL"),
            sqlite_where=text("designation_id IS NOT NULL"),
        ),
        Index(
            "uq_practice_attendance_log_published_source",
            "teacher_ci",
            "published_schedule_assignment_id",
            "date",
            "scheduled_start",
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
    actual_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    academic_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="absent"
    )  # attended | absent | late | justified
    observation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    registered_by: Mapped[Optional[str]] = mapped_column(
        String(20), ForeignKey("users.ci"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    teacher: Mapped["Teacher"] = relationship("Teacher")  # noqa: F821
    designation: Mapped[Optional["Designation"]] = relationship("Designation")  # noqa: F821
    published_schedule_assignment: Mapped[Optional["AcademicSchedulePublishedAssignment"]] = relationship(  # noqa: F821
        "AcademicSchedulePublishedAssignment", back_populates="practice_attendance_logs"
    )

    @property
    def source_kind(self) -> str:
        return "legacy" if self.designation_id is not None else "published"

    @property
    def source_id(self) -> int:
        value = self.designation_id or self.published_schedule_assignment_id
        if value is None:  # pragma: no cover - database CHECK invariant
            raise ValueError("Practice attendance source identity is missing")
        return value

    @property
    def source_key(self) -> str:
        return f"{self.source_kind}:{self.source_id}"

    def __repr__(self) -> str:
        return f"<PracticeAttendanceLog id={self.id} ci={self.teacher_ci} date={self.date} status={self.status}>"
