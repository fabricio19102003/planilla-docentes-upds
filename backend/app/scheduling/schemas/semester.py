from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.scheduling.schemas.subject import SubjectResponse


class SemesterCreate(BaseModel):
    career_id: int
    number: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=100)


class SemesterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class SemesterResponse(BaseModel):
    id: int
    career_id: int
    number: int
    name: str
    is_active: bool
    subject_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class SemesterWithSubjects(SemesterResponse):
    subjects: list[SubjectResponse] = []
