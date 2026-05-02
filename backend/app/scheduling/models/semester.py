from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.career import Career
    from app.scheduling.models.subject import Subject


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("career_id", "number", name="uq_semester_career_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    career_id: Mapped[int] = mapped_column(Integer, ForeignKey("careers.id", ondelete="CASCADE"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3...
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "1er Semestre"
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    career: Mapped["Career"] = relationship("Career", back_populates="semesters")
    subjects: Mapped[list["Subject"]] = relationship(
        "Subject", back_populates="semester", cascade="all, delete-orphan",
        order_by="Subject.code"
    )

    def __repr__(self) -> str:
        return f"<Semester id={self.id} number={self.number} career_id={self.career_id}>"
