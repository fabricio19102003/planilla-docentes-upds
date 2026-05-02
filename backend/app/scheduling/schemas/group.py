"""Schemas for Group CRUD operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    academic_period_id: int
    semester_id: int
    shift_id: int
    number: int = Field(ge=1)
    is_special: bool = False
    student_count: int | None = None


class GroupBulkCreate(BaseModel):
    academic_period_id: int
    semester_id: int
    groups: list[GroupCreate]


class GroupUpdate(BaseModel):
    student_count: int | None = None
    is_active: bool | None = None


class GroupResponse(BaseModel):
    id: int
    academic_period_id: int
    semester_id: int
    semester_name: str = ""
    shift_id: int
    shift_code: str = ""
    shift_name: str = ""
    number: int
    code: str
    is_special: bool
    student_count: int | None = None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
