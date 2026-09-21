from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic_management import (
    AcademicGroup,
    AcademicProgram,
    AcademicSubject,
    Classroom,
    SubjectOffering,
    TeacherAvailability,
)
from app.models.user import User
from app.schemas.academic_management import (
    AvailabilityCreate,
    AvailabilityCompatibilityQuery,
    AvailabilityResponse,
    AvailabilityUpdate,
    ClassroomCreate,
    ClassroomResponse,
    ClassroomUpdate,
    CompatibleTeacherResponse,
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    OfferingCreate,
    OfferingResponse,
    OfferingUpdate,
    ProgramCreate,
    ProgramResponse,
    ProgramUpdate,
    PaginatedCompatibleTeachersResponse,
    ScheduleAssignmentCorrection,
    ScheduleAssignmentCreate,
    ScheduleAssignmentReplace,
    ScheduleAssignmentResponse,
    ScheduleBlockCreate,
    ScheduleBlockResponse,
    ScheduleBlockUpdate,
    ScheduleDraftCreate,
    ScheduleDraftResponse,
    ScheduleDraftUpdate,
    SchedulePublicationCloneRequest,
    SchedulePublicationPreviewRequest,
    SchedulePublicationPreviewResponse,
    SchedulePublicationPublishRequest,
    SchedulePublicationResponse,
    ScheduleWorkloadResponse,
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
)
from app.services import academic_management_service as service
from app.services import academic_schedule_publication_service as publication_service
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

router = APIRouter(
    prefix="/api/admin/academic-management",
    tags=["academic-management"],
    dependencies=[Depends(require_admin)],
)


def _audit(
    db: Session, request: Request, user: User, action: str, entity_type: str
):
    action_labels = {
        "create": "creado", "update": "actualizado", "deactivate": "desactivado",
        "archive": "archivado", "delete": "eliminado", "replace": "reemplazado",
        "correct": "corregido", "publish": "publicado", "clone": "clonado",
    }
    entity_labels = {
        "academic_program": "Programa académico",
        "academic_subject": "Asignatura",
        "subject_offering": "Oferta académica",
        "academic_group": "Grupo académico",
        "classroom": "Aula",
        "teacher_availability": "Disponibilidad docente",
        "academic_schedule_draft": "Borrador de horario",
        "academic_schedule_block": "Bloque de horario",
        "academic_schedule_assignment": "Asignación docente",
        "academic_schedule_publication": "Publicación de horario",
    }

    def record(entity: Any) -> None:
        log_activity(
            db,
            action=f"{action}_{entity_type}",
            category="academic_management",
            description=f"{entity_labels[entity_type]} {action_labels[action]}",
            user=user,
            details={"entity_id": entity.id},
            request=request,
        )
    return record


def _availability_response(item: TeacherAvailability) -> AvailabilityResponse:
    response = AvailabilityResponse.model_validate(item)
    return response.model_copy(update={"teacher_name": item.teacher.full_name if item.teacher else None})


def _compatibility_query(
    academic_period: str = Query(min_length=1, max_length=30),
    weekday: str = Query(),
    start_time: str = Query(),
    end_time: str = Query(),
) -> AvailabilityCompatibilityQuery:
    try:
        return AvailabilityCompatibilityQuery.model_validate({
            "academic_period": academic_period,
            "weekday": weekday,
            "start_time": start_time,
            "end_time": end_time,
        })
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.get("/programs", response_model=list[ProgramResponse])
def list_programs(search: str | None = None, db: Session = Depends(get_db)):
    return service.list_catalog(db, AcademicProgram, search)


