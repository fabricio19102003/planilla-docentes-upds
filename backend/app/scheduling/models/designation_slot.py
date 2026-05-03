"""DesignationSlot model — a single time block for a designation (day + time range + optional room)."""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.designation import Designation
    from app.scheduling.models.room import Room


class DesignationSlot(Base):
    __tablename__ = "designation_slots"
    __table_args__ = (
        UniqueConstraint("designation_id", "day_of_week", "start_time", name="uq_designation_slot"),
        Index("ix_designation_slots_room_day", "room_id", "day_of_week"),
        Index("ix_designation_slots_designation", "designation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    designation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("designations.id", ondelete="CASCADE"), nullable=False
    )
    room_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # Auto-computed
    academic_hours: Mapped[int] = mapped_column(Integer, nullable=False)  # Auto: round(duration/45)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    designation: Mapped["Designation"] = relationship("Designation", backref="slots_scheduled")
    room: Mapped[Optional["Room"]] = relationship("Room")
