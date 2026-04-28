from __future__ import annotations
from datetime import time
from pydantic import BaseModel, Field, ConfigDict


class ScheduledSlotDTO(BaseModel):
    """DTO for scheduled slots consumed by payroll services."""
    designation_id: int
    teacher_ci: str
    day_name: str = Field(..., description="Normalized day name (lunes, martes, etc.)")
    start_time: time
    end_time: time
    academic_hours: int
    subject: str
    group_code: str

    model_config = ConfigDict(from_attributes=True)