from sqlalchemy import Integer, DateTime, String, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional, Any
from decimal import Decimal

from app.database import Base


class PlanillaOutput(Base):
    __tablename__ = "planilla_outputs"

    __table_args__ = (
        UniqueConstraint("month", "year", name="uq_planilla_month_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    total_teachers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    payment_overrides_json: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="generated", nullable=False)

    def __repr__(self) -> str:
        return f"<PlanillaOutput id={self.id} month={self.month}/{self.year} status={self.status}>"
