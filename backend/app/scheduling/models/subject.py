from sqlalchemy import String, Integer, Text, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.semester import Semester


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    semester_id: Mapped[int] = mapped_column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True)  # Null for electives
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    theoretical_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # HT from curriculum
    practical_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)    # HP from curriculum
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)             # CR from curriculum
    is_elective: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    semester: Mapped["Semester"] = relationship("Semester", back_populates="subjects")

    def __repr__(self) -> str:
        return f"<Subject id={self.id} code={self.code} name={self.name}>"
