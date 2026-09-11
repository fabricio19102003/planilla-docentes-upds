"""Provider-free creation of one immutable, controlled WhatsApp activation."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.billing_notification import (
    BillingNotificationBatch, BillingNotificationJob, BillingWhatsAppActivationTest,
    BillingWhatsAppDispatchAuthorization,
)
from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.models.user import User
from app.models.whatsapp_preference import WhatsAppPreference
from app.schemas.whatsapp_activation import WhatsAppActivationCreate, WhatsAppActivationProjection
from app.services.billing_pdf_service import BillingPdfService
from app.services.publication_revisions import PublicationRevisionError, validate_publication_revision


class WhatsAppActivationError(ValueError):
    """Bounded error code safe for a future router boundary."""


_ACTIVATION_TERMINAL = {"failed", "undelivered", "read", "cancelled"}
_ACTIVATION_TRANSITIONS = {
    "queued": {"leased", "cancelled"}, "leased": {"sending", "cancelled"},
    "sending": {"accepted", "ambiguous", "cancelled"},
    "ambiguous": {"accepted", "sent", "delivered", "read", "failed", "undelivered"},
    "accepted": {"sent", "delivered", "read", "failed", "undelivered"},
    "sent": {"delivered", "read", "failed", "undelivered"}, "delivered": {"read"},
}
_ACTIVATION_REASONS = {
    "activation_disabled", "activation_readiness_unavailable",
    "activation_requires_global_delivery_disabled", "activation_recipient_mismatch",
    "activation_consent_revision_mismatch", "activation_consent_ineligible",
    "activation_publication_not_current", "activation_publication_corrupt",
    "activation_teacher_not_in_revision", "activation_template_unapproved",
    "activation_artifact_unavailable", "activation_provider_failed",
}


def project_activation_status(
    db: Session, job: BillingNotificationJob, terminal_reason: str | None = None,
) -> BillingWhatsAppActivationTest | None:
    """Synchronize one activation's safe lifecycle projection within its job transaction."""
    if job.intent_type != "activation_test" or BillingWhatsAppActivationTest.__tablename__ not in inspect(db.get_bind()).get_table_names():
        return None
    activation = db.scalar(select(BillingWhatsAppActivationTest).where(
        BillingWhatsAppActivationTest.job_id == job.id
    ).with_for_update())
    if activation is None or activation.status in _ACTIVATION_TERMINAL:
        return activation
    if job.status != activation.status and job.status not in _ACTIVATION_TRANSITIONS.get(activation.status, set()):
        return activation
    activation.status = job.status
    if job.status == "cancelled" and terminal_reason in _ACTIVATION_REASONS:
        activation.terminal_reason = terminal_reason
    return activation


class WhatsAppActivationService:
    """Creates a single activation graph; the caller owns the successful commit.

    This service makes no provider or configuration call. The caller supplies a
    successful readiness projection and its approved configured Content SID.
    """

    def __init__(self, db: Session, *, recipient_hmac_key: str, pdf_service: BillingPdfService | None = None):
        if len(recipient_hmac_key.encode("utf-8")) < 32:
            raise ValueError("invalid_recipient_hmac_key")
        self.db = db
        self.recipient_hmac_key = recipient_hmac_key.encode("utf-8")
        self.pdf_service = pdf_service or BillingPdfService(db)

    def create(
        self,
        *,
        actor_user_id: int,
        request: WhatsAppActivationCreate,
        idempotency_key: str,
        readiness: dict[str, Any],
        configured_content_sid: str | None,
        approved_content_sid: str | None,
        ip_address: str | None = None,
    ) -> WhatsAppActivationProjection:
        key_hash = self._key_hash(idempotency_key)
        recipient_hmac = self._recipient_hmac(request.recipient_e164)
        request_digest = self._request_digest(request, recipient_hmac)
        actor = self.db.scalar(select(User).where(User.id == actor_user_id).with_for_update())
        if actor is None:
            raise WhatsAppActivationError("actor_not_found")
        existing = self.db.scalar(select(BillingWhatsAppActivationTest).where(
            BillingWhatsAppActivationTest.actor_user_id == actor.id,
            BillingWhatsAppActivationTest.idempotency_key_hash == key_hash,
        ).with_for_update())
        if existing is not None:
            if hmac.compare_digest(existing.request_digest, request_digest):
                return self.project(self.db, existing, replayed=True)
            raise WhatsAppActivationError("activation_idempotency_conflict")
        self._require_readiness(readiness, configured_content_sid, approved_content_sid)
        artifact: Path | None = None
        artifact_is_new = False
        try:
            preference = self.db.scalar(select(WhatsAppPreference).where(
                WhatsAppPreference.teacher_ci == request.teacher_ci).with_for_update())
            if preference is None:
                raise WhatsAppActivationError("teacher_not_found")
            if preference.phone_e164 != request.recipient_e164:
                raise WhatsAppActivationError("activation_recipient_mismatch")
            if preference.consent_revision != request.consent_revision:
                raise WhatsAppActivationError("activation_consent_revision_mismatch")
            if not preference.is_eligible_for_whatsapp:
                raise WhatsAppActivationError("activation_consent_ineligible")
            revision = self.db.scalar(select(BillingPublicationRevision).where(
                BillingPublicationRevision.id == request.publication_revision_id).with_for_update())
            publication = self.db.scalar(select(BillingPublication).where(
                BillingPublication.id == (revision.publication_id if revision else None)).with_for_update())
            if revision is None or publication is None or publication.status != "published" or revision.status != "published" or publication.version != revision.version:
                raise WhatsAppActivationError("activation_publication_not_current")
            try:
                _, billing = validate_publication_revision(revision)
            except PublicationRevisionError as exc:
                raise WhatsAppActivationError("activation_publication_corrupt") from exc
            details = [item for item in billing.get("teacher_details", []) if isinstance(item, dict) and item.get("teacher_ci") == request.teacher_ci]
            if len(details) != 1:
                raise WhatsAppActivationError("activation_teacher_not_in_revision")
            batch = BillingNotificationBatch(
                publication_id=publication.id, publication_version=revision.version,
                digest=self._batch_digest(actor.id, key_hash, request_digest),
                readiness_snapshot={"activation_capable": True, "content_template_bound": True}, status="queued",
            )
            self.db.add(batch)
            self.db.flush()
            job = BillingNotificationJob(batch_id=batch.id, teacher_ci=request.teacher_ci, channel="whatsapp", intent_type="activation_test", content_sid=configured_content_sid, status="queued")
            self.db.add(job)
            self.db.flush()
            media = self.pdf_service.issue_activation(batch, job, details[0], publication_revision_id=revision.id, publication_version=revision.version, billing_digest=revision.billing_digest)
            artifact, artifact_is_new = Path(media.artifact_path), media.artifact_created
            activation = BillingWhatsAppActivationTest(
                actor_user_id=actor.id, actor_ci=actor.ci, idempotency_key_hash=key_hash, request_digest=request_digest,
                teacher_ci_at_creation=request.teacher_ci, recipient_hmac=recipient_hmac,
                recipient_masked=self._mask(request.recipient_e164), consent_revision=request.consent_revision,
                publication_id=publication.id, publication_revision_id=revision.id, publication_version=revision.version,
                billing_digest=revision.billing_digest, content_sid=configured_content_sid, batch_id=batch.id, job_id=job.id,
                media_token_id=media.token_id, artifact_hash=media.artifact_hash, artifact_size=media.artifact_size, status="queued",
            )
            self.db.add(activation)
            self.db.flush()
            self.db.add(BillingWhatsAppDispatchAuthorization(
                activation_id=activation.id, job_id=job.id, creator_user_id=actor.id,
                state="pending", expires_at=activation.created_at + timedelta(minutes=30),
            ))
            self.db.flush()
            self.db.add(ActivityLog(
                user_id=actor.id, user_ci=actor.ci, action="whatsapp_activation_created", category="whatsapp",
                description="Controlled WhatsApp activation created",
                details={"activation_id": activation.id, "teacher_ci_at_creation": request.teacher_ci,
                         "consent_revision": request.consent_revision, "publication_revision_id": revision.id,
                         "publication_version": revision.version, "job_id": job.id,
                         "content_template_bound": True, "pdf_bound": True}, ip_address=ip_address,
            ))
            self.db.flush()
            return self.project(self.db, activation)
        except Exception:
            if artifact_is_new and artifact is not None:
                try:
                    artifact.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    @staticmethod
    def _require_readiness(readiness: dict[str, Any], configured_sid: str | None, approved_sid: str | None) -> None:
        activation = readiness.get("activation") if isinstance(readiness, dict) else None
        global_delivery = readiness.get("global_delivery") if isinstance(readiness, dict) else None
        configuration = readiness.get("provider_configuration") if isinstance(readiness, dict) else None
        provider_live = readiness.get("provider_live") if isinstance(readiness, dict) else None
        if not isinstance(global_delivery, dict) or global_delivery.get("requested") is not False or global_delivery.get("effective") is not False:
            raise WhatsAppActivationError("activation_requires_global_delivery_disabled")
        if not isinstance(activation, dict) or activation.get("creation_capable") is not True:
            raise WhatsAppActivationError("activation_readiness_unavailable")
        if not isinstance(configured_sid, str) or re.fullmatch(r"HX[0-9A-Fa-f]{32}", configured_sid) is None or approved_sid != configured_sid or readiness.get("approved_content_sid") != configured_sid:
            raise WhatsAppActivationError("activation_template_unapproved")

    @staticmethod
    def _key_hash(key: str) -> str:
        if not isinstance(key, str) or not 16 <= len(key) <= 128 or not key.isascii() or not key.isprintable():
            raise WhatsAppActivationError("invalid_idempotency_key")
        return hashlib.sha256(key.encode("ascii")).hexdigest()

    def _recipient_hmac(self, recipient: str) -> str:
        return hmac.new(self.recipient_hmac_key, recipient.encode("ascii"), hashlib.sha256).hexdigest()

    @staticmethod
    def _request_digest(request: WhatsAppActivationCreate, recipient_hmac: str) -> str:
        facts = {"schema": "official-whatsapp-activation/v1", "teacher_ci": request.teacher_ci,
                 "recipient_hmac": recipient_hmac, "consent_revision": request.consent_revision,
                 "publication_revision_id": request.publication_revision_id}
        return hashlib.sha256(json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _batch_digest(actor_id: int, key_hash: str, request_digest: str) -> str:
        return hashlib.sha256(f"official-whatsapp-activation-batch/v1:{actor_id}:{key_hash}:{request_digest}".encode()).hexdigest()

    @staticmethod
    def _mask(phone: str) -> str:
        return f"{phone[:4]}••••{phone[-4:]}"

    @staticmethod
    def project(db: Session, activation: BillingWhatsAppActivationTest, *, replayed: bool = False) -> WhatsAppActivationProjection:
        """Build a persisted projection without requiring runtime HMAC configuration."""
        job = db.get(BillingNotificationJob, activation.job_id)
        authorization = db.scalar(select(BillingWhatsAppDispatchAuthorization).where(
            BillingWhatsAppDispatchAuthorization.activation_id == activation.id,
            BillingWhatsAppDispatchAuthorization.job_id == activation.job_id,
        ))
        if authorization is None:
            raise WhatsAppActivationError("activation_authorization_unavailable")
        return WhatsAppActivationProjection(
            id=activation.id, status=activation.status, terminal_reason=activation.terminal_reason,
            teacher_ci_at_creation=activation.teacher_ci_at_creation, recipient_masked=activation.recipient_masked,
            consent_revision=activation.consent_revision, publication_revision_id=activation.publication_revision_id,
            publication_version=activation.publication_version,
            content_template_bound=True, pdf_bound=True,
            job_id=activation.job_id, job_status=job.status if job else activation.status,
            created_at=activation.created_at, updated_at=activation.updated_at,
            authorization_state=authorization.state, authorization_expires_at=authorization.expires_at,
            authorized_at=authorization.released_at, consumed_at=authorization.consumed_at,
            revoked_at=authorization.revoked_at, attestation_code=authorization.attestation_code,
            authorization_terminal_reason=authorization.terminal_reason, replayed=replayed,
        )
