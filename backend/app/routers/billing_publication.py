from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.models.notification import Notification
from app.models.planilla import PlanillaOutput
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.user import User
from app.services.activity_logger import log_activity
from app.services.billing_notification_preview import BillingNotificationPreviewService, NotificationPlanError
from app.services.billing_notification_service import (
    BillingNotificationService,
    SqlAlchemyAttemptStore,
)
from app.services.email_service import EmailService
from app.services.monetary_snapshot import SnapshotReconciliationError, require_reconciled_snapshot
from app.services.publication_revisions import (
    PublicationRevisionError,
    append_publication_revision,
    validate_publication_revision,
)
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing-publication"])

# Month name lookup
MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

_MONEY_QUANTUM = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value if value is not None else 0)).quantize(
        _MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _serialize_teacher_financials(teacher_map: dict[str, dict]) -> list[dict]:
    monetary_fields = (
        "gross_payment",
        "total_payment",
        "retention_amount",
        "admin_adjustment",
        "final_payment",
        "net_payment",
    )
    details: list[dict] = []
    for teacher in teacher_map.values():
        details.append({
            **teacher,
            **{field: float(_money(teacher[field])) for field in monetary_fields},
            "retention_rate": float(Decimal(str(teacher["retention_rate"]))),
        })
    return details


def _rows_from_calculation_snapshot(snapshot: dict, expected_total) -> list[SimpleNamespace]:
    require_reconciled_snapshot(snapshot, expected_total)
    overrides = snapshot.get("overrides", {})
    rows = []
    for item in snapshot["designations"]:
        row_key = f'{item["teacher_ci"]}:{item["designation_id"]}'
        rows.append(SimpleNamespace(
            designation_id=item["designation_id"],
            teacher_ci=item["teacher_ci"],
            teacher_name=item["teacher_name"],
            has_biometric=item["has_biometric"],
            has_retention=item["has_retention"],
            subject=item["subject"],
            group_code=item["group"],
            semester=item["semester"],
            base_monthly_hours=item["base_hours"],
            absent_hours=item["absent_hours"],
            payable_hours=item["payable_hours"],
            calculated_payment=item["gross"],
            retention_amount=item["retention"],
            retention_rate=item["retention_rate"],
            final_payment=item["amount"],
            has_admin_override=item["teacher_ci"] in overrides or row_key in overrides,
        ))
    return rows


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


class BillingNotificationPreviewRequest(BaseModel):
    month: int
    year: int
    teacher_cis: list[str]


class BillingNotificationConfirmRequest(BillingNotificationPreviewRequest):
    digest: str


class BillingNotificationRecipientResponse(BaseModel):
    teacher_ci: str
    phone_masked: str | None
    channel: str
    reason: str


class BillingNotificationPreviewResponse(BaseModel):
    digest: str
    recipients: list[BillingNotificationRecipientResponse]
    readiness: dict[str, Any]


class BillingNotificationConfirmResponse(BaseModel):
    batch_id: int
    digest: str
    status: str


class PublicationResponse(BaseModel):
    id: int
    month: int
    year: int
    planilla_type: str = "regular"
    status: str
    version: int
    total_teachers: int
    total_payment: float
    published_by: Optional[int]
    published_at: Optional[datetime]
    unpublished_at: Optional[datetime]
    notes: Optional[str]


class PublicationRevisionSummary(BaseModel):
    version: int
    status: str
    calculation_digest: str
    billing_digest: str
    created_at: datetime
    total_teachers: int
    total_payment: float


class PublicationRevisionDetail(PublicationRevisionSummary):
    """Admin-only evidence; CI is the stable payroll join key and name makes the salary record human-auditable."""

    calculation_snapshot: dict[str, Any]
    billing_snapshot: dict[str, Any]


class PublicationRevisionCurrent(BaseModel):
    publication_status: str
    revision_count: int
    current_revision: PublicationRevisionSummary


def _revision_context(
    db: Session, planilla_type: str, month: int, year: int,
) -> tuple[BillingPublication, list[BillingPublicationRevision]]:
    publication = db.query(BillingPublication).filter_by(
        month=month, year=year, planilla_type=planilla_type,
    ).first()
    if publication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication not found")
    revisions = db.query(BillingPublicationRevision).filter_by(
        publication_id=publication.id,
    ).order_by(BillingPublicationRevision.version.asc()).all()
    if not revisions:
        error = PublicationRevisionError(
            "legacy_revision_missing", "Existing publication has no revision lineage; manual backfill is required",
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error.as_detail())
    return publication, revisions


def _revision_data(revision: BillingPublicationRevision, *, detail: bool = False) -> dict[str, Any]:
    try:
        calculation, billing = validate_publication_revision(revision)
    except PublicationRevisionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.as_detail()) from exc
    data = {
        "version": revision.version,
        "status": revision.status,
        "calculation_digest": revision.calculation_digest,
        "billing_digest": revision.billing_digest,
        "created_at": revision.created_at,
        "total_teachers": billing["total_teachers"],
        "total_payment": float(billing["total_payment"]),
    }
    if detail:
        data.update(calculation_snapshot=calculation, billing_snapshot=billing)
    return data


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

        billing_snapshot = None
        try:
            snapshot = stored_planilla.calculation_snapshot
            rows = _rows_from_calculation_snapshot(snapshot, stored_planilla.total_payment)
            total_teachers = len({r.teacher_ci for r in rows})

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
                        "gross_payment": Decimal("0.00"),
                        "total_payment": Decimal("0.00"),
                        "retention_rate": Decimal("0.13") if row.has_retention else Decimal("0"),
                        "retention_amount": Decimal("0.00"),
                        "admin_adjustment": Decimal("0.00"),
                        "final_payment": Decimal("0.00"),
                        "net_payment": Decimal("0.00"),
                        "has_admin_override": False,
                    }
                t = teacher_map[row.teacher_ci]

                row_gross = _money(row.calculated_payment)
                row_retention = _money(row.retention_amount)
                row_net = _money(row.final_payment)
                row_adjustment = _money(row_net - (row_gross - row_retention))
                has_override = row.has_admin_override
                t["designations"].append({
                    "subject": row.subject,
                    "group": row.group_code,
                    "semester": row.semester,
                    "base_hours": row.base_monthly_hours,
                    "absent_hours": row.absent_hours,
                    "payable_hours": row.payable_hours,
                    "gross_payment": float(row_gross),
                    "retention_rate": float(Decimal(str(getattr(row, "retention_rate", 0.13 if row.has_retention else 0)))),
                    "retention_amount": float(row_retention),
                    "admin_adjustment": float(row_adjustment),
                    "net_payment": float(row_net),
                    "has_admin_override": has_override,
                    "payment": float(row_net),
                })
                t["total_hours"] += row.payable_hours
                t["gross_payment"] += row_gross
                t["retention_amount"] += row_retention
                t["admin_adjustment"] += row_adjustment
                t["total_payment"] += row_net
                t["final_payment"] = t["total_payment"]
                t["net_payment"] = t["total_payment"]
                t["has_admin_override"] = t["has_admin_override"] or has_override

            total_payment = float(stored_planilla.total_payment)
            planilla_id = stored_planilla.id
            logger.info(
                "Publish: using approved PlanillaOutput id=%d for %d/%d (total=%.2f, overrides=%d)",
                stored_planilla.id, month, year, total_payment, len(snapshot["overrides"]),
            )

            billing_snapshot = {
                "teacher_details": _serialize_teacher_financials(teacher_map),
                "total_payment": float(total_payment),
                "total_teachers": total_teachers,
                "rate_per_hour": float(snapshot["rates"][0]) if snapshot["rates"] else 0.0,
                "start_date": snapshot["period"]["start"],
                "end_date": snapshot["period"]["end"],
                "excluded_days_json": snapshot["excluded_days"],
                "source": "planilla_output",
                "planilla_id": planilla_id,
                "discount_mode": snapshot["discount_mode"],
                "calculation_snapshot_version": snapshot["schema_version"],
                "calculation_snapshot_digest": snapshot["digest"],
            }
        except HTTPException:
            raise
        except SnapshotReconciliationError as exc:
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

        # A publication is immutable once this period/type has a snapshot.
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
                status="draft",
                version=0,
                total_teachers=0,
                total_payment=0,
                notes=payload.notes,
            )
            db.add(publication)
        elif payload.notes is not None:
            publication.notes = payload.notes

        db.flush()
        append_publication_revision(
            db, publication, snapshot, billing_snapshot,
            actor_id=current_user.id, published_at=now,
        )

        # Defensive cleanup for notifications left by legacy publication attempts.
        db.query(Notification).filter(
            Notification.notification_type == "billing_published",
            Notification.reference_month == month,
            Notification.reference_year == year,
        ).delete()
        db.flush()

        # Notify only docentes represented in this immutable publication snapshot.
        published_teacher_cis = set(teacher_map)
        docente_users = [
            user for user in (
            db.query(User)
            .options(joinedload(User.teacher))
            .filter(User.role == "docente", User.is_active == True)
            .all()
            )
            if user.teacher_ci in published_teacher_cis
        ]
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
            notification_result = BillingNotificationService(
                store=SqlAlchemyAttemptStore(db),
                email_service=EmailService(),
            ).send_billing_published(publication, docente_users)
            logger.info(
                "Billing publication outbound step completed for %d/%d: eligible=%d sent=%d failed=%d skipped=%d whatsapp_sent=%d email_sent=%d",
                month,
                year,
                notification_result.eligible,
                notification_result.sent,
                notification_result.failed,
                notification_result.skipped,
                notification_result.whatsapp_sent,
                notification_result.email_sent,
            )
        except Exception as exc:  # pragma: no cover - defensive best-effort boundary
            logger.exception(
                "Billing publication outbound step failed after commit for %d/%d: %s",
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
            version=publication.version,
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
    except PublicationRevisionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.as_detail()) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to publish billing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo publicar la facturación",
        ) from exc


