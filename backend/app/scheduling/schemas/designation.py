"""Schemas for scheduling-based designation CRUD (E6)."""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, ConfigDict, Field

from app.scheduling.schemas.slot import SlotResponse


# ─── Inputs ──────────────────────────────────────────────────────────


class SlotInput(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    room_id: int | None = None


class DesignationSchedulingCreate(BaseModel):
    teacher_ci: str
    period_id: int
    subject_id: int
    group_id: int
    semester_hours: int | None = None
    slots: list[SlotInput] = []


class DesignationSchedulingUpdate(BaseModel):
    subject_id: int | None = None
    group_id: int | None = None
    semester_hours: int | None = None


# ─── Responses ───────────────────────────────────────────────────────


class DesignationSchedulingResponse(BaseModel):
    id: int
    teacher_ci: str
    teacher_name: str = ""
    academic_period: str
    academic_period_id: int | None = None
    subject: str
    subject_id: int | None = None
    group_code: str
    group_id: int | None = None
    semester: str
    status: str
    source: str
    weekly_hours_calculated: int | None = None
    monthly_hours: int | None = None
    semester_hours: int | None = None
    designation_type: str
    slots: list[SlotResponse] = []

    model_config = ConfigDict(from_attributes=True)


class MigrationResult(BaseModel):
    migrated: int
    skipped: int
    errors: list[str]
