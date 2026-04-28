from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    rooms: Mapped[list["Room"]] = relationship(
        "Room",
        back_populates="room_type",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RoomType code={self.code} name={self.name}>"
