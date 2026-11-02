"""Admin API for curriculum, students and the legacy academic history import."""
from __future__ import annotations

import zlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic_records import AcademicHistoryImport, CurriculumPlan, Student
from app.models.user import User
from app.schemas.academic_records import CurriculumPlanResponse, CurriculumPlanSummary
from app.services import academic_history_import as importer
from app.services import academic_records_queries as records_queries
from app.services import academic_records_service as service
from app.services import curriculum_editing
from app.services import student_accounts
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/admin/academic-records", tags=["academic-records"])

CATEGORY = "academic_records"


@router.post("/curricula/default/load", response_model=CurriculumPlanResponse)
def load_default_curriculum(
    request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    plan = service.load_default_curriculum(db)
    log_activity(
        db, action="load_curriculum", category=CATEGORY,
        description=f"Cargó la malla curricular {plan.name}", user=admin,
        details={"plan_id": plan.id}, request=request,
    )
    db.commit()
    return service.serialize_plan(plan)


@router.get("/curricula", response_model=list[CurriculumPlanSummary])
def list_curricula(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return service.list_plans(db)


@router.get("/curricula/{plan_id}", response_model=CurriculumPlanResponse)
def get_curriculum(plan_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    plan = db.get(CurriculumPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan de estudio no encontrado")
    return service.serialize_plan(plan)


# ── Curriculum editing ───────────────────────────────────────────────────────

class CurriculumSlotIn(BaseModel):
    semester: int = Field(..., ge=1, le=20)
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, pattern=r"^[A-Z]{3} [0-9]{4}$")
    theory_hours: int = Field(..., ge=0, le=40)
    practice_hours: int = Field(..., ge=0, le=40)
    credits: int = Field(..., ge=0, le=40)
    is_elective: bool = False


class OfferingGeneration(BaseModel):
    academic_period: str = Field(..., pattern=r"^(I|II|INV|VER)/[0-9]{4}$")


class SemesterOrder(BaseModel):
    slot_ids: list[int] = Field(..., max_length=50)


def _curriculum_changed(db: Session, request: Request, admin: User, plan, change: str,
                        before: dict | None = None, after: dict | None = None):
    log_activity(
        db, action="update_curriculum", category=CATEGORY, description=f"Modificó la malla {plan.name} ({change})",
        user=admin, details={"plan_id": plan.id, "change": change, "before": before, "after": after}, request=request,
    )
    db.commit()
    db.refresh(plan)
    return service.serialize_plan(plan)


@router.post("/curricula/{plan_id}/slots", response_model=CurriculumPlanResponse, status_code=201)
def add_curriculum_slot(plan_id: int, payload: CurriculumSlotIn, request: Request,
                        db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    plan = curriculum_editing.get_plan(db, plan_id)
    slot = curriculum_editing.add_slot(db, plan, payload.model_dump())
    return _curriculum_changed(db, request, admin, plan, "add_subject", after=curriculum_editing.slot_values(slot))


@router.put("/curricula/{plan_id}/slots/{slot_id}", response_model=CurriculumPlanResponse)
def update_curriculum_slot(plan_id: int, slot_id: int, payload: CurriculumSlotIn, request: Request,
                           db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    plan = curriculum_editing.get_plan(db, plan_id)
    slot = curriculum_editing.get_slot(plan, slot_id)
    before = curriculum_editing.slot_values(slot)
    curriculum_editing.update_slot(db, plan, slot, payload.model_dump())
    return _curriculum_changed(db, request, admin, plan, "update_subject", before, curriculum_editing.slot_values(slot))


@router.delete("/curricula/{plan_id}/slots/{slot_id}", response_model=CurriculumPlanResponse)
def remove_curriculum_slot(plan_id: int, slot_id: int, request: Request,
                           db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    plan = curriculum_editing.get_plan(db, plan_id)
    slot = curriculum_editing.get_slot(plan, slot_id)
    before = curriculum_editing.slot_values(slot)
    curriculum_editing.remove_slot(db, plan, slot)
    return _curriculum_changed(db, request, admin, plan, "remove_subject", before=before)


@router.put("/curricula/{plan_id}/semesters/{semester}/order", response_model=CurriculumPlanResponse)
def reorder_curriculum_semester(plan_id: int, semester: int, payload: SemesterOrder, request: Request,
                                db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    plan = curriculum_editing.get_plan(db, plan_id)
    curriculum_editing.reorder(db, plan, semester, payload.slot_ids)
    return _curriculum_changed(db, request, admin, plan, "reorder_semester", after={"semester": semester,
                                                                                    "slot_ids": payload.slot_ids})


@router.post("/curricula/{plan_id}/offerings")
def generate_curriculum_offerings(plan_id: int, payload: OfferingGeneration, request: Request,
                                  db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    plan = curriculum_editing.get_plan(db, plan_id)
    result = curriculum_editing.generate_offerings(db, plan, payload.academic_period)
    log_activity(
        db, action="generate_offerings_from_curriculum", category=CATEGORY,
        description=f"Generó las ofertas de {payload.academic_period} desde la malla {plan.name}", user=admin,
        details={"plan_id": plan.id, "academic_period": payload.academic_period, "created": len(result["created"]),
                 "existing": len(result["existing"]), "skipped": len(result["skipped"])}, request=request,
    )
    db.commit()
    return result


@router.post("/curricula/{plan_id}/semesters", response_model=CurriculumPlanResponse)
def add_curriculum_semester(plan_id: int, request: Request, db: Session = Depends(get_db),
                            admin: User = Depends(require_admin)):
    plan = curriculum_editing.get_plan(db, plan_id)
    curriculum_editing.add_semester(db, plan)
    return _curriculum_changed(db, request, admin, plan, "add_semester", after={"total_semesters": plan.total_semesters})


@router.delete("/curricula/{plan_id}/semesters/{semester}", response_model=CurriculumPlanResponse)
def remove_curriculum_semester(plan_id: int, semester: int, request: Request, db: Session = Depends(get_db),
                               admin: User = Depends(require_admin)):
    plan = curriculum_editing.get_plan(db, plan_id)
    curriculum_editing.remove_semester(db, plan, semester)
    return _curriculum_changed(db, request, admin, plan, "remove_semester", after={"total_semesters": plan.total_semesters})


# ── Legacy academic history import ───────────────────────────────────────────

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
# The 2026 export is ~27 MB as CSV; the frontend gzips it to fit the proxy limit.
MAX_CSV_BYTES = 120 * 1024 * 1024
GZIP_MAGIC = b"\x1f\x8b"


async def _read_csv_upload(file: UploadFile) -> tuple[bytes, str]:
    """Return the CSV bytes and file name, transparently inflating a gzip upload."""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(400, detail="El archivo está vacío")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail="El archivo supera el límite de 20 MB")
    name = (file.filename or "importacion.csv").strip()
    if content.startswith(GZIP_MAGIC):
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            content = inflater.decompress(content, MAX_CSV_BYTES + 1)
        except zlib.error as exc:
            raise HTTPException(400, detail="El archivo comprimido está dañado") from exc
        if len(content) > MAX_CSV_BYTES or inflater.unconsumed_tail:
            raise HTTPException(413, detail="El CSV descomprimido supera el límite permitido")
        # A cut-off stream or a second member would silently import only part of the file.
        if not inflater.eof or inflater.unused_data:
            raise HTTPException(400, detail="El archivo comprimido está dañado")
        if name.lower().endswith(".gz"):
            name = name[:-3]
    return content, name


@router.post("/imports/preview")
async def preview_import(
    file: UploadFile = File(...), db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    content, name = await _read_csv_upload(file)
    try:
        return importer.preview(db, content, name)
    except importer.ImportFormatError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.post("/imports/apply")
async def apply_import(
    request: Request,
    file: UploadFile = File(...),
    expected_sha256: str = Form(..., pattern=r"^[0-9a-f]{64}$"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    content, name = await _read_csv_upload(file)
    try:
        result = importer.apply(db, content, name, expected_sha256, admin)
    except importer.ImportFormatError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except importer.ImportConflict as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    log_activity(
        db, action="apply_academic_history_import", category=CATEGORY,
        description=f"Importó historial académico desde {name}", user=admin, request=request,
        details={"import_id": result["import_id"], "file_sha256": result["file_sha256"], "counts": result["counts"]},
    )
    db.commit()
    return result


@router.get("/imports")
def list_imports(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = (
        db.query(AcademicHistoryImport, User.full_name)
        .outerjoin(User, User.id == AcademicHistoryImport.actor_id)
        .order_by(AcademicHistoryImport.id.desc())
        .limit(100)
    )
    return [
        {
            "id": receipt.id, "file_name": receipt.file_name, "file_sha256": receipt.file_sha256,
            "counts": receipt.counts, "terms": receipt.terms, "issue_count": len(receipt.issues),
            "actor_name": actor_name, "created_at": receipt.created_at,
        }
        for receipt, actor_name in rows
    ]


# ── Terms and students ───────────────────────────────────────────────────────

@router.get("/terms")
def list_terms(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return records_queries.list_terms(db)


@router.get("/students")
def list_students(
    search: str | None = Query(None, max_length=120),
    status: str | None = Query(None, max_length=30),
    foreign: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return records_queries.list_students(
        db, search=search, status=status, foreign=foreign, page=page, page_size=page_size
    )


@router.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    student = _student_or_404(db, student_id)
    detail = records_queries.student_detail(db, student)
    return {**detail, "account": student_accounts.account_summary(student_accounts.get_account(db, student))}


def _student_or_404(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return student


# ── Student portal accounts ──────────────────────────────────────────────────

class BulkTemporaryPasswords(BaseModel):
    student_ids: list[int] = Field(..., min_length=1, max_length=student_accounts.MAX_BULK)


def _log_issue(db: Session, request: Request, admin: User, credentials: list[dict]) -> None:
    # The passwords themselves are shown once to staff and never stored in the log.
    log_activity(
        db, action="issue_student_temporary_password", category=CATEGORY,
        description=f"Generó clave temporal del portal para {len(credentials)} estudiante(s)", user=admin,
        details={"student_ids": [c["student_id"] for c in credentials]}, request=request,
    )


@router.post("/students/{student_id}/account/temporary-password")
def issue_temporary_password(
    student_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    credential = student_accounts.issue_temporary_password(db, _student_or_404(db, student_id), admin)
    _log_issue(db, request, admin, [credential])
    db.commit()
    return credential


@router.post("/student-accounts/temporary-passwords")
def issue_temporary_passwords(
    payload: BulkTemporaryPasswords, request: Request,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    ids = list(dict.fromkeys(payload.student_ids))
    found = {s.id: s for s in db.query(Student).filter(Student.id.in_(ids))}
    missing = [str(i) for i in ids if i not in found]
    if missing:
        raise HTTPException(status_code=404, detail="Estudiantes no encontrados: " + ", ".join(missing))
    credentials = [student_accounts.issue_temporary_password(db, found[i], admin) for i in ids]
    _log_issue(db, request, admin, credentials)
    db.commit()
    return {"credentials": credentials}


def _set_account_active(db: Session, request: Request, admin: User, student_id: int, active: bool):
    account = student_accounts.set_active(db, _student_or_404(db, student_id), active)
    log_activity(
        db, action="enable_student_account" if active else "disable_student_account", category=CATEGORY,
        description=("Habilitó" if active else "Deshabilitó") + " la cuenta del portal de un estudiante",
        user=admin, details={"student_id": student_id}, request=request,
    )
    db.commit()
    return {"account": student_accounts.account_summary(account)}


@router.post("/students/{student_id}/account/disable")
def disable_account(student_id: int, request: Request, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    return _set_account_active(db, request, admin, student_id, False)


@router.post("/students/{student_id}/account/enable")
def enable_account(student_id: int, request: Request, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    return _set_account_active(db, request, admin, student_id, True)
