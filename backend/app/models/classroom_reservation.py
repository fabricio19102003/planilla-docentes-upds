from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.academic_management import TimestampedCatalog


class ClassroomReservation(TimestampedCatalog, Base):
    """One-off reservation of a classroom or laboratory by a teacher, confirmed on creation."""

    __tablename__ = "classroom_reservations"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_classroom_reservation_time_order"),
        CheckConstraint("academic_periods >= 1", name="ck_classroom_reservation_periods"),
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="ck_classroom_reservation_status"),
        Index("ix_classroom_reservations_room_date", "classroom_id", "reservation_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    classroom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("classrooms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="RESTRICT"), nullable=False, index=True
    )
    reservation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    academic_periods: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="confirmed", index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    classroom: Mapped[Any] = relationship("Classroom")
    teacher: Mapped[Any] = relationship("Teacher")
