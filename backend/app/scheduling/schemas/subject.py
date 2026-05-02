from pydantic import BaseModel, ConfigDict, Field


class SubjectCreate(BaseModel):
    semester_id: int
    code: str | None = Field(default=None, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    theoretical_hours: int = Field(default=0, ge=0)
    practical_hours: int = Field(default=0, ge=0)
    credits: int = Field(default=0, ge=0)
    is_elective: bool = False


class SubjectUpdate(BaseModel):
    code: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    theoretical_hours: int | None = Field(default=None, ge=0)
    practical_hours: int | None = Field(default=None, ge=0)
    credits: int | None = Field(default=None, ge=0)
    is_elective: bool | None = None
    is_active: bool | None = None


class SubjectResponse(BaseModel):
    id: int
    semester_id: int
    code: str | None = None
    name: str
    theoretical_hours: int
    practical_hours: int
    credits: int
    is_elective: bool
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
