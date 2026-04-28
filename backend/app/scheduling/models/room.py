from sqlalchemy import String, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    building: Mapped[str] = mapped_column(String(100), nullable=False)
    floor: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("room_types.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    room_type: Mapped["RoomType"] = relationship(
        "RoomType",
        back_populates="rooms",
    )
    room_equipment: Mapped[list["RoomEquipment"]] = relationship(
        "RoomEquipment",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    slots: Mapped[list["DesignationSlot"]] = relationship(
        "DesignationSlot",
        back_populates="room",
    )

    def __repr__(self) -> str:
        return f"<Room code={self.code} building={self.building} floor={self.floor}>"