def _notification_publication(db: Session, month: int, year: int) -> BillingPublication:
    publication = db.query(BillingPublication).filter_by(month=month, year=year, planilla_type="regular").first()
    if publication is None or publication.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="billing_publication_not_found")
    return publication


@router.post("/notifications/preview", response_model=BillingNotificationPreviewResponse)
def preview_billing_notifications(payload: BillingNotificationPreviewRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> BillingNotificationPreviewResponse:
    plan = BillingNotificationPreviewService(db).preview(_notification_publication(db, payload.month, payload.year), payload.teacher_cis)
    recipients = [BillingNotificationRecipientResponse(**{key: item[key] for key in ("teacher_ci", "phone_masked", "channel", "reason")}) for item in plan.recipients]
    return BillingNotificationPreviewResponse(digest=plan.digest, recipients=recipients, readiness=plan.readiness)


@router.post("/notifications/confirm", response_model=BillingNotificationConfirmResponse)
def confirm_billing_notifications(payload: BillingNotificationConfirmRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> BillingNotificationConfirmResponse:
    try:
        batch = BillingNotificationPreviewService(db).confirm(_notification_publication(db, payload.month, payload.year), payload.teacher_cis, payload.digest)
        db.commit()
    except NotificationPlanError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": exc.code}) from exc
    return BillingNotificationConfirmResponse(batch_id=batch.id, digest=batch.digest, status=batch.status)


@router.post("/send-emails", response_model=SendBillingEmailsResponse)
def send_billing_emails(
    payload: SendBillingEmailsRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SendBillingEmailsResponse:
    """Send billing-published notifications to selected active docentes."""
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

    notification_result = BillingNotificationService(
        store=SqlAlchemyAttemptStore(db),
        email_service=EmailService(),
    ).send_billing_published(publication, docente_users)
    logger.info(
        "Selective billing outbound step completed for %d/%d: requested=%d eligible=%d sent=%d failed=%d skipped=%d",
        payload.month,
        payload.year,
        len(teacher_cis),
        notification_result.eligible,
        notification_result.sent,
        notification_result.failed,
        notification_result.skipped,
    )

    return SendBillingEmailsResponse(
        sent=notification_result.sent,
        failed=notification_result.failed,
        skipped=notification_result.skipped,
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
            version=publication.version,
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
                version=p.version,
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
        version=publication.version,
        total_teachers=publication.total_teachers,
        total_payment=float(publication.total_payment),
        published_by=publication.published_by,
        published_at=publication.published_at,
        unpublished_at=publication.unpublished_at,
        notes=publication.notes,
    )


@router.get(
    "/revisions/{planilla_type}/{month}/{year}",
    response_model=list[PublicationRevisionSummary],
)
def list_publication_revisions(
    planilla_type: Literal["regular", "practice"],
    month: int,
    year: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PublicationRevisionSummary]:
    """List integrity-checked revision metadata without teacher PII."""
    _, revisions = _revision_context(db, planilla_type, month, year)
    return [PublicationRevisionSummary(**_revision_data(item)) for item in revisions]


@router.get(
    "/revisions/{planilla_type}/{month}/{year}/current",
    response_model=PublicationRevisionCurrent,
)
def get_current_publication_revision(
    planilla_type: Literal["regular", "practice"],
    month: int,
    year: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PublicationRevisionCurrent:
    """Return current publication status and latest integrity-checked revision."""
    publication, revisions = _revision_context(db, planilla_type, month, year)
    current = PublicationRevisionSummary(**_revision_data(revisions[-1]))
    return PublicationRevisionCurrent(
        publication_status=publication.status,
        revision_count=len(revisions),
        current_revision=current,
    )


@router.get(
    "/revisions/{planilla_type}/{month}/{year}/{version}",
    response_model=PublicationRevisionDetail,
)
def get_publication_revision(
    planilla_type: Literal["regular", "practice"],
    month: int,
    year: int,
    version: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PublicationRevisionDetail:
    """Return one immutable revision after validating both stored snapshots."""
    _, revisions = _revision_context(db, planilla_type, month, year)
    revision = next((item for item in revisions if item.version == version), None)
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publication revision not found")
    return PublicationRevisionDetail(**_revision_data(revision, detail=True))


# ==================================================================
# Practice billing publication endpoints
# Same flow as regular, but:
#   - Reads from PracticePlanillaOutput (not PlanillaOutput)
#   - Reads the approved practice calculation snapshot
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

        billing_snapshot = None
        try:
            snapshot = stored_planilla.calculation_snapshot
            rows = _rows_from_calculation_snapshot(snapshot, stored_planilla.total_payment)
            total_teachers = len({r.teacher_ci for r in rows})

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
                        "gross_payment": Decimal("0.00"),
                        "total_payment": Decimal("0.00"),
                        "retention_rate": Decimal("0.13") if row.has_retention else Decimal("0"),
                        "retention_amount": Decimal("0.00"),
                        "admin_adjustment": Decimal("0.00"),
                        "final_payment": Decimal("0.00"),
                        "net_payment": Decimal("0.00"),
                        "has_admin_override": False,
                    }
                t = teacher_map[row.teacher_ci]
                row_gross = _money(row.calculated_payment)
                row_retention = _money(row.retention_amount)
                row_net = _money(row.final_payment)
                row_adjustment = _money(row_net - (row_gross - row_retention))
                has_override = row.has_admin_override
                t["designations"].append({
                    "subject": row.subject,
                    "group": row.group_code,
                    "semester": row.semester,
                    "base_hours": row.base_monthly_hours,
                    "absent_hours": row.absent_hours,
                    "payable_hours": row.payable_hours,
                    "gross_payment": float(row_gross),
                    "retention_rate": float(Decimal(str(getattr(row, "retention_rate", 0.13 if row.has_retention else 0)))),
                    "retention_amount": float(row_retention),
                    "admin_adjustment": float(row_adjustment),
                    "net_payment": float(row_net),
                    "has_admin_override": has_override,
                    "payment": float(row_net),
                })
                t["total_hours"] += row.payable_hours
                t["gross_payment"] += row_gross
                t["retention_amount"] += row_retention
                t["admin_adjustment"] += row_adjustment
                t["total_payment"] += row_net
                t["final_payment"] = t["total_payment"]
                t["net_payment"] = t["total_payment"]
                t["has_admin_override"] = t["has_admin_override"] or has_override

            total_payment = float(stored_planilla.total_payment)
            planilla_id = stored_planilla.id
            logger.info(
                "Practice publish: using approved PracticePlanillaOutput id=%d for %d/%d (total=%.2f)",
                planilla_id, month, year, total_payment,
            )

            billing_snapshot = {
                "teacher_details": _serialize_teacher_financials(teacher_map),
                "total_payment": float(total_payment),
                "total_teachers": total_teachers,
                "rate_per_hour": float(snapshot["rates"][0]) if snapshot["rates"] else 0.0,
                "start_date": snapshot["period"]["start"],
                "end_date": snapshot["period"]["end"],
                "excluded_days_json": snapshot["excluded_days"],
                "source": "practice_planilla_output",
                "planilla_id": planilla_id,
                "discount_mode": snapshot["discount_mode"],
                "calculation_snapshot_version": snapshot["schema_version"],
                "calculation_snapshot_digest": snapshot["digest"],
            }
        except HTTPException:
            raise
        except SnapshotReconciliationError as exc:
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

        # A publication is immutable once this period/type has a snapshot.
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
                status="draft",
                version=0,
                total_teachers=0,
                total_payment=0,
                notes=payload.notes,
            )
            db.add(publication)
        elif payload.notes is not None:
            publication.notes = payload.notes

        db.flush()
        append_publication_revision(
            db, publication, snapshot, billing_snapshot,
            actor_id=current_user.id, published_at=now,
        )

        month_name = MONTH_NAMES.get(month, str(month))

        db.query(Notification).filter(
            Notification.notification_type == "practice_billing_published",
            Notification.reference_month == month,
            Notification.reference_year == year,
        ).delete()
        db.flush()

        published_teacher_cis = set(teacher_map)
        docente_users = [
            user for user in (
            db.query(User)
            .options(joinedload(User.teacher))
            .filter(User.role == "docente", User.is_active == True)
            .all()
            )
            if user.teacher_ci in published_teacher_cis
        ]

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
            notification_result = BillingNotificationService(
                store=SqlAlchemyAttemptStore(db),
                email_service=EmailService(),
            ).send_billing_published(publication, docente_users)
            logger.info(
                "Practice billing publication outbound step completed for %d/%d: eligible=%d sent=%d failed=%d skipped=%d whatsapp_sent=%d email_sent=%d",
                month,
                year,
                notification_result.eligible,
                notification_result.sent,
                notification_result.failed,
                notification_result.skipped,
                notification_result.whatsapp_sent,
                notification_result.email_sent,
            )
        except Exception as exc:  # pragma: no cover - defensive best-effort boundary
            logger.exception(
                "Practice billing publication outbound step failed after commit for %d/%d: %s",
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
            version=publication.version,
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
    except PublicationRevisionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.as_detail()) from exc
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
            version=publication.version,
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
    """Send practice billing-published notifications to selected active docentes."""
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

    notification_result = BillingNotificationService(
        store=SqlAlchemyAttemptStore(db),
        email_service=EmailService(),
    ).send_billing_published(publication, docente_users)
    logger.info(
        "Selective practice billing outbound step completed for %d/%d: requested=%d eligible=%d sent=%d failed=%d skipped=%d",
        payload.month,
        payload.year,
        len(teacher_cis),
        notification_result.eligible,
        notification_result.sent,
        notification_result.failed,
        notification_result.skipped,
    )

    return SendBillingEmailsResponse(
        sent=notification_result.sent,
        failed=notification_result.failed,
        skipped=notification_result.skipped,
    )
