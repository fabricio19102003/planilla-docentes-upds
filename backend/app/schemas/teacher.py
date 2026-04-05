from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.designation import DesignationResponse


class TeacherBase(BaseModel):
    ci: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    external_permanent: Optional[str] = None
    academic_level: Optional[str] = None
    profession: Optional[str] = None
    specialty: Optional[str] = None
    bank: Optional[str] = None
    account_number: Optional[str] = None
    nit: Optional[str] = None
    sap_code: Optional[str] = None
    invoice_retention: Optional[str] = None


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    ci: Optional[str] = None  # Changing CI cascades to designations, attendance, users
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    external_permanent: Optional[str] = None
    academic_level: Optional[str] = None
    profession: Optional[str] = None
    specialty: Optional[str] = None
    bank: Optional[str] = None
    account_number: Optional[str] = None
    nit: Optional[str] = None
    sap_code: Optional[str] = None
    invoice_retention: Optional[str] = None


class TeacherResponse(TeacherBase):
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TeacherWithDesignations(TeacherResponse):
    designations: list[DesignationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TeacherAttendanceSummary(BaseModel):
    total_records: int = 0
    attended: int = 0
    late: int = 0
    absent: int = 0
    no_exit: int = 0
    total_academic_hours: int = 0


class PaginatedTeachersResponse(BaseModel):
    items: list[TeacherResponse] = Field(default_factory=list)
    total: int
    page: int
    per_page: int


class TeacherDetailResponse(TeacherResponse):
    designations: list[DesignationResponse] = Field(default_factory=list)
    attendance_summary: TeacherAttendanceSummary = Field(default_factory=TeacherAttendanceSummary)

    model_config = ConfigDict(from_attributes=True)
