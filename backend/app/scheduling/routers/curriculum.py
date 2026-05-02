"""Router for scheduling module: careers, semesters, subjects, curriculum import."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.auth import require_admin

from app.scheduling.schemas.career import (
    CareerCreate,
    CareerUpdate,
    CareerResponse,
    CareerWithSemesters,
    CurriculumImportRequest,
    CurriculumImportResponse,
)
from app.scheduling.schemas.semester import (
    SemesterCreate,
    SemesterUpdate,
    SemesterResponse,
    SemesterWithSubjects,
)
from app.scheduling.schemas.subject import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
)
from app.scheduling.services.career_service import CareerService
from app.scheduling.services.semester_service import SemesterService
from app.scheduling.services.subject_service import SubjectService

router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])

career_svc = CareerService()
semester_svc = SemesterService()
subject_svc = SubjectService()


# ─── Career CRUD ──────────────────────────────────────────────────────

@router.post("/careers", response_model=CareerResponse, status_code=201)
def create_career(
    data: CareerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    career = career_svc.create(db, code=data.code, name=data.name, description=data.description)
    db.commit()
    return CareerResponse(
        id=career.id,
        code=career.code,
        name=career.name,
        description=career.description,
        is_active=career.is_active,
        semester_count=0,
        subject_count=0,
    )


@router.get("/careers", response_model=list[CareerResponse])
def list_careers(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return career_svc.list_all(db, active_only=active_only)


@router.get("/careers/{career_id}", response_model=CareerWithSemesters)
def get_career(
    career_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return career_svc.get(db, career_id)


@router.put("/careers/{career_id}", response_model=CareerResponse)
def update_career(
    career_id: int,
    data: CareerUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    career = career_svc.update(db, career_id, **fields)
    db.commit()
    # Re-fetch to get counts
    return career_svc.get(db, career_id)


@router.delete("/careers/{career_id}", response_model=CareerResponse)
def deactivate_career(
    career_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    career = career_svc.deactivate(db, career_id)
    db.commit()
    return career_svc.get(db, career_id)


@router.post(
    "/careers/{career_id}/import-curriculum",
    response_model=CurriculumImportResponse,
)
def import_curriculum_to_career(
    career_id: int,
    data: CurriculumImportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Import malla curricular JSON into an existing career."""
    # Override career lookup — use the one specified by ID
    from app.scheduling.models.career import Career

    career = db.query(Career).filter(Career.id == career_id).first()
    if not career:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Career not found")
    # Temporarily override the carrera name to match the existing career
    data.carrera = career.name
    result = career_svc.import_curriculum(db, data)
    db.commit()
    return result


@router.post(
    "/careers/import-curriculum",
    response_model=CurriculumImportResponse,
)
def import_curriculum_auto(
    data: CurriculumImportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Import malla curricular JSON — auto-creates career if needed."""
    result = career_svc.import_curriculum(db, data)
    db.commit()
    return result


# ─── Semester CRUD ────────────────────────────────────────────────────

@router.post("/semesters", response_model=SemesterResponse, status_code=201)
def create_semester(
    data: SemesterCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    semester = semester_svc.create(
        db, career_id=data.career_id, number=data.number, name=data.name
    )
    db.commit()
    return SemesterResponse(
        id=semester.id,
        career_id=semester.career_id,
        number=semester.number,
        name=semester.name,
        is_active=semester.is_active,
        subject_count=0,
    )


@router.get("/semesters", response_model=list[SemesterResponse])
def list_semesters(
    career_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return semester_svc.list_by_career(db, career_id)


@router.get("/semesters/{semester_id}", response_model=SemesterWithSubjects)
def get_semester(
    semester_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return semester_svc.get(db, semester_id)


@router.put("/semesters/{semester_id}", response_model=SemesterResponse)
def update_semester(
    semester_id: int,
    data: SemesterUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    semester = semester_svc.update(db, semester_id, **fields)
    db.commit()
    return semester_svc.get(db, semester_id)


@router.delete("/semesters/{semester_id}")
def delete_semester(
    semester_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = semester_svc.delete(db, semester_id)
    db.commit()
    return result


# ─── Subject CRUD ─────────────────────────────────────────────────────

@router.post("/subjects", response_model=SubjectResponse, status_code=201)
def create_subject(
    data: SubjectCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    subject = subject_svc.create(
        db,
        semester_id=data.semester_id,
        code=data.code,
        name=data.name,
        theoretical_hours=data.theoretical_hours,
        practical_hours=data.practical_hours,
        credits=data.credits,
        is_elective=data.is_elective,
    )
    db.commit()
    return subject


@router.get("/subjects", response_model=list[SubjectResponse])
def list_subjects(
    semester_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return subject_svc.list_by_semester(db, semester_id)


@router.get("/subjects/search", response_model=list[SubjectResponse])
def search_subjects(
    q: str = Query(..., min_length=1),
    career_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return subject_svc.search(db, q, career_id=career_id)


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return subject_svc.get(db, subject_id)


@router.put("/subjects/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: int,
    data: SubjectUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    subject = subject_svc.update(db, subject_id, **fields)
    db.commit()
    return subject


@router.delete("/subjects/{subject_id}")
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = subject_svc.delete(db, subject_id)
    db.commit()
    return result
