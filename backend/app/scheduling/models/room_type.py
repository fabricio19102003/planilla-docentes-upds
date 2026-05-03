"""RoomType model — classification for rooms (lab, aula, auditorio, etc.)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.room import Room


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="room_type")
