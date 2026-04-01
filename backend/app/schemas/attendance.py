from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date, time
from typing import Optional


class AttendanceRecordBase(BaseModel):
    teacher_ci: str
    designation_id: int
    date: date
    scheduled_start: time
    scheduled_end: time
    actual_entry: Optional[time] = None
    actual_exit: Optional[time] = None
    status: str  # ATTENDED, LATE, ABSENT
    academic_hours: int = 0
    late_minutes: int = 0
    observation: Optional[str] = None
    biometric_record_id: Optional[int] = None
    month: int
    year: int


class AttendanceRecordResponse(AttendanceRecordBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceWithDetails(AttendanceRecordResponse):
    """Attendance record enriched with teacher name and subject."""
    teacher_name: Optional[str] = None
    subject: Optional[str] = None
    group_code: Optional[str] = None
    semester: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AttendanceSummary(BaseModel):
    """Summary statistics for a given month/year."""
    month: int
    year: int
    total_teachers: int
    total_attended: int
    total_late: int
    total_absent: int
    total_academic_hours: int


class AttendanceProcessRequest(BaseModel):
    upload_id: int
    month: int
    year: int


class AttendanceProcessResponse(BaseModel):
    total_records: int
    attended: int
    late: int
    absent: int
    no_exit: int
    attendance_rate: float
    observations_count: int
    warnings: list[str] = Field(default_factory=list)


class PaginatedAttendanceResponse(BaseModel):
    items: list[AttendanceWithDetails] = Field(default_factory=list)
    total: int
    page: int
    per_page: int


class ObservationResponse(BaseModel):
    id: int
    teacher_ci: str
    teacher_name: Optional[str] = None
    designation_id: int
    subject: Optional[str] = None
    group_code: Optional[str] = None
    date: date
    scheduled_start: time
    scheduled_end: time
    status: str
    late_minutes: int = 0
    observation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MonthlyAttendanceSummaryResponse(BaseModel):
    total_teachers: int
    total_slots: int
    attended: int
    late: int
    absent: int
    no_exit: int
    attendance_rate: float
    total_academic_hours: int
    observations: list[ObservationResponse] = Field(default_factory=list)
