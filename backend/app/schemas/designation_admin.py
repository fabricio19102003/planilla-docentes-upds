from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.designation_change import DesignationChangeBlocker, DesignationChangeRegeneration


class ScheduleSlotInput(BaseModel):
    dia: str = Field(max_length=20)
    hora_inicio: str = Field(max_length=5)
    hora_fin: str = Field(max_length=5)
    horas_academicas: int | None = None


class DesignationWriteRequest(BaseModel):
    """One designation as an admin types it; hours per week and the schedule text are derived."""

    teacher_ci: str = Field(min_length=1, max_length=20)
    subject: str = Field(max_length=200)
    semester: str = Field(max_length=50)
    group_code: str = Field(max_length=20)
    academic_period: str | None = Field(default=None, max_length=20)
    designation_type: Literal["regular", "practice"] | None = None
    schedule: list[ScheduleSlotInput] = Field(default_factory=list)
    monthly_hours: int = Field(ge=0)
    semester_hours: int | None = Field(default=None, ge=0)
    contract_start_date: date | None = None
    contract_end_date: date | None = None


class DesignationFinalizeRequest(BaseModel):
    end_date: date


class DesignationActionState(BaseModel):
    allowed: bool
    reason: str | None = None


class DesignationActions(BaseModel):
    edit: DesignationActionState
    edit_dates: DesignationActionState
    finalize: DesignationActionState
    delete: DesignationActionState


class DesignationAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_ci: str
    teacher_name: str
    subject: str
    semester: str
    group_code: str
    academic_period: str
    designation_type: str
    schedule_json: Any
    semester_hours: int | None
    monthly_hours: int | None
    weekly_hours: int | None
    weekly_hours_calculated: int | None
    schedule_raw: str | None
    contract_start_date: date | None
    contract_end_date: date | None
    created_at: datetime
    status: Literal["active", "finalized"]
    has_contract: bool
    attendance_count: int
    actions: DesignationActions


class DesignationAdminList(BaseModel):
    academic_period: str
    periods: list[str]
    items: list[DesignationAdminItem]


class DesignationAdminMutation(DesignationAdminItem):
    regenerate: list[DesignationChangeRegeneration] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "DesignationActionState",
    "DesignationActions",
    "DesignationAdminItem",
    "DesignationAdminList",
    "DesignationAdminMutation",
    "DesignationChangeBlocker",
    "DesignationFinalizeRequest",
    "DesignationWriteRequest",
    "ScheduleSlotInput",
]
