from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
from typing import Optional, Any, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.academic_period import AcademicPeriod
    from app.scheduling.models.subject import Subject
    from app.scheduling.models.group import Group


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
        UniqueConstraint(
            "teacher_ci",
            "academic_period_id",
            "subject_id",
            "group_id",
            name="uq_designation_teacher_period_subject_group_fk",
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

    # ─── Scheduling FK columns (Phase 2 — nullable during transition) ────
    # These provide relational links to the scheduling module entities.
    # The string columns above (subject, semester, group_code, academic_period)
    # are maintained in parallel by CompatibilityAdapter during the transition.
    academic_period_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("academic_periods.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="legacy_import"
    )  # "manual" | "legacy_import"
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="confirmed"
    )  # "draft" | "confirmed" | "cancelled"

    # Relationships
    teacher: Mapped["Teacher"] = relationship(  # noqa: F821
        "Teacher", back_populates="designations"
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(  # noqa: F821
        "AttendanceRecord", back_populates="designation"
    )

    # Scheduling relationships (optional during transition)
    period_rel: Mapped[Optional["AcademicPeriod"]] = relationship("AcademicPeriod")
    subject_rel: Mapped[Optional["Subject"]] = relationship("Subject")
    group_rel: Mapped[Optional["Group"]] = relationship("Group")

    def __repr__(self) -> str:
        return f"<Designation id={self.id} ci={self.teacher_ci} subject={self.subject} group={self.group_code}>"
