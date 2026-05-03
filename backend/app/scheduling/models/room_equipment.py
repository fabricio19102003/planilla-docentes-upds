"""RoomEquipment model — junction table linking rooms to equipment with quantity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.scheduling.models.equipment import Equipment
    from app.scheduling.models.room import Room


class RoomEquipment(Base):
    __tablename__ = "room_equipment"
    __table_args__ = (UniqueConstraint("room_id", "equipment_id", name="uq_room_equipment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    room: Mapped["Room"] = relationship("Room", back_populates="equipment_items")
    equipment: Mapped["Equipment"] = relationship("Equipment")
