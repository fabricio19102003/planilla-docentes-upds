from __future__ import annotations

import importlib.util
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.designation import DesignationUploadResponse
from app.services.designation_loader import DesignationLoader
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _uploads_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_upload_file(upload: UploadFile) -> tuple[Path, str]:
    original_name = Path(upload.filename or "upload.bin").name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stored_name = f"{timestamp}_{original_name}"
    destination = _uploads_dir() / stored_name
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return destination, stored_name


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

        designaciones.append(
            {
                "docente": row["docente"],
                "materia": row["materia"],
                "semestre": row["semestre"],
                "grupo": module.normalize_group(row["grupo"]),
                "carga_horaria_semestral": row["carga_semestral"],
                "carga_horaria_mensual": row["carga_mensual"],
                "carga_horaria_semanal": row["carga_semanal_ex"],
                "horario": entries,
                "total_horas_academicas_semanal_calculado": sum(
                    entry["horas_academicas"] for entry in entries
                ),
                "horario_raw": horario,
            }
        )

    output = {
        "metadata": {
            "source_file": excel_path.name,
            "generated_at": datetime.now().isoformat(),
            "total_designaciones": len(rows),
            "parsed_successfully": len(designaciones),
            "skipped_no_schedule": skipped_no_schedule,
            "skipped_no_time": skipped_no_time,
            "parse_errors": parse_errors,
        },
        "designaciones": designaciones,
        "errores": [],
        "advertencias": warnings,
    }

    json_path = excel_path.with_name(f"{excel_path.stem}_normalizado.json")
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)

    return json_path, warnings


@router.post("/designations", response_model=DesignationUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_designations(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DesignationUploadResponse:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in {".json", ".xlsx"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo debe ser .json o .xlsx")

    try:
        saved_path, stored_name = _save_upload_file(file)
        logger.info("Processing designation upload %s", stored_name)

        loader = DesignationLoader()
        warnings: list[str] = []

        if extension == ".json":
            result = loader.load_from_json(db=db, json_path=str(saved_path))
        else:
            normalized_json, parser_warnings = _normalize_designations_excel(saved_path)
            warnings.extend(parser_warnings)
            result = loader.load_from_json(db=db, json_path=str(normalized_json))

        db.commit()

        return DesignationUploadResponse(
            teachers_created=result.teachers_created,
            teachers_reused=result.teachers_reused,
            designations_loaded=result.designations_loaded,
            skipped=result.total_skipped,
            warnings=warnings + result.warnings,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Designation upload failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo procesar el archivo de designaciones",
        ) from exc
    finally:
        file.file.close()
