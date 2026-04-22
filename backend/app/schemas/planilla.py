from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date, datetime
from typing import Literal, Optional
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
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    discount_mode: Literal["attendance", "full"] = "attendance"

    model_config = ConfigDict(from_attributes=True)


class PlanillaGenerateRequest(BaseModel):
    """Request body to trigger planilla generation."""
    month: int
    year: int
    payment_overrides: dict[str, float] = Field(default_factory=dict)
    start_date: date | None = None   # Optional: start of attendance period for filtering
    end_date: date | None = None     # Optional: end of attendance period for filtering
    # "attendance" = apply attendance-based discounts (default)
    # "full" = pay full assigned hours to all teachers (no discounts)
    discount_mode: Literal["attendance", "full"] = "attendance"


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
    discount_mode: Literal["attendance", "full"] = "attendance"


class SalaryReportRequest(BaseModel):
    """Request body for salary report (Planilla Salarios) generation."""
    month: int
    year: int
    # Override config defaults when provided
    company_name: Optional[str] = None
    company_nit: Optional[str] = None
    discount_mode: Literal["attendance", "full"] = "attendance"
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class DashboardSummaryResponse(BaseModel):
    recent_uploads: list[BiometricUploadResponse] = Field(default_factory=list)
    latest_attendance_summary: Optional[MonthlyAttendanceSummaryResponse] = None
    teacher_count: int
    designation_count: int

    # Chart data
    attendance_distribution: list[dict] = Field(default_factory=list)
    top_earners: list[dict] = Field(default_factory=list)
    group_distribution: list[dict] = Field(default_factory=list)
    semester_distribution: list[dict] = Field(default_factory=list)
    total_monthly_payment: float = 0.0
    pending_requests: int = 0
