"""Immutable teacher contract ledger and legacy file compatibility routes."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.contract import ContractDocument
from app.models.teacher import Teacher
from app.models.user import User
from app.services import app_settings_service
from app.services.activity_logger import log_activity
from app.services.contract_ledger_service import ContractIssuanceError, issue_contract
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

DEPARTMENTS = [
    "Pando", "La Paz", "Cochabamba", "Santa Cruz", "Beni", "Oruro",
    "Potosí", "Chuquisaca", "Tarija",
]


class ContractRequest(BaseModel):
    department: str = "Pando"
    academic_period: Optional[str] = None


class BatchContractRequest(ContractRequest):
    teacher_cis: Optional[list[str]] = None


class ContractLineResponse(BaseModel):
    line_number: int
    activity_kind: str
    rate_class: str
    hourly_rate: float
    hours: float
    hour_basis: str
    subject_label: str
    group_label: str
    semester_label: str
    schedule_label: str
    effective_from: str
    effective_to: str
    source_kind: str
    source_id: int
    designation_id: Optional[int] = None
    publication_id: Optional[int] = None
    publication_sequence: Optional[int] = None
    published_block_id: Optional[int] = None
    published_assignment_id: Optional[int] = None
    change_kind: str
    previous_hours: Optional[float] = None
    previous_hourly_rate: Optional[float] = None


class ContractDocumentResponse(BaseModel):
    id: int
    public_id: str
    teacher_ci: str
    teacher_name: str
    academic_period: str
    document_kind: str
    amendment_sequence: int
    version: int
    effective_date: str
    issued_at: str
    source_digest: str
    artifact_sha256: str
    artifact_size: int
    filename: str
    download_url: str
    status: str
    lines: list[ContractLineResponse]


class ContractFileInfo(BaseModel):
    teacher_ci: str
    teacher_name: str
    filename: str
    file_size: int
    public_id: Optional[str] = None
    document_kind: Optional[str] = None
    version: Optional[int] = None
    download_url: Optional[str] = None


class BatchContractResponse(BaseModel):
    total_generated: int
    contracts: list[ContractFileInfo]
    zip_filename: str
    errors: list[str] = Field(default_factory=list)


def _contracts_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "contracts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_department(department: str) -> None:
    if department not in DEPARTMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Departamento inválido. Debe ser uno de: {', '.join(DEPARTMENTS)}",
        )


def _serialize(document: ContractDocument) -> ContractDocumentResponse:
    return ContractDocumentResponse(
        id=document.id,
        public_id=document.public_id,
        teacher_ci=document.teacher_ci,
        teacher_name=document.teacher_name,
        academic_period=document.academic_period,
        document_kind=document.document_kind,
        amendment_sequence=document.amendment_sequence,
        version=document.amendment_sequence + 1,
        effective_date=document.effective_date.isoformat(),
        issued_at=document.issued_at.isoformat(),
        source_digest=document.source_digest,
        artifact_sha256=document.artifact_sha256,
        artifact_size=document.artifact_size,
        filename=document.artifact_filename,
        download_url=f"/api/contracts/documents/{document.public_id}/download",
        status=document.status,
        lines=[ContractLineResponse(
            line_number=line.line_number,
            activity_kind=line.activity_kind,
            rate_class=line.rate_class,
            hourly_rate=float(line.hourly_rate),
            hours=float(line.hours),
            hour_basis=line.hour_basis,
            subject_label=line.subject_label,
            group_label=line.group_label,
            semester_label=line.semester_label,
            schedule_label=line.schedule_label,
            effective_from=line.effective_from.isoformat(),
            effective_to=line.effective_to.isoformat(),
            source_kind=line.source_kind,
            source_id=line.source_id,
            designation_id=line.designation_id,
            publication_id=line.publication_id,
            publication_sequence=line.publication_sequence,
            published_block_id=line.published_block_id,
            published_assignment_id=line.published_assignment_id,
            change_kind=line.change_kind,
            previous_hours=float(line.previous_hours) if line.previous_hours is not None else None,
            previous_hourly_rate=float(line.previous_hourly_rate) if line.previous_hourly_rate is not None else None,
        ) for line in document.lines],
    )


def _get_document(db: Session, public_id: str) -> ContractDocument:
    document = db.query(ContractDocument).options(
        selectinload(ContractDocument.lines)
    ).filter(ContractDocument.public_id == public_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    return document


def _issue(db: Session, teacher_ci: str, payload: ContractRequest) -> ContractDocument:
    _validate_department(payload.department)
    academic_period = payload.academic_period or app_settings_service.get_active_academic_period(db)
    try:
        return issue_contract(
            db,
            teacher_ci=teacher_ci,
            academic_period=academic_period,
            department=payload.department,
        )
    except ContractIssuanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/issue/{teacher_ci}", response_model=ContractDocumentResponse)
def issue_teacher_contract(
    teacher_ci: str,
    payload: ContractRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ContractDocumentResponse:
    document = _issue(db, teacher_ci, payload)
    log_activity(
        db,
        "issue_contract",
        "contracts",
        f"Contrato {document.public_id} emitido o recuperado",
        user=current_user,
        details={"public_id": document.public_id, "source_digest": document.source_digest},
        request=request,
    )
    db.commit()
    return _serialize(document)


@router.post("/generate/{teacher_ci}")
def generate_single_contract_compatibility(
    teacher_ci: str,
    payload: ContractRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Compatibility route: issue/read the ledger; never mutate Designation dates."""
    document = _issue(db, teacher_ci, payload)
    log_activity(
        db,
        "generate_contract_compatibility",
        "contracts",
        f"Contrato inmutable descargado: {document.public_id}",
        user=current_user,
        details={"public_id": document.public_id},
        request=request,
    )
    db.commit()
    return Response(
        content=document.artifact_content,
        media_type=document.artifact_media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.artifact_filename}"',
            "ETag": f'"{document.artifact_sha256}"',
            "X-Contract-Id": document.public_id,
        },
    )


