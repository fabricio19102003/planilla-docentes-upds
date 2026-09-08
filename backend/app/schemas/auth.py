from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ------------------------------------------------------------------
# User schemas
# ------------------------------------------------------------------


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ci: str
    full_name: str
    email: Optional[str] = None
    role: str
    teacher_ci: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    last_login: Optional[datetime] = None
    must_change_password: bool = False


class UserListSummary(BaseModel):
    total: int = 0
    admins: int = 0
    docentes: int = 0
    active: int = 0


class PaginatedUsersResponse(BaseModel):
    items: list[UserResponse] = Field(default_factory=list)
    total: int
    page: int
    per_page: int
    summary: UserListSummary = Field(default_factory=UserListSummary)


class UserCreate(BaseModel):
    ci: str
    full_name: str
    email: Optional[str] = None
    password: str
    role: str = "docente"  # 'admin' | 'docente'
    teacher_ci: Optional[str] = None  # required if role is 'docente'

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not any(c.isupper() for c in v):
            raise ValueError('La contraseña debe incluir al menos una mayúscula')
        if not any(c.islower() for c in v):
            raise ValueError('La contraseña debe incluir al menos una minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('La contraseña debe incluir al menos un número')
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
    teacher_ci: Optional[str] = None


class PasswordReset(BaseModel):
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not any(c.isupper() for c in v):
            raise ValueError('La contraseña debe incluir al menos una mayúscula')
        if not any(c.islower() for c in v):
            raise ValueError('La contraseña debe incluir al menos una minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('La contraseña debe incluir al menos un número')
        return v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not any(c.isupper() for c in v):
            raise ValueError('La contraseña debe incluir al menos una mayúscula')
        if not any(c.islower() for c in v):
            raise ValueError('La contraseña debe incluir al menos una minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('La contraseña debe incluir al menos un número')
        return v


# ------------------------------------------------------------------
# Auth schemas
# ------------------------------------------------------------------


class LoginRequest(BaseModel):
    ci: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    must_change_password: bool = False


# ------------------------------------------------------------------
# Detail Request schemas
# ------------------------------------------------------------------


class DetailRequestCreate(BaseModel):
    month: int
    year: int
    request_type: str  # 'biometric_detail' | 'hours_summary' | 'schedule_detail'
    message: Optional[str] = None


class ScheduleResolutionSlot(BaseModel):
    dia: str
    hora_inicio: str
    hora_fin: str
    horas_academicas: int


class ScheduleResolutionDesignation(BaseModel):
    subject: str
    semester: str
    group_code: str
    weekly_hours: Optional[int] = None
    monthly_hours: Optional[int] = None
    schedule: list[ScheduleResolutionSlot]


class ScheduleResolutionSnapshot(BaseModel):
    kind: Literal["schedule_detail"]
    academic_period: str
    designations: list[ScheduleResolutionDesignation]


class HoursSummaryResolutionSnapshot(BaseModel):
    kind: Literal["hours_summary"]
    month: int
    year: int
    total_records: int
    total_academic_hours: int
    status_counts: dict[str, int]


class BiometricResolutionRecord(BaseModel):
    date: str
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    worked_minutes: Optional[int] = None
    shift: Optional[str] = None


class BiometricResolutionSnapshot(BaseModel):
    kind: Literal["biometric_detail"]
    month: int
    year: int
    records: list[BiometricResolutionRecord]


DetailRequestResolutionSnapshot = Union[
    ScheduleResolutionSnapshot,
    HoursSummaryResolutionSnapshot,
    BiometricResolutionSnapshot,
]


class DetailRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_ci: str
    teacher_name: Optional[str] = None
    month: int
    year: int
    request_type: str
    message: Optional[str] = None
    status: str
    admin_response: Optional[str] = None
    resolution_snapshot: Optional[DetailRequestResolutionSnapshot] = None
    responded_at: Optional[datetime] = None
    created_at: datetime


class DetailRequestAction(BaseModel):
    status: str  # 'approved' | 'rejected'
    admin_response: Optional[str] = None
