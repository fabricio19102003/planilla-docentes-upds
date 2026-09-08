from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord, BiometricUpload
from app.models.designation import Designation
from app.models.detail_request import DetailRequest
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.auth import DetailRequestAction, DetailRequestCreate, DetailRequestResponse
from app.services import app_settings_service
from app.services.activity_logger import log_activity
from app.utils.auth import get_current_user, require_admin, require_docente

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/detail-requests", tags=["detail-requests"])

DAY_ORDER = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
}


def _schedule_resolution(req: DetailRequest, db: Session) -> dict:
    academic_period = app_settings_service.get_active_academic_period(db)
    designations = (
        db.query(Designation)
        .filter(
            Designation.teacher_ci == req.teacher_ci,
            Designation.academic_period == academic_period,
        )
        .order_by(Designation.subject, Designation.group_code, Designation.semester)
        .all()
    )
    result = []
    for designation in designations:
        raw_slots = designation.schedule_json if isinstance(designation.schedule_json, list) else []
        slots = sorted(
            raw_slots,
            key=lambda slot: (
                DAY_ORDER.get(str(slot.get("dia", "")).lower(), 99),
                str(slot.get("hora_inicio", "")),
            ),
        )
        result.append(
            {
                "subject": designation.subject,
                "semester": designation.semester,
                "group_code": designation.group_code,
                "weekly_hours": designation.weekly_hours,
                "monthly_hours": designation.monthly_hours,
                "schedule": [
                    {
                        "dia": str(slot.get("dia", "")),
                        "hora_inicio": str(slot.get("hora_inicio", "")),
                        "hora_fin": str(slot.get("hora_fin", "")),
                        "horas_academicas": int(slot.get("horas_academicas", 0)),
                    }
                    for slot in slots
                ],
            }
        )
    return {
        "kind": "schedule_detail",
        "academic_period": academic_period,
        "designations": result,
    }


def _hours_summary_resolution(req: DetailRequest, db: Session) -> dict:
    records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.teacher_ci == req.teacher_ci,
            AttendanceRecord.month == req.month,
            AttendanceRecord.year == req.year,
        )
        .all()
    )
    status_counts: dict[str, int] = {}
    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
    return {
        "kind": "hours_summary",
        "month": req.month,
        "year": req.year,
        "total_records": len(records),
        "total_academic_hours": sum(record.academic_hours for record in records),
        "status_counts": status_counts,
    }


def _biometric_resolution(req: DetailRequest, db: Session) -> dict:
    records = (
        db.query(BiometricRecord)
        .join(BiometricUpload, BiometricUpload.id == BiometricRecord.upload_id)
        .filter(
            BiometricRecord.teacher_ci == req.teacher_ci,
            BiometricUpload.month == req.month,
            BiometricUpload.year == req.year,
        )
        .order_by(BiometricRecord.date, BiometricRecord.entry_time, BiometricRecord.id)
        .all()
    )
    return {
        "kind": "biometric_detail",
        "month": req.month,
        "year": req.year,
        "records": [
            {
                "date": record.date.isoformat(),
                "entry_time": record.entry_time.isoformat() if record.entry_time else None,
                "exit_time": record.exit_time.isoformat() if record.exit_time else None,
                "worked_minutes": record.worked_minutes,
                "shift": record.shift,
            }
            for record in records
        ],
    }


def _build_resolution_snapshot(req: DetailRequest, db: Session) -> dict:
    builders = {
        "schedule_detail": _schedule_resolution,
        "hours_summary": _hours_summary_resolution,
        "biometric_detail": _biometric_resolution,
    }
    return builders[req.request_type](req, db)


def _enrich_response(req: DetailRequest, db: Session) -> DetailRequestResponse:
    """Build DetailRequestResponse, resolving teacher name."""
    teacher = db.query(Teacher).filter(Teacher.ci == req.teacher_ci).first()
    return DetailRequestResponse(
        id=req.id,
        teacher_ci=req.teacher_ci,
        teacher_name=teacher.full_name if teacher else None,
        month=req.month,
        year=req.year,
        request_type=req.request_type,
        message=req.message,
        status=req.status,
        admin_response=req.admin_response,
        resolution_snapshot=req.resolution_snapshot,
        responded_at=req.responded_at,
        created_at=req.created_at,
    )


# ------------------------------------------------------------------
# Docente endpoints
# ------------------------------------------------------------------


@router.post("", response_model=DetailRequestResponse, status_code=status.HTTP_201_CREATED)
def create_detail_request(
    payload: DetailRequestCreate,
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> DetailRequestResponse:
    """Create a new detail request (docente only)."""
    if not current_user.teacher_ci:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu cuenta de docente no tiene un docente vinculado",
        )

    valid_types = {"biometric_detail", "hours_summary", "schedule_detail"}
    if payload.request_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo de solicitud inválido. Opciones: {', '.join(valid_types)}",
        )

    try:
        req = DetailRequest(
            teacher_ci=current_user.teacher_ci,
            requested_by=current_user.id,
            month=payload.month,
            year=payload.year,
            request_type=payload.request_type,
            message=payload.message,
            status="pending",
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        return _enrich_response(req, db)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create detail request: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo crear la solicitud",
        ) from exc


@router.get("/my", response_model=list[DetailRequestResponse])
def get_my_requests(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> list[DetailRequestResponse]:
    """Get all requests made by the current docente."""
    requests = (
        db.query(DetailRequest)
        .filter(DetailRequest.requested_by == current_user.id)
        .order_by(DetailRequest.created_at.desc())
        .all()
    )
    return [_enrich_response(req, db) for req in requests]


# ------------------------------------------------------------------
# Admin endpoints
# ------------------------------------------------------------------


@router.get("", response_model=list[DetailRequestResponse])
def list_all_requests(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[DetailRequestResponse]:
    """List all detail requests (admin only)."""
    requests = (
        db.query(DetailRequest)
        .order_by(DetailRequest.created_at.desc())
        .all()
    )
    return [_enrich_response(req, db) for req in requests]


@router.put("/{request_id}/respond", response_model=DetailRequestResponse)
def respond_to_request(
    request_id: int,
    payload: DetailRequestAction,
    http_request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DetailRequestResponse:
    """Approve or reject a detail request (admin only)."""
    if payload.status not in {"approved", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El estado debe ser 'approved' o 'rejected'",
        )

    req = db.query(DetailRequest).filter(DetailRequest.id == request_id).first()
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden responder solicitudes en estado 'pending'",
        )

    try:
        req.status = payload.status
        req.admin_response = payload.admin_response
        req.resolution_snapshot = _build_resolution_snapshot(req, db)
        req.responded_by = current_user.id
        req.responded_at = datetime.utcnow()

        action_label = "aprobada" if payload.status == "approved" else "rechazada"
        log_activity(
            db,
            "respond_request",
            "requests",
            f"Solicitud #{request_id} {action_label} (docente CI: {req.teacher_ci})",
            user=current_user,
            details={
                "request_id": request_id,
                "status": payload.status,
                "teacher_ci": req.teacher_ci,
                "request_type": req.request_type,
            },
            request=http_request,
        )

        db.commit()
        db.refresh(req)
        return _enrich_response(req, db)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to respond to request %d: %s", request_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo procesar la respuesta",
        ) from exc
