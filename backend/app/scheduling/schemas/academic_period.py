from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class AcademicPeriodCreate(BaseModel):
    code: str = Field(..., example="I/2026")
    name: str = Field(..., example="Primer Semestre 2026")
    start_date: date
    end_date: date
    status: str = Field(default="planning", example="planning")
    is_active: bool = Field(default=False)


class AcademicPeriodResponse(AcademicPeriodCreate):
    id: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
