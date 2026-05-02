"""AcademicPeriod model — represents a semester period (e.g. I/2026, II/2026)."""

from sqlalchemy import String, Integer, Date, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.group import Group


class AcademicPeriod(Base):
    __tablename__ = "academic_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)  # "I/2026", "II/2026"
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Primer Semestre 2026"
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planning")  # planning|active|closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    groups: Mapped[list["Group"]] = relationship("Group", back_populates="academic_period", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AcademicPeriod id={self.id} code={self.code} status={self.status}>"
