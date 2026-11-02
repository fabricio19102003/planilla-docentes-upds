"""Summer/winter intensive courses opened by registration staff and taken by students from the portal."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.academic_management import AcademicSubject, TimestampedCatalog
from app.models.academic_records import Student
from app.models.teacher import Teacher

COURSE_STATUSES = ("open", "closed")


class IntensiveCourseSettings(TimestampedCatalog, Base):
    """Single row (id 1): amounts of intensive courses, independent of the payroll hourly rates."""

    __tablename__ = "intensive_course_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_intensive_settings_single_row"),
        CheckConstraint("theory_hourly_rate IS NULL OR theory_hourly_rate > 0", name="ck_intensive_settings_theory"),
        CheckConstraint("practice_hourly_rate IS NULL OR practice_hourly_rate > 0",
                        name="ck_intensive_settings_practice"),
        CheckConstraint("margin_factor >= 1", name="ck_intensive_settings_factor"),
        CheckConstraint("min_price > 0 AND min_price <= max_price", name="ck_intensive_settings_prices"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Null means "not configured": no course can be opened until both rates are set.
    theory_hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    practice_hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    margin_factor: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=Decimal("1.10"))
    min_price: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    max_price: Mapped[int] = mapped_column(Integer, nullable=False, default=1600)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class IntensiveCourse(TimestampedCatalog, Base):
    __tablename__ = "intensive_courses"
    __table_args__ = (
        UniqueConstraint("term_code", "subject_id", name="uq_intensive_course_term_subject"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_intensive_course_status"),
        CheckConstraint("capacity >= 1", name="ck_intensive_course_capacity"),
        CheckConstraint("enrollment_ends_on >= enrollment_starts_on", name="ck_intensive_course_dates"),
        CheckConstraint("theory_hours >= 0 AND practice_hours >= 0", name="ck_intensive_course_hours"),
        CheckConstraint("theory_hours > 0 OR practice_hours > 0", name="ck_intensive_course_has_hours"),
        CheckConstraint(
            "status = 'open' OR (final_enrolled IS NOT NULL AND final_price IS NOT NULL)",
            name="ck_intensive_course_closed_price",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("academic_subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="RESTRICT"), nullable=False, index=True
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    enrollment_starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    enrollment_ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    theory_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    practice_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open", index=True)
    # Fixed when the enrollment is closed.
    final_enrolled: Mapped[Optional[int]] = mapped_column(Integer)
    final_price: Mapped[Optional[int]] = mapped_column(Integer)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    closed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    subject: Mapped[AcademicSubject] = relationship()
    teacher: Mapped[Teacher] = relationship()
    enrollments: Mapped[list["IntensiveEnrollment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="IntensiveEnrollment.id"
    )


class IntensiveEnrollment(Base):
    __tablename__ = "intensive_enrollments"
    __table_args__ = (UniqueConstraint("course_id", "student_id", name="uq_intensive_enrollment_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("intensive_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now(), nullable=False
    )

    course: Mapped[IntensiveCourse] = relationship(back_populates="enrollments")
    student: Mapped[Student] = relationship()
