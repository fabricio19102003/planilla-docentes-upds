from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional

from app.database import Base


class DetailRequest(Base):
    __tablename__ = "detail_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    request_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'biometric_detail' | 'hours_summary' | 'schedule_detail'
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    admin_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    teacher = relationship("Teacher", foreign_keys=[teacher_ci])
    requester = relationship("User", foreign_keys=[requested_by])
    responder = relationship("User", foreign_keys=[responded_by])

    def __repr__(self) -> str:
        return f"<DetailRequest id={self.id} teacher_ci={self.teacher_ci} status={self.status}>"
