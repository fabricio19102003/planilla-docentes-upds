"""
Model: AppSetting

Key/value table for business-configurable settings that used to live in
``.env`` / ``config.py``.  Values are stored as TEXT and interpreted by the
service layer (``app.services.app_settings_service``) — numeric fields like
``HOURLY_RATE`` are cast to ``float`` on read.

Rows are seeded on first startup (see ``main.py`` lifespan).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"<AppSetting {self.key}={self.value!r}>"
