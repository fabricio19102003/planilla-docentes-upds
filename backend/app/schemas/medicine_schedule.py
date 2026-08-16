from datetime import time
from typing import Any, Literal

from pydantic import BaseModel, Field


class MedicineIssuePreview(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    location: dict[str, Any]

class MedicineMeetingPreview(BaseModel):
    activity: str
    teacher_raw: str | None
    teacher_key: str | None
    day: str
    start_time: time
    end_time: time
    source_cell: str
    raw_payload: dict[str, Any]

class MedicineOfferingPreview(BaseModel):
    category: Literal["regular", "convalidacion"]
    semester: int | None
    subject_raw: str
    subject_key: str
    group_code: str
    shift: Literal["morning", "afternoon", "night"]
    source_sheet: str
    source_row: int
    raw_payload: dict[str, Any]
    meetings: list[MedicineMeetingPreview] = Field(default_factory=list)

class MedicineWorkbookPreview(BaseModel):
    workbook_sha256: str
    parser_schema_version: str
    offerings: list[MedicineOfferingPreview] = Field(default_factory=list)
    issues: list[MedicineIssuePreview] = Field(default_factory=list)
    unsupported_semesters: list[int] = Field(default_factory=list)

class MedicineVersionPreviewResponse(BaseModel):
    academic_period: str
    description: str | None = None
    preview: MedicineWorkbookPreview
