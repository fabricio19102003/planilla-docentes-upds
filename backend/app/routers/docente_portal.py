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
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.teacher import TeacherResponse
from app.utils.auth import require_docente

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


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


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
    """Aggregate attendance hours into a billing summary for a given month/year."""
    rows = (
        db.query(
            AttendanceRecord.designation_id,
            func.sum(AttendanceRecord.academic_hours).label("total_hours"),
        )
        .filter(
            AttendanceRecord.teacher_ci == teacher_ci,
            AttendanceRecord.month == month,
            AttendanceRecord.year == year,
            AttendanceRecord.status.in_(["ATTENDED", "LATE"]),
        )
        .group_by(AttendanceRecord.designation_id)
        .all()
    )

    designation_ids = [row.designation_id for row in rows]
    hours_by_designation = {row.designation_id: int(row.total_hours or 0) for row in rows}

    designations: list[DesignationBilling] = []
    total_hours = 0

    rate = settings.HOURLY_RATE

    if designation_ids:
        desigs = db.query(Designation).filter(Designation.id.in_(designation_ids)).all()
        for d in desigs:
            h = hours_by_designation.get(d.id, 0)
            total_hours += h
            designations.append(
                DesignationBilling(
                    subject=d.subject,
                    group=d.group_code,
                    hours=h,
                    semester=d.semester,
                    payment=round(h * rate, 2),
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
    """Get current month billing summary for the authenticated docente."""
    teacher = _get_teacher_or_raise(current_user, db)
    now = datetime.now()
    return _build_billing(teacher.ci, now.month, now.year, db)


@router.get("/billing/history", response_model=list[BillingHistoryItem])
def get_billing_history(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> list[BillingHistoryItem]:
    """Get billing history (all months with attendance data) for the authenticated docente."""
    teacher = _get_teacher_or_raise(current_user, db)

    # Get distinct month/year combinations that have attendance data
    periods = (
        db.query(AttendanceRecord.month, AttendanceRecord.year)
        .filter(
            AttendanceRecord.teacher_ci == teacher.ci,
            AttendanceRecord.status.in_(["ATTENDED", "LATE"]),
        )
        .distinct()
        .order_by(AttendanceRecord.year.desc(), AttendanceRecord.month.desc())
        .all()
    )

    history: list[BillingHistoryItem] = []
    for period in periods:
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
