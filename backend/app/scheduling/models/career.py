from sqlalchemy import String, Integer, Text, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.semester import Semester


class Career(Base):
    __tablename__ = "careers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)  # "MED", "ODO"
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # "Medicina"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    semesters: Mapped[list["Semester"]] = relationship(
        "Semester", back_populates="career", cascade="all, delete-orphan",
        order_by="Semester.number"
    )

    def __repr__(self) -> str:
        return f"<Career id={self.id} code={self.code} name={self.name}>"
