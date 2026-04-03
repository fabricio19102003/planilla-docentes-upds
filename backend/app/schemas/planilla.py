from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from app.schemas.attendance import MonthlyAttendanceSummaryResponse
from app.schemas.biometric import BiometricUploadResponse


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
    payment_overrides: dict[str, float] = Field(default_factory=dict)
    start_date: date | None = None   # Optional: start of attendance period for filtering
    end_date: date | None = None     # Optional: end of attendance period for filtering


class PlanillaGenerateResponse(BaseModel):
    """Response after triggering planilla generation."""
    planilla_id: int
    month: int
    year: int
    file_path: Optional[str] = None
    total_teachers: int
    total_hours: int
    total_payment: Decimal
    warnings: list[str] = Field(default_factory=list)


class DashboardSummaryResponse(BaseModel):
    recent_uploads: list[BiometricUploadResponse] = Field(default_factory=list)
    latest_attendance_summary: Optional[MonthlyAttendanceSummaryResponse] = None
    teacher_count: int
    designation_count: int
