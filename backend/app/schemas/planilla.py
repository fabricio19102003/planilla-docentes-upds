from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import date, datetime
from typing import Literal, Optional
from decimal import Decimal

from app.schemas.attendance import MonthlyAttendanceSummaryResponse
from app.schemas.biometric import BiometricUploadResponse


class ExcludedDaySchema(BaseModel):
    """Represents a day excluded from planilla calculation.

    Scopes:
      - global: excludes the date for ALL teachers, subjects, and semesters.
      - semester: excludes the date only for a specific semester (requires semester_id).
      - subject: excludes the date only for a specific (subject, group) pair.
                 The combination (subject_id, group_id) is unique and irrepetible —
                 the same subject+group never exists in two different semesters, so
                 semester_id is NOT needed for subject scope.

    Field names match the published API contract:
      - semester_id: required when scope=semester ONLY
      - subject_id:  required when scope=subject
      - group_id:    required when scope=subject
    """

    date: date
    scope: Literal["global", "semester", "subject"]
    semester_id: Optional[str] = None
    subject_id: Optional[str] = None
    group_id: Optional[str] = None
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_scope_fields(self) -> "ExcludedDaySchema":
        if self.scope == "semester" and not self.semester_id:
            raise ValueError("semester_id is required for scope='semester'")
        if self.scope == "subject" and (not self.subject_id or not self.group_id):
            raise ValueError("subject_id and group_id are required for scope='subject'")
        return self


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
    excluded_days: list[ExcludedDaySchema] = Field(default_factory=list)


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
    # None (field omitted) → inherit stored planilla exclusions
    # [] (explicit empty list) → no exclusions (overrides stored)
    # [<entries>] → use caller-supplied exclusions (overrides stored)
    excluded_days: Optional[list[ExcludedDaySchema]] = None


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
