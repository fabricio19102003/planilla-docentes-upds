"""TeacherAvailability model — a teacher's availability declaration for an academic period."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.availability_slot import AvailabilitySlot


class TeacherAvailability(Base):
    __tablename__ = "teacher_availabilities"
    __table_args__ = (
        UniqueConstraint("teacher_ci", "academic_period_id", name="uq_teacher_period_availability"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False
    )
    academic_period_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("academic_periods.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    slots: Mapped[list["AvailabilitySlot"]] = relationship(
        "AvailabilitySlot", back_populates="availability", cascade="all, delete-orphan"
    )
    teacher = relationship("Teacher")
    academic_period = relationship("AcademicPeriod")
