from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.scheduling.schemas.semester import SemesterResponse


# --- Curriculum import sub-models (defined before CurriculumImportRequest) ---

class CurriculumSubject(BaseModel):
    codigo: str | None = None
    nombre: str
    HT: int = 0   # theoretical hours
    HP: int = 0   # practical hours
    CR: int = 0   # credits

    @field_validator("CR", mode="before")
    @classmethod
    def coerce_cr(cls, v: Any) -> int:
        """Handle malformed JSON where CR might be a string like 'CR: 2' or ' 2'."""
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            # Strip any leading label like "CR: "
            cleaned = v.strip().lstrip("CR:").strip()
            try:
                return int(cleaned)
            except ValueError:
                return 0
        return 0


class CurriculumSemester(BaseModel):
    semestre: int
    materias: list[CurriculumSubject]


class CurriculumImportRequest(BaseModel):
    """JSON format for importing malla curricular."""
    carrera: str
    universidad: str | None = None
    semestres: list[CurriculumSemester]


class CurriculumImportResponse(BaseModel):
    career_id: int
    career_code: str
    semesters_created: int
    semesters_existing: int
    subjects_created: int
    subjects_updated: int
    warnings: list[str] = []


# --- Career CRUD schemas ---

class CareerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class CareerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class CareerResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    is_active: bool
    semester_count: int = 0
    subject_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class CareerWithSemesters(CareerResponse):
    semesters: list[SemesterResponse] = []
