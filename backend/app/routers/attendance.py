from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel as PydanticBaseModel, field_validator
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


def _get_audit_data(
    teacher_ci: str,
    month: int,
    year: int,
    db: Session,
):
    """Shared data-collection logic for the audit GET and PDF endpoints."""
    from app.models.biometric import BiometricRecord, BiometricUpload
    from app.services import app_settings_service

    teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Docente no encontrado")

    # 1. Teacher's designations (schedule)
    designations = db.query(Designation).filter(
        Designation.teacher_ci == teacher_ci,
        Designation.academic_period == app_settings_service.get_active_academic_period(db),
    ).all()

    # 2. Raw biometric records for this teacher in this period
    bio_records = (
        db.query(BiometricRecord)
        .join(BiometricUpload)
        .filter(
            BiometricRecord.teacher_ci == teacher_ci,
            BiometricUpload.month == month,
            BiometricUpload.year == year,
        )
        .order_by(BiometricRecord.date, BiometricRecord.entry_time)
        .all()
    )

    # 3. Processed attendance records (the system's output)
    att_records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.teacher_ci == teacher_ci,
            AttendanceRecord.month == month,
            AttendanceRecord.year == year,
        )
        .order_by(AttendanceRecord.date, AttendanceRecord.scheduled_start)
        .all()
    )

    return teacher, designations, bio_records, att_records


