from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    room_equipment: Mapped[list["RoomEquipment"]] = relationship(
        "RoomEquipment",
        back_populates="equipment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Equipment code={self.code} name={self.name}>"
