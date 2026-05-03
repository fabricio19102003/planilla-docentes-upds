"""AvailabilitySlot model — a single time block in a teacher's availability declaration."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.teacher_availability import TeacherAvailability


class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    __table_args__ = (
        UniqueConstraint(
            "availability_id", "day_of_week", "start_time", "end_time",
            name="uq_availability_slot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    availability_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teacher_availabilities.id", ondelete="CASCADE"), nullable=False
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    availability: Mapped["TeacherAvailability"] = relationship(
        "TeacherAvailability", back_populates="slots"
    )
