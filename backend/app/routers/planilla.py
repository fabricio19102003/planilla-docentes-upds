from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricUpload
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.biometric import BiometricUploadResponse
from app.schemas.planilla import (
    DashboardSummaryResponse,
    PlanillaGenerateRequest,
    PlanillaGenerateResponse,
    PlanillaOutputResponse,
)
from app.services.attendance_engine import AttendanceEngine
from app.services.planilla_generator import PlanillaGenerator
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["planilla"])


def _output_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/planilla/generate", response_model=PlanillaGenerateResponse)
def generate_planilla(
    payload: PlanillaGenerateRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PlanillaGenerateResponse:
    try:
        logger.info("Generating planilla for %02d/%d", payload.month, payload.year)
        generator = PlanillaGenerator(output_dir=str(_output_dir()))
        result = generator.generate(
            db=db,
            month=payload.month,
            year=payload.year,
            payment_overrides=payload.payment_overrides,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        log_activity(
            db,
            "generate_planilla",
            "planilla",
            f"Planilla generada: {MONTH_NAMES.get(payload.month, str(payload.month))} {payload.year}",
            user=current_user,
            details={
                "month": payload.month,
                "year": payload.year,
                "total_teachers": result.total_teachers,
                "total_hours": result.total_hours,
                "total_payment": float(result.total_payment),
            },
            request=request,
        )

        db.commit()

        if result.planilla_output_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar la planilla generada",
            )

        return PlanillaGenerateResponse(
            planilla_id=result.planilla_output_id,
            month=result.month,
            year=result.year,
            file_path=result.file_path,
            total_teachers=result.total_teachers,
            total_hours=result.total_hours,
            total_payment=result.total_payment,
            warnings=result.warnings,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Planilla generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar la planilla",
        ) from exc


@router.get("/planilla/{planilla_id}/download")
def download_planilla(
    planilla_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        planilla = db.query(PlanillaOutput).filter(PlanillaOutput.id == planilla_id).first()
        if planilla is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planilla no encontrada")

        file_path = Path(planilla.file_path or "")
        if not planilla.file_path or not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo de planilla no encontrado")

        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Planilla download failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo descargar la planilla",
        ) from exc


@router.get("/planilla/{month}/{year}/detail")
def get_planilla_detail(
    month: int,
    year: int,
    start_date: date | None = None,
    end_date: date | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return detailed planilla breakdown per teacher/designation for a given month/year.

    Optional ``start_date`` / ``end_date`` query parameters narrow the attendance
    window passed to the generator (same semantics as the generate endpoint).
    """
    try:
        generator = PlanillaGenerator()
        rows, _detail_rows, warnings = generator._build_planilla_data(
            db, month=month, year=year,
            start_date=start_date, end_date=end_date,
        )

        detail = []
        for row in rows:
            detail.append({
                "teacher_ci": row.teacher_ci,
                "teacher_name": row.teacher_name,
                "subject": row.subject,
                "semester": row.semester,
                "group_code": row.group_code,
                "base_monthly_hours": row.base_monthly_hours,
                "absent_hours": row.absent_hours,
                "payable_hours": row.payable_hours,
                "rate_per_hour": row.rate_per_hour,
                "calculated_payment": row.calculated_payment,
                "has_biometric": row.has_biometric,
                "late_count": row.late_count,
                "absent_count": row.absent_count,
                "observations": row.observations,
            })

        # Group by teacher for totals
        teacher_totals: dict = {}
        for d in detail:
            ci = d["teacher_ci"]
            if ci not in teacher_totals:
                teacher_totals[ci] = {
                    "teacher_ci": ci,
                    "teacher_name": d["teacher_name"],
                    "total_base_hours": 0,
                    "total_absent_hours": 0,
                    "total_payable_hours": 0,
                    "total_payment": 0.0,
                    "designation_count": 0,
                    "has_biometric": d["has_biometric"],
                }
            teacher_totals[ci]["total_base_hours"] += d["base_monthly_hours"]
            teacher_totals[ci]["total_absent_hours"] += d["absent_hours"]
            teacher_totals[ci]["total_payable_hours"] += d["payable_hours"]
            teacher_totals[ci]["total_payment"] += d["calculated_payment"]
            teacher_totals[ci]["designation_count"] += 1

        # Check if there is a stored planilla with potential admin overrides
        stored = (
            db.query(PlanillaOutput)
            .filter(PlanillaOutput.month == month, PlanillaOutput.year == year)
            .order_by(PlanillaOutput.generated_at.desc())
            .first()
        )

        computed_total = sum(d["calculated_payment"] for d in detail)

        # Use stored planilla total ONLY for full-month requests (no date filter).
        # Partial date ranges produce a subset of data that won't match the stored total.
        is_full_month = start_date is None and end_date is None
        use_stored = stored is not None and is_full_month

        response: dict = {
            "month": month,
            "year": year,
            "total_teachers": len(teacher_totals),
            "total_designations": len(detail),
            "total_payment": float(stored.total_payment) if use_stored else computed_total,
            "detail": detail,
            "teacher_totals": list(teacher_totals.values()),
            "warnings": warnings,
            "has_stored_planilla": stored is not None,
        }
        if stored is not None:
            response["stored_total_payment"] = float(stored.total_payment)

        return response
    except Exception as exc:
        logger.exception("Failed to load planilla detail: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el detalle de la planilla",
        ) from exc


@router.get("/teachers/{teacher_ci}/designations")
def get_teacher_designations(
    teacher_ci: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all designations (with schedule details) for a given teacher."""
    try:
        teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
        if teacher is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docente no encontrado")

        designations = db.query(Designation).filter(Designation.teacher_ci == teacher_ci).all()

        DAY_ORDER = {"lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6}

        result = []
        for d in designations:
            slots = d.schedule_json or []
            sorted_slots = sorted(slots, key=lambda s: (DAY_ORDER.get(s.get("dia", "").lower(), 99), s.get("hora_inicio", "")))
            result.append({
                "id": d.id,
                "subject": d.subject,
                "semester": d.semester,
                "group_code": d.group_code,
                "semester_hours": d.semester_hours,
                "monthly_hours": d.monthly_hours,
                "weekly_hours": d.weekly_hours,
                "schedule": [
                    {
                        "dia": slot.get("dia", ""),
                        "hora_inicio": slot.get("hora_inicio", ""),
                        "hora_fin": slot.get("hora_fin", ""),
                        "horas_academicas": slot.get("horas_academicas", 0),
                    }
                    for slot in sorted_slots
                ],
                "schedule_raw": d.schedule_raw,
            })

        return {
            "teacher_ci": teacher.ci,
            "teacher_name": teacher.full_name,
            "designation_count": len(result),
            "total_weekly_hours": sum(d.get("weekly_hours") or 0 for d in result),
            "designations": result,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to load teacher designations: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener las designaciones del docente",
        ) from exc


@router.get("/planilla/history", response_model=list[PlanillaOutputResponse])
def planilla_history(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PlanillaOutputResponse]:
    try:
        rows = db.query(PlanillaOutput).order_by(PlanillaOutput.generated_at.desc()).all()
        return [PlanillaOutputResponse.model_validate(row) for row in rows]
    except Exception as exc:
        logger.exception("Failed to load planilla history: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el historial de planillas",
        ) from exc


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    try:
        recent_uploads = (
            db.query(BiometricUpload)
            .order_by(BiometricUpload.upload_date.desc(), BiometricUpload.id.desc())
            .limit(5)
            .all()
        )
        teacher_count = db.query(func.count(Teacher.ci)).scalar() or 0
        designation_count = db.query(func.count(Designation.id)).scalar() or 0

        latest_period = (
            db.query(AttendanceRecord.month, AttendanceRecord.year)
            .order_by(desc(AttendanceRecord.year), desc(AttendanceRecord.month))
            .first()
        )

        latest_summary = None
        if latest_period is not None:
            engine = AttendanceEngine()
            base_summary = engine.get_month_summary(
                db=db,
                month=latest_period.month,
                year=latest_period.year,
            )
            total_teachers = (
                db.query(func.count(func.distinct(AttendanceRecord.teacher_ci)))
                .filter(
                    AttendanceRecord.month == latest_period.month,
                    AttendanceRecord.year == latest_period.year,
                )
                .scalar()
                or 0
            )
            from app.schemas.attendance import MonthlyAttendanceSummaryResponse

            latest_summary = MonthlyAttendanceSummaryResponse(
                total_teachers=total_teachers,
                total_slots=base_summary["total_slots"],
                attended=base_summary["by_status"]["ATTENDED"],
                late=base_summary["by_status"]["LATE"],
                absent=base_summary["by_status"]["ABSENT"],
                no_exit=base_summary["by_status"]["NO_EXIT"],
                attendance_rate=base_summary["attendance_rate"],
                total_academic_hours=base_summary["total_academic_hours"],
                observations=[],
            )

        # ── Attendance distribution (for donut chart) ────
        attendance_distribution = []
        if latest_summary:
            attendance_distribution = [
                {"name": "Asistidos", "value": latest_summary.attended, "color": "#16a34a"},
                {"name": "Tardanzas", "value": latest_summary.late, "color": "#d97706"},
                {"name": "Ausencias", "value": latest_summary.absent, "color": "#dc2626"},
                {"name": "Sin salida", "value": latest_summary.no_exit, "color": "#6b7280"},
            ]

        # ── Top earners (for bar chart) ──────────────────
        top_earners = []
        total_monthly_payment = 0.0
        if latest_period:
            try:
                gen = PlanillaGenerator()
                planilla_rows, _, _ = gen._build_planilla_data(db, month=latest_period.month, year=latest_period.year)
                teacher_payments: dict = {}
                for r in planilla_rows:
                    if r.teacher_ci not in teacher_payments:
                        teacher_payments[r.teacher_ci] = {"name": r.teacher_name, "hours": 0, "payment": 0.0}
                    teacher_payments[r.teacher_ci]["hours"] += r.payable_hours
                    teacher_payments[r.teacher_ci]["payment"] += r.calculated_payment
                total_monthly_payment = sum(v["payment"] for v in teacher_payments.values())
                top_earners = sorted(teacher_payments.values(), key=lambda x: -x["payment"])[:10]

                # If there is a stored planilla with admin overrides, use its total
                stored_planilla = (
                    db.query(PlanillaOutput)
                    .filter(
                        PlanillaOutput.month == latest_period.month,
                        PlanillaOutput.year == latest_period.year,
                    )
                    .order_by(PlanillaOutput.generated_at.desc())
                    .first()
                )
                if stored_planilla:
                    total_monthly_payment = float(stored_planilla.total_payment)
            except Exception:
                logger.warning("Could not compute top earners for dashboard")

        # ── Group distribution (for pie/bar chart) ───────
        group_dist_query = (
            db.query(Designation.group_code, func.count(Designation.id))
            .group_by(Designation.group_code)
            .order_by(func.count(Designation.id).desc())
            .all()
        )
        group_distribution = [{"group": g, "count": c} for g, c in group_dist_query]

        # ── Semester distribution ────────────────────────
        semester_dist_query = (
            db.query(Designation.semester, func.count(Designation.id))
            .group_by(Designation.semester)
            .order_by(func.count(Designation.id).desc())
            .all()
        )
        semester_distribution = [{"semester": s, "count": c} for s, c in semester_dist_query]

        # ── Pending requests ─────────────────────────────
        from app.models.detail_request import DetailRequest
        pending_requests = db.query(func.count(DetailRequest.id)).filter(DetailRequest.status == "pending").scalar() or 0

        return DashboardSummaryResponse(
            recent_uploads=[BiometricUploadResponse.model_validate(upload) for upload in recent_uploads],
            latest_attendance_summary=latest_summary,
            teacher_count=teacher_count,
            designation_count=designation_count,
            attendance_distribution=attendance_distribution,
            top_earners=top_earners,
            group_distribution=group_distribution,
            semester_distribution=semester_distribution,
            total_monthly_payment=total_monthly_payment,
            pending_requests=pending_requests,
        )
    except Exception as exc:
        logger.exception("Failed to load dashboard summary: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el resumen del dashboard",
        ) from exc
