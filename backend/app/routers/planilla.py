from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricUpload
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.teacher import Teacher
from app.schemas.biometric import BiometricUploadResponse
from app.schemas.planilla import (
    DashboardSummaryResponse,
    PlanillaGenerateRequest,
    PlanillaGenerateResponse,
    PlanillaOutputResponse,
)
from app.services.attendance_engine import AttendanceEngine
from app.services.planilla_generator import PlanillaGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["planilla"])


def _output_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/planilla/generate", response_model=PlanillaGenerateResponse)
def generate_planilla(
    payload: PlanillaGenerateRequest,
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
def download_planilla(planilla_id: int, db: Session = Depends(get_db)) -> FileResponse:
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


@router.get("/planilla/history", response_model=list[PlanillaOutputResponse])
def planilla_history(db: Session = Depends(get_db)) -> list[PlanillaOutputResponse]:
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
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummaryResponse:
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

        return DashboardSummaryResponse(
            recent_uploads=[BiometricUploadResponse.model_validate(upload) for upload in recent_uploads],
            latest_attendance_summary=latest_summary,
            teacher_count=teacher_count,
            designation_count=designation_count,
        )
    except Exception as exc:
        logger.exception("Failed to load dashboard summary: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el resumen del dashboard",
        ) from exc
