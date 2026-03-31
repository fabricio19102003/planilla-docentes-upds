from sqlalchemy import String, Integer, DateTime, Date, Time, Text, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date, time
from typing import Optional

from app.database import Base


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    __table_args__ = (
        UniqueConstraint(
            "teacher_ci", "designation_id", "date", "scheduled_start",
            name="uq_attendance_record"
        ),
    )

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
    designation: Mapped["Designation"] = relationship(  # noqa: F821
        "Designation", back_populates="attendance_records"
    )
    biometric_record: Mapped[Optional["BiometricRecord"]] = relationship(  # noqa: F821
        "BiometricRecord", back_populates="attendance_records"
    )

    def __repr__(self) -> str:
        return f"<AttendanceRecord ci={self.teacher_ci} date={self.date} status={self.status}>"
