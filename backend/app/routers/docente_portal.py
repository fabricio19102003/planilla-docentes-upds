from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models.attendance import AttendanceRecord
from app.models.billing_publication import BillingPublication
from app.models.designation import Designation
from app.models.notification import Notification
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.teacher import TeacherResponse
from app.utils.auth import require_docente

# Map Python weekday() index → Spanish lowercase day name
_WEEKDAY_MAP: dict[int, str] = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo",
}
# Accent-free alternates for robust matching
_WEEKDAY_ALT: dict[int, str] = {
    2: "miercoles", 5: "sabado",
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portal", tags=["docente-portal"])

# Month name lookup
MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# ------------------------------------------------------------------
# Response schemas (inline — portal-specific)
# ------------------------------------------------------------------


class DesignationBilling(BaseModel):
    subject: str
    group: str
    hours: int
    semester: str
    payment: float = 0.0


class BillingResponse(BaseModel):
    month: int
    year: int
    month_name: str
    total_hours: int
    rate_per_hour: float
    total_payment: float
    adjusted_payment: Optional[float] = None
    designations: list[DesignationBilling]


class BillingHistoryItem(BaseModel):
    month: int
    year: int
    month_name: str
    total_hours: int
    total_payment: float
    adjusted_payment: Optional[float] = None
    designations: list[DesignationBilling] = []


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ci: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    external_permanent: Optional[str] = None
    academic_level: Optional[str] = None
    profession: Optional[str] = None
    specialty: Optional[str] = None
    bank: Optional[str] = None
    account_number: Optional[str] = None
    designation_count: int = 0


class ProfileUpdateRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    bank: Optional[str] = None
    account_number: Optional[str] = None


class ScheduleSlotResponse(BaseModel):
    dia: str
    hora_inicio: str
    hora_fin: str
    horas_academicas: int


class DesignationScheduleResponse(BaseModel):
    subject: str
    semester: str
    group_code: str
    weekly_hours: Optional[int] = None
    monthly_hours: Optional[int] = None
    schedule: list[ScheduleSlotResponse]


class MyScheduleResponse(BaseModel):
    teacher_name: str
    designation_count: int
    total_weekly_hours: int
    designations: list[DesignationScheduleResponse]


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    reference_month: Optional[int] = None
    reference_year: Optional[int] = None
    created_at: datetime


class UnreadCountResponse(BaseModel):
    count: int


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _get_slot_hours_for_absent(schedule: list[dict], rec: AttendanceRecord) -> int:
    """
    Recover the scheduled academic hours for an ABSENT attendance record.

    The attendance engine writes academic_hours=0 on ABSENT records, so we
    cannot simply sum that column.  Instead we look up the matching slot in
    designation.schedule_json using the same three-pass strategy as
    PlanillaGenerator._get_slot_hours():

      Pass 1 — weekday name + hora_inicio  (most specific)
      Pass 2 — hora_inicio only             (fallback when slot lacks "dia")
      Pass 3 — weekly average               (last-resort estimate)
    """
    if not schedule or rec.date is None:
        return 0

    rec_start_str = rec.scheduled_start.strftime("%H:%M")
    target_weekday = rec.date.weekday()
    target_day = _WEEKDAY_MAP.get(target_weekday, "")
    target_day_alt = _WEEKDAY_ALT.get(target_weekday, target_day)

    # Pass 1: weekday + hora_inicio
    for slot in schedule:
        slot_dia = slot.get("dia", "").lower()
        if slot.get("hora_inicio", "") == rec_start_str and slot_dia in (target_day, target_day_alt):
            return int(slot.get("horas_academicas", 0))

    # Pass 2: hora_inicio only (slot may lack "dia" field)
    for slot in schedule:
        if slot.get("hora_inicio", "") == rec_start_str:
            return int(slot.get("horas_academicas", 0))

    # Pass 3: weekly average across all slots (last resort)
    if schedule:
        total_weekly = sum(int(s.get("horas_academicas", 0)) for s in schedule)
        return total_weekly // max(len(schedule), 1)

    return 0


def _get_teacher_or_raise(current_user: User, db: Session) -> Teacher:
    if not current_user.teacher_ci:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu cuenta no tiene un docente vinculado",
        )
    teacher = db.query(Teacher).filter(Teacher.ci == current_user.teacher_ci).first()
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docente vinculado no encontrado",
        )
    return teacher


