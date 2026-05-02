"""Group model — represents a student group within an academic period + semester + shift."""

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.academic_period import AcademicPeriod
    from app.scheduling.models.shift import Shift
    from app.scheduling.models.semester import Semester


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("academic_period_id", "semester_id", "code", name="uq_group_period_semester_code"),
        Index("ix_groups_period_semester", "academic_period_id", "semester_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    academic_period_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("academic_periods.id", ondelete="CASCADE"), nullable=False,
    )
    semester_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("semesters.id", ondelete="RESTRICT"), nullable=False,
    )
    shift_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)  # Parallel number: 1, 2, 3...
    code: Mapped[str] = mapped_column(String(20), nullable=False)  # Auto: "M-1", "T-2", "G.E."
    is_special: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # G.E. groups
    student_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    academic_period: Mapped["AcademicPeriod"] = relationship("AcademicPeriod", back_populates="groups")
    semester: Mapped["Semester"] = relationship("Semester")
    shift: Mapped["Shift"] = relationship("Shift", back_populates="groups")

    def __repr__(self) -> str:
        return f"<Group id={self.id} code={self.code} period={self.academic_period_id}>"
