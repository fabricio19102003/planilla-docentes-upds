from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.teacher import (
    PaginatedTeachersResponse,
    TeacherAttendanceSummary,
    TeacherDetailResponse,
    TeacherResponse,
)
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
