from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.designation import DesignationContractDatesUpdate, DesignationResponse
from app.schemas.teacher import (
    PaginatedTeachersResponse,
    TeacherAttendanceSummary,
    TeacherCreate,
    TeacherDetailResponse,
    TeacherResponse,
    TeacherUpdate,
    TeacherProfileImportApplyResponse,
    TeacherProfileImportPreviewResponse,
)
from app.services.activity_logger import log_activity
from app.services.teacher_profile_import_service import (
    TeacherProfileImportError,
    TeacherProfileImportPlan,
    TeacherProfileImportService,
)
from app.services.teacher_photo_service import (
    apply_photo_metadata,
    clear_photo_metadata,
    delete_photo_file,
    save_upload_file,
)
from app.utils.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


@router.get("", response_model=PaginatedTeachersResponse)
def list_teachers(
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedTeachersResponse:
    try:
        query = db.query(Teacher)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(or_(Teacher.full_name.ilike(term), Teacher.ci.ilike(term)))

        total = query.count()
        teachers = (
            query.order_by(Teacher.full_name.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return PaginatedTeachersResponse(
            items=[TeacherResponse.model_validate(teacher) for teacher in teachers],
            total=total,
            page=page,
            per_page=per_page,
        )
    except Exception as exc:
        logger.exception("Failed to load teachers: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener la lista de docentes",
        ) from exc


@router.get("/{ci}", response_model=TeacherDetailResponse)
def get_teacher(
    ci: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeacherDetailResponse:
    # Admin can see any teacher; docente can only see their own
    if current_user.role == "docente" and current_user.teacher_ci != ci:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo podés ver tu propio perfil de docente",
        )
    try:
        teacher = (
            db.query(Teacher)
            .options(selectinload(Teacher.designations))
            .filter(Teacher.ci == ci)
            .first()
        )
        if teacher is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docente no encontrado")

        attendance_rows = db.query(AttendanceRecord).filter(AttendanceRecord.teacher_ci == ci).all()
        summary = TeacherAttendanceSummary(
            total_records=len(attendance_rows),
            attended=sum(1 for row in attendance_rows if row.status == "ATTENDED"),
            late=sum(1 for row in attendance_rows if row.status == "LATE"),
            absent=sum(1 for row in attendance_rows if row.status == "ABSENT"),
            no_exit=sum(1 for row in attendance_rows if row.status == "NO_EXIT"),
            total_academic_hours=sum(row.academic_hours for row in attendance_rows),
        )

        payload = TeacherDetailResponse.model_validate(teacher)
        payload.attendance_summary = summary
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to load teacher %s: %s", ci, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el docente",
        ) from exc


@router.post("", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(
    request: Request,
    payload: TeacherCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TeacherResponse:
    """Create a new teacher manually."""
    try:
        existing = db.query(Teacher).filter(Teacher.ci == payload.ci).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un docente con CI {payload.ci}",
            )

        teacher = Teacher(
            ci=payload.ci,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            gender=payload.gender,
            external_permanent=payload.external_permanent,
            academic_level=payload.academic_level,
            profession=payload.profession,
            specialty=payload.specialty,
            bank=payload.bank,
            account_number=payload.account_number,
            nit=payload.nit,
            sap_code=payload.sap_code,
            invoice_retention=payload.invoice_retention,
        )
        db.add(teacher)

        log_activity(
            db,
            "create_teacher",
            "teachers",
            f"Docente creado: {teacher.full_name} (CI: {teacher.ci})",
            user=current_user,
            details={"ci": teacher.ci, "full_name": teacher.full_name},
            request=request,
        )

        db.commit()
        db.refresh(teacher)

        return TeacherResponse.model_validate(teacher)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create teacher: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo crear el docente") from exc


@router.put("/{ci}", response_model=TeacherResponse)
def update_teacher(
    request: Request,
    ci: str,
    payload: TeacherUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TeacherResponse:
    """Update an existing teacher's information. Supports CI change with cascade."""
    try:
        teacher = db.query(Teacher).filter(Teacher.ci == ci).first()
        if teacher is None:
            raise HTTPException(status_code=404, detail="Docente no encontrado")

        update_data = payload.model_dump(exclude_unset=True)
        new_ci = update_data.pop("ci", None)

        # Handle CI change — must cascade to all FK references
        if new_ci and new_ci != ci:
            # Check new CI doesn't already exist
            existing = db.query(Teacher).filter(Teacher.ci == new_ci).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un docente con CI {new_ci}",
                )

            from app.models.designation import Designation
            from sqlalchemy import text

            # Update ALL FK references via raw SQL (SQLAlchemy can't cascade PK changes)
            db.execute(text("UPDATE designations SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})
            db.execute(text("UPDATE attendance_records SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})
            db.execute(text("UPDATE biometric_records SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})
            db.execute(text("UPDATE detail_requests SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})
            db.execute(text("UPDATE users SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})
            # Also update the user's login CI so they can still authenticate after a CI change
            db.execute(text("UPDATE users SET ci = :new WHERE ci = :old AND role = 'docente'"), {"new": new_ci, "old": ci})

            # Update the PK itself
            db.execute(text("UPDATE teachers SET ci = :new WHERE ci = :old"), {"new": new_ci, "old": ci})
            db.flush()

            # Re-fetch with new CI
            teacher = db.query(Teacher).filter(Teacher.ci == new_ci).first()

        # Update remaining fields
        for field, value in update_data.items():
            setattr(teacher, field, value)

        log_activity(
            db,
            "update_teacher",
            "teachers",
            f"Docente actualizado: {teacher.full_name} (CI: {teacher.ci})" + (f" [CI cambiado: {ci} → {new_ci}]" if new_ci and new_ci != ci else ""),
            user=current_user,
            details={"old_ci": ci, "new_ci": new_ci or ci, "fields_updated": list(update_data.keys()) + (["ci"] if new_ci and new_ci != ci else [])},
            request=request,
        )

        db.commit()
        db.refresh(teacher)

        return TeacherResponse.model_validate(teacher)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to update teacher %s: %s", ci, exc)
        raise HTTPException(status_code=500, detail="No se pudo actualizar el docente") from exc


@router.put("/{ci}/photo", response_model=TeacherResponse)
def upload_teacher_photo(
    request: Request,
    ci: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TeacherResponse:
    """Upload or replace a teacher profile photo."""
    new_filename: str | None = None
    old_filename: str | None = None
    try:
        teacher = db.query(Teacher).filter(Teacher.ci == ci).first()
        if teacher is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docente no encontrado")

        new_filename, content_type = save_upload_file(file)
        old_filename = apply_photo_metadata(teacher, new_filename, content_type)

        log_activity(
            db,
            "upload_teacher_photo",
            "teachers",
            f"Foto de docente actualizada: {teacher.full_name} (CI: {teacher.ci})",
            user=current_user,
            details={"ci": teacher.ci, "content_type": content_type},
            request=request,
        )

        db.commit()
        db.refresh(teacher)
        delete_photo_file(old_filename)
        return TeacherResponse.model_validate(teacher)
    except HTTPException:
        delete_photo_file(new_filename)
        raise
    except Exception as exc:
        db.rollback()
        delete_photo_file(new_filename)
        logger.exception("Failed to upload teacher photo for %s: %s", ci, exc)
        raise HTTPException(status_code=500, detail="No se pudo actualizar la foto del docente") from exc
    finally:
        file.file.close()


@router.delete("/{ci}/photo", response_model=TeacherResponse)
def delete_teacher_photo(
    request: Request,
    ci: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TeacherResponse:
    """Remove a teacher profile photo association and delete its file best-effort."""
    old_filename: str | None = None
    try:
        teacher = db.query(Teacher).filter(Teacher.ci == ci).first()
        if teacher is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docente no encontrado")

        old_filename = clear_photo_metadata(teacher)

        log_activity(
            db,
            "delete_teacher_photo",
            "teachers",
            f"Foto de docente eliminada: {teacher.full_name} (CI: {teacher.ci})",
            user=current_user,
            details={"ci": teacher.ci},
            request=request,
        )

        db.commit()
        db.refresh(teacher)
        delete_photo_file(old_filename)
        return TeacherResponse.model_validate(teacher)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to delete teacher photo for %s: %s", ci, exc)
        raise HTTPException(status_code=500, detail="No se pudo eliminar la foto del docente") from exc


@router.put("/designations/{designation_id}/contract-dates", response_model=DesignationResponse)
def update_designation_contract_dates(
    request: Request,
    designation_id: int,
    payload: DesignationContractDatesUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DesignationResponse:
    """Update contract dates for one assignment/designation."""
    try:
        designation = db.query(Designation).filter(Designation.id == designation_id).first()
        if designation is None:
            raise HTTPException(status_code=404, detail="Designación no encontrada")

        if (
            payload.contract_start_date is not None
            and payload.contract_end_date is not None
            and payload.contract_end_date < payload.contract_start_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de fin no puede ser anterior a la fecha de inicio",
            )

        designation.contract_start_date = payload.contract_start_date
        designation.contract_end_date = payload.contract_end_date

        log_activity(
            db,
            "update_designation_contract_dates",
            "teachers",
            f"Fechas de contrato actualizadas: {designation.subject} {designation.group_code}",
            user=current_user,
            details={
                "designation_id": designation.id,
                "teacher_ci": designation.teacher_ci,
                "contract_start_date": str(designation.contract_start_date) if designation.contract_start_date else None,
                "contract_end_date": str(designation.contract_end_date) if designation.contract_end_date else None,
            },
            request=request,
        )

        db.commit()
        db.refresh(designation)
        return DesignationResponse.model_validate(designation)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to update designation %s contract dates: %s", designation_id, exc)
        raise HTTPException(status_code=500, detail="No se pudieron actualizar las fechas de contrato") from exc


MAX_TEACHER_PROFILE_UPLOAD_BYTES = 10 * 1024 * 1024


async def _teacher_profile_json_bytes(file: UploadFile) -> bytes:
    filename = file.filename or "upload.bin"
    if Path(filename).suffix.lower() != ".json":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El importador seguro de perfiles admite únicamente archivos .json audit_envelope.",
        )
    content = await file.read(MAX_TEACHER_PROFILE_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(content) > MAX_TEACHER_PROFILE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 10 MB.")
    return content


def _teacher_profile_response(plan: TeacherProfileImportPlan) -> TeacherProfileImportPreviewResponse:
    return TeacherProfileImportPreviewResponse(
        digest=plan.digest,
        parsed_format=plan.parsed_format,
        academic_period=plan.academic_period,
        scope=plan.scope,
        policy=plan.policy,
        total_rows=plan.total_rows,
        rows_with_fills=plan.rows_with_fills,
        can_apply=plan.can_apply,
        identity=plan.identity.__dict__,
        fields={name: counts.__dict__ for name, counts in plan.fields.items()},
        warnings=plan.warnings,
        errors=plan.errors,
    )


@router.post("/import/preview", response_model=TeacherProfileImportPreviewResponse)
async def preview_teacher_profiles(
    file: UploadFile = File(...),
    academic_period: str = Query(..., description="Período académico explícito, ej: II/2026"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TeacherProfileImportPreviewResponse:
    try:
        content = await _teacher_profile_json_bytes(file)
        return _teacher_profile_response(
            TeacherProfileImportService().preview(db, content, academic_period)
        )
    finally:
        await file.close()


@router.post(
    "/import",
    response_model=TeacherProfileImportApplyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_teacher_profiles(
    request: Request,
    file: UploadFile = File(...),
    academic_period: str = Query(..., description="Período académico explícito, ej: II/2026"),
    confirmation_digest: str = Query(..., min_length=64, max_length=64),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TeacherProfileImportApplyResponse:
    try:
        content = await _teacher_profile_json_bytes(file)
        plan = TeacherProfileImportService().apply(
            db,
            content,
            academic_period,
            confirmation_digest,
        )
        log_activity(
            db,
            "import_teacher_profiles",
            "upload",
            f"Perfiles docentes confirmados: {plan.total_rows} filas para {academic_period}",
            user=current_user,
            details={
                "digest": plan.digest,
                "format": plan.parsed_format,
                "academic_period": academic_period,
                "scope": plan.scope,
                "policy": plan.policy,
                "total_rows": plan.total_rows,
                "field_fills": {name: counts.fills for name, counts in plan.fields.items()},
            },
            request=request,
        )
        db.commit()
        return TeacherProfileImportApplyResponse(
            **_teacher_profile_response(plan).model_dump(),
            applied=True,
        )
    except TeacherProfileImportError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="\n".join(exc.errors)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        # Database exception strings may include bound values. Log only the
        # exception class so uploaded profile PII can never reach application logs.
        logger.error("Teacher profile import failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="No se pudo importar los perfiles docentes.") from exc
    finally:
        await file.close()


@router.post("/upload", status_code=status.HTTP_410_GONE)
async def retired_teacher_list_upload(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
):
    """Fail closed instead of silently applying the unsafe legacy upsert."""
    await file.close()
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "La carga directa fue retirada porque podía sobrescribir datos y confundir "
            "NOMBRE con Nombre del Banco. Usá Cargas > Lista de Docentes > "
            "Generar vista previa y luego Confirmar e importar."
        ),
    )


class BulkDeleteRequest(PydanticBaseModel):
    teacher_cis: list[str]


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_teachers(
    request: Request,
    payload: BulkDeleteRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete multiple teachers and their associated data."""
    if not payload.teacher_cis:
        raise HTTPException(400, detail="No se seleccionaron docentes")

    deleted = 0
    errors = []

    for ci in payload.teacher_cis:
        teacher = db.query(Teacher).filter(Teacher.ci == ci).first()
        if teacher:
            name = teacher.full_name
            try:
                # Delete associated user accounts: match by teacher_ci link OR by ci (same identity)
                db.execute(
                    text("DELETE FROM users WHERE (teacher_ci = :ci OR ci = :ci) AND role = 'docente'"),
                    {"ci": ci},
                )
                db.delete(teacher)
                db.flush()
                deleted += 1
            except Exception as e:
                errors.append(f"{name}: {str(e)}")
        else:
            errors.append(f"CI {ci}: no encontrado")

    log_activity(
        db,
        "bulk_delete_teachers",
        "teachers",
        f"{deleted} docente(s) eliminado(s)",
        user=current_user,
        details={"deleted": deleted, "requested": len(payload.teacher_cis), "errors": errors},
        request=request,
    )

    db.commit()

    return {
        "deleted": deleted,
        "errors": errors,
    }


@router.delete("/{ci}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teacher(
    request: Request,
    ci: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a teacher. This also cascades to their designations."""
    try:
        teacher = db.query(Teacher).filter(Teacher.ci == ci).first()
        if teacher is None:
            raise HTTPException(status_code=404, detail="Docente no encontrado")

        name = teacher.full_name
        log_activity(
            db,
            "delete_teacher",
            "teachers",
            f"Docente eliminado: {name} (CI: {ci})",
            user=current_user,
            details={"ci": ci, "full_name": name},
            request=request,
        )

        db.delete(teacher)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to delete teacher %s: %s", ci, exc)
        raise HTTPException(status_code=500, detail="No se pudo eliminar el docente") from exc
