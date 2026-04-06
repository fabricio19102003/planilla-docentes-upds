from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.billing_publication import BillingPublication
from app.models.notification import Notification
from app.models.planilla import PlanillaOutput
from app.models.user import User
from app.services.planilla_generator import PlanillaGenerator
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing-publication"])

# Month name lookup
MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------


class PublishRequest(BaseModel):
    month: int
    year: int
    notes: Optional[str] = None


class UnpublishRequest(BaseModel):
    month: int
    year: int


class PublicationResponse(BaseModel):
    id: int
    month: int
    year: int
    status: str
    total_teachers: int
    total_payment: float
    published_by: Optional[int]
    published_at: Optional[datetime]
    unpublished_at: Optional[datetime]
    notes: Optional[str]


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.post("/publish", response_model=PublicationResponse)
def publish_billing(
    payload: PublishRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PublicationResponse:
    """Publish billing for a given month/year. Creates notifications for all docentes."""
    try:
        month = payload.month
        year = payload.year

        if not (1 <= month <= 12):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mes inválido")
        if year < 2000 or year > 2100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Año inválido")

        # Get snapshot from planilla generator.
        # Prefer the stored PlanillaOutput (generated with admin overrides) over live recalculation.
        generator = PlanillaGenerator()
        billing_snapshot = None
        try:
            # Check for an existing generated planilla (which includes admin overrides)
            stored_planilla = (
                db.query(PlanillaOutput)
                .filter(PlanillaOutput.month == month, PlanillaOutput.year == year)
                .order_by(PlanillaOutput.generated_at.desc())
                .first()
            )

            # Retrieve stored overrides if a planilla was generated with admin adjustments
            stored_overrides: dict[str, float] = {}
            if stored_planilla and stored_planilla.payment_overrides_json:
                stored_overrides = stored_planilla.payment_overrides_json

            # Use stored start/end dates when a generated planilla exists
            sd = stored_planilla.start_date if stored_planilla else None
            ed = stored_planilla.end_date if stored_planilla else None
            rows, _detail_rows, _warnings = generator._build_planilla_data(
                db, month=month, year=year, start_date=sd, end_date=ed
            )
            total_teachers = len({r.teacher_ci for r in rows})

            # Resolve overrides using the generator's canonical logic
            # (handles teacher-level override minus row-level overrides correctly)
            resolved_payments: dict[str, float] = {}  # "teacher_ci:designation_id" → effective_payment
            if stored_overrides:
                for row in rows:
                    row_key = f"{row.teacher_ci}:{row.designation_id}"
                    override = generator._resolve_override(row.teacher_ci, row.designation_id, stored_overrides)
                    if override is not None:
                        # Simple row-level or plain teacher-level — use as-is only if no
                        # teacher-level allocation is needed (allocations take precedence)
                        teacher_rows = [r for r in rows if r.teacher_ci == row.teacher_ci]
                        allocations = generator._get_teacher_override_allocations(teacher_rows, stored_overrides)
                        if allocations is not None and row.designation_id in allocations:
                            resolved_payments[row_key] = float(allocations[row.designation_id])
                        elif allocations is None:
                            # No teacher-level override: check row-level directly
                            row_level = stored_overrides.get(row_key)
                            if row_level is not None:
                                resolved_payments[row_key] = float(row_level)

            # Build per-teacher snapshot
            teacher_map: dict[str, dict] = {}
            for row in rows:
                if row.teacher_ci not in teacher_map:
                    teacher_map[row.teacher_ci] = {
                        "teacher_ci": row.teacher_ci,
                        "teacher_name": row.teacher_name,
                        "has_biometric": row.has_biometric,
                        "has_retention": row.has_retention,
                        "designations": [],
                        "total_hours": 0,
                        "gross_payment": 0.0,
                        "total_payment": 0.0,
                        "retention_amount": 0.0,
                        "final_payment": 0.0,
                    }
                t = teacher_map[row.teacher_ci]

                row_key = f"{row.teacher_ci}:{row.designation_id}"
                effective_payment = resolved_payments.get(row_key, row.final_payment)

                row_retention = row.retention_amount if row_key not in resolved_payments else 0.0
                t["designations"].append({
                    "subject": row.subject,
                    "group": row.group_code,
                    "semester": row.semester,
                    "base_hours": row.base_monthly_hours,
                    "absent_hours": row.absent_hours,
                    "payable_hours": row.payable_hours,
                    "gross_payment": round(row.calculated_payment, 2),   # Bruto (before retention)
                    "retention_amount": round(row_retention, 2),
                    "payment": round(effective_payment, 2),               # Neto (after retention + overrides)
                })
                t["total_hours"] += row.payable_hours
                t["gross_payment"] = round(t.get("gross_payment", 0.0) + row.calculated_payment, 2)
                t["retention_amount"] = round(t.get("retention_amount", 0.0) + row_retention, 2)
                t["total_payment"] += effective_payment
                t["final_payment"] = round(float(t["total_payment"]), 2)

            if stored_planilla:
                total_payment = float(stored_planilla.total_payment)
                snapshot_source = "planilla_output"
                planilla_id = stored_planilla.id
                logger.info(
                    "Publish: using stored PlanillaOutput id=%d for %d/%d (total=%.2f, overrides=%d)",
                    stored_planilla.id, month, year, total_payment, len(stored_overrides),
                )
            else:
                total_payment = sum(r.final_payment for r in rows)
                snapshot_source = "live_calculation"
                planilla_id = None
                logger.warning(
                    "Publish: no stored PlanillaOutput for %d/%d — using live calculation",
                    month, year,
                )

            billing_snapshot = {
                "teacher_details": list(teacher_map.values()),
                "total_payment": float(total_payment),
                "total_teachers": total_teachers,
                "rate_per_hour": 70.0,
                "generated_at": datetime.now().isoformat(),
                "source": snapshot_source,
                "planilla_id": planilla_id,
            }
        except Exception as exc:
            logger.exception("Failed to build planilla snapshot for %d/%d: %s", month, year, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo generar la facturación. Verificá que existan designaciones y datos de asistencia para este período.",
            ) from exc

        # Create or update BillingPublication
        now = datetime.now()
        publication = (
            db.query(BillingPublication)
            .filter(BillingPublication.month == month, BillingPublication.year == year)
            .first()
        )

        if publication is None:
            publication = BillingPublication(
                month=month,
                year=year,
                status="published",
                version=1,
                total_teachers=total_teachers,
                total_payment=total_payment,
                published_by=current_user.id,
                published_at=now,
                unpublished_at=None,
                notes=payload.notes,
                billing_snapshot=billing_snapshot,
            )
            db.add(publication)
        else:
            publication.status = "published"
            publication.version = (publication.version or 1) + 1  # increment on each re-publish
            publication.total_teachers = total_teachers
            publication.total_payment = total_payment
            publication.published_by = current_user.id
            publication.published_at = now
            publication.unpublished_at = None
            publication.billing_snapshot = billing_snapshot
            if payload.notes is not None:
                publication.notes = payload.notes

        db.flush()  # Get ID if new

        # Remove old notifications for this period to prevent spam on re-publish
        db.query(Notification).filter(
            Notification.notification_type == "billing_published",
            Notification.reference_month == month,
            Notification.reference_year == year,
        ).delete()
        db.flush()

        # Create notifications for ALL docente users
        docente_users = db.query(User).filter(User.role == "docente", User.is_active == True).all()
        month_name = MONTH_NAMES.get(month, str(month))

        for docente in docente_users:
            notif = Notification(
                user_id=docente.id,
                title=f"Facturación {month_name} {year} publicada",
                message=(
                    f"El monto a facturar para {month_name} {year} ya está disponible. "
                    f"Revisá tu portal para ver el detalle."
                ),
                notification_type="billing_published",
                is_read=False,
                reference_month=month,
                reference_year=year,
            )
            db.add(notif)

        log_activity(
            db,
            "publish_billing",
            "billing",
            f"Facturación publicada: {month_name} {year} ({total_teachers} docentes, Bs {total_payment:,.2f})",
            user=current_user,
            details={
                "month": month,
                "year": year,
                "total_teachers": total_teachers,
                "total_payment": float(total_payment),
            },
            request=request,
        )

        db.commit()
        db.refresh(publication)

        logger.info(
            "Billing published for %d/%d by user %d — %d teachers, Bs %.2f",
            month, year, current_user.id, total_teachers, total_payment,
        )

        return PublicationResponse(
            id=publication.id,
            month=publication.month,
            year=publication.year,
            status=publication.status,
            total_teachers=publication.total_teachers,
            total_payment=float(publication.total_payment),
            published_by=publication.published_by,
            published_at=publication.published_at,
            unpublished_at=publication.unpublished_at,
            notes=publication.notes,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to publish billing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo publicar la facturación",
        ) from exc


@router.post("/unpublish", response_model=PublicationResponse)
def unpublish_billing(
    payload: UnpublishRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PublicationResponse:
    """Unpublish billing for a given month/year to allow adjustments."""
    try:
        publication = (
            db.query(BillingPublication)
            .filter(
                BillingPublication.month == payload.month,
                BillingPublication.year == payload.year,
            )
            .first()
        )

        if publication is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe publicación para este mes/año",
            )

        publication.status = "draft"
        publication.unpublished_at = datetime.now()

        log_activity(
            db,
            "unpublish_billing",
            "billing",
            f"Facturación despublicada: {MONTH_NAMES.get(payload.month, str(payload.month))} {payload.year}",
            user=current_user,
            details={"month": payload.month, "year": payload.year},
            request=request,
        )

        db.commit()
        db.refresh(publication)

        logger.info("Billing unpublished for %d/%d", payload.month, payload.year)

        return PublicationResponse(
            id=publication.id,
            month=publication.month,
            year=publication.year,
            status=publication.status,
            total_teachers=publication.total_teachers,
            total_payment=float(publication.total_payment),
            published_by=publication.published_by,
            published_at=publication.published_at,
            unpublished_at=publication.unpublished_at,
            notes=publication.notes,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to unpublish billing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo despublicar la facturación",
        ) from exc


@router.get("/publications", response_model=list[PublicationResponse])
def list_publications(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PublicationResponse]:
    """List all billing publications ordered by year desc, month desc."""
    try:
        publications = (
            db.query(BillingPublication)
            .order_by(BillingPublication.year.desc(), BillingPublication.month.desc())
            .all()
        )
        return [
            PublicationResponse(
                id=p.id,
                month=p.month,
                year=p.year,
                status=p.status,
                total_teachers=p.total_teachers,
                total_payment=float(p.total_payment),
                published_by=p.published_by,
                published_at=p.published_at,
                unpublished_at=p.unpublished_at,
                notes=p.notes,
            )
            for p in publications
        ]
    except Exception as exc:
        logger.exception("Failed to list publications: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo obtener el listado de publicaciones",
        ) from exc


@router.get("/publication/{month}/{year}", response_model=PublicationResponse)
def get_publication(
    month: int,
    year: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PublicationResponse:
    """Check if a specific month/year has a billing publication."""
    publication = (
        db.query(BillingPublication)
        .filter(BillingPublication.month == month, BillingPublication.year == year)
        .first()
    )
    if publication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe publicación para este mes/año",
        )
    return PublicationResponse(
        id=publication.id,
        month=publication.month,
        year=publication.year,
        status=publication.status,
        total_teachers=publication.total_teachers,
        total_payment=float(publication.total_payment),
        published_by=publication.published_by,
        published_at=publication.published_at,
        unpublished_at=publication.unpublished_at,
        notes=publication.notes,
    )
