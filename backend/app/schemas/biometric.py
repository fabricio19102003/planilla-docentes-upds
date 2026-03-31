from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from datetime import datetime, date, time
from typing import Optional


class BiometricUploadResponse(BaseModel):
    id: int
    filename: str
    upload_date: datetime
    month: int
    year: int
    total_records: int
    total_teachers: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class BiometricRecordBase(BaseModel):
    teacher_ci: str
    teacher_name: Optional[str] = None
    date: date
    entry_time: Optional[time] = None
    exit_time: Optional[time] = None
    worked_minutes: Optional[int] = None
    shift: Optional[str] = None


class BiometricRecordResponse(BiometricRecordBase):
    id: int
    upload_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BiometricUploadCreate(BaseModel):
    """Used when creating a new biometric upload record."""
    filename: str
    month: int
    year: int
