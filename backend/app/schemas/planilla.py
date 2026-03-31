from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from decimal import Decimal


class PlanillaOutputResponse(BaseModel):
    id: int
    month: int
    year: int
    generated_at: datetime
    file_path: Optional[str] = None
    total_teachers: int
    total_hours: int
    total_payment: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)


class PlanillaGenerateRequest(BaseModel):
    """Request body to trigger planilla generation."""
    month: int
    year: int


class PlanillaGenerateResponse(BaseModel):
    """Response after triggering planilla generation."""
    planilla_id: int
    month: int
    year: int
    file_url: Optional[str] = None
    total_teachers: int
    total_hours: int
    total_payment: Decimal
    status: str