@router.get("/attendance/audit/{teacher_ci}")
def get_attendance_audit(
    teacher_ci: str,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get detailed attendance audit for a teacher — shows schedule, biometric data, and processing result."""
    from app.models.biometric import BiometricRecord

    teacher, designations, bio_records, att_records = _get_audit_data(
        teacher_ci, month, year, db
    )

    schedule_info = []
    for d in designations:
        slots = d.schedule_json or []
        schedule_info.append({
            "designation_id": d.id,
            "subject": d.subject,
            "group_code": d.group_code,
            "semester": d.semester,
            "monthly_hours": d.monthly_hours,
            "weekly_hours": d.weekly_hours,
            "slots": slots,
        })

    biometric_data = [
        {
            "id": r.id,
            "date": r.date.isoformat() if r.date else None,
            "entry_time": r.entry_time.strftime("%H:%M") if r.entry_time else None,
            "exit_time": r.exit_time.strftime("%H:%M") if r.exit_time else None,
            "worked_minutes": r.worked_minutes,
        }
        for r in bio_records
    ]

    # Build detailed audit trail per record
    attendance_audit = []
    for rec in att_records:
        desig = next((d for d in designations if d.id == rec.designation_id), None)

        # Find the linked biometric record
        bio_match = None
        if rec.biometric_record_id:
            bio = db.query(BiometricRecord).filter(BiometricRecord.id == rec.biometric_record_id).first()
            if bio:
                bio_match = {
                    "id": bio.id,
                    "entry_time": bio.entry_time.strftime("%H:%M") if bio.entry_time else None,
                    "exit_time": bio.exit_time.strftime("%H:%M") if bio.exit_time else None,
                    "worked_minutes": bio.worked_minutes,
                }

        # Build explanation of why this status was assigned
        explanation = ""
        if rec.status == "ABSENT":
            explanation = "No se encontró registro biométrico para este horario programado"
        elif rec.status == "LATE":
            explanation = f"Entrada registrada {rec.late_minutes} minutos después del horario programado ({rec.scheduled_start.strftime('%H:%M')})"
        elif rec.status == "ATTENDED":
            explanation = "Entrada registrada dentro del margen de tolerancia"
        elif rec.status == "NO_EXIT":
            explanation = "Se registró entrada pero no se registró salida"

        attendance_audit.append({
            "date": rec.date.isoformat() if rec.date else None,
            "day_name": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][rec.date.weekday()] if rec.date else None,
            "scheduled_start": rec.scheduled_start.strftime("%H:%M") if rec.scheduled_start else None,
            "scheduled_end": rec.scheduled_end.strftime("%H:%M") if rec.scheduled_end else None,
            "actual_entry": rec.actual_entry.strftime("%H:%M") if rec.actual_entry else None,
            "actual_exit": rec.actual_exit.strftime("%H:%M") if rec.actual_exit else None,
            "status": rec.status,
            "academic_hours": rec.academic_hours,
            "late_minutes": rec.late_minutes,
            "observation": rec.observation,
            "subject": desig.subject if desig else "—",
            "group_code": desig.group_code if desig else "—",
            "biometric_match": bio_match,
            "explanation": explanation,
            "has_biometric_link": rec.biometric_record_id is not None,
        })

    # 4. Summary stats
    total_slots = len(att_records)
    attended = sum(1 for r in att_records if r.status == "ATTENDED")
    late = sum(1 for r in att_records if r.status == "LATE")
    absent = sum(1 for r in att_records if r.status == "ABSENT")
    no_exit = sum(1 for r in att_records if r.status == "NO_EXIT")

    has_biometric = len(bio_records) > 0

    return {
        "teacher_ci": teacher.ci,
        "teacher_name": teacher.full_name,
        "month": month,
        "year": year,
        "has_biometric": has_biometric,
        "biometric_records_count": len(bio_records),
        "summary": {
            "total_slots": total_slots,
            "attended": attended,
            "late": late,
            "absent": absent,
            "no_exit": no_exit,
            "attendance_rate": round((attended + late + no_exit) / total_slots * 100, 1) if total_slots > 0 else 0,
        },
        "schedule": schedule_info,
        "biometric_raw": biometric_data,
        "attendance_detail": attendance_audit,
    }


@router.get("/attendance/audit/{teacher_ci}/pdf")
def export_attendance_audit_pdf(
    teacher_ci: str,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2020, le=2100),
    request: Request = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate and download a PDF audit report for a specific teacher."""
    from app.services.audit_report_pdf import generate_audit_report_pdf
    from fastapi.responses import FileResponse

    teacher, designations, bio_records, att_records = _get_audit_data(
        teacher_ci, month, year, db
    )

    pdf_path = generate_audit_report_pdf(
        teacher=teacher,
        month=month,
        year=year,
        designations=designations,
        bio_records=bio_records,
        att_records=att_records,
        db=db,
    )

    log_activity(
        db,
        "export_audit_report",
        "reports",
        f"Reporte de auditoría exportado: {teacher.full_name} — {MONTH_NAMES.get(month)} {year}",
        user=current_user,
        request=request,
    )
    db.commit()

    safe_name = teacher.full_name.replace(" ", "_")
    return FileResponse(
        path=pdf_path,
        filename=f"Auditoria_Asistencia_{safe_name}_{month}_{year}.pdf",
        media_type="application/pdf",
    )


class BatchAuditRequest(PydanticBaseModel):
    teacher_cis: list[str] | None = None  # None or empty = ALL teachers
    month: int
    year: int

    @field_validator('month')
    @classmethod
    def validate_month(cls, v: int) -> int:
        if v < 1 or v > 12:
            raise ValueError('El mes debe estar entre 1 y 12')
        return v

    @field_validator('year')
    @classmethod
    def validate_year(cls, v: int) -> int:
        if v < 2020 or v > 2100:
            raise ValueError('El año debe estar entre 2020 y 2100')
        return v


def _build_audit_response(
    teacher: Teacher,
    designations: list,
    bio_records: list,
    att_records: list,
) -> dict:
    """Build the audit dict used by the batch PDF generator."""
    WEEKDAY_NAMES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

    attendance_detail = []
    for rec in att_records:
        desig = next((d for d in designations if d.id == rec.designation_id), None)

        if rec.status == "ABSENT":
            explanation = "No se encontró registro biométrico para este horario programado"
        elif rec.status == "LATE":
            explanation = f"Entrada registrada {rec.late_minutes} minutos después del horario programado ({rec.scheduled_start.strftime('%H:%M')})"
        elif rec.status == "ATTENDED":
            explanation = "Entrada registrada dentro del margen de tolerancia"
        elif rec.status == "NO_EXIT":
            explanation = "Se registró entrada pero no se registró salida"
        else:
            explanation = rec.status

        attendance_detail.append({
            "date": rec.date.isoformat() if rec.date else None,
            "date_formatted": rec.date.strftime("%d/%m/%Y") if rec.date else "—",
            "day_name": WEEKDAY_NAMES[rec.date.weekday()].capitalize() if rec.date else "—",
            "scheduled_start": rec.scheduled_start.strftime("%H:%M") if rec.scheduled_start else "—",
            "scheduled_end": rec.scheduled_end.strftime("%H:%M") if rec.scheduled_end else "—",
            "actual_entry": rec.actual_entry.strftime("%H:%M") if rec.actual_entry else None,
            "actual_exit": rec.actual_exit.strftime("%H:%M") if rec.actual_exit else None,
            "status": rec.status,
            "late_minutes": rec.late_minutes or 0,
            "subject": desig.subject if desig else "—",
            "group_code": desig.group_code if desig else "—",
            "explanation": explanation,
        })

    total_slots = len(att_records)
    attended = sum(1 for r in att_records if r.status == "ATTENDED")
    late = sum(1 for r in att_records if r.status == "LATE")
    absent = sum(1 for r in att_records if r.status == "ABSENT")
    no_exit = sum(1 for r in att_records if r.status == "NO_EXIT")

    return {
        "has_biometric": len(bio_records) > 0,
        "summary": {
            "total_slots": total_slots,
            "attended": attended,
            "late": late,
            "absent": absent,
            "no_exit": no_exit,
            "attendance_rate": round((attended + late + no_exit) / total_slots * 100, 1) if total_slots > 0 else 0,
        },
        "attendance_detail": attendance_detail,
    }


@router.post("/attendance/audit/batch-pdf")
def export_batch_audit_pdf(
    request: Request,
    payload: BatchAuditRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate a single PDF with audit data for multiple (or all) teachers."""
    from app.services.audit_report_pdf import generate_batch_audit_pdf
    from app.services import app_settings_service
    from fastapi.responses import FileResponse

    month = payload.month
    year = payload.year

    # Determine which teachers to include
    if payload.teacher_cis:
        teachers = (
            db.query(Teacher)
            .filter(Teacher.ci.in_(payload.teacher_cis))
            .order_by(Teacher.full_name)
            .all()
        )
    else:
        # All teachers with active designations (excluding TEMP-)
        teacher_cis_with_desig = {
            d.teacher_ci
            for d in db.query(Designation).filter(
                Designation.academic_period == app_settings_service.get_active_academic_period(db),
                ~Designation.teacher_ci.startswith("TEMP-"),
            ).all()
        }
        teachers = (
            db.query(Teacher)
            .filter(Teacher.ci.in_(teacher_cis_with_desig))
            .order_by(Teacher.full_name)
            .all()
        )

    if not teachers:
        raise HTTPException(400, detail="No se encontraron docentes para el reporte")

    # Collect audit data for each teacher
    all_audit_data = []
    for teacher in teachers:
        t_obj, designations, bio_records, att_records = _get_audit_data(
            teacher.ci, month, year, db
        )
        audit = _build_audit_response(t_obj, designations, bio_records, att_records)
        all_audit_data.append({
            "teacher": teacher,
            "audit": audit,
        })

    pdf_path = generate_batch_audit_pdf(
        all_audit_data=all_audit_data,
        month=month,
        year=year,
        generated_by_name=current_user.full_name,
    )

    log_activity(
        db,
        "export_batch_audit",
        "reports",
        f"Reporte de auditoría masivo: {len(teachers)} docentes — {MONTH_NAMES.get(month)} {year}",
        user=current_user,
        details={"teacher_count": len(teachers), "month": month, "year": year},
        request=request,
    )
    db.commit()

    month_name = MONTH_NAMES.get(month, str(month))
    filename = (
        f"Auditoria_Asistencia_General_{month_name}_{year}.pdf"
        if not payload.teacher_cis
        else f"Auditoria_Asistencia_{len(teachers)}_docentes_{month_name}_{year}.pdf"
    )

    return FileResponse(path=pdf_path, filename=filename, media_type="application/pdf")


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
