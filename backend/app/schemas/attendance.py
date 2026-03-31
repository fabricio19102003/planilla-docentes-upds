from __future__ import annotations

from pydantic import BaseModel, ConfigDict
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
