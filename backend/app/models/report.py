from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
from typing import Optional, Any

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'financial', 'attendance', 'comparative'
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Filters used to generate
    filters: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)  # {month, year, teacher_ci, semester, group_code, subject}

    # Output
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Metadata
    generated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="generated", nullable=False)  # 'generated', 'error'

    def __repr__(self) -> str:
        return f"<Report id={self.id} type={self.report_type} status={self.status}>"
