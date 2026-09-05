from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.services.monetary_snapshot import require_reconciled_snapshot


class PublicationRevisionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

    def as_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _digest(value: Any) -> str:
    canonical = json.dumps(value, default=str, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PublicationRevisionError("billing_snapshot_mismatch", "Billing snapshot contains invalid money") from exc
    if not amount.is_finite() or amount < 0:
        raise PublicationRevisionError("billing_snapshot_mismatch", "Billing snapshot money is invalid")
    return amount


def validate_publication_revision(
    revision: BillingPublicationRevision,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        calculation = _copy(revision.calculation_snapshot)
        billing = _copy(revision.billing_snapshot)
        if not isinstance(calculation, dict) or not isinstance(billing, dict):
            raise ValueError("snapshots must be objects")
        require_reconciled_snapshot(calculation, billing.get("total_payment"))
        if calculation.get("digest") != revision.calculation_digest:
            raise ValueError("calculation digest mismatch")
        if _digest(billing) != revision.billing_digest:
            raise ValueError("billing digest mismatch")
        if (
            billing.get("calculation_snapshot_digest") != revision.calculation_digest
            or billing.get("calculation_snapshot_version") != calculation.get("schema_version")
        ):
            raise ValueError("snapshot lineage mismatch")
        details = billing.get("teacher_details")
        if not isinstance(details, list) or billing.get("total_teachers") != len(details):
            raise ValueError("teacher count mismatch")
        visible_total = sum(
            (_money(row.get("net_payment")) for teacher in details for row in teacher.get("designations", [])),
            Decimal("0.00"),
        )
        if visible_total != _money(billing.get("total_payment")):
            raise ValueError("billing rows do not reconcile")
        return calculation, billing
    except Exception as exc:
        raise PublicationRevisionError(
            "revision_corrupt", "Stored publication revision failed integrity validation",
        ) from exc


def append_publication_revision(
    db: Session,
    publication: BillingPublication,
    calculation_snapshot: Any,
    billing_snapshot: Any,
    *,
    actor_id: int | None,
    published_at: datetime,
) -> BillingPublicationRevision:
    if publication.id is None:
        db.flush()
    revisions = (
        db.query(BillingPublicationRevision)
        .filter(BillingPublicationRevision.publication_id == publication.id)
        .order_by(BillingPublicationRevision.version.asc()).all()
    )
    if not revisions and publication.billing_snapshot is not None:
        raise PublicationRevisionError(
            "legacy_revision_missing",
            "Existing publication has no revision lineage; manual backfill is required",
        )
    expected_total = billing_snapshot.get("total_payment") if isinstance(billing_snapshot, dict) else None
    require_reconciled_snapshot(calculation_snapshot, expected_total)
    calculation_digest = calculation_snapshot["digest"]
    if (
        billing_snapshot.get("calculation_snapshot_digest") != calculation_digest
        or billing_snapshot.get("calculation_snapshot_version") != calculation_snapshot["schema_version"]
    ):
        raise PublicationRevisionError("billing_snapshot_mismatch", "Billing snapshot lineage does not match calculation snapshot")
    details = billing_snapshot.get("teacher_details")
    if not isinstance(details, list) or billing_snapshot.get("total_teachers") != len(details):
        raise PublicationRevisionError("billing_snapshot_mismatch", "Billing snapshot teacher count is invalid")
    visible_total = sum(
        (_money(row.get("net_payment")) for teacher in details for row in teacher.get("designations", [])),
        Decimal("0.00"),
    )
    if visible_total != _money(expected_total):
        raise PublicationRevisionError("billing_snapshot_mismatch", "Billing rows do not reconcile with total")
    calculation_copy, billing_copy = _copy(calculation_snapshot), _copy(billing_snapshot)
    billing_digest = _digest(billing_copy)
    duplicate = next((item for item in revisions if item.calculation_digest == calculation_digest), None)
    if duplicate:
        code = "snapshot_already_published" if duplicate.billing_digest == billing_digest else "snapshot_conflict"
        raise PublicationRevisionError(code, "Calculation snapshot already has a publication revision")
    version = revisions[-1].version + 1 if revisions else 1
    revision = BillingPublicationRevision(
        publication_id=publication.id, version=version, status="published",
        calculation_digest=calculation_digest, billing_digest=billing_digest,
        calculation_snapshot=calculation_copy, billing_snapshot=billing_copy,
        created_by=actor_id, created_at=published_at,
    )
    db.add(revision)
    publication.version = version
    publication.status = "published"
    publication.total_teachers = billing_snapshot["total_teachers"]
    publication.total_payment = float(_money(expected_total))
    publication.billing_snapshot = billing_copy
    publication.published_by = actor_id
    publication.published_at = published_at
    publication.unpublished_at = None
    db.flush()
    return revision
