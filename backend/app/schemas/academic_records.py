from __future__ import annotations

from pydantic import BaseModel


class CurriculumSlotResponse(BaseModel):
    id: int
    subject_id: int | None
    code: str | None
    name: str
    theory_hours: int
    practice_hours: int
    credits: int
    is_elective: bool


class CurriculumSemesterResponse(BaseModel):
    semester: int
    subjects: list[CurriculumSlotResponse]


class CurriculumPlanResponse(BaseModel):
    id: int
    code: str
    name: str
    program_code: str
    total_semesters: int
    semesters: list[CurriculumSemesterResponse]


class CurriculumPlanSummary(BaseModel):
    id: int
    code: str
    name: str
    program_code: str
    total_semesters: int
    subject_count: int
