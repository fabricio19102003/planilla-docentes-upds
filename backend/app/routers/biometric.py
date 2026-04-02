from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.biometric import BiometricUpload
from app.models.user import User
from app.schemas.biometric import BiometricUploadResponse, BiometricUploadResult
from app.services.biometric_parser import BiometricParser
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


@router.post("/biometric", response_model=BiometricUploadResult, status_code=status.HTTP_201_CREATED)
def upload_biometric(
    file: UploadFile = File(...),
    month: int = Form(..., ge=1, le=12),
    year: int = Form(..., ge=2000, le=2100),
    _: User = Depends(require_admin),
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
        upload = parser.save_to_db(
            db=db,
            parse_result=parse_result,
            month=month,
            year=year,
            filename=stored_name,
        )

        ci_name_map = {
            ci: entries[0].teacher_name
            for ci, entries in parse_result.records.items()
            if entries and entries[0].teacher_name
        }
        linked_teachers = loader.link_teachers_by_name(db, ci_name_map) if ci_name_map else 0
        db.commit()
        db.refresh(upload)

        warnings = list(parse_result.warnings)
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
