from __future__ import annotations

import importlib.util
import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.designation import (
    DesignationImportApplyResponse,
    DesignationImportPreviewResponse,
)
from app.services.designation_import_service import (
    DesignationImportError,
    DesignationImportPlan,
    DesignationImportService,
)
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])
MAX_DESIGNATION_UPLOAD_BYTES = 10 * 1024 * 1024


def _load_normalizer_module():
    script_path = Path(__file__).resolve().parents[3] / "normalizar_horarios.py"
    spec = importlib.util.spec_from_file_location("normalizar_horarios", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("No se pudo cargar normalizar_horarios.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_designations_excel(excel_path: Path) -> tuple[Path, list[str]]:
    module = _load_normalizer_module()
    rows = module.leer_excel(str(excel_path))

    designaciones: list[dict] = []
    warnings: list[str] = []
    skipped_no_schedule = 0
    skipped_no_time = 0
    parse_errors = 0

    for row in rows:
        horario = row["horario_raw"]
        docente = row["docente"] or ""
        fila = row["fila"]

        if not horario or horario in ("None", ""):
            skipped_no_schedule += 1
            continue

        entries, row_warnings = module.parse_horario(horario, fila, docente)
        warnings.extend(item["mensaje"] for item in row_warnings)

        if not entries:
            if row_warnings:
                skipped_no_time += 1
            else:
                parse_errors += 1
                warnings.append(f"Fila {fila}: no se pudo interpretar el horario de '{docente}'")
            continue

        # Transform entries from old internal format to new horario_detalle format
        horario_detalle = [
            {
                "dia": entry["dia"].capitalize(),  # "lunes" → "Lunes"
                "hora_inicio": entry["hora_inicio"],
                "hora_fin": entry["hora_fin"],
                "horas_academicas": entry.get("horas_academicas"),
            }
            for entry in entries
        ]

        designaciones.append(
            {
                "docente": row["docente"],
                "materias": row["materia"],
                "semestre": row["semestre"],
                "grupo": module.normalize_group(row["grupo"]),
                "carga_horaria": row["carga_semestral"],
                "mes": row["carga_mensual"],
                "semana": row["carga_semanal_ex"],
                "horario": horario,
                "horario_detalle": horario_detalle,
            }
        )

    output = designaciones  # direct array — new format

    json_path = excel_path.with_name(f"{excel_path.stem}_normalizado.json")
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)

    return json_path, warnings


async def _designation_json_bytes(file: UploadFile) -> tuple[bytes, list[str], bytes]:
    """Read a bounded upload and normalize Excel inside an auto-cleaned directory."""
    filename = Path(file.filename or "upload.bin").name
    extension = Path(filename).suffix.lower()
    if extension not in {".json", ".xlsx"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo debe ser .json o .xlsx (extensión recibida: '{extension}').",
        )

    content = await file.read(MAX_DESIGNATION_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(content) > MAX_DESIGNATION_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 10 MB.")
    if extension == ".json":
        return content, [], content

    with tempfile.TemporaryDirectory(prefix="sipad-designations-") as temp_dir:
        excel_path = Path(temp_dir) / filename
        excel_path.write_bytes(content)
        normalized_path, warnings = _normalize_designations_excel(excel_path)
        return normalized_path.read_bytes(), warnings, content


def _preview_response(plan: DesignationImportPlan) -> DesignationImportPreviewResponse:
    return DesignationImportPreviewResponse(
        digest=plan.digest,
        parsed_format=plan.parsed_format,
        academic_period=plan.academic_period,
        total_rows=plan.total_rows,
        can_apply=plan.can_apply,
        teachers=plan.teachers.__dict__,
        designations=plan.designations.__dict__,
        users=plan.users.__dict__,
        warnings=plan.warnings,
        errors=plan.errors,
    )


@router.post("/designations/preview", response_model=DesignationImportPreviewResponse)
async def preview_designations(
    file: UploadFile = File(...),
    academic_period: str = Query(..., description="Período académico explícito, ej: II/2026"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DesignationImportPreviewResponse:
    try:
        json_bytes, parser_warnings, upload_bytes = await _designation_json_bytes(file)
        plan = DesignationImportService().preview(
            db,
            json_bytes,
            academic_period,
            digest_bytes=upload_bytes,
        )
        plan.warnings.extend(parser_warnings)
        return _preview_response(plan)
    finally:
        await file.close()


@router.post(
    "/designations",
    response_model=DesignationImportApplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_designations(
    request: Request,
    file: UploadFile = File(...),
    academic_period: str = Query(..., description="Período académico explícito, ej: II/2026"),
    confirmation_digest: str = Query(..., min_length=64, max_length=64),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DesignationImportApplyResponse:
    try:
        json_bytes, parser_warnings, upload_bytes = await _designation_json_bytes(file)
        plan = DesignationImportService().apply(
            db,
            json_bytes,
            academic_period,
            confirmation_digest,
            actor_id=current_user.id,
            digest_bytes=upload_bytes,
        )
        plan.warnings.extend(parser_warnings)

        log_activity(
            db,
            "upload_designations",
            "upload",
            f"Importación de designaciones confirmada: {plan.total_rows} filas para {academic_period}",
            user=current_user,
            details={
                "digest": plan.digest,
                "format": plan.parsed_format,
                "academic_period": academic_period,
                "total_rows": plan.total_rows,
                "teachers_created": plan.teachers.creates,
                "designations_created": plan.designations.creates,
                "designations_updated": plan.designations.updates,
                "users_created": plan.users.creates,
            },
            request=request,
        )
        db.commit()
        return DesignationImportApplyResponse(
            **_preview_response(plan).model_dump(),
            applied=True,
        )
    except DesignationImportError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="\n".join(exc.errors)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Designation import failed; transaction rolled back")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La importación falló y no se aplicó ningún cambio.",
        ) from exc
    finally:
        await file.close()
