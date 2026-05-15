"""
Router: Contracts

Endpoints for generating and downloading teacher contract PDFs.
"""
from __future__ import annotations

import io
import logging
import zipfile
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.services import app_settings_service
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
    errors: list[str] = Field(default_factory=list)


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
    designations = (
        db.query(Designation)
        .filter(
            Designation.teacher_ci == teacher_ci,
            Designation.academic_period == app_settings_service.get_active_academic_period(db),
        )
        .all()
    )
    return teacher, designations


def _number_to_spanish(value: int) -> str:
    """Return a compact Spanish literal for integers from 0 to 10000."""
    if value < 0 or value > 10000:
        raise ValueError("Solo se soportan montos entre 0 y 10000")

    units = {
        0: "cero", 1: "un", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
        6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
        11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince",
        16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve",
        20: "veinte", 21: "veintiún", 22: "veintidós", 23: "veintitrés",
        24: "veinticuatro", 25: "veinticinco", 26: "veintiséis", 27: "veintisiete",
        28: "veintiocho", 29: "veintinueve",
    }
    tens = {
        30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta",
        70: "setenta", 80: "ochenta", 90: "noventa",
    }
    hundreds = {
        100: "cien", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos",
        500: "quinientos", 600: "seiscientos", 700: "setecientos", 800: "ochocientos",
        900: "novecientos",
    }

    if value < 30:
        return units[value]
    if value < 100:
        ten = (value // 10) * 10
        rest = value % 10
        return tens[ten] if rest == 0 else f"{tens[ten]} y {units[rest]}"
    if value < 1000:
        hundred = (value // 100) * 100
        rest = value % 100
        if rest == 0:
            return hundreds[hundred]
        prefix = "ciento" if hundred == 100 else hundreds[hundred]
        return f"{prefix} {_number_to_spanish(rest)}"
    if value == 1000:
        return "mil"
    if value < 10000:
        thousands = value // 1000
        rest = value % 1000
        prefix = "mil" if thousands == 1 else f"{_number_to_spanish(thousands)} mil"
        return prefix if rest == 0 else f"{prefix} {_number_to_spanish(rest)}"
    return "diez mil"


def _format_contract_rate(rate: float) -> tuple[str, str]:
    amount = Decimal(str(rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount < 0 or amount > Decimal("10000.00"):
        raise ValueError("La tarifa por hora debe estar entre 0 y 10000 Bs")

    integer_part = int(amount)
    cents = int((amount - Decimal(integer_part)) * 100)
    numeric = f"{integer_part},{cents:02d}"
    currency = "boliviano" if integer_part == 1 else "bolivianos"
    literal = f"{_number_to_spanish(integer_part).capitalize()} {currency} {cents:02d}/100"
    return numeric, literal


def _resolve_contract_rate(designations: list[Designation], db: Session) -> tuple[str, str]:
    """Pick the contract rate for one teacher's active-period designations."""
    all_practice = bool(designations) and all(
        designation.designation_type == "practice" for designation in designations
    )
    rate = (
        app_settings_service.get_practice_hourly_rate(db)
        if all_practice
        else app_settings_service.get_hourly_rate(db)
    )
    return _format_contract_rate(rate)


MONTH_NAMES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _format_spanish_date(value: date) -> str:
    return f"{value.day:02d} de {MONTH_NAMES[value.month]} de {value.year}"


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _format_duration_text(start: date, end: date) -> str:
    if end < start:
        raise ValueError("La fecha de fin del contrato no puede ser anterior a la fecha de inicio")

    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1

    anchor = _add_months(start, months)
    days = (end - anchor).days

    parts: list[str] = []
    if months:
        parts.append(f"{months} mes{'es' if months != 1 else ''}")
    if days:
        parts.append(f"{days} día{'s' if days != 1 else ''}")
    return " y ".join(parts) if parts else "0 días"


def _resolve_contract_dates(designations: list[Designation]) -> tuple[str, str, str]:
    if not designations:
        raise ValueError("El docente no tiene designaciones en el período académico activo")

    missing = [
        f"{designation.subject} ({designation.group_code})"
        for designation in designations
        if designation.contract_start_date is None or designation.contract_end_date is None
    ]
    if missing:
        raise ValueError(
            "Faltan fechas de contrato en las siguientes designaciones: "
            + "; ".join(missing)
        )

    start = min(designation.contract_start_date for designation in designations if designation.contract_start_date)
    end = max(designation.contract_end_date for designation in designations if designation.contract_end_date)
    return _format_duration_text(start, end), _format_spanish_date(start), _format_spanish_date(end)


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
        hourly_rate, hourly_rate_literal = _resolve_contract_rate(designations, db)
        duration_text, start_date, end_date = _resolve_contract_dates(designations)
        pdf_path = generate_contract_pdf(
            teacher=teacher,
            designations=designations,
            department=payload.department,
            duration_text=duration_text,
            start_date=start_date,
            end_date=end_date,
            hourly_rate=hourly_rate,
            hourly_rate_literal=hourly_rate_literal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
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
        # All teachers with at least one designation in the active period, excluding TEMP
        teachers = (
            db.query(Teacher)
            .join(Designation, Teacher.ci == Designation.teacher_ci)
            .filter(
                ~Teacher.ci.startswith("TEMP-"),
                Designation.academic_period == app_settings_service.get_active_academic_period(db),
            )
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
        designations = (
            db.query(Designation)
            .filter(
                Designation.teacher_ci == teacher.ci,
                Designation.academic_period == app_settings_service.get_active_academic_period(db),
            )
            .all()
        )
        if not designations:
            continue
        try:
            hourly_rate, hourly_rate_literal = _resolve_contract_rate(designations, db)
            duration_text, start_date, end_date = _resolve_contract_dates(designations)
            pdf_path_str = generate_contract_pdf(
                teacher=teacher,
                designations=designations,
                department=payload.department,
                duration_text=duration_text,
                start_date=start_date,
                end_date=end_date,
                hourly_rate=hourly_rate,
                hourly_rate_literal=hourly_rate_literal,
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
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo generar ningún contrato PDF. " + " | ".join(errors),
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
        errors=errors,
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
