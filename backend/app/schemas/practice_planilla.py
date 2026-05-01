from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Literal, Optional
from decimal import Decimal


class PracticePlanillaGenerateRequest(BaseModel):
    """Request body to trigger practice planilla generation."""

    month: int
    year: int
    payment_overrides: dict[str, float] = Field(default_factory=dict)
    start_date: date | None = None
    end_date: date | None = None
    discount_mode: Literal["attendance", "full"] = "attendance"


class PracticePlanillaGenerateResponse(BaseModel):
    """Response after triggering practice planilla generation."""

    planilla_id: int
    month: int
    year: int
    file_path: Optional[str] = None
    total_teachers: int
    total_hours: int
    total_payment: Decimal
    warnings: list[str] = Field(default_factory=list)
    discount_mode: Literal["attendance", "full"] = "attendance"


class PracticePlanillaOutputResponse(BaseModel):
    """History list item for a generated practice planilla."""

    id: int
    month: int
    year: int
    generated_at: datetime
    file_path: Optional[str] = None
    total_teachers: int
    total_hours: int
    total_payment: Decimal
    status: str
    discount_mode: Literal["attendance", "full"] = "attendance"
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)
