from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
from typing import Optional, Any

from app.database import Base


class Designation(Base):
    __tablename__ = "designations"

    __table_args__ = (
        UniqueConstraint(
            "teacher_ci",
            "subject",
            "semester",
            "group_code",
            "academic_period",
            name="uq_designation_teacher_subject_semester_group_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    semester: Mapped[str] = mapped_column(String(50), nullable=False)
    group_code: Mapped[str] = mapped_column(String(20), nullable=False)  # Normalized: M-1, T-2, N-3, G.E.
    # NOTE: The actual default used at upload time comes from the DB-backed
    # app_settings (key ACTIVE_ACADEMIC_PERIOD), resolved via the router/service.
    # This model-level default is only a safety fallback and should never be
    # relied upon directly.
    academic_period: Mapped[str] = mapped_column(String(20), nullable=False, default="I/2026", index=True)
    schedule_json: Mapped[Any] = mapped_column(JSON, nullable=False)  # array of schedule slots
    semester_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    monthly_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weekly_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weekly_hours_calculated: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    schedule_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # "regular" = docente de teoría (tarifa HOURLY_RATE)
    # "practice" = docente asistencial / prácticas internas (tarifa PRACTICE_HOURLY_RATE)
    designation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="regular", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    teacher: Mapped["Teacher"] = relationship(  # noqa: F821
        "Teacher", back_populates="designations"
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(  # noqa: F821
        "AttendanceRecord", back_populates="designation"
    )

    def __repr__(self) -> str:
        return f"<Designation id={self.id} ci={self.teacher_ci} subject={self.subject} group={self.group_code}>"
