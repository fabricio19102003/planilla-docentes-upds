from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    is_active: bool
    last_login: Optional[datetime] = None


class UserCreate(BaseModel):
    ci: str
    full_name: str
    email: Optional[str] = None
    password: str
    role: str  # 'admin' | 'docente'
    teacher_ci: Optional[str] = None  # required if role is 'docente'


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
    teacher_ci: Optional[str] = None


class PasswordReset(BaseModel):
    new_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


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


# ------------------------------------------------------------------
# Detail Request schemas
# ------------------------------------------------------------------


class DetailRequestCreate(BaseModel):
    month: int
    year: int
    request_type: str  # 'biometric_detail' | 'hours_summary' | 'schedule_detail'
    message: Optional[str] = None


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
    responded_at: Optional[datetime] = None
    created_at: datetime


class DetailRequestAction(BaseModel):
    status: str  # 'approved' | 'rejected'
    admin_response: Optional[str] = None
