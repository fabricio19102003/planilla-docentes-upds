from __future__ import annotations

import logging
from datetime import date, time as time_type

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.academic_management import AcademicSchedulePublishedAssignment
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.practice_attendance import (
    PracticeAttendanceBulkCreate,
    PracticeAttendanceResponse,
    PracticeAttendanceSummary,
    PracticeAttendanceUpdate,
)
from app.services import app_settings_service
from app.services.activity_logger import log_activity
from app.services.practice_attendance_export import (
    generate_practice_attendance_pdf,
    generate_practice_attendance_excel,
)
from app.services.planilla_generator import (
    PayrollDataError,
    _effective_designation_range,
    _resolve_payroll_period,
)
from app.services.payroll_schedule_source_service import payroll_schedule_sources
from app.services.practice_attendance_source_service import practice_attendance_source_details
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/practice-attendance", tags=["practice-attendance"])

# Canonical weekday mapping (Monday=0 ... Sunday=6) → Spanish lowercase
WEEKDAY_MAP: dict[int, str] = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo",
}


def _normalize_day(raw: str) -> str:
    """Normalize a Spanish day name: lowercase + strip accents."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", raw.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_time(t: str) -> time_type | None:
    """Parse HH:MM string to time object."""
    try:
        parts = t.strip().split(":")
        return time_type(int(parts[0]), int(parts[1]))
    except Exception:
        return None


def _resolve_period(month: int, year: int, start_date: date | None, end_date: date | None) -> tuple[date, date]:
    """Resolve optional date bounds against the selected month."""
    try:
        period_start, period_end, _ = _resolve_payroll_period(
            month, year, start_date, end_date,
        )
        return period_start, period_end
    except PayrollDataError as exc:
        raise HTTPException(400, detail=exc.as_detail()) from exc


@router.post("/generate")
def generate_practice_attendance(
    payload: PracticeAttendanceBulkCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate attendance skeleton from practice designations' schedule.

    Creates one PracticeAttendanceLog entry per scheduled slot per day in the
    period.  Existing entries (same teacher_ci + designation_id + date +
    scheduled_start) are skipped so the operation is idempotent.
    """
    month = payload.month
    year = payload.year

    period_start, period_end = _resolve_period(month, year, payload.start_date, payload.end_date)

    academic_period = app_settings_service.get_active_academic_period(db)

    sources = payroll_schedule_sources(
        db,
        academic_period=academic_period,
        period_start=period_start,
        period_end=period_end,
        activity_kind="practice",
    )
    if not sources:
        raise HTTPException(
            404,
            detail="No se encontraron designaciones de práctica para el período académico activo",
        )

    # Build a set of existing entries to avoid duplicates
    existing: set[tuple[str, str, date, time_type]] = set()
    existing_rows = (
        db.query(
            PracticeAttendanceLog.teacher_ci,
            PracticeAttendanceLog.designation_id,
            PracticeAttendanceLog.published_schedule_assignment_id,
            PracticeAttendanceLog.date,
            PracticeAttendanceLog.scheduled_start,
        )
        .filter(
            PracticeAttendanceLog.date >= period_start,
            PracticeAttendanceLog.date <= period_end,
        )
        .all()
    )
    for row in existing_rows:
        source_key = f"legacy:{row[1]}" if row[1] is not None else f"published:{row[2]}"
        existing.add((row[0], source_key, row[3], row[4]))

    created = 0
    for source in sources:
        for slot in source.payable_slots:
            key = (source.teacher_ci, source.source_key, slot.date, slot.scheduled_start)
            if key in existing:
                continue
            db.add(PracticeAttendanceLog(
                teacher_ci=source.teacher_ci,
                designation_id=source.designation_id,
                published_schedule_assignment_id=source.published_assignment_id,
                date=slot.date,
                scheduled_start=slot.scheduled_start,
                scheduled_end=slot.scheduled_end,
                academic_hours=slot.academic_hours,
                status="absent",
                registered_by=current_user.ci,
            ))
            existing.add(key)
            created += 1

    db.flush()

    log_activity(
        db,
        "generate_practice_attendance",
        "practice_attendance",
        f"Generación de asistencia prácticas: {created} entradas creadas ({month}/{year})",
        user=current_user,
        details={"month": month, "year": year, "created": created},
        request=request,
    )
    db.commit()

    return {"created": created, "month": month, "year": year}


