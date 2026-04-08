from __future__ import annotations

import importlib.util
import json
import logging
import secrets
import shutil
import string
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.designation import DesignationUploadResponse
from app.services.auth_service import AuthService
from app.services.designation_loader import DesignationLoader
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def _uploads_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _generate_compliant_password() -> str:
    """Generate a random 12-char password that always meets the strength policy.

    Guarantees at least one uppercase letter, one lowercase letter, and one digit
    (avoids the weakness of secrets.token_urlsafe which may lack any of these).
    """
    chars = string.ascii_letters + string.digits
    while True:
        pwd = "".join(secrets.choice(chars) for _ in range(12))
        if (
            any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
        ):
            return pwd


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

        # Transform entries from old internal format to new horario_detalle format
        horario_detalle = [
            {
                "dia": entry["dia"].capitalize(),  # "lunes" → "Lunes"
                "hora_inicio": entry["hora_inicio"],
                "hora_fin": entry["hora_fin"],
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


def _auto_create_docente_users(db: Session) -> tuple[int, int]:
    """Create user accounts for all teachers that don't have one yet,
    and fix existing docente users that have ``teacher_ci=None``.

    Each new user receives a unique random password via secrets.token_urlsafe(8).
    Passwords are NOT stored in plaintext, NOT returned in responses, NOT logged.
    Admins must use the password reset flow to provide credentials to teachers.

    Returns ``(created, skipped)`` counts.
    """
    auth_service = AuthService()
    current_year = datetime.now().year  # noqa: F841  kept for future use

    # ── Phase 1: Fix existing docente users with teacher_ci=None ─────
    unlinked_users = (
        db.query(User)
        .filter(User.role == "docente", User.teacher_ci.is_(None))
        .all()
    )
    linked_count = 0
    for user in unlinked_users:
        # Only exact CI match — name matching is too dangerous for payroll data
        teacher = db.query(Teacher).filter(Teacher.ci == user.ci).first()
        if teacher:
            user.teacher_ci = teacher.ci
            linked_count += 1

    if linked_count:
        db.flush()
        logger.info("Linked %d existing docente users to their teacher records", linked_count)

    # ── Phase 2: Create new users for teachers without accounts ──────
    existing_user_cis: set[str] = {row[0] for row in db.query(User.ci).all()}

    # Also check by name to avoid creating duplicates for teachers whose CI changed
    existing_user_names: set[str] = {
        row[0].strip().upper()
        for row in db.query(User.full_name).filter(User.role == "docente").all()
    }

    teachers_without_user = (
        db.query(Teacher)
        .filter(~Teacher.ci.in_(existing_user_cis), ~Teacher.ci.startswith("TEMP-"))
        .all()
    )

    created = 0
    skipped = 0

    for teacher in teachers_without_user:
        # Skip if a user with the same name already exists (prevents duplicates)
        if teacher.full_name.strip().upper() in existing_user_names:
            skipped += 1
            continue

        try:
            # Each teacher gets a unique random password — never reused across accounts
            password = _generate_compliant_password()
            user = User(
                ci=teacher.ci,
                full_name=teacher.full_name,
                password_hash=auth_service.hash_password(password),
                role="docente",
                teacher_ci=teacher.ci,
                is_active=True,
                must_change_password=True,
            )
            db.add(user)
            db.flush()
            created += 1
            existing_user_names.add(teacher.full_name.strip().upper())
        except Exception:
            skipped += 1
            logger.warning("Could not create user for teacher CI=%s", teacher.ci)

    # NOTE: passwords are NOT logged — admin must use password reset flow
    logger.info("Auto-created %d docente users (%d skipped)", created, skipped)
    return created, skipped


@router.post("/designations", response_model=DesignationUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_designations(
    request: Request,
    file: UploadFile = File(...),
    academic_period: str = Query(default=settings.ACTIVE_ACADEMIC_PERIOD, description="Período académico, ej: I/2026, II/2025"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DesignationUploadResponse:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    logger.info(
        "Designation upload received: filename=%r, extension=%r, content_type=%r, period=%r",
        filename, extension, file.content_type, academic_period,
    )
    if extension not in {".json", ".xlsx"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo debe ser .json o .xlsx (recibido: '{filename}', extensión: '{extension}')",
        )

    try:
        saved_path, stored_name = _save_upload_file(file)
        logger.info("Processing designation upload %s (period=%s)", stored_name, academic_period)

        loader = DesignationLoader()
        warnings: list[str] = []

        if extension == ".json":
            result = loader.load_from_json(db=db, json_path=str(saved_path), academic_period=academic_period)
        else:
            normalized_json, parser_warnings = _normalize_designations_excel(saved_path)
            warnings.extend(parser_warnings)
            result = loader.load_from_json(db=db, json_path=str(normalized_json), academic_period=academic_period)

        # Auto-create docente user accounts for all loaded teachers
        users_created, users_skipped = _auto_create_docente_users(db)

        log_activity(
            db,
            "upload_designations",
            "upload",
            f"Subida de designaciones: {result.designations_loaded} cargadas, {users_created} usuarios creados",
            user=current_user,
            details={
                "filename": filename,
                "designations_loaded": result.designations_loaded,
                "teachers_created": result.teachers_created,
                "users_created": users_created,
            },
            request=request,
        )

        db.commit()

        return DesignationUploadResponse(
            teachers_created=result.teachers_created,
            teachers_reused=result.teachers_reused,
            designations_loaded=result.designations_loaded,
            skipped=result.total_skipped,
            users_created=users_created,
            users_skipped=users_skipped,
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