@router.post("/generate-batch", response_model=BatchContractResponse)
def generate_batch_contracts(
    payload: BatchContractRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BatchContractResponse:
    _validate_department(payload.department)
    query = db.query(Teacher).filter(~Teacher.ci.startswith("TEMP-"))
    if payload.teacher_cis:
        query = query.filter(Teacher.ci.in_(payload.teacher_cis))
    teachers = query.order_by(Teacher.full_name).all()
    if not teachers:
        raise HTTPException(status_code=404, detail="No se encontraron docentes para emitir contratos")
    contracts: list[ContractFileInfo] = []
    errors: list[str] = []
    for teacher in teachers:
        try:
            document = _issue(db, teacher.ci, payload)
            contracts.append(ContractFileInfo(
                teacher_ci=teacher.ci,
                teacher_name=document.teacher_name,
                filename=document.artifact_filename,
                file_size=document.artifact_size,
                public_id=document.public_id,
                document_kind=document.document_kind,
                version=document.amendment_sequence + 1,
                download_url=f"/api/contracts/documents/{document.public_id}/download",
            ))
        except HTTPException as exc:
            errors.append(f"{teacher.full_name} ({teacher.ci}): {exc.detail}")
    if not contracts:
        raise HTTPException(status_code=400, detail="No se pudo emitir ningún contrato. " + " | ".join(errors))
    log_activity(
        db,
        "issue_batch_contracts",
        "contracts",
        f"Contratos emitidos o recuperados: {len(contracts)}",
        user=current_user,
        details={"public_ids": [item.public_id for item in contracts], "errors": errors},
        request=request,
    )
    db.commit()
    return BatchContractResponse(
        total_generated=len(contracts),
        contracts=contracts,
        zip_filename=f"Contratos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        errors=errors,
    )


@router.get("/history", response_model=list[ContractDocumentResponse])
def list_contract_history(
    teacher_ci: Optional[str] = None,
    academic_period: Optional[str] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ContractDocumentResponse]:
    query = db.query(ContractDocument).options(selectinload(ContractDocument.lines))
    if teacher_ci:
        query = query.filter(ContractDocument.teacher_ci == teacher_ci)
    if academic_period:
        query = query.filter(ContractDocument.academic_period == academic_period)
    documents = query.order_by(
        ContractDocument.teacher_name,
        ContractDocument.academic_period,
        ContractDocument.amendment_sequence,
    ).all()
    return [_serialize(document) for document in documents]


@router.get("/documents/{public_id}", response_model=ContractDocumentResponse)
def get_contract_document(
    public_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ContractDocumentResponse:
    return _serialize(_get_document(db, public_id))


@router.get("/documents/{public_id}/download")
def download_contract_document(
    public_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    document = _get_document(db, public_id)
    return Response(
        content=document.artifact_content,
        media_type=document.artifact_media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.artifact_filename}"',
            "ETag": f'"{document.artifact_sha256}"',
            "Cache-Control": "private, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/download/{filename}")
def download_legacy_contract(filename: str, _: User = Depends(require_admin)) -> FileResponse:
    """Keep historical filesystem PDFs readable without rewriting them."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    file_path = _contracts_dir() / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo de contrato no encontrado")
    return FileResponse(path=file_path, filename=filename, media_type="application/pdf")


@router.get("/list")
def list_legacy_contracts(_: User = Depends(require_admin)) -> list[dict]:
    """Preserve the historical filesystem response shape."""
    files = sorted(_contracts_dir().glob("*.pdf"), key=lambda item: item.stat().st_mtime, reverse=True)
    return [
        {"filename": item.name, "file_size": item.stat().st_size, "created_at": item.stat().st_mtime}
        for item in files
    ]


@router.post("/download-zip")
def download_contracts_zip(
    filenames: list[str],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Download ledger artifacts and historical filesystem files by stable filename."""
    ledger = {
        item.artifact_filename: item
        for item in db.query(ContractDocument).filter(ContractDocument.artifact_filename.in_(filenames)).all()
    }
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in filenames:
            if "/" in filename or "\\" in filename or ".." in filename:
                continue
            if filename in ledger:
                archive.writestr(filename, ledger[filename].artifact_content)
                continue
            legacy_path = _contracts_dir() / filename
            if legacy_path.is_file():
                archive.write(legacy_path, arcname=filename)
    zip_buffer.seek(0)
    zip_name = f"Contratos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )
