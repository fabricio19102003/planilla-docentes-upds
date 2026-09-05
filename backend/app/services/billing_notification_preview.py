"""Preview and confirmation for immutable official billing notification intents."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any
from sqlalchemy.orm import Session
from app.models.billing_notification import BillingNotificationBatch, BillingNotificationJob
from app.models.whatsapp_preference import WhatsAppPreference
from app.services.billing_notification_policy import BillingChannelPolicy, BillingDigestPlanner
from app.services.billing_pdf_service import BillingPdfService
from app.config import settings

@dataclass(frozen=True)
class NotificationPlan:
    digest: str
    recipients: list[dict[str, Any]]
    readiness: dict[str, Any]

class NotificationPlanError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

class BillingNotificationPreviewService:
    """Build and confirm plans without provider I/O."""
    def __init__(self, db: Session, *, readiness: dict[str, Any] | None = None) -> None:
        self.db = db
        self.policy = BillingChannelPolicy()
        self.digest_planner = BillingDigestPlanner()
        self.readiness = readiness or {"ready": False, "reason": "readiness_adapter_unavailable"}

    def preview(self, publication: Any, teacher_cis: list[str]) -> NotificationPlan:
        requested = sorted(set(teacher_cis))
        details = {str(item.get("teacher_ci")): item for item in (getattr(publication, "billing_snapshot", {}) or {}).get("teacher_details", []) if isinstance(item, dict) and item.get("teacher_ci") in requested}
        preferences = {item.teacher_ci: item for item in self.db.query(WhatsAppPreference).filter(WhatsAppPreference.teacher_ci.in_(requested)).all()}
        recipients = [self._recipient(ci, details[ci], preferences.get(ci)) for ci in sorted(details)]
        digest = self.digest_planner.digest(publication_id=publication.id, publication_version=publication.version, billing_digest=self._billing_digest(publication), recipients=recipients)
        whatsapp_recipients = sum(item["channel"] == "whatsapp" for item in recipients)
        readiness = {**self.readiness, "requested_recipients": len(recipients), "whatsapp_recipients": whatsapp_recipients, "capacity": self._capacity_forecast(whatsapp_recipients)}
        return NotificationPlan(digest=digest, recipients=recipients, readiness=readiness)

    def confirm(self, publication: Any, teacher_cis: list[str], digest: str) -> BillingNotificationBatch:
        plan = self.preview(publication, teacher_cis)
        if not hmac.compare_digest(plan.digest, digest):
            raise NotificationPlanError("stale_notification_plan")
        capacity = plan.readiness["capacity"]
        if not plan.readiness.get("ready", False) or not capacity["available"]:
            raise NotificationPlanError("notification_readiness_unavailable")
        if capacity["exceeded"]:
            raise NotificationPlanError("notification_capacity_exceeded")
        batch = self.db.query(BillingNotificationBatch).filter_by(digest=plan.digest).first()
        if batch is not None:
            return batch
        batch = BillingNotificationBatch(publication_id=publication.id, publication_version=publication.version, digest=plan.digest, readiness_snapshot=plan.readiness, status="queued")
        self.db.add(batch)
        self.db.flush()
        details = {str(item.get("teacher_ci")): item for item in (publication.billing_snapshot or {}).get("teacher_details", []) if isinstance(item, dict)}
        for recipient in plan.recipients:
            if recipient["channel"] != "blocked":
                job = BillingNotificationJob(batch_id=batch.id, teacher_ci=recipient["teacher_ci"], channel=recipient["channel"], content_sid=recipient["content_sid"], status="queued")
                self.db.add(job)
                self.db.flush()
                if job.channel == "whatsapp":
                    media = BillingPdfService(self.db).issue(batch, job, details[job.teacher_ci], commit=False)
                    job.media_snapshot = {"token_id": media.token_id, "artifact_hash": media.artifact_hash, "artifact_size": media.artifact_size}
        self.db.flush()
        return batch

    def _recipient(self, teacher_ci: str, detail: dict[str, Any], preference: Any | None) -> dict[str, Any]:
        decision = self.policy.select(preference)
        encoded = json.dumps(detail, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        return {"teacher_ci": teacher_ci, "phone_masked": self._mask_phone(getattr(preference, "phone_e164", None)), "consent_revision": self.policy.consent_snapshot(preference)["consent_revision"], "channel": decision.channel, "reason": decision.reason, "content_sid": settings.TWILIO_OFFICIAL_CONTENT_SID, "pdf_sha256": hashlib.sha256(encoded).hexdigest(), "pdf_size": len(encoded)}

    def _capacity_forecast(self, requested: int) -> dict[str, Any]:
        capacity = self.readiness.get("capacity")
        if not isinstance(capacity, dict) or not capacity.get("available", False):
            return {"available": False, "requested": requested, "remaining": None, "exceeded": None}
        remaining = int(capacity.get("remaining", 0))
        return {"available": True, "requested": requested, "remaining": remaining, "exceeded": requested > remaining}

    @staticmethod
    def _billing_digest(publication: Any) -> str:
        snapshot = getattr(publication, "billing_snapshot", {}) or {}
        return str(snapshot.get("calculation_snapshot_digest") or hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest())

    @staticmethod
    def _mask_phone(phone: Any) -> str | None:
        return f"{phone[:4]}*****{phone[-3:]}" if isinstance(phone, str) and len(phone) >= 7 else None