@router.get("/{month}/{year}", response_model=list[PracticeAttendanceResponse])
def list_practice_attendance(
    month: int,
    year: int,
    teacher_ci: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all practice attendance entries for a month/year with optional filters."""
    period_start, period_end = _resolve_period(month, year, start_date, end_date)

    query = (
        db.query(PracticeAttendanceLog, Teacher.full_name)
        .join(Teacher, Teacher.ci == PracticeAttendanceLog.teacher_ci)
        .options(
            joinedload(PracticeAttendanceLog.designation),
            joinedload(PracticeAttendanceLog.published_schedule_assignment).joinedload(
                AcademicSchedulePublishedAssignment.block
            ),
        )
        .filter(
            PracticeAttendanceLog.date >= period_start,
            PracticeAttendanceLog.date <= period_end,
        )
    )

    if teacher_ci:
        query = query.filter(PracticeAttendanceLog.teacher_ci == teacher_ci)

    query = query.order_by(Teacher.full_name, PracticeAttendanceLog.date, PracticeAttendanceLog.scheduled_start)
    rows = query.all()

    result = []
    for log, teacher_name in rows:
        source = practice_attendance_source_details(log)
        result.append(
            PracticeAttendanceResponse(
                id=log.id,
                teacher_ci=log.teacher_ci,
                teacher_name=teacher_name,
                designation_id=log.designation_id,
                published_schedule_assignment_id=log.published_schedule_assignment_id,
                source_kind=source.source_kind,
                source_key=source.source_key,
                subject=source.subject,
                group_code=source.group_code,
                semester=source.semester,
                date=log.date,
                scheduled_start=log.scheduled_start,
                scheduled_end=log.scheduled_end,
                actual_start=log.actual_start,
                actual_end=log.actual_end,
                academic_hours=log.academic_hours,
                status=log.status,
                observation=log.observation,
                registered_by=log.registered_by,
                created_at=log.created_at.isoformat() if log.created_at else None,
            )
        )
    return result


@router.get("/{month}/{year}/summary", response_model=list[PracticeAttendanceSummary])
def get_practice_attendance_summary(
    month: int,
    year: int,
    teacher_ci: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Calculate attendance summary per teacher for the given period."""
    period_start, period_end = _resolve_period(month, year, start_date, end_date)

    query = (
        db.query(PracticeAttendanceLog, Teacher.full_name)
        .join(Teacher, Teacher.ci == PracticeAttendanceLog.teacher_ci)
        .filter(
            PracticeAttendanceLog.date >= period_start,
            PracticeAttendanceLog.date <= period_end,
        )
    )

    if teacher_ci:
        query = query.filter(PracticeAttendanceLog.teacher_ci == teacher_ci)

    rows = query.all()

    teacher_data: dict[str, dict] = {}
    for log, teacher_name in rows:
        if log.teacher_ci not in teacher_data:
            teacher_data[log.teacher_ci] = {
                "teacher_ci": log.teacher_ci,
                "teacher_name": teacher_name,
                "total_scheduled": 0,
                "total_attended": 0,
                "total_absent": 0,
                "total_late": 0,
                "total_justified": 0,
                "total_hours_scheduled": 0,
                "total_hours_attended": 0,
            }
        data = teacher_data[log.teacher_ci]
        data["total_scheduled"] += 1
        data["total_hours_scheduled"] += log.academic_hours

        if log.status == "attended":
            data["total_attended"] += 1
            data["total_hours_attended"] += log.academic_hours
        elif log.status == "absent":
            data["total_absent"] += 1
        elif log.status == "late":
            data["total_late"] += 1
            data["total_hours_attended"] += log.academic_hours
        elif log.status == "justified":
            data["total_justified"] += 1
            data["total_hours_attended"] += log.academic_hours  # Justified = paid hours

    result = []
    for ci, data in sorted(teacher_data.items(), key=lambda x: x[1]["teacher_name"]):
        total = data["total_scheduled"]
        present = data["total_attended"] + data["total_late"] + data["total_justified"]
        rate = round(present / total * 100, 1) if total > 0 else 0.0
        result.append(
            PracticeAttendanceSummary(
                **data,
                attendance_rate=rate,
            )
        )
    return result


@router.put("/{entry_id}", response_model=PracticeAttendanceResponse)
def update_practice_attendance(
    entry_id: int,
    payload: PracticeAttendanceUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a single practice attendance entry (status, times, observation)."""
    entry = db.query(PracticeAttendanceLog).filter(PracticeAttendanceLog.id == entry_id).first()
    if not entry:
        raise HTTPException(404, detail="Entrada de asistencia no encontrada")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(400, detail="No se proporcionaron campos para actualizar")

    if "observation" in update_data and (
        update_data["observation"] is None or update_data["observation"].strip() == ""
    ):
        update_data["observation"] = None

    old_status = entry.status
    for field, value in update_data.items():
        setattr(entry, field, value)

    entry.registered_by = current_user.ci

    db.flush()

    # Fetch teacher name and designation info for response
    teacher = db.query(Teacher).filter(Teacher.ci == entry.teacher_ci).first()
    entry = (
        db.query(PracticeAttendanceLog)
        .options(
            joinedload(PracticeAttendanceLog.designation),
            joinedload(PracticeAttendanceLog.published_schedule_assignment).joinedload(
                AcademicSchedulePublishedAssignment.block
            ),
        )
        .filter(PracticeAttendanceLog.id == entry_id)
        .one()
    )
    source = practice_attendance_source_details(entry)

    new_status = update_data.get("status", old_status)
    if new_status != old_status:
        log_activity(
            db,
            "update_practice_attendance",
            "practice_attendance",
            f"Asistencia práctica actualizada: {teacher.full_name if teacher else entry.teacher_ci} "
            f"({entry.date}) {old_status} → {new_status}",
            user=current_user,
            details={"entry_id": entry_id, "old_status": old_status, "new_status": new_status},
            request=request,
        )

    db.commit()

    return PracticeAttendanceResponse(
        id=entry.id,
        teacher_ci=entry.teacher_ci,
        teacher_name=teacher.full_name if teacher else None,
        designation_id=entry.designation_id,
        published_schedule_assignment_id=entry.published_schedule_assignment_id,
        source_kind=source.source_kind,
        source_key=source.source_key,
        subject=source.subject,
        group_code=source.group_code,
        semester=source.semester,
        date=entry.date,
        scheduled_start=entry.scheduled_start,
        scheduled_end=entry.scheduled_end,
        actual_start=entry.actual_start,
        actual_end=entry.actual_end,
        academic_hours=entry.academic_hours,
        status=entry.status,
        observation=entry.observation,
        registered_by=entry.registered_by,
        created_at=entry.created_at.isoformat() if entry.created_at else None,
    )


@router.delete("/{entry_id}")
def delete_practice_attendance(
    entry_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a single practice attendance entry."""
    entry = db.query(PracticeAttendanceLog).filter(PracticeAttendanceLog.id == entry_id).first()
    if not entry:
        raise HTTPException(404, detail="Entrada de asistencia no encontrada")

    teacher = db.query(Teacher).filter(Teacher.ci == entry.teacher_ci).first()

    log_activity(
        db,
        "delete_practice_attendance",
        "practice_attendance",
        f"Asistencia práctica eliminada: {teacher.full_name if teacher else entry.teacher_ci} ({entry.date})",
        user=current_user,
        details={"entry_id": entry_id, "teacher_ci": entry.teacher_ci, "date": str(entry.date)},
        request=request,
    )

    db.delete(entry)
    db.commit()

    return {"success": True, "deleted_id": entry_id}


@router.get("/{month}/{year}/export/pdf")
def export_practice_attendance_pdf(
    month: int,
    year: int,
    request: Request,
    start_date: date | None = None,
    end_date: date | None = None,
    teacher_ci: str | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Export practice attendance as PDF."""
    period_start, period_end = _resolve_period(month, year, start_date, end_date)
    try:
        client_ip = request.client.host if request.client else "unknown"
        filepath = generate_practice_attendance_pdf(
            db, month, year,
            start_date=period_start, end_date=period_end,
            teacher_ci=teacher_ci,
            generated_by=current_user.full_name or current_user.ci,
            generated_by_ci=current_user.ci,
            client_ip=client_ip,
        )
        return FileResponse(
            path=str(filepath),
            filename=filepath.name,
            media_type="application/pdf",
        )
    except Exception as exc:
        logger.exception("Failed to generate practice attendance PDF: %s", exc)
        raise HTTPException(status_code=500, detail="Error al generar PDF de asistencia")


@router.get("/{month}/{year}/export/excel")
def export_practice_attendance_excel(
    month: int,
    year: int,
    start_date: date | None = None,
    end_date: date | None = None,
    teacher_ci: str | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Export practice attendance as Excel."""
    period_start, period_end = _resolve_period(month, year, start_date, end_date)
    try:
        filepath = generate_practice_attendance_excel(
            db, month, year,
            start_date=period_start, end_date=period_end,
            teacher_ci=teacher_ci,
        )
        return FileResponse(
            path=str(filepath),
            filename=filepath.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        logger.exception("Failed to generate practice attendance Excel: %s", exc)
        raise HTTPException(status_code=500, detail="Error al generar Excel de asistencia")
