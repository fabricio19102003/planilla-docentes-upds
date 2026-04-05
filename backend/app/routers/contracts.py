"""
Router: Contracts

Endpoints for generating and downloading teacher contract PDFs.
"""
from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

DEPARTMENTS = [
    "Pando", "La Paz", "Cochabamba", "Santa Cruz",
    "Beni", "Oruro", "Potosí", "Chuquisaca", "Tarija",
]


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------


class ContractRequest(BaseModel):
    department: str = "Pando"
    duration_text: str = "4 meses y 13 días"
    start_date: str = ""
    end_date: str = ""
    hourly_rate: str = "70,00"
    hourly_rate_literal: str = "Setenta bolivianos 00/100"


class BatchContractRequest(ContractRequest):
    teacher_cis: Optional[list[str]] = None  # None = all teachers


class ContractFileInfo(BaseModel):
    teacher_ci: str
    teacher_name: str
    filename: str
    file_size: int


class BatchContractResponse(BaseModel):
    total_generated: int
    contracts: list[ContractFileInfo]
    zip_filename: str


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


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


def _get_teacher_designations(teacher_ci: str, db: Session) -> tuple[Teacher, list[Designation]]:
    teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Docente con CI {teacher_ci} no encontrado",
        )
    designations = db.query(Designation).filter(Designation.teacher_ci == teacher_ci).all()
    return teacher, designations


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/generate/{teacher_ci}", response_class=FileResponse)
def generate_single_contract(
    teacher_ci: str,
    payload: ContractRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Generate and return a contract PDF for a single teacher."""
    from app.services.contract_pdf import generate_contract_pdf

    _validate_department(payload.department)
    teacher, designations = _get_teacher_designations(teacher_ci, db)

    # TEMP teachers don't have a real CI — contracts cannot be issued for them
    if teacher.ci.startswith("TEMP-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede generar contrato para un docente sin CI real (TEMP). Vinculá el docente a su CI real primero.",
        )

    try:
        pdf_path = generate_contract_pdf(
            teacher=teacher,
            designations=designations,
            department=payload.department,
            duration_text=payload.duration_text,
            start_date=payload.start_date,
            end_date=payload.end_date,
            hourly_rate=payload.hourly_rate,
            hourly_rate_literal=payload.hourly_rate_literal,
        )
    except Exception as exc:
        logger.exception("Failed to generate contract for teacher %s: %s", teacher_ci, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar el contrato PDF",
        ) from exc

    log_activity(
        db,
        "generate_contract",
        "contracts",
        f"Contrato generado: {teacher.full_name}",
        user=current_user,
        details={"teacher_ci": teacher_ci, "teacher_name": teacher.full_name, "department": payload.department},
        request=request,
    )
    db.commit()

    safe_name = teacher.full_name.replace(" ", "_")
    return FileResponse(
        path=pdf_path,
        filename=f"Contrato_{safe_name}.pdf",
        media_type="application/pdf",
    )


@router.post("/generate-batch", response_model=BatchContractResponse)
def generate_batch_contracts(
    payload: BatchContractRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BatchContractResponse:
    """
    Generate contracts for multiple teachers.

    If teacher_cis is None or empty, generates for ALL teachers with designations.
    PDFs are saved to data/contracts/. Returns metadata for client to download individually.
    """
    from app.services.contract_pdf import generate_contract_pdf

    _validate_department(payload.department)

    # Determine which teachers to process — always exclude TEMP teachers (no real CI)
    if payload.teacher_cis:
        teachers = (
            db.query(Teacher)
            .filter(
                Teacher.ci.in_(payload.teacher_cis),
                ~Teacher.ci.startswith("TEMP-"),
            )
            .all()
        )
    else:
        # All teachers with at least one designation, excluding TEMP placeholders
        teachers = (
            db.query(Teacher)
            .join(Designation, Teacher.ci == Designation.teacher_ci)
            .filter(~Teacher.ci.startswith("TEMP-"))
            .distinct()
            .all()
        )

    if not teachers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontraron docentes con designaciones para generar contratos",
        )

    contracts: list[ContractFileInfo] = []
    errors: list[str] = []

    for teacher in teachers:
        designations = db.query(Designation).filter(Designation.teacher_ci == teacher.ci).all()
        if not designations:
            continue
        try:
            pdf_path_str = generate_contract_pdf(
                teacher=teacher,
                designations=designations,
                department=payload.department,
                duration_text=payload.duration_text,
                start_date=payload.start_date,
                end_date=payload.end_date,
                hourly_rate=payload.hourly_rate,
                hourly_rate_literal=payload.hourly_rate_literal,
            )
            pdf_path = Path(pdf_path_str)
            contracts.append(ContractFileInfo(
                teacher_ci=teacher.ci,
                teacher_name=teacher.full_name,
                filename=pdf_path.name,
                file_size=pdf_path.stat().st_size,
            ))
        except Exception as exc:
            logger.exception("Failed to generate contract for teacher %s: %s", teacher.ci, exc)
            errors.append(f"{teacher.full_name} ({teacher.ci}): {exc}")

    if not contracts:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar ningún contrato PDF",
        )

    from datetime import datetime
    zip_filename = f"Contratos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    log_activity(
        db,
        "generate_batch_contracts",
        "contracts",
        f"Contratos batch generados: {len(contracts)} docentes",
        user=current_user,
        details={
            "total_generated": len(contracts),
            "department": payload.department,
            "errors": errors,
        },
        request=request,
    )
    db.commit()

    return BatchContractResponse(
        total_generated=len(contracts),
        contracts=contracts,
        zip_filename=zip_filename,
    )


@router.get("/download/{filename}")
def download_contract(
    filename: str,
    _: User = Depends(require_admin),
) -> FileResponse:
    """Download a previously generated contract PDF by filename."""
    # Security: prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de archivo inválido",
        )

    contracts_dir = _contracts_dir()
    file_path = contracts_dir / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo de contrato no encontrado",
        )

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/pdf",
    )


@router.post("/download-zip")
def download_contracts_zip(
    filenames: list[str],
    _: User = Depends(require_admin),
) -> StreamingResponse:
    """Download multiple contract PDFs as a single ZIP archive."""
    contracts_dir = _contracts_dir()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in filenames:
            # Security: prevent path traversal
            if "/" in filename or "\\" in filename or ".." in filename:
                continue
            file_path = contracts_dir / filename
            if file_path.exists() and file_path.is_file():
                zf.write(file_path, arcname=filename)

    zip_buffer.seek(0)

    from datetime import datetime
    zip_name = f"Contratos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


@router.get("/list")
def list_contracts(
    _: User = Depends(require_admin),
) -> list[dict]:
    """List all generated contract PDF files in data/contracts/."""
    contracts_dir = _contracts_dir()
    files = sorted(contracts_dir.glob("*.pdf"), key=lambda f: f.stat().st_mtime, reverse=True)

    return [
        {
            "filename": f.name,
            "file_size": f.stat().st_size,
            "created_at": f.stat().st_mtime,
        }
        for f in files
    ]
