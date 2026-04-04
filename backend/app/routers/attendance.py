from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricUpload
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.attendance import (
    AttendanceProcessRequest,
    AttendanceProcessResponse,
    AttendanceWithDetails,
    MonthlyAttendanceSummaryResponse,
    ObservationResponse,
    PaginatedAttendanceResponse,
)
from app.services.attendance_engine import AttendanceEngine
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["attendance"])


def _attendance_query(db: Session, month: int, year: int):
    return (
        db.query(AttendanceRecord, Teacher.full_name, Designation.subject, Designation.group_code, Designation.semester)
        .join(Teacher, Teacher.ci == AttendanceRecord.teacher_ci)
        .join(Designation, Designation.id == AttendanceRecord.designation_id)
        .filter(AttendanceRecord.month == month, AttendanceRecord.year == year)
    )


def _to_attendance_with_details(row) -> AttendanceWithDetails:
    attendance, teacher_name, subject, group_code, semester = row
    payload = AttendanceWithDetails.model_validate(attendance)
    payload.teacher_name = teacher_name
    payload.subject = subject
    payload.group_code = group_code
    payload.semester = semester
    return payload


def _to_observation_response(row) -> ObservationResponse:
    attendance, teacher_name, subject, group_code, _semester = row
    return ObservationResponse(
        id=attendance.id,
        teacher_ci=attendance.teacher_ci,
        teacher_name=teacher_name,
        designation_id=attendance.designation_id,
        subject=subject,
        group_code=group_code,
        date=attendance.date,
        scheduled_start=attendance.scheduled_start,
        scheduled_end=attendance.scheduled_end,
        status=attendance.status,
        late_minutes=attendance.late_minutes,
        observation=attendance.observation,
    )


@router.post("/attendance/process", response_model=AttendanceProcessResponse)
def process_attendance(
    payload: AttendanceProcessRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AttendanceProcessResponse:
    try:
        upload = db.query(BiometricUpload).filter(BiometricUpload.id == payload.upload_id).first()
        if upload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload biométrico no encontrado")

        logger.info(
            "Running attendance process for upload_id=%d month=%02d year=%d",
            payload.upload_id,
            payload.month,
            payload.year,
        )

        engine = AttendanceEngine()
        result = engine.process_month(
            db=db,
            upload_id=payload.upload_id,
            month=payload.month,
            year=payload.year,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        log_activity(
            db,
            "process_attendance",
            "planilla",
            f"Procesamiento de asistencia: {MONTH_NAMES.get(payload.month, str(payload.month))} {payload.year}",
            user=current_user,
            details={
                "month": payload.month,
                "year": payload.year,
                "upload_id": payload.upload_id,
                "total_slots": result.total_slots,
                "attended": result.attended,
            },
            request=request,
        )

        db.commit()

        observations_count = (
            db.query(func.count(AttendanceRecord.id))
            .filter(
                AttendanceRecord.month == payload.month,
                AttendanceRecord.year == payload.year,
                AttendanceRecord.observation.isnot(None),
            )
            .scalar()
            or 0
        )
        attendance_rate = round(result.present / result.total_slots * 100, 1) if result.total_slots else 0.0

        return AttendanceProcessResponse(
            total_records=result.total_slots,
            attended=result.attended,
            late=result.late,
            absent=result.absent,
            no_exit=result.no_exit,
            attendance_rate=attendance_rate,
            observations_count=observations_count,
            warnings=result.warnings,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Attendance processing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo procesar la asistencia",
        ) from exc


@router.get("/attendance/{month}/{year}/summary", response_model=MonthlyAttendanceSummaryResponse)
def get_attendance_summary(
    month: int,
    year: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MonthlyAttendanceSummaryResponse:
    try:
        engine = AttendanceEngine()
        base_summary = engine.get_month_summary(db=db, month=month, year=year)

        total_teachers = (
            db.query(func.count(func.distinct(AttendanceRecord.teacher_ci)))
            .filter(AttendanceRecord.month == month, AttendanceRecord.year == year)
            .scalar()
            or 0
        )
        observation_rows = (
            _attendance_query(db, month, year)
            .filter(or_(AttendanceRecord.observation.isnot(None), AttendanceRecord.status.in_(["LATE", "ABSENT", "NO_EXIT"])))
            .order_by(AttendanceRecord.date.asc(), AttendanceRecord.scheduled_start.asc())
            .all()
        )

        return MonthlyAttendanceSummaryResponse(
            total_teachers=total_teachers,
            total_slots=base_summary["total_slots"],
            attended=base_summary["by_status"]["ATTENDED"],
            late=base_summary["by_status"]["LATE"],
            absent=base_summary["by_status"]["ABSENT"],
            no_exit=base_summary["by_status"]["NO_EXIT"],
            attendance_rate=base_summary["attendance_rate"],
            total_academic_hours=base_summary["total_academic_hours"],
            observations=[_to_observation_response(row) for row in observation_rows],
        )
    except Exception as exc:
        logger.exception("Failed to load attendance summary: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el resumen de asistencia",
        ) from exc


@router.get("/attendance/{month}/{year}", response_model=PaginatedAttendanceResponse)
def get_attendance(
    month: int,
    year: int,
    teacher_ci: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedAttendanceResponse:
    try:
        query = _attendance_query(db, month, year)
        if teacher_ci:
            query = query.filter(AttendanceRecord.teacher_ci == teacher_ci)
        if status_filter:
            query = query.filter(AttendanceRecord.status == status_filter.upper())

        total = query.count()
        rows = (
            query.order_by(AttendanceRecord.date.asc(), AttendanceRecord.scheduled_start.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return PaginatedAttendanceResponse(
            items=[_to_attendance_with_details(row) for row in rows],
            total=total,
            page=page,
            per_page=per_page,
        )
    except Exception as exc:
        logger.exception("Failed to load attendance records: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener la asistencia",
        ) from exc


@router.get("/observations/{month}/{year}", response_model=list[ObservationResponse])
def get_observations(
    month: int,
    year: int,
    type: str | None = Query(default=None),
    teacher_ci: str | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ObservationResponse]:
    try:
        query = _attendance_query(db, month, year)
        statuses = [value.strip().upper() for value in (type or "").split(",") if value.strip()]
        if statuses:
            query = query.filter(AttendanceRecord.status.in_(statuses))
        else:
            query = query.filter(AttendanceRecord.status.in_(["LATE", "ABSENT", "NO_EXIT"]))

        if teacher_ci:
            query = query.filter(AttendanceRecord.teacher_ci == teacher_ci)

        rows = query.order_by(AttendanceRecord.date.asc(), AttendanceRecord.scheduled_start.asc()).all()
        return [_to_observation_response(row) for row in rows]
    except Exception as exc:
        logger.exception("Failed to load observations: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudieron obtener las observaciones",
        ) from exc
