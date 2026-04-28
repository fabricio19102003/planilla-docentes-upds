from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RoomEquipment(Base):
    __tablename__ = "room_equipment"
    __table_args__ = (
        UniqueConstraint("room_id", "equipment_id", name="uq_room_equipment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    equipment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="room_equipment",
    )
    equipment: Mapped["Equipment"] = relationship(
        "Equipment",
        back_populates="room_equipment",
    )

    def __repr__(self) -> str:
        return f"<RoomEquipment room_id={self.room_id} equipment_id={self.equipment_id}>"
