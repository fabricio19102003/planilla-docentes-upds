"""Room model — physical classroom/lab with type, capacity, and equipment."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.room_equipment import RoomEquipment
    from app.scheduling.models.room_type import RoomType


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (Index("ix_rooms_building_floor", "building", "floor"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    building: Mapped[str] = mapped_column(String(100), nullable=False)
    floor: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("room_types.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    room_type: Mapped["RoomType"] = relationship("RoomType", back_populates="rooms")
    equipment_items: Mapped[list["RoomEquipment"]] = relationship(
        "RoomEquipment", back_populates="room", cascade="all, delete-orphan"
    )
