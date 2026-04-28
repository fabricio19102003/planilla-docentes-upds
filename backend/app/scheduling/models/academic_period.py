from datetime import date, datetime
from sqlalchemy import Boolean, String, Integer, Date, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AcademicPeriod(Base):
    __tablename__ = "academic_periods"
    __table_args__ = (
        UniqueConstraint("code", name="uq_academic_period_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planning")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    designations: Mapped[list["Designation"]] = relationship(
        "Designation",
        back_populates="academic_period_rel",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AcademicPeriod code={self.code} status={self.status} active={self.is_active}>"
