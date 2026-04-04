from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.teacher import (
    PaginatedTeachersResponse,
    TeacherAttendanceSummary,
    TeacherCreate,
    TeacherDetailResponse,
    TeacherResponse,
    TeacherUpdate,
)
from app.services.activity_logger import log_activity
from app.utils.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/teachers", tags=["teachers"])


@router.get("", response_model=PaginatedTeachersResponse)
def list_teachers(
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
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

            # Update FK references via raw SQL (SQLAlchemy can't cascade PK changes)
            db.execute(text("UPDATE designations SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})
            db.execute(text("UPDATE attendance_records SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})
            db.execute(text("UPDATE biometric_records SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})
            db.execute(text("UPDATE users SET teacher_ci = :new WHERE teacher_ci = :old"), {"new": new_ci, "old": ci})

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
