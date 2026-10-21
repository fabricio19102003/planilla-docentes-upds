from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DesignationChangeRequest(BaseModel):
    """Hand a legacy designation (or every active one of a teacher) to another teacher from a date."""

    academic_period: str | None = Field(default=None, max_length=20)
    effective_from: date
    incoming_teacher_ci: str = Field(min_length=1, max_length=20)
    scope: Literal["designation", "teacher"] = "designation"
    designation_id: int | None = None
    outgoing_teacher_ci: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _scope_identifier(self) -> "DesignationChangeRequest":
        if self.scope == "designation" and self.designation_id is None:
            raise ValueError("designation_id es obligatorio para cambiar una designación")
        if self.scope == "teacher" and not self.outgoing_teacher_ci:
            raise ValueError("outgoing_teacher_ci es obligatorio para cambiar todas las designaciones de un docente")
        return self


class DesignationChangeItem(BaseModel):
    designation_id: int
    subject: str
    semester: str
    group_code: str
    designation_type: str
    outgoing_teacher_ci: str
    incoming_teacher_ci: str
    outgoing_until: date
    incoming_from: date
    incoming_until: date | None


class DesignationChangeBlocker(BaseModel):
    code: str
    message: str
    designation_id: int | None = None
    dates: list[date] = Field(default_factory=list)


class DesignationChangeRegeneration(BaseModel):
    planilla: Literal["regular", "practice"]
    month: int
    year: int
    status: str


class DesignationChangeTeacherImpact(BaseModel):
    teacher_ci: str
    teacher_name: str
    activity: Literal["theory", "practice"]
    hours_before: int
    hours_after: int
    amount_before: float
    amount_after: float


class DesignationChangeImpact(BaseModel):
    month: int
    year: int
    teachers: list[DesignationChangeTeacherImpact]


class DesignationChangePreview(BaseModel):
    can_apply: bool
    items: list[DesignationChangeItem]
    blockers: list[DesignationChangeBlocker]
    warnings: list[str]
    regenerate: list[DesignationChangeRegeneration]
    impact: DesignationChangeImpact


class DesignationChangeResult(BaseModel):
    ended_designation_ids: list[int]
    created_designation_ids: list[int]
    regenerate: list[DesignationChangeRegeneration]
    impact: DesignationChangeImpact


class PublicationPayrollSimulationRequest(BaseModel):
    effective_from: date
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)


class PublicationPayrollSimulation(BaseModel):
    draft_id: int
    effective_from: date
    month: int
    year: int
    teachers: list[DesignationChangeTeacherImpact]
    total_before: float
    total_after: float
