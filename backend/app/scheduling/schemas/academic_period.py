"""Schemas for AcademicPeriod CRUD operations."""

from __future__ import annotations

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AcademicPeriodCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)  # "I/2026"
    name: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=2020, le=2100)
    semester_number: int = Field(ge=1, le=2)
    start_date: date
    end_date: date

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.match(r"^(I|II)/\d{4}$", v):
            raise ValueError("Code must match format I/YYYY or II/YYYY")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("end_date must be after start_date")
        return v


class AcademicPeriodUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None


class AcademicPeriodResponse(BaseModel):
    id: int
    code: str
    name: str
    year: int
    semester_number: int
    start_date: date
    end_date: date
    is_active: bool
    status: str
    group_count: int = 0
    model_config = ConfigDict(from_attributes=True)
