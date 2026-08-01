from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.billing_publication import BillingPublication
from app.models.notification import Notification
from app.models.planilla import PlanillaOutput
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.user import User
from app.services.planilla_generator import PayrollDataError, PlanillaGenerator
from app.services.practice_planilla_generator import PracticePlanillaGenerator
from app.services.activity_logger import log_activity
from app.services import app_settings_service
from app.services.email_service import EmailService
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


class SendBillingEmailsRequest(BaseModel):
    month: int
    year: int
    teacher_cis: list[str]


class SendBillingEmailsResponse(BaseModel):
    sent: int
    failed: int
    skipped: int


class PublicationResponse(BaseModel):
    id: int
    month: int
    year: int
    planilla_type: str = "regular"
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

        # Require an existing, approved PlanillaOutput — publication must NEVER bypass the
        # approval workflow by falling back to live calculation.
        stored_planilla = (
            db.query(PlanillaOutput)
            .filter(PlanillaOutput.month == month, PlanillaOutput.year == year)
            .order_by(PlanillaOutput.generated_at.desc())
            .first()
        )

        if not stored_planilla:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No existe una planilla generada para este período. Genere una planilla primero.",
            )

        if stored_planilla.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La planilla debe estar aprobada antes de publicar (estado actual: {stored_planilla.status})",
            )

        generator = PlanillaGenerator()
        billing_snapshot = None
        try:
            # Retrieve stored overrides if a planilla was generated with admin adjustments
            stored_overrides: dict[str, float] = {}
            if stored_planilla.payment_overrides_json:
                stored_overrides = stored_planilla.payment_overrides_json

            # Use stored start/end dates and discount_mode from the approved planilla.
            # `discount_mode` is a NOT NULL column with a default of "attendance",
            # so direct attribute access is always safe — no defensive getattr needed.
            sd = stored_planilla.start_date
            ed = stored_planilla.end_date
            dm = stored_planilla.discount_mode

            # Load stored exclusions so published amounts match the approved planilla
            stored_exclusions = None
            if stored_planilla.excluded_days_json:
                try:
                    from app.schemas.planilla import ExcludedDaySchema
                    stored_exclusions = [
                        ExcludedDaySchema.model_validate(item)
                        for item in stored_planilla.excluded_days_json
                    ]
                except Exception as exc:
                    raise PayrollDataError(
                        "La planilla aprobada contiene exclusiones inválidas; regenerala antes de publicar",
                        code="invalid_stored_exclusions",
                    ) from exc

            rows, _detail_rows, _warnings = generator._build_planilla_data(
                db, month=month, year=year, start_date=sd, end_date=ed,
                discount_mode=dm,
                excluded_days=stored_exclusions,
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

            total_payment = float(stored_planilla.total_payment)
            planilla_id = stored_planilla.id
            logger.info(
                "Publish: using approved PlanillaOutput id=%d for %d/%d (total=%.2f, overrides=%d)",
                stored_planilla.id, month, year, total_payment, len(stored_overrides),
            )

            billing_snapshot = {
                "teacher_details": list(teacher_map.values()),
                "total_payment": float(total_payment),
                "total_teachers": total_teachers,
                "rate_per_hour": app_settings_service.get_hourly_rate(db),
                "start_date": str(stored_planilla.start_date) if stored_planilla.start_date else None,
                "end_date": str(stored_planilla.end_date) if stored_planilla.end_date else None,
                "excluded_days_json": stored_planilla.excluded_days_json or [],
                "generated_at": datetime.now().isoformat(),
                "source": "planilla_output",
                "planilla_id": planilla_id,
                "discount_mode": dm,
            }
        except HTTPException:
            raise
        except PayrollDataError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=exc.as_detail(),
            ) from exc
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
            .filter(
                BillingPublication.month == month,
                BillingPublication.year == year,
                BillingPublication.planilla_type == "regular",
            )
            .first()
        )

        if publication is None:
            publication = BillingPublication(
                month=month,
                year=year,
                planilla_type="regular",
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

        # Create notifications for ALL active docente users and keep their linked
        # Teacher row available for the post-commit email step (email fallback + CI match).
        docente_users = (
            db.query(User)
            .options(joinedload(User.teacher))
            .filter(User.role == "docente", User.is_active == True)
            .all()
        )
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

        try:
            email_result = EmailService().send_billing_published(publication, docente_users)
            logger.info(
                "Billing publication email step completed for %d/%d: eligible=%d sent=%d failed=%d skipped=%d",
                month,
                year,
                email_result.eligible,
                email_result.sent,
                email_result.failed,
                email_result.skipped,
            )
        except Exception as exc:  # pragma: no cover - defensive best-effort boundary
            logger.exception(
                "Billing publication email step failed after commit for %d/%d: %s",
                month,
                year,
                exc,
            )

        logger.info(
            "Billing published for %d/%d by user %d — %d teachers, Bs %.2f",
            month, year, current_user.id, total_teachers, total_payment,
        )

        return PublicationResponse(
            id=publication.id,
            month=publication.month,
            year=publication.year,
            planilla_type=publication.planilla_type,
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


@router.post("/send-emails", response_model=SendBillingEmailsResponse)
def send_billing_emails(
    payload: SendBillingEmailsRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SendBillingEmailsResponse:
    """Send billing-published emails to selected active docentes."""
    if not (1 <= payload.month <= 12):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mes inválido")
    if payload.year < 2000 or payload.year > 2100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Año inválido")

    teacher_cis = [ci.strip() for ci in payload.teacher_cis if ci.strip()]
    if not teacher_cis:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seleccioná al menos un docente")

    publication = (
        db.query(BillingPublication)
        .filter(
            BillingPublication.month == payload.month,
            BillingPublication.year == payload.year,
            BillingPublication.planilla_type == "regular",
        )
        .first()
    )
    if publication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe publicación para este mes/año",
        )
    if publication.status != "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La facturación no está publicada para este período",
        )

    docente_users = (
        db.query(User)
        .options(joinedload(User.teacher))
        .filter(
            User.role == "docente",
            User.is_active == True,
            User.teacher_ci.in_(teacher_cis),
        )
        .all()
    )

    email_result = EmailService().send_billing_published(publication, docente_users)
    logger.info(
        "Selective billing email step completed for %d/%d: requested=%d eligible=%d sent=%d failed=%d skipped=%d",
        payload.month,
        payload.year,
        len(teacher_cis),
        email_result.eligible,
        email_result.sent,
        email_result.failed,
        email_result.skipped,
    )

    return SendBillingEmailsResponse(
        sent=email_result.sent,
        failed=email_result.failed,
        skipped=email_result.skipped,
    )


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
                BillingPublication.planilla_type == "regular",
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
            planilla_type=publication.planilla_type,
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
    planilla_type: Literal["regular", "practice"] = "regular",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PublicationResponse]:
    """List billing publications by type ordered by year desc, month desc."""
    try:
        publications = (
            db.query(BillingPublication)
            .filter(BillingPublication.planilla_type == planilla_type)
            .order_by(BillingPublication.year.desc(), BillingPublication.month.desc())
            .all()
        )
        return [
            PublicationResponse(
                id=p.id,
                month=p.month,
                year=p.year,
                planilla_type=p.planilla_type,
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
    planilla_type: Literal["regular", "practice"] = "regular",
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PublicationResponse:
    """Check if a specific month/year has a billing publication.

    Pass ``planilla_type=practice`` to query the practice publication instead of
    the regular one (backward-compatible: defaults to ``regular``).
    """
    publication = (
        db.query(BillingPublication)
        .filter(
            BillingPublication.month == month,
            BillingPublication.year == year,
            BillingPublication.planilla_type == planilla_type,
        )
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
        planilla_type=publication.planilla_type,
        status=publication.status,
        total_teachers=publication.total_teachers,
        total_payment=float(publication.total_payment),
        published_by=publication.published_by,
        published_at=publication.published_at,
        unpublished_at=publication.unpublished_at,
        notes=publication.notes,
    )


# ==================================================================
# Practice billing publication endpoints
# Same flow as regular, but:
#   - Reads from PracticePlanillaOutput (not PlanillaOutput)
#   - Uses PracticePlanillaGenerator (not PlanillaGenerator)
#   - Sets planilla_type="practice" on BillingPublication
# ==================================================================


@router.post("/practice/publish", response_model=PublicationResponse)
def publish_practice_billing(
    payload: PublishRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PublicationResponse:
    """Publish practice billing for a given month/year."""
    try:
        month = payload.month
        year = payload.year

        if not (1 <= month <= 12):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mes inválido")
        if year < 2000 or year > 2100:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Año inválido")

        stored_planilla = (
            db.query(PracticePlanillaOutput)
            .filter(PracticePlanillaOutput.month == month, PracticePlanillaOutput.year == year)
            .order_by(PracticePlanillaOutput.generated_at.desc())
            .first()
        )

        if not stored_planilla:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No existe una planilla de prácticas generada para este período. Genere una planilla primero.",
            )

        if stored_planilla.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La planilla de prácticas debe estar aprobada antes de publicar (estado actual: {stored_planilla.status})",
            )

        generator = PracticePlanillaGenerator()
        billing_snapshot = None
        try:
            stored_overrides: dict[str, float] = {}
            if stored_planilla.payment_overrides_json:
                stored_overrides = stored_planilla.payment_overrides_json

            sd = stored_planilla.start_date
            ed = stored_planilla.end_date
            dm = stored_planilla.discount_mode

            stored_exclusions = None
            if stored_planilla.excluded_days_json:
                try:
                    from app.schemas.planilla import ExcludedDaySchema
                    stored_exclusions = [
                        ExcludedDaySchema.model_validate(item)
                        for item in stored_planilla.excluded_days_json
                    ]
                except Exception as exc:
                    raise PayrollDataError(
                        "La planilla práctica aprobada contiene exclusiones inválidas; regenerala antes de publicar",
                        code="invalid_stored_exclusions",
                    ) from exc

            rows, _warnings = generator._build_planilla_data(
                db, month=month, year=year, start_date=sd, end_date=ed,
                discount_mode=dm,
                excluded_days=stored_exclusions,
            )
            total_teachers = len({r.teacher_ci for r in rows})

            resolved_payments: dict[str, float] = {}
            if stored_overrides:
                rows_by_teacher: dict[str, list] = {}
                for row in rows:
                    rows_by_teacher.setdefault(row.teacher_ci, []).append(row)

                teacher_allocations: dict[str, dict[int, float]] = {}
                for teacher_ci, teacher_rows in rows_by_teacher.items():
                    allocations = generator._get_teacher_override_allocations(teacher_rows, stored_overrides)
                    if allocations is not None:
                        teacher_allocations[teacher_ci] = allocations

                for row in rows:
                    row_key = f"{row.teacher_ci}:{row.designation_id}"
                    allocation = teacher_allocations.get(row.teacher_ci, {}).get(row.designation_id)
                    if allocation is not None:
                        resolved_payments[row_key] = float(allocation)
                    elif row_key in stored_overrides:
                        resolved_payments[row_key] = float(stored_overrides[row_key])

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
                    "gross_payment": round(row.calculated_payment, 2),
                    "retention_amount": round(row_retention, 2),
                    "payment": round(effective_payment, 2),
                })
                t["total_hours"] += row.payable_hours
                t["gross_payment"] = round(t.get("gross_payment", 0.0) + row.calculated_payment, 2)
                t["retention_amount"] = round(t.get("retention_amount", 0.0) + row_retention, 2)
                t["total_payment"] += effective_payment
                t["final_payment"] = round(float(t["total_payment"]), 2)

            total_payment = float(stored_planilla.total_payment)
            planilla_id = stored_planilla.id
            logger.info(
                "Practice publish: using approved PracticePlanillaOutput id=%d for %d/%d (total=%.2f)",
                planilla_id, month, year, total_payment,
            )

            practice_rate = app_settings_service.get_practice_hourly_rate(db)
            billing_snapshot = {
                "teacher_details": list(teacher_map.values()),
                "total_payment": float(total_payment),
                "total_teachers": total_teachers,
                "rate_per_hour": practice_rate,
                "start_date": str(stored_planilla.start_date) if stored_planilla.start_date else None,
                "end_date": str(stored_planilla.end_date) if stored_planilla.end_date else None,
                "excluded_days_json": stored_planilla.excluded_days_json or [],
                "generated_at": datetime.now().isoformat(),
                "source": "practice_planilla_output",
                "planilla_id": planilla_id,
                "discount_mode": dm,
            }
        except HTTPException:
            raise
        except PayrollDataError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=exc.as_detail(),
            ) from exc
        except Exception as exc:
            logger.exception("Failed to build practice planilla snapshot for %d/%d: %s", month, year, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo generar la facturación de prácticas. Verificá que existan designaciones y datos de asistencia para este período.",
            ) from exc

        # Create or update BillingPublication with planilla_type="practice"
        now = datetime.now()
        publication = (
            db.query(BillingPublication)
            .filter(
                BillingPublication.month == month,
                BillingPublication.year == year,
                BillingPublication.planilla_type == "practice",
            )
            .first()
        )

        if publication is None:
            publication = BillingPublication(
                month=month,
                year=year,
                planilla_type="practice",
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
            publication.version = (publication.version or 1) + 1
            publication.total_teachers = total_teachers
            publication.total_payment = total_payment
            publication.published_by = current_user.id
            publication.published_at = now
            publication.unpublished_at = None
            publication.billing_snapshot = billing_snapshot
            if payload.notes is not None:
                publication.notes = payload.notes

        db.flush()

        month_name = MONTH_NAMES.get(month, str(month))

        db.query(Notification).filter(
            Notification.notification_type == "practice_billing_published",
            Notification.reference_month == month,
            Notification.reference_year == year,
        ).delete()
        db.flush()

        docente_users = (
            db.query(User)
            .options(joinedload(User.teacher))
            .filter(User.role == "docente", User.is_active == True)
            .all()
        )

        for docente in docente_users:
            notif = Notification(
                user_id=docente.id,
                title=f"Facturación de prácticas {month_name} {year} publicada",
                message=(
                    f"El monto a facturar por prácticas para {month_name} {year} ya está disponible. "
                    f"Revisá tu portal para ver el detalle."
                ),
                notification_type="practice_billing_published",
                is_read=False,
                reference_month=month,
                reference_year=year,
            )
            db.add(notif)

        log_activity(
            db,
            "publish_practice_billing",
            "billing",
            f"Facturación prácticas publicada: {month_name} {year} ({total_teachers} docentes, Bs {total_payment:,.2f})",
            user=current_user,
            details={
                "month": month,
                "year": year,
                "total_teachers": total_teachers,
                "total_payment": float(total_payment),
                "planilla_type": "practice",
            },
            request=request,
        )

        db.commit()
        db.refresh(publication)

        try:
            email_result = EmailService().send_billing_published(publication, docente_users)
            logger.info(
                "Practice billing publication email step completed for %d/%d: eligible=%d sent=%d failed=%d skipped=%d",
                month,
                year,
                email_result.eligible,
                email_result.sent,
                email_result.failed,
                email_result.skipped,
            )
        except Exception as exc:  # pragma: no cover - defensive best-effort boundary
            logger.exception(
                "Practice billing publication email step failed after commit for %d/%d: %s",
                month,
                year,
                exc,
            )

        logger.info(
            "Practice billing published for %d/%d by user %d — %d teachers, Bs %.2f",
            month, year, current_user.id, total_teachers, total_payment,
        )

        return PublicationResponse(
            id=publication.id,
            month=publication.month,
            year=publication.year,
            planilla_type=publication.planilla_type,
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
        logger.exception("Failed to publish practice billing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo publicar la facturación de prácticas",
        ) from exc


@router.post("/practice/unpublish", response_model=PublicationResponse)
def unpublish_practice_billing(
    payload: UnpublishRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PublicationResponse:
    """Unpublish practice billing for a given month/year."""
    try:
        publication = (
            db.query(BillingPublication)
            .filter(
                BillingPublication.month == payload.month,
                BillingPublication.year == payload.year,
                BillingPublication.planilla_type == "practice",
            )
            .first()
        )

        if publication is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe publicación de prácticas para este mes/año",
            )

        publication.status = "draft"
        publication.unpublished_at = datetime.now()

        log_activity(
            db,
            "unpublish_practice_billing",
            "billing",
            f"Facturación prácticas despublicada: {MONTH_NAMES.get(payload.month, str(payload.month))} {payload.year}",
            user=current_user,
            details={"month": payload.month, "year": payload.year, "planilla_type": "practice"},
            request=request,
        )

        db.commit()
        db.refresh(publication)

        logger.info("Practice billing unpublished for %d/%d", payload.month, payload.year)

        return PublicationResponse(
            id=publication.id,
            month=publication.month,
            year=publication.year,
            planilla_type=publication.planilla_type,
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
        logger.exception("Failed to unpublish practice billing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo despublicar la facturación de prácticas",
        ) from exc


@router.post("/practice/send-emails", response_model=SendBillingEmailsResponse)
def send_practice_billing_emails(
    payload: SendBillingEmailsRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SendBillingEmailsResponse:
    """Send practice billing-published emails to selected active docentes."""
    if not (1 <= payload.month <= 12):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mes inválido")
    if payload.year < 2000 or payload.year > 2100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Año inválido")

    teacher_cis = [ci.strip() for ci in payload.teacher_cis if ci.strip()]
    if not teacher_cis:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seleccioná al menos un docente")

    publication = (
        db.query(BillingPublication)
        .filter(
            BillingPublication.month == payload.month,
            BillingPublication.year == payload.year,
            BillingPublication.planilla_type == "practice",
        )
        .first()
    )
    if publication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe publicación de prácticas para este mes/año",
        )
    if publication.status != "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La facturación de prácticas no está publicada para este período",
        )

    docente_users = (
        db.query(User)
        .options(joinedload(User.teacher))
        .filter(
            User.role == "docente",
            User.is_active == True,
            User.teacher_ci.in_(teacher_cis),
        )
        .all()
    )

    email_result = EmailService().send_billing_published(publication, docente_users)
    logger.info(
        "Selective practice billing email step completed for %d/%d: requested=%d eligible=%d sent=%d failed=%d skipped=%d",
        payload.month,
        payload.year,
        len(teacher_cis),
        email_result.eligible,
        email_result.sent,
        email_result.failed,
        email_result.skipped,
    )

    return SendBillingEmailsResponse(
        sent=email_result.sent,
        failed=email_result.failed,
        skipped=email_result.skipped,
    )
