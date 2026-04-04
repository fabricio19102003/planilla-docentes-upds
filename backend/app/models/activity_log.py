from sqlalchemy import String, Integer, DateTime, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
from typing import Optional, Any

from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Who
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_ci: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # What
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Details (optional structured data)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Result
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)

    # When
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False, index=True)

    # Where (optional)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<ActivityLog id={self.id} action={self.action} user={self.user_ci}>"
