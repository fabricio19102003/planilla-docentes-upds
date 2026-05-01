from sqlalchemy import String, Integer, Numeric, Text, DateTime, Date, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date as date_type
from typing import Optional, Any
from decimal import Decimal

from app.database import Base


class PracticePlanillaOutput(Base):
    """Persisted record for each generated practice-teacher planilla.

    Separate from ``PlanillaOutput`` because practice planillas have a
    different hourly rate, attendance source, and approval workflow.
    """

    __tablename__ = "practice_planilla_outputs"

    __table_args__ = (
        UniqueConstraint("month", "year", name="uq_practice_planilla_month_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_teachers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    payment_overrides_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="generated", nullable=False)
    # "attendance" = apply attendance-based discounts (default)
    # "full" = pay all practice teachers their full assigned hours
    discount_mode: Mapped[str] = mapped_column(String(20), default="attendance", nullable=False)
    start_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PracticePlanillaOutput id={self.id} "
            f"month={self.month}/{self.year} status={self.status}>"
        )
