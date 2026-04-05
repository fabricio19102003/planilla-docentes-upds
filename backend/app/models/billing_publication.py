from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Any, Optional

from app.database import Base


class BillingPublication(Base):
    __tablename__ = "billing_publications"

    __table_args__ = (
        UniqueConstraint("month", "year", name="uq_billing_publication_month_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="published", nullable=False)  # 'published' | 'draft'
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # increments on each re-publish

    # Snapshot of billing data at publication time
    total_teachers: Mapped[int] = mapped_column(Integer, default=0)
    total_payment: Mapped[float] = mapped_column(nullable=False, default=0.0)

    # Full billing snapshot stored at publish time — prevents retroactive recalculation
    # Structure: {"teacher_details": [...], "total_payment": float, "total_teachers": int,
    #             "rate_per_hour": float, "generated_at": str}
    billing_snapshot: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Audit
    published_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    unpublished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<BillingPublication {self.month}/{self.year} status={self.status}>"
