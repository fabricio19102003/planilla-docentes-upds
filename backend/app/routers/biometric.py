from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.biometric import BiometricUpload
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.biometric import BiometricUploadResponse, BiometricUploadResult
from app.services.biometric_parser import BiometricParser
from app.services.designation_loader import DesignationLoader, names_match
from app.services.activity_logger import log_activity
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


@router.post("/biometric", response_model=BiometricUploadResult, status_code=status.HTTP_201_CREATED)
def upload_biometric(
    request: Request,
    file: UploadFile = File(...),
    month: int = Form(..., ge=1, le=12),
    year: int = Form(..., ge=2000, le=2100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BiometricUploadResult:
    filename = file.filename or ""
    if not filename.lower().endswith(".xls"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo biométrico debe ser .xls")

    try:
        saved_path, stored_name = _save_upload_file(file)
        logger.info("Processing biometric upload %s for %02d/%d", stored_name, month, year)

        parser = BiometricParser()
        loader = DesignationLoader()

        parse_result = parser.parse_file(str(saved_path))

        # ── Build CI alias map: bio_ci → real_teacher_ci ──────────────────
        # When a biometric CI doesn't match any teacher record directly, try to
        # resolve via fuzzy name matching.  This handles cases where the CI was
        # entered differently in each system (e.g. "10752810" vs "E-10152810").
        all_teachers = db.query(Teacher).all()
        ci_alias_map: dict[str, str] = {}

        for bio_ci, bio_entries in parse_result.records.items():
            # Check for exact CI match first — no alias needed
            if db.query(Teacher).filter(Teacher.ci == bio_ci).first():
                continue

            bio_name = bio_entries[0].teacher_name if bio_entries else ""
            if not bio_name:
                continue

            for teacher in all_teachers:
                if names_match(bio_name, teacher.full_name):
                    ci_alias_map[bio_ci] = teacher.ci
                    logger.info(
                        "CI alias: bio %s (%s) → teacher %s (%s)",
                        bio_ci,
                        bio_name,
                        teacher.ci,
                        teacher.full_name,
                    )
                    break
        # ──────────────────────────────────────────────────────────────────

        upload = parser.save_to_db(
            db=db,
            parse_result=parse_result,
            month=month,
            year=year,
            filename=stored_name,
            ci_alias_map=ci_alias_map,
        )

        ci_name_map = {
            ci: entries[0].teacher_name
            for ci, entries in parse_result.records.items()
            if entries and entries[0].teacher_name
        }
        linked_teachers = loader.link_teachers_by_name(db, ci_name_map) if ci_name_map else 0

        log_activity(
            db,
            "upload_biometric",
            "upload",
            f"Subida de datos biométricos: {upload.total_teachers} docentes, {upload.total_records} registros ({month:02d}/{year})",
            user=current_user,
            details={
                "filename": stored_name,
                "month": month,
                "year": year,
                "teachers_found": upload.total_teachers,
                "records_count": upload.total_records,
                "ci_aliases_applied": len(ci_alias_map),
            },
            request=request,
        )

        db.commit()
        db.refresh(upload)

        warnings = list(parse_result.warnings)
        if ci_alias_map:
            warnings.append(
                f"Se resolvieron {len(ci_alias_map)} CI(s) biométrico(s) por nombre "
                f"(CIs no coincidían entre sistemas)."
            )
        if linked_teachers:
            warnings.append(f"Se vincularon {linked_teachers} docente(s) por nombre.")

        return BiometricUploadResult(
            upload_id=upload.id,
            filename=upload.filename,
            teachers_found=upload.total_teachers,
            records_count=upload.total_records,
            warnings=warnings,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Biometric upload failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo procesar el archivo biométrico",
        ) from exc
    finally:
        file.file.close()


@router.get("/history", response_model=list[BiometricUploadResponse])
def get_upload_history(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[BiometricUploadResponse]:
    try:
        uploads = (
            db.query(BiometricUpload)
            .order_by(BiometricUpload.upload_date.desc(), BiometricUpload.id.desc())
            .all()
        )
        return [BiometricUploadResponse.model_validate(upload) for upload in uploads]
    except Exception as exc:
        logger.exception("Failed to load upload history: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el historial de cargas",
        ) from exc
