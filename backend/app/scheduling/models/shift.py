"""Shift model — represents time shifts (Mañana, Tarde, Noche)."""

from sqlalchemy import String, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import time
from typing import TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.group import Group


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(5), nullable=False, unique=True)  # "M", "T", "N"
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # "Mañana", "Tarde", "Noche"
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    groups: Mapped[list["Group"]] = relationship("Group", back_populates="shift")

    def __repr__(self) -> str:
        return f"<Shift id={self.id} code={self.code} name={self.name}>"
