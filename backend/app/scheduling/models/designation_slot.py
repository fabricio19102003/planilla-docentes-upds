from datetime import datetime, time
from sqlalchemy import Integer, String, Time, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class DesignationSlot(Base):
    __tablename__ = "designation_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    designation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("designations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dia: Mapped[str] = mapped_column(String(20), nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[time] = mapped_column(Time, nullable=False)
    duracion_minutos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    horas_academicas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    room_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    designation: Mapped["Designation"] = relationship(
        "Designation",
        back_populates="slots",
    )
    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="slots",
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "dia": self.dia,
            "hora_inicio": self.hora_inicio.strftime("%H:%M") if self.hora_inicio else "",
            "hora_fin": self.hora_fin.strftime("%H:%M") if self.hora_fin else "",
            "duracion_minutos": self.duracion_minutos,
            "horas_academicas": self.horas_academicas,
        }
