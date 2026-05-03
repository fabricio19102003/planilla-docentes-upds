"""Schemas for TeacherAvailability and AvailabilitySlot CRUD."""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, ConfigDict, Field

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


# ─── Input ────────────────────────────────────────────────────────────

class AvailabilitySlotInput(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


class SetAvailabilityRequest(BaseModel):
    teacher_ci: str
    period_id: int
    slots: list[AvailabilitySlotInput]


# ─── Response ─────────────────────────────────────────────────────────

class AvailabilitySlotResponse(BaseModel):
    id: int
    day_of_week: int
    day_name: str = ""
    start_time: str
    end_time: str

    model_config = ConfigDict(from_attributes=True)


class TeacherAvailabilityResponse(BaseModel):
    id: int
    teacher_ci: str
    teacher_name: str = ""
    academic_period_id: int
    slots: list[AvailabilitySlotResponse] = []

    model_config = ConfigDict(from_attributes=True)
