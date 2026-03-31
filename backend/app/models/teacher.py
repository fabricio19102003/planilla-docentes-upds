from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List

from app.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    ci: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    external_permanent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Externo/Permanente
    academic_level: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profession: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    specialty: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    bank: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sap_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    invoice_retention: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    # Relationships
    designations: Mapped[List["Designation"]] = relationship(  # noqa: F821
        "Designation", back_populates="teacher", cascade="all, delete-orphan"
    )
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(  # noqa: F821
        "AttendanceRecord", back_populates="teacher"
    )

    def __repr__(self) -> str:
        return f"<Teacher ci={self.ci} name={self.full_name}>"
