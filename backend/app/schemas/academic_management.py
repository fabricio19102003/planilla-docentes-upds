from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
ScheduleWeekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
ClassroomType = Literal["classroom", "laboratory", "virtual", "other"]


def _required_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("El valor no puede estar vacío.")
    return normalized


def _code(value: str) -> str:
    return _required_text(value).upper()


def _naive_time(value: time) -> time:
    if value.tzinfo is not None and value.utcoffset() is not None:
        raise ValueError("La hora no debe incluir zona horaria.")
    return value


class CatalogResponse(BaseModel):
    id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProgramCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=200)
    _normalize_code = field_validator("code")(_code)
    _normalize_name = field_validator("name")(_required_text)


class ProgramUpdate(ProgramCreate):
    pass


class ProgramResponse(ProgramCreate, CatalogResponse):
    pass


class SubjectCreate(ProgramCreate):
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return _required_text(value) if value and value.strip() else None


class SubjectUpdate(SubjectCreate):
    pass


class SubjectResponse(SubjectCreate, CatalogResponse):
    pass


class OfferingCreate(BaseModel):
    subject_id: int = Field(gt=0)
    program_id: int = Field(gt=0)
    academic_period: str = Field(min_length=1, max_length=30)
    semester: int = Field(gt=0, le=20)
    theory_hours: int = Field(default=0, ge=0, le=1000)
    practice_hours: int = Field(default=0, ge=0, le=1000)
    _normalize_period = field_validator("academic_period")(_required_text)

    @model_validator(mode="after")
    def validate_hours(self):
        if self.theory_hours == 0 and self.practice_hours == 0:
            raise ValueError("Debe registrar al menos una hora de teoría o práctica.")
        return self


class OfferingUpdate(OfferingCreate):
    pass


class OfferingResponse(OfferingCreate, CatalogResponse):
    subject: SubjectResponse
    program: ProgramResponse


class GroupCreate(BaseModel):
    program_id: int = Field(gt=0)
    academic_period: str = Field(min_length=1, max_length=30)
    semester: int = Field(gt=0, le=20)
    shift: str = Field(min_length=1, max_length=30)
    code: str = Field(min_length=1, max_length=30)
    expected_size: int | None = Field(default=None, gt=0, le=10000)
    _normalize_period = field_validator("academic_period")(_required_text)
    _normalize_shift = field_validator("shift")(_required_text)
    _normalize_code = field_validator("code")(_code)


class GroupUpdate(GroupCreate):
    pass


class GroupResponse(GroupCreate, CatalogResponse):
    program: ProgramResponse


class ClassroomCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=200)
    campus: str = Field(min_length=1, max_length=120)
    capacity: int | None = Field(default=None, gt=0, le=10000)
    classroom_type: ClassroomType
    resources: list[str] = Field(default_factory=list, max_length=50)
    _normalize_code = field_validator("code")(_code)
    _normalize_name = field_validator("name", "campus")(_required_text)

    @model_validator(mode="after")
    def validate_capacity_for_type(self):
        if self.classroom_type in {"classroom", "laboratory"} and self.capacity is None:
            raise ValueError("La capacidad es obligatoria para aulas y laboratorios.")
        return self

    @field_validator("resources")
    @classmethod
    def normalize_resources(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = _required_text(value).casefold()
            if len(item) > 80:
                raise ValueError("Cada recurso debe tener 80 caracteres o menos.")
            if item not in seen:
                normalized.append(item)
                seen.add(item)
        return normalized


class ClassroomUpdate(ClassroomCreate):
    pass


class ClassroomResponse(ClassroomCreate, CatalogResponse):
    pass


class AvailabilityCreate(BaseModel):
    teacher_ci: str = Field(min_length=1, max_length=20)
    academic_period: str = Field(min_length=1, max_length=30)
    weekday: Weekday
    start_time: time
    end_time: time
    _normalize_teacher = field_validator("teacher_ci")(_required_text)
    _normalize_period = field_validator("academic_period")(_required_text)
    _validate_naive_times = field_validator("start_time", "end_time")(_naive_time)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_time >= self.end_time:
            raise ValueError("La hora de inicio debe ser anterior a la hora de fin.")
        return self


class AvailabilityUpdate(AvailabilityCreate):
    pass


class AvailabilityCompatibilityQuery(BaseModel):
    academic_period: str = Field(min_length=1, max_length=30)
    weekday: Weekday
    start_time: time
    end_time: time
    _normalize_period = field_validator("academic_period")(_required_text)
    _validate_naive_times = field_validator("start_time", "end_time")(_naive_time)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_time >= self.end_time:
            raise ValueError("La hora de inicio debe ser anterior a la hora de fin.")
        return self


class AvailabilityResponse(AvailabilityCreate, CatalogResponse):
    teacher_name: str | None = None


class CompatibleTeacherResponse(BaseModel):
    ci: str
    full_name: str
    model_config = ConfigDict(from_attributes=True)


class ScheduleDraftCreate(BaseModel):
    program_id: int = Field(gt=0)
    academic_period: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)
    _normalize_period = field_validator("academic_period")(_required_text)
    _normalize_name = field_validator("name")(_required_text)