@router.post("/programs", response_model=ProgramResponse, status_code=201)
def create_program(payload: ProgramCreate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.create_entity(db, AcademicProgram, payload.model_dump(), _audit(db, request, user, "create", "academic_program"))


@router.put("/programs/{entity_id}", response_model=ProgramResponse)
def update_program(entity_id: int, payload: ProgramUpdate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.update_entity(db, service.get_or_404(db, AcademicProgram, entity_id), payload.model_dump(), _audit(db, request, user, "update", "academic_program"))


@router.post("/programs/{entity_id}/deactivate", response_model=ProgramResponse)
def deactivate_program(entity_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.deactivate_entity(db, service.get_or_404(db, AcademicProgram, entity_id), _audit(db, request, user, "deactivate", "academic_program"))


@router.get("/subjects", response_model=list[SubjectResponse])
def list_subjects(search: str | None = None, db: Session = Depends(get_db)):
    return service.list_catalog(db, AcademicSubject, search)


@router.post("/subjects", response_model=SubjectResponse, status_code=201)
def create_subject(payload: SubjectCreate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.create_entity(db, AcademicSubject, payload.model_dump(), _audit(db, request, user, "create", "academic_subject"))


@router.put("/subjects/{entity_id}", response_model=SubjectResponse)
def update_subject(entity_id: int, payload: SubjectUpdate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.update_entity(db, service.get_or_404(db, AcademicSubject, entity_id), payload.model_dump(), _audit(db, request, user, "update", "academic_subject"))


@router.post("/subjects/{entity_id}/deactivate", response_model=SubjectResponse)
def deactivate_subject(entity_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.deactivate_entity(db, service.get_or_404(db, AcademicSubject, entity_id), _audit(db, request, user, "deactivate", "academic_subject"))


@router.get("/offerings", response_model=list[OfferingResponse])
def list_offerings(db: Session = Depends(get_db)):
    return service.list_catalog(db, SubjectOffering)


@router.post("/offerings", response_model=OfferingResponse, status_code=201)
def create_offering(payload: OfferingCreate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.create_entity(db, SubjectOffering, payload.model_dump(), _audit(db, request, user, "create", "subject_offering"))


@router.put("/offerings/{entity_id}", response_model=OfferingResponse)
def update_offering(entity_id: int, payload: OfferingUpdate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.update_entity(db, service.get_or_404(db, SubjectOffering, entity_id), payload.model_dump(), _audit(db, request, user, "update", "subject_offering"))


@router.post("/offerings/{entity_id}/deactivate", response_model=OfferingResponse)
def deactivate_offering(entity_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.deactivate_entity(db, service.get_or_404(db, SubjectOffering, entity_id), _audit(db, request, user, "deactivate", "subject_offering"))


@router.get("/groups", response_model=list[GroupResponse])
def list_groups(db: Session = Depends(get_db)):
    return service.list_catalog(db, AcademicGroup)


@router.post("/groups", response_model=GroupResponse, status_code=201)
def create_group(payload: GroupCreate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.create_entity(db, AcademicGroup, payload.model_dump(), _audit(db, request, user, "create", "academic_group"))


@router.put("/groups/{entity_id}", response_model=GroupResponse)
def update_group(entity_id: int, payload: GroupUpdate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.update_entity(db, service.get_or_404(db, AcademicGroup, entity_id), payload.model_dump(), _audit(db, request, user, "update", "academic_group"))


@router.post("/groups/{entity_id}/deactivate", response_model=GroupResponse)
def deactivate_group(entity_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.deactivate_entity(db, service.get_or_404(db, AcademicGroup, entity_id), _audit(db, request, user, "deactivate", "academic_group"))


@router.get("/classrooms", response_model=list[ClassroomResponse])
def list_classrooms(search: str | None = None, db: Session = Depends(get_db)):
    return service.list_catalog(db, Classroom, search)


@router.post("/classrooms", response_model=ClassroomResponse, status_code=201)
def create_classroom(payload: ClassroomCreate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.create_entity(db, Classroom, payload.model_dump(), _audit(db, request, user, "create", "classroom"))


@router.put("/classrooms/{entity_id}", response_model=ClassroomResponse)
def update_classroom(entity_id: int, payload: ClassroomUpdate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.update_entity(db, service.get_or_404(db, Classroom, entity_id), payload.model_dump(), _audit(db, request, user, "update", "classroom"))


@router.post("/classrooms/{entity_id}/deactivate", response_model=ClassroomResponse)
def deactivate_classroom(entity_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return service.deactivate_entity(db, service.get_or_404(db, Classroom, entity_id), _audit(db, request, user, "deactivate", "classroom"))


@router.get("/availability", response_model=list[AvailabilityResponse])
def list_teacher_availability(
    teacher_ci: str = Query(min_length=1), academic_period: str = Query(min_length=1), db: Session = Depends(get_db)
):
    return [_availability_response(item) for item in service.list_availability(db, teacher_ci, academic_period)]


@router.post("/availability", response_model=AvailabilityResponse, status_code=201)
def create_availability(payload: AvailabilityCreate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    values = payload.model_dump()
    service.ensure_references(db, values)
    service.ensure_availability_no_overlap(db, values)
    item = service.create_entity(db, TeacherAvailability, values, _audit(db, request, user, "create", "teacher_availability"))
    return _availability_response(item)


@router.put("/availability/{entity_id}", response_model=AvailabilityResponse)
def update_availability(entity_id: int, payload: AvailabilityUpdate, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    values = payload.model_dump()
    service.ensure_references(db, values)
    service.ensure_availability_no_overlap(db, values, entity_id)
    item = service.update_entity(db, service.get_or_404(db, TeacherAvailability, entity_id), values, _audit(db, request, user, "update", "teacher_availability"))
    return _availability_response(item)


@router.post("/availability/{entity_id}/deactivate", response_model=AvailabilityResponse)
def deactivate_availability(entity_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = service.deactivate_entity(db, service.get_or_404(db, TeacherAvailability, entity_id), _audit(db, request, user, "deactivate", "teacher_availability"))
    return _availability_response(item)


@router.get("/availability/compatible-teachers", response_model=list[CompatibleTeacherResponse])
def list_compatible_teachers(
    query: AvailabilityCompatibilityQuery = Depends(_compatibility_query),
    db: Session = Depends(get_db),
):
    return service.compatible_teachers(
        db, query.academic_period, query.weekday, query.start_time, query.end_time
    )


@router.get("/schedule-drafts", response_model=list[ScheduleDraftResponse])
def list_schedule_drafts(
    program_id: int | None = Query(default=None, gt=0),
    academic_period: str | None = Query(default=None, min_length=1, max_length=30),
    db: Session = Depends(get_db),
):
    return service.list_schedule_drafts(db, program_id, academic_period)


@router.post("/schedule-drafts", response_model=ScheduleDraftResponse, status_code=201)
def create_schedule_draft(
    payload: ScheduleDraftCreate,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.create_schedule_draft(
        db, payload.model_dump(), _audit(db, request, user, "create", "academic_schedule_draft")
    )


@router.put("/schedule-drafts/{draft_id}", response_model=ScheduleDraftResponse)
def update_schedule_draft(
    draft_id: int,
    payload: ScheduleDraftUpdate,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.update_schedule_draft(
        db, draft_id, payload.model_dump(), _audit(db, request, user, "update", "academic_schedule_draft")
    )


@router.post("/schedule-drafts/{draft_id}/archive", response_model=ScheduleDraftResponse)
def archive_schedule_draft(
    draft_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.archive_schedule_draft(
        db, draft_id, _audit(db, request, user, "archive", "academic_schedule_draft")
    )


@router.get("/schedule-drafts/{draft_id}/blocks", response_model=list[ScheduleBlockResponse])
def list_schedule_blocks(draft_id: int, db: Session = Depends(get_db)):
    return service.list_schedule_blocks(db, draft_id)


@router.post("/schedule-drafts/{draft_id}/blocks", response_model=ScheduleBlockResponse, status_code=201)
def create_schedule_block(
    draft_id: int,
    payload: ScheduleBlockCreate,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.save_schedule_block(
        db, draft_id, payload.model_dump(), before_commit=_audit(db, request, user, "create", "academic_schedule_block")
    )


@router.put("/schedule-drafts/{draft_id}/blocks/{block_id}", response_model=ScheduleBlockResponse)
def update_schedule_block(
    draft_id: int,
    block_id: int,
    payload: ScheduleBlockUpdate,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.save_schedule_block(
        db, draft_id, payload.model_dump(), block_id,
        _audit(db, request, user, "update", "academic_schedule_block"),
    )


@router.delete("/schedule-drafts/{draft_id}/blocks/{block_id}", status_code=204)
def delete_schedule_block(
    draft_id: int,
    block_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service.delete_schedule_block(
        db, draft_id, block_id, _audit(db, request, user, "delete", "academic_schedule_block")
    )
    return Response(status_code=204)


@router.get(
    "/schedule-drafts/{draft_id}/blocks/{block_id}/assignments",
    response_model=list[ScheduleAssignmentResponse],
)
def list_schedule_assignments(draft_id: int, block_id: int, db: Session = Depends(get_db)):
    return service.list_schedule_assignments(db, draft_id, block_id)


@router.post(
    "/schedule-drafts/{draft_id}/blocks/{block_id}/assignments",
    response_model=ScheduleAssignmentResponse,
    status_code=201,
)
def create_schedule_assignment(
    draft_id: int,
    block_id: int,
    payload: ScheduleAssignmentCreate,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.create_schedule_assignment(
        db, draft_id, block_id, payload.model_dump(),
        _audit(db, request, user, "create", "academic_schedule_assignment"),
    )


@router.post(
    "/schedule-drafts/{draft_id}/blocks/{block_id}/assignments/replace",
    response_model=ScheduleAssignmentResponse,
    status_code=201,
)
def replace_schedule_assignment(
    draft_id: int,
    block_id: int,
    payload: ScheduleAssignmentReplace,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.replace_schedule_assignment(
        db, draft_id, block_id, payload.model_dump(),
        _audit(db, request, user, "replace", "academic_schedule_assignment"),
    )


@router.put(
    "/schedule-drafts/{draft_id}/blocks/{block_id}/assignments/{assignment_id}",
    response_model=ScheduleAssignmentResponse,
)
def correct_schedule_assignment(
    draft_id: int,
    block_id: int,
    assignment_id: int,
    payload: ScheduleAssignmentCorrection,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return service.correct_schedule_assignment(
        db, draft_id, block_id, assignment_id, payload.model_dump(),
        _audit(db, request, user, "correct", "academic_schedule_assignment"),
    )


@router.delete(
    "/schedule-drafts/{draft_id}/blocks/{block_id}/assignments/{assignment_id}",
    status_code=204,
)
def delete_schedule_assignment(
    draft_id: int,
    block_id: int,
    assignment_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service.delete_schedule_assignment(
        db, draft_id, block_id, assignment_id,
        _audit(db, request, user, "delete", "academic_schedule_assignment"),
    )
    return Response(status_code=204)


@router.get(
    "/schedule-drafts/{draft_id}/blocks/{block_id}/compatible-teachers",
    response_model=PaginatedCompatibleTeachersResponse,
)
def list_compatible_schedule_teachers(
    draft_id: int,
    block_id: int,
    effective_from: date = Query(),
    effective_to: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if effective_to is not None and effective_to < effective_from:
        raise HTTPException(422, detail="La fecha final debe ser igual o posterior a la fecha inicial.")
    return service.compatible_schedule_teachers(
        db, draft_id, block_id, effective_from, effective_to, search, page, per_page
    )


@router.get("/schedule-drafts/{draft_id}/workload", response_model=ScheduleWorkloadResponse)
def get_schedule_workload(
    draft_id: int,
    reference_date: date = Query(),
    db: Session = Depends(get_db),
):
    return service.schedule_workload_summary(db, draft_id, reference_date)


@router.post(
    "/schedule-drafts/{draft_id}/publication-preview",
    response_model=SchedulePublicationPreviewResponse,
)
def preview_schedule_publication(
    draft_id: int,
    payload: SchedulePublicationPreviewRequest,
    db: Session = Depends(get_db),
):
    return publication_service.preview_publication(db, draft_id, payload.effective_from)


@router.post(
    "/schedule-drafts/{draft_id}/publish",
    response_model=SchedulePublicationResponse,
    status_code=201,
)
def publish_schedule_draft(
    draft_id: int,
    payload: SchedulePublicationPublishRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return publication_service.publish(
        db,
        draft_id,
        payload.effective_from,
        payload.preview_digest,
        user.id,
        _audit(db, request, user, "publish", "academic_schedule_publication"),
    )


@router.get("/schedule-publications", response_model=list[SchedulePublicationResponse])
def list_schedule_publications(
    program_id: int | None = Query(default=None, gt=0),
    academic_period: str | None = Query(default=None, min_length=1, max_length=30),
    db: Session = Depends(get_db),
):
    return publication_service.list_publications(db, program_id, academic_period)


@router.get(
    "/schedule-publications/{publication_id}",
    response_model=SchedulePublicationResponse,
)
def get_schedule_publication(publication_id: int, db: Session = Depends(get_db)):
    return publication_service.get_publication(db, publication_id)


@router.post(
    "/schedule-publications/{publication_id}/clone",
    response_model=ScheduleDraftResponse,
    status_code=201,
)
def clone_schedule_publication(
    publication_id: int,
    payload: SchedulePublicationCloneRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return publication_service.clone_publication(
        db,
        publication_id,
        payload.name,
        _audit(db, request, user, "clone", "academic_schedule_draft"),
    )
