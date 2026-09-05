from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime
from typing import Optional, Any


class DesignationBase(BaseModel):
    teacher_ci: str
    subject: str
    semester: str
    group_code: str
    schedule_json: Any  # JSON array of schedule slots
    semester_hours: Optional[int] = None
    monthly_hours: Optional[int] = None
    weekly_hours: Optional[int] = None
    weekly_hours_calculated: Optional[int] = None
    schedule_raw: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None


class DesignationCreate(DesignationBase):
    pass


class DesignationResponse(DesignationBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DesignationContractDatesUpdate(BaseModel):
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None


class DesignationUploadResponse(BaseModel):
    teachers_created: int
    teachers_reused: int
    designations_loaded: int
    skipped: int
    users_created: int = 0
    users_skipped: int = 0
    warnings: list[str] = Field(default_factory=list)


class DesignationImportCounts(BaseModel):
    creates: int = 0
    updates: int = 0
    noops: int = 0
    conflicts: int = 0


class DesignationImportPreviewResponse(BaseModel):
    digest: str
    parsed_format: str
    academic_period: str
    total_rows: int
    can_apply: bool
    teachers: DesignationImportCounts
    designations: DesignationImportCounts
    users: DesignationImportCounts
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DesignationImportApplyResponse(DesignationImportPreviewResponse):
    applied: bool = True