class ScheduleDraftUpdate(ScheduleDraftCreate):
    pass


class ScheduleDraftResponse(ScheduleDraftCreate):
    id: int
    status: Literal["draft", "archived", "published"]
    created_at: datetime
    updated_at: datetime
    program: ProgramResponse
    model_config = ConfigDict(from_attributes=True)


class ScheduleBlockCreate(BaseModel):
    offering_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    classroom_id: int = Field(gt=0)
    activity_type: Literal["theory", "practice"]
    weekday: ScheduleWeekday
    start_time: time
    end_time: time
    _validate_naive_times = field_validator("start_time", "end_time")(_naive_time)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_time >= self.end_time:
            raise ValueError("La hora de inicio debe ser anterior a la hora de fin.")
        return self


class ScheduleBlockUpdate(ScheduleBlockCreate):
    pass


class ScheduleBlockResponse(ScheduleBlockCreate):
    id: int
    draft_id: int
    created_at: datetime
    updated_at: datetime
    offering: OfferingResponse
    group: GroupResponse
    classroom: ClassroomResponse
    model_config = ConfigDict(from_attributes=True)


class ScheduleAssignmentCreate(BaseModel):
    teacher_ci: str = Field(min_length=1, max_length=20)
    effective_from: date
    effective_to: date | None = None
    _normalize_teacher = field_validator("teacher_ci")(_required_text)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("La fecha final debe ser igual o posterior a la fecha inicial.")
        return self


class ScheduleAssignmentReplace(ScheduleAssignmentCreate):
    pass


class ScheduleAssignmentCorrection(BaseModel):
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_interval(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("La fecha final debe ser igual o posterior a la fecha inicial.")
        return self


class ScheduleAssignmentResponse(ScheduleAssignmentCreate):
    id: int
    block_id: int
    teacher_name: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CompatibleScheduleTeacherResponse(BaseModel):
    ci: str
    full_name: str
    model_config = ConfigDict(from_attributes=True)


class PaginatedCompatibleTeachersResponse(BaseModel):
    items: list[CompatibleScheduleTeacherResponse]
    total: int
    page: int
    per_page: int


class ScheduleWorkloadItem(BaseModel):
    teacher_ci: str
    teacher_name: str
    theory_minutes_week: int
    practice_minutes_week: int
    total_minutes_week: int


class ScheduleWorkloadResponse(BaseModel):
    draft_id: int
    reference_date: date
    items: list[ScheduleWorkloadItem]


class SchedulePublicationPreviewRequest(BaseModel):
    effective_from: date


class SchedulePublicationPublishRequest(SchedulePublicationPreviewRequest):
    preview_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class SchedulePublicationBlocker(BaseModel):
    category: str
    count: int = Field(ge=0)
    message: str


class SchedulePublicationDiff(BaseModel):
    added_blocks: int = 0
    removed_blocks: int = 0
    changed_blocks: int = 0
    teacher_replacements: int = 0
    workload_changes: list[ScheduleWorkloadItem] = Field(default_factory=list)


class SchedulePublicationPreviewResponse(BaseModel):
    draft_id: int
    program_id: int
    academic_period: str
    effective_from: date
    sequence: int
    digest: str
    can_publish: bool
    block_count: int
    assignment_count: int
    blockers: list[SchedulePublicationBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    diff: SchedulePublicationDiff


class PublishedScheduleAssignmentResponse(BaseModel):
    id: int
    source_assignment_id: int
    teacher_ci: str
    teacher_name: str
    effective_from: date
    effective_to: date | None
    model_config = ConfigDict(from_attributes=True)


class PublishedScheduleBlockResponse(BaseModel):
    id: int
    source_block_id: int
    source_offering_id: int
    source_subject_id: int
    source_group_id: int
    source_classroom_id: int
    subject_code: str
    subject_name: str
    group_code: str
    semester: int
    classroom_code: str
    classroom_name: str
    activity_type: Literal["theory", "practice"]
    weekday: ScheduleWeekday
    start_time: time
    end_time: time
    notes: str | None
    assignments: list[PublishedScheduleAssignmentResponse]
    model_config = ConfigDict(from_attributes=True)


class SchedulePublicationResponse(BaseModel):
    id: int
    program_id: int
    academic_period: str
    effective_from: date
    sequence: int
    content_digest: str
    source_draft_id: int
    created_by: int | None
    created_at: datetime
    blocks: list[PublishedScheduleBlockResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class SchedulePublicationCloneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    _normalize_name = field_validator("name")(_required_text)
