from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, time as time_type

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.designation import Designation
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

    # Determine date range
    if payload.start_date and payload.end_date:
        period_start = payload.start_date
        period_end = payload.end_date
    else:
        period_start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        period_end = date(year, month, last_day)

    if period_start > period_end:
        raise HTTPException(400, detail="start_date no puede ser posterior a end_date")

    academic_period = app_settings_service.get_active_academic_period(db)

    # Get all practice designations for the active period
    practice_designations = (
        db.query(Designation)
        .filter(
            Designation.designation_type == "practice",
            Designation.academic_period == academic_period,
        )
        .all()
    )

    if not practice_designations:
        raise HTTPException(
            404,
            detail="No se encontraron designaciones de práctica para el período académico activo",
        )

    # Build a set of existing entries to avoid duplicates
    existing = set()
    existing_rows = (
        db.query(
            PracticeAttendanceLog.teacher_ci,
            PracticeAttendanceLog.designation_id,
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
        existing.add((row[0], row[1], row[2], row[3]))

    created = 0
    num_days = (period_end - period_start).days + 1

    for desig in practice_designations:
        schedule_json = desig.schedule_json or []
        if not schedule_json:
            continue

        # Build weekday → list of slots mapping
        slots_by_weekday: dict[str, list[dict]] = {}
        for slot in schedule_json:
            dia = _normalize_day(slot.get("dia", ""))
            if dia:
                slots_by_weekday.setdefault(dia, []).append(slot)

        # Iterate each day in the range
        from datetime import timedelta

        for i in range(num_days):
            current_date = period_start + timedelta(days=i)
            weekday_name = WEEKDAY_MAP.get(current_date.weekday(), "")
            day_slots = slots_by_weekday.get(weekday_name, [])

            for slot in day_slots:
                hora_inicio = _parse_time(slot.get("hora_inicio", ""))
                hora_fin = _parse_time(slot.get("hora_fin", ""))
                academic_hours = int(slot.get("horas_academicas", 0) or 0)

                if not hora_inicio or not hora_fin:
                    continue

                key = (desig.teacher_ci, desig.id, current_date, hora_inicio)
                if key in existing:
                    continue

                entry = PracticeAttendanceLog(
                    teacher_ci=desig.teacher_ci,
                    designation_id=desig.id,
                    date=current_date,
                    scheduled_start=hora_inicio,
                    scheduled_end=hora_fin,
                    academic_hours=academic_hours,
                    status="absent",
                    registered_by=current_user.ci,
                )
                db.add(entry)
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
    # Default date range = full month
    if start_date is None:
        start_date = date(year, month, 1)
    if end_date is None:
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

    query = (
        db.query(PracticeAttendanceLog, Teacher.full_name, Designation.subject, Designation.group_code, Designation.semester)
        .join(Teacher, Teacher.ci == PracticeAttendanceLog.teacher_ci)
        .join(Designation, Designation.id == PracticeAttendanceLog.designation_id)
        .filter(
            PracticeAttendanceLog.date >= start_date,
            PracticeAttendanceLog.date <= end_date,
        )
    )

    if teacher_ci:
        query = query.filter(PracticeAttendanceLog.teacher_ci == teacher_ci)

    query = query.order_by(Teacher.full_name, PracticeAttendanceLog.date, PracticeAttendanceLog.scheduled_start)
    rows = query.all()

    result = []
    for log, teacher_name, subject, group_code, semester in rows:
        result.append(
            PracticeAttendanceResponse(
                id=log.id,
                teacher_ci=log.teacher_ci,
                teacher_name=teacher_name,
                designation_id=log.designation_id,
                subject=subject,
                group_code=group_code,
                semester=semester,
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
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Calculate attendance summary per teacher for the given period."""
    period_start = date(year, month, 1)
    _, last_day = monthrange(year, month)
    period_end = date(year, month, last_day)

    rows = (
        db.query(PracticeAttendanceLog, Teacher.full_name)
        .join(Teacher, Teacher.ci == PracticeAttendanceLog.teacher_ci)
        .filter(
            PracticeAttendanceLog.date >= period_start,
            PracticeAttendanceLog.date <= period_end,
        )
        .all()
    )

    # Group by teacher
    from collections import defaultdict

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

    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(400, detail="No se proporcionaron campos para actualizar")

    old_status = entry.status
    for field, value in update_data.items():
        setattr(entry, field, value)

    entry.registered_by = current_user.ci

    db.flush()

    # Fetch teacher name and designation info for response
    teacher = db.query(Teacher).filter(Teacher.ci == entry.teacher_ci).first()
    desig = db.query(Designation).filter(Designation.id == entry.designation_id).first()

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
        subject=desig.subject if desig else None,
        group_code=desig.group_code if desig else None,
        semester=desig.semester if desig else None,
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
