from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Any


class DesignationBase(BaseModel):
    teacher_ci: str
    subject: str
    semester: str
    group_code: str
    schedule_json: Any  # JSON array of schedule slots
    semester_hours: Optional[int] = None
    monthly_hours: Optional[int] = None
    weekly_hours: Optional[int] = None
    weekly_hours_calculated: Optional[int] = None
    schedule_raw: Optional[str] = None


class DesignationCreate(DesignationBase):
    pass


class DesignationResponse(DesignationBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
