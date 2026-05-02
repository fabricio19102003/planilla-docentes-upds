"""Schemas for Shift operations."""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, ConfigDict


class ShiftUpdate(BaseModel):
    name: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    display_order: int | None = None


class ShiftResponse(BaseModel):
    id: int
    code: str
    name: str
    start_time: str  # Serialize time as "HH:MM"
    end_time: str
    display_order: int
    model_config = ConfigDict(from_attributes=True)
