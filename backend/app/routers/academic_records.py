"""Admin API for curriculum, students and the legacy academic history import."""
from __future__ import annotations

import zlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic_records import AcademicHistoryImport, CurriculumPlan, Student
from app.models.user import User
from app.schemas.academic_records import CurriculumPlanResponse, CurriculumPlanSummary
from app.services import academic_history_import as importer
from app.services import academic_records_queries as records_queries
from app.services import academic_records_service as service
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
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return records_queries.student_detail(db, student)
