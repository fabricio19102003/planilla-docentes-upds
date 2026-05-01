from pydantic import BaseModel, ConfigDict, Field
from datetime import date, time
from typing import Literal


class PracticeAttendanceCreate(BaseModel):
    teacher_ci: str
    designation_id: int
    date: date
    scheduled_start: time
    scheduled_end: time
    actual_start: time | None = None
    actual_end: time | None = None
    academic_hours: int = Field(ge=0)
    status: Literal["attended", "absent", "late", "justified"] = "absent"
    observation: str | None = None


class PracticeAttendanceBulkCreate(BaseModel):
    """Bulk create: admin generates attendance entries for a period from schedule."""
    month: int
    year: int
    start_date: date | None = None
    end_date: date | None = None


class PracticeAttendanceUpdate(BaseModel):
    actual_start: time | None = None
    actual_end: time | None = None
    status: Literal["attended", "absent", "late", "justified"] | None = None
    observation: str | None = None


class PracticeAttendanceResponse(BaseModel):
    id: int
    teacher_ci: str
    teacher_name: str | None = None
    designation_id: int
    subject: str | None = None
    group_code: str | None = None
    semester: str | None = None
    date: date
    scheduled_start: time
    scheduled_end: time
    actual_start: time | None = None
    actual_end: time | None = None
    academic_hours: int
    status: str
    observation: str | None = None
    registered_by: str | None = None
    created_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PracticeAttendanceSummary(BaseModel):
    """Summary per teacher for the period."""
    teacher_ci: str
    teacher_name: str
    total_scheduled: int  # total scheduled classes
    total_attended: int
    total_absent: int
    total_late: int
    total_justified: int
    total_hours_scheduled: int
    total_hours_attended: int
    attendance_rate: float  # percentage
