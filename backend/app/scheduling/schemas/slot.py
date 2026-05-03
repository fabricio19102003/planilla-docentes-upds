"""Schemas for DesignationSlot CRUD and conflict validation."""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, ConfigDict, Field


# ─── Day-of-week helper ──────────────────────────────────────────────

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


# ─── Slot CRUD ────────────────────────────────────────────────────────

class SlotCreate(BaseModel):
    designation_id: int
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    room_id: int | None = None


class SlotUpdate(BaseModel):
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    room_id: int | None = None


class SlotResponse(BaseModel):
    id: int
    designation_id: int
    room_id: int | None = None
    room_code: str = ""
    day_of_week: int
    day_name: str = ""
    start_time: str
    end_time: str
    duration_minutes: int
    academic_hours: int

    model_config = ConfigDict(from_attributes=True)


class SlotValidateRequest(BaseModel):
    """Dry-run validation — returns conflicts without saving."""

    designation_id: int
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    room_id: int | None = None


class RoomAssignRequest(BaseModel):
    room_id: int


# ─── Conflict response ───────────────────────────────────────────────

class ConflictResponse(BaseModel):
    type: str
    severity: str
    message: str
    conflicting_slot_id: int | None = None
    details: dict = {}
