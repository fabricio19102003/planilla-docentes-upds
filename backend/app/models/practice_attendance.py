from sqlalchemy import String, Integer, Text, DateTime, Date, Time, ForeignKey, func
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False, index=True
    )
    designation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("designations.id", ondelete="CASCADE"), nullable=False, index=True
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
    designation: Mapped["Designation"] = relationship("Designation")  # noqa: F821

    def __repr__(self) -> str:
        return f"<PracticeAttendanceLog id={self.id} ci={self.teacher_ci} date={self.date} status={self.status}>"