def _build_billing(teacher_ci: str, month: int, year: int, db: Session) -> BillingResponse:
    """
    Build billing summary for a teacher using Payment Model C.

    Model C:
      - Base = designation.monthly_hours (assigned load)
      - Deduct ONLY ABSENT hours from base
      - Teachers without biometric data for the period get full pay (0 deductions)
    """
    from app.models.biometric import BiometricRecord, BiometricUpload  # avoid circular at module level

    rate = settings.HOURLY_RATE

    # Get all designations for this teacher
    all_designations = db.query(Designation).filter(Designation.teacher_ci == teacher_ci).all()

    # Check if teacher has biometric data scoped to THIS specific period
    has_biometric = (
        db.query(BiometricRecord.id)
        .join(BiometricUpload, BiometricRecord.upload_id == BiometricUpload.id)
        .filter(
            BiometricRecord.teacher_ci == teacher_ci,
            BiometricUpload.month == month,
            BiometricUpload.year == year,
        )
        .first()
        is not None
    )

    designations: list[DesignationBilling] = []
    total_hours = 0

    for d in all_designations:
        base_hours = d.monthly_hours or 0

        if has_biometric:
            # Model C: deduct ABSENT hours using scheduled slot hours from schedule_json.
            # IMPORTANT: AttendanceRecord.academic_hours is always 0 for ABSENT records
            # (set by the attendance engine), so summing that column returns 0 and absences
            # are never deducted.  Instead, count ABSENT records and recover the scheduled
            # hours from designation.schedule_json — same logic as PlanillaGenerator._get_slot_hours().
            absent_records = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.teacher_ci == teacher_ci,
                    AttendanceRecord.designation_id == d.id,
                    AttendanceRecord.month == month,
                    AttendanceRecord.year == year,
                    AttendanceRecord.status == "ABSENT",
                )
                .all()
            )

            schedule: list[dict] = d.schedule_json or []
            absent_hours = 0

            for rec in absent_records:
                slot_hours = _get_slot_hours_for_absent(schedule, rec)
                absent_hours += slot_hours
        else:
            absent_hours = 0

        payable = max(0, base_hours - absent_hours)
        total_hours += payable
        designations.append(
            DesignationBilling(
                subject=d.subject,
                group=d.group_code,
                hours=payable,
                semester=d.semester,
                payment=round(payable * rate, 2),
            )
        )

    total_payment = round(total_hours * rate, 2)

    return BillingResponse(
        month=month,
        year=year,
        month_name=MONTH_NAMES.get(month, str(month)),
        total_hours=total_hours,
        rate_per_hour=rate,
        total_payment=total_payment,
        adjusted_payment=None,
        designations=designations,
    )


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/billing/current", response_model=BillingResponse)
def get_current_billing(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> BillingResponse:
    """Get current month billing summary for the authenticated docente.

    Returns 404 if the current month's billing has not been published by admin.
    """
    teacher = _get_teacher_or_raise(current_user, db)
    now = datetime.now()

    # Check publication status before returning billing
    publication = (
        db.query(BillingPublication)
        .filter(
            BillingPublication.month == now.month,
            BillingPublication.year == now.year,
            BillingPublication.status == "published",
        )
        .first()
    )
    if not publication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La facturación de este mes aún no ha sido publicada",
        )

    return _build_billing(teacher.ci, now.month, now.year, db)


@router.get("/billing/history", response_model=list[BillingHistoryItem])
def get_billing_history(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> list[BillingHistoryItem]:
    """Get billing history for the authenticated docente.

    Only returns periods that have a published BillingPublication.
    """
    teacher = _get_teacher_or_raise(current_user, db)

    # Get distinct month/year combinations that have ANY attendance data
    # (Model C: we show all periods with records, not just ATTENDED/LATE)
    periods = (
        db.query(AttendanceRecord.month, AttendanceRecord.year)
        .filter(AttendanceRecord.teacher_ci == teacher.ci)
        .distinct()
        .order_by(AttendanceRecord.year.desc(), AttendanceRecord.month.desc())
        .all()
    )

    # Only return periods that have a published BillingPublication
    published_periods = (
        db.query(BillingPublication.month, BillingPublication.year)
        .filter(BillingPublication.status == "published")
        .all()
    )
    published_set = {(p.month, p.year) for p in published_periods}

    history: list[BillingHistoryItem] = []
    for period in periods:
        if (period.month, period.year) not in published_set:
            continue
        billing = _build_billing(teacher.ci, period.month, period.year, db)
        history.append(
            BillingHistoryItem(
                month=billing.month,
                year=billing.year,
                month_name=billing.month_name,
                total_hours=billing.total_hours,
                total_payment=billing.total_payment,
                adjusted_payment=billing.adjusted_payment,
                designations=billing.designations,
            )
        )

    return history


@router.get("/profile", response_model=ProfileResponse)
def get_docente_profile(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Get authenticated docente's own teacher profile with designation count."""
    teacher = _get_teacher_or_raise(current_user, db)

    # Load designations count
    designation_count = (
        db.query(func.count(Designation.id)).filter(Designation.teacher_ci == teacher.ci).scalar() or 0
    )

    return ProfileResponse(
        ci=teacher.ci,
        full_name=teacher.full_name,
        email=teacher.email,
        phone=teacher.phone,
        gender=teacher.gender,
        external_permanent=teacher.external_permanent,
        academic_level=teacher.academic_level,
        profession=teacher.profession,
        specialty=teacher.specialty,
        bank=teacher.bank,
        account_number=teacher.account_number,
        designation_count=int(designation_count),
    )


@router.put("/profile")
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> dict:
    """Update docente's personal information (email, phone, bank, account_number)."""
    teacher = _get_teacher_or_raise(current_user, db)

    if payload.email is not None:
        teacher.email = payload.email
        current_user.email = payload.email
    if payload.phone is not None:
        teacher.phone = payload.phone
    if payload.bank is not None:
        teacher.bank = payload.bank
    if payload.account_number is not None:
        teacher.account_number = payload.account_number

    db.commit()
    db.refresh(teacher)

    return {
        "success": True,
        "message": "Perfil actualizado correctamente",
    }


@router.get("/schedule/pdf")
def export_schedule_pdf(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
):
    """Generate and return a PDF of the docente's weekly schedule."""
    from fastapi.responses import FileResponse

    from app.services.schedule_pdf import generate_schedule_pdf

    teacher = _get_teacher_or_raise(current_user, db)
    designations = db.query(Designation).filter(Designation.teacher_ci == teacher.ci).all()

    pdf_path = generate_schedule_pdf(teacher, designations)

    safe_name = teacher.full_name.replace(' ', '_')
    return FileResponse(
        path=pdf_path,
        filename=f"horario_{safe_name}.pdf",
        media_type="application/pdf",
    )


@router.get("/schedule", response_model=MyScheduleResponse)
def get_my_schedule(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> MyScheduleResponse:
    """Get the authenticated docente's weekly schedule with all designations."""
    teacher = _get_teacher_or_raise(current_user, db)

    DAY_ORDER: dict[str, int] = {
        "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
        "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5,
    }

    designations = db.query(Designation).filter(Designation.teacher_ci == teacher.ci).all()

    result: list[DesignationScheduleResponse] = []
    for d in designations:
        slots = d.schedule_json or []
        sorted_slots = sorted(
            slots,
            key=lambda s: (DAY_ORDER.get(s.get("dia", "").lower(), 99), s.get("hora_inicio", "")),
        )
        result.append(
            DesignationScheduleResponse(
                subject=d.subject,
                semester=d.semester,
                group_code=d.group_code,
                weekly_hours=d.weekly_hours,
                monthly_hours=d.monthly_hours,
                schedule=[
                    ScheduleSlotResponse(
                        dia=s.get("dia", ""),
                        hora_inicio=s.get("hora_inicio", ""),
                        hora_fin=s.get("hora_fin", ""),
                        horas_academicas=int(s.get("horas_academicas", 0)),
                    )
                    for s in sorted_slots
                ],
            )
        )

    total_weekly_hours = sum(d.weekly_hours or 0 for d in designations)

    return MyScheduleResponse(
        teacher_name=teacher.full_name,
        designation_count=len(result),
        total_weekly_hours=total_weekly_hours,
        designations=result,
    )


# ------------------------------------------------------------------
# Notification endpoints
# ------------------------------------------------------------------


@router.get("/notifications", response_model=list[NotificationResponse])
def get_notifications(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> list[NotificationResponse]:
    """Get the 20 most recent notifications for the authenticated docente."""
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        NotificationResponse(
            id=n.id,
            title=n.title,
            message=n.message,
            notification_type=n.notification_type,
            is_read=n.is_read,
            reference_month=n.reference_month,
            reference_year=n.reference_year,
            created_at=n.created_at,
        )
        for n in notifications
    ]


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> UnreadCountResponse:
    """Get the count of unread notifications for the authenticated docente."""
    count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)  # noqa: E712
        .scalar()
        or 0
    )
    return UnreadCountResponse(count=int(count))


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> dict:
    """Mark a specific notification as read."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada",
        )
    notification.is_read = True
    db.commit()
    return {"success": True}


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> dict:
    """Mark all notifications as read for the authenticated docente."""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"success": True}
