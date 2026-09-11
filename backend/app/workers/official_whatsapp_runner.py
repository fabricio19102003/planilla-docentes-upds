"""Process entry point for the fail-closed official WhatsApp billing worker."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta

import httpx
import os
from dataclasses import dataclass
from time import sleep
from typing import Any
from urllib.parse import urlparse

from app.database import SessionLocal
from app.models.billing_notification import BillingMediaToken, BillingNotificationBatch, BillingNotificationJob, BillingWhatsAppActivationTest, BillingWhatsAppDispatchAuthorization
from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.models.whatsapp_preference import WhatsAppPreference
from app.services.twilio_content_transport import TwilioContentTransport
from app.services.twilio_readiness_adapter import TwilioReadinessAdapter
from app.services.whatsapp_activation_service import project_activation_status
from app.services.whatsapp_delivery_control import current_delivery_status, mark_worker_heartbeat, status_from_readiness
from app.services.publication_revisions import PublicationRevisionError, validate_publication_revision
from app.workers.billing_notification_worker import BillingNotificationWorker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActivationDispatch:
    job: BillingNotificationJob
    recipient: str
    media_token: str


@dataclass(frozen=True, repr=False)
class OfficialWhatsAppRuntime:
    account_sid: str
    api_key_sid: str
    api_key_secret: str
    from_number: str
    sender_sid: str
    default_content_sid: str
    status_callback_url: str
    inbound_callback_url: str
    media_base_url: str
    capacity: dict[str, Any]
    transport: Any

    @classmethod
    def configuration_readiness(cls, settings: Any) -> dict[str, Any]:
        fields = (
            "TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
            "TWILIO_OFFICIAL_FROM", "TWILIO_OFFICIAL_SENDER_SID", "TWILIO_OFFICIAL_CONTENT_SID",
            "TWILIO_STATUS_CALLBACK_URL", "TWILIO_INBOUND_CALLBACK_URL", "TWILIO_AUTH_TOKEN",
            "BILLING_MEDIA_PUBLIC_BASE_URL",
        )
        if not all(getattr(settings, name, None) for name in fields):
            return {"ready": False, "reason": "configuration_missing"}
        base_url = settings.BILLING_MEDIA_PUBLIC_BASE_URL
        capacity = {
            "available": True,
            "moving_recipient_limit": getattr(settings, "TWILIO_OFFICIAL_MOVING_RECIPIENT_LIMIT", 0),
            "media_mps": getattr(settings, "TWILIO_OFFICIAL_MEDIA_MPS", 0),
            "window_seconds": getattr(settings, "TWILIO_OFFICIAL_CAPACITY_WINDOW_SECONDS", 86400),
        }
        safe = (
            _is_https_url(base_url)
            and _is_canonical_callback(settings.TWILIO_STATUS_CALLBACK_URL, base_url, "/api/twilio/whatsapp/status")
            and _is_canonical_callback(settings.TWILIO_INBOUND_CALLBACK_URL, base_url, "/api/twilio/whatsapp/inbound")
            and isinstance(capacity["moving_recipient_limit"], int)
            and capacity["moving_recipient_limit"] >= 1
            and isinstance(capacity["media_mps"], (int, float))
            and capacity["media_mps"] > 0
        )
        return {"ready": safe, "reason": None if safe else "configuration_unsafe"}

    @classmethod
    def from_settings(cls, settings: Any, *, transport: Any | None = None) -> "OfficialWhatsAppRuntime | None":
        if not cls.configuration_readiness(settings)["ready"]:
            return None
        capacity = {
            "available": True,
            "moving_recipient_limit": settings.TWILIO_OFFICIAL_MOVING_RECIPIENT_LIMIT,
            "media_mps": settings.TWILIO_OFFICIAL_MEDIA_MPS,
            "window_seconds": settings.TWILIO_OFFICIAL_CAPACITY_WINDOW_SECONDS,
        }
        return cls(
            settings.TWILIO_ACCOUNT_SID, settings.TWILIO_API_KEY_SID, settings.TWILIO_API_KEY_SECRET,
            settings.TWILIO_OFFICIAL_FROM, settings.TWILIO_OFFICIAL_SENDER_SID, settings.TWILIO_OFFICIAL_CONTENT_SID,
            settings.TWILIO_STATUS_CALLBACK_URL, settings.TWILIO_INBOUND_CALLBACK_URL,
            settings.BILLING_MEDIA_PUBLIC_BASE_URL.rstrip("/"), capacity,
            transport or TwilioContentTransport(
                settings.TWILIO_ACCOUNT_SID, settings.TWILIO_API_KEY_SID, settings.TWILIO_API_KEY_SECRET,
                settings.TWILIO_OFFICIAL_FROM, settings.TWILIO_STATUS_CALLBACK_URL,
                api_base_url=getattr(settings, "TWILIO_API_BASE_URL", "https://api.twilio.com"), timeout_seconds=getattr(settings, "WHATSAPP_TIMEOUT_SECONDS", 3.0),
            ),
        )

    def readiness_facts(self, *, sender_status: str | None = None, templates_approved: bool = False) -> dict[str, Any]:
        return TwilioReadinessAdapter().evaluate({
            "sender_status": sender_status,
            "templates_approved": templates_approved,
            "capacity": self.capacity,
        })

    def live_readiness(self) -> dict[str, Any]:
        """Query current sender/template state; unavailable or malformed data is false."""
        try:
            with httpx.Client(timeout=3.0) as client:
                sender = client.get(
                    f"https://messaging.twilio.com/v2/Channels/Senders/{self.sender_sid}",
                    auth=(self.api_key_sid, self.api_key_secret),
                ).json()
                content = client.get(
                    f"https://content.twilio.com/v1/Content/{self.default_content_sid}",
                    auth=(self.api_key_sid, self.api_key_secret),
                ).json()
            approvals = content.get("approval_requests")
            approved = isinstance(approvals, list) and any(
                item.get("status", "").lower() == "approved"
                and item.get("category", "").lower() == "utility"
                for item in approvals if isinstance(item, dict)
            )
            return self.readiness_facts(
                sender_status=sender.get("status") if isinstance(sender, dict) else None,
                templates_approved=approved,
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return {"ready": False, "reason": "provider_unavailable", "capacity": {"available": False}}

    def transport_job(self, job: BillingNotificationJob, *, phone_e164: str, media_token: str) -> Any:
        return self.transport.send(
            to=phone_e164,
            content_sid=job.content_sid or self.default_content_sid,
            content_variables=json.dumps(
                {"1": f"api/public/billing-media/{media_token}.pdf"},
                separators=(",", ":"),
            ),
        )


def run() -> int:
    from app.config import settings

    runtime = OfficialWhatsAppRuntime.from_settings(settings)
    if runtime is None:
        logger.error("Official WhatsApp worker configuration is unavailable; refusing dispatch")
        return 2
    # Live sender/template status is deliberately not inferred from environment.
    # Until a provider readiness collector supplies current facts, every lease backs off.
    while True:
        db = SessionLocal()
        try:
            mark_worker_heartbeat(db)
            db.commit()
            cycle: dict[str, Any] = {}
            def status() -> dict[str, Any]:
                if not cycle:
                    cycle.update(status_from_readiness(
                        db, runtime.live_readiness(),
                        official_process_enabled=settings.OFFICIAL_WHATSAPP_ENABLED,
                        dispatch_process_enabled=settings.WHATSAPP_DISPATCH_ENABLED,
                        activation_api_enabled=getattr(settings, "BILLING_WHATSAPP_ACTIVATION_API_ENABLED", False),
                        activation_dispatch_enabled=getattr(settings, "BILLING_WHATSAPP_ACTIVATION_DISPATCH_ENABLED", False),
                        recipient_hmac_key=getattr(settings, "WHATSAPP_RECIPIENT_HMAC_KEY", None),
                    ))
                return cycle
            def intent() -> str | None:
                facts = status()
                global_delivery = facts.get("global_delivery")
                if global_delivery is None:  # Compatibility for a bounded legacy status projection.
                    return "ordinary" if facts.get("effective_enabled") and facts.get("readiness", {}).get("ready") else None
                if global_delivery["requested"] and global_delivery["effective"] and facts["readiness"]["ready"]:
                    return "ordinary"
                if not global_delivery["requested"] and facts["activation"]["capable"]:
                    return "activation_test"
                return None
            activation = status().get("activation")
            if isinstance(activation, dict) and activation.get("capable") is not True:
                rollback_unleased_activation(db)
            worker = BillingNotificationWorker(
                db, readiness=status, transport=lambda item: _send(db, runtime, item),
                owner=f"official-whatsapp-{os.getpid()}",
                claim_intent=intent,
                dispatch_allowed=lambda: status()["effective_enabled"],
                activation_authorize=lambda job_id, facts: _authorize_activation(db, job_id, facts, getattr(settings, "WHATSAPP_RECIPIENT_HMAC_KEY", ""), f"official-whatsapp-{os.getpid()}", runtime.default_content_sid),
            )
            if worker.process_one() is None:
                sleep(1)
        except Exception:
            logger.exception("Official WhatsApp worker cycle failed")
            sleep(5)
        finally:
            db.close()


def _cancel_activation(db: Any, job: BillingNotificationJob, activation: BillingWhatsAppActivationTest | None, reason: str) -> None:
    """Fail closed before provider I/O and revoke the one-shot activation authority."""
    if job is not None and activation is not None and job.intent_type == "activation_test" and job.status in {"queued", "leased", "sending"}:
        now = datetime.utcnow()
        authorization = db.query(BillingWhatsAppDispatchAuthorization).filter_by(
            activation_id=activation.id, job_id=job.id,
        ).with_for_update().one_or_none()
        job.status, job.lease_owner, job.lease_expires_at, job.next_attempt_at, job.last_error_code = "cancelled", None, None, None, reason
        project_activation_status(db, job, reason)
        if authorization is not None and authorization.consumed_at is None:
            authorization.state, authorization.revoked_at, authorization.terminal_reason = "revoked", now, "pre_provider_rejected"
        db.query(BillingMediaToken).filter_by(id=activation.media_token_id, revoked_at=None).update({"revoked_at": now})
    db.commit()


def _lock_activation_graph(db: Any, job_id: int, owner: str):
    """Lock an activation graph in canonical order, only after its job is compatible."""
    job = db.query(BillingNotificationJob).filter_by(id=job_id).with_for_update().one_or_none()
    if job is None:
        return None
    if job.intent_type != "activation_test" or job.status != "leased" or job.lease_owner != owner:
        # Never lock a downstream row for an absent, stale, or foreign lease.
        return None
    activation = db.query(BillingWhatsAppActivationTest).filter_by(job_id=job.id).with_for_update().one_or_none()
    authorization = db.query(BillingWhatsAppDispatchAuthorization).filter_by(job_id=job.id).with_for_update().one_or_none()
    token = db.query(BillingMediaToken).filter_by(id=activation.media_token_id if activation else None).with_for_update().one_or_none()
    preference = db.query(WhatsAppPreference).filter_by(teacher_ci=job.teacher_ci).with_for_update().one_or_none()
    batch = db.query(BillingNotificationBatch).filter_by(id=job.batch_id).with_for_update().one_or_none()
    revision = db.query(BillingPublicationRevision).filter_by(id=activation.publication_revision_id if activation else None).with_for_update().one_or_none()
    publication = db.query(BillingPublication).filter_by(id=revision.publication_id if revision else None).with_for_update().one_or_none()
    return job, activation, authorization, token, preference, batch, revision, publication


def _authorize_activation(db: Any, job_id: int, facts: dict[str, Any], hmac_key: str, owner: str = "worker", configured_sid: str | None = None) -> ActivationDispatch | None:
    """Consume a leased activation authority before the single provider call."""
    db.expire_all()
    locked = _lock_activation_graph(db, job_id, owner)
    if locked is None:
        # The job lock attempt opened a transaction; rollback releases it.
        db.rollback()
        return None
    job, activation, authorization, token, preference, batch, revision, publication = locked
    now = datetime.utcnow()
    fresh = current_delivery_status(db)
    try:
        recipient_hmac = hmac.new(hmac_key.encode("utf-8"), preference.phone_e164.encode("ascii"), hashlib.sha256).hexdigest() if preference else ""
        artifact = __import__("pathlib").Path(token.artifact_path) if token else None
        content = artifact.read_bytes() if artifact else b""
        valid_revision = publication and revision and publication.status == revision.status == "published" and publication.version == revision.version
        if valid_revision:
            validate_publication_revision(revision)
        capable = fresh.get("activation", {}).get("dispatch_capable", fresh.get("activation", {}).get("capable"))
        valid = bool(
            authorization and authorization.activation_id == activation.id and authorization.creator_user_id == activation.actor_user_id
            and authorization.state == "authorized" and authorization.expires_at > now and authorization.consumed_at is None and authorization.revoked_at is None
            and authorization.attestation_code == "dispatch_reviewed_and_authorized_v1" and authorization.release_actor_user_id is not None
            and authorization.release_key_hash and authorization.release_request_digest and authorization.released_at
            and job.lease_expires_at and job.lease_expires_at > now and capable is True
            and fresh.get("global_delivery", {}).get("requested") is False and fresh.get("global_delivery", {}).get("effective") is False
            and fresh.get("provider_configuration", {}).get("ready") is True and fresh.get("provider_live", {}).get("ready") is True
            and fresh.get("worker", {}).get("ready") is True and fresh.get("process_gates", {}).get("official") is True and fresh.get("process_gates", {}).get("dispatch") is True
            and (configured_sid is None or job.content_sid == configured_sid)
            and activation.status == "leased" and preference and preference.is_eligible_for_whatsapp and recipient_hmac and hmac.compare_digest(activation.recipient_hmac, recipient_hmac)
            and preference.teacher_ci == activation.teacher_ci_at_creation == job.teacher_ci and preference.consent_revision == activation.consent_revision
            and token and token.revoked_at is None and token.expires_at > now and token.job_id == job.id and batch and token.batch_id == batch.id
            and job.channel == "whatsapp" and activation.batch_id == batch.id and activation.job_id == job.id and job.content_sid == activation.content_sid and token.teacher_ci == job.teacher_ci
            and activation.publication_revision_id == revision.id and revision.publication_id == publication.id
            and batch.publication_id == activation.publication_id == publication.id
            and batch.publication_version == activation.publication_version == revision.version
            and token.artifact_hash == activation.artifact_hash and token.artifact_size == activation.artifact_size
            and isinstance(job.media_snapshot, dict) and job.media_snapshot == {"token_id": token.id, "artifact_hash": token.artifact_hash, "artifact_size": token.artifact_size}
            and len(content) == token.artifact_size and hashlib.sha256(content).hexdigest() == token.artifact_hash
            and valid_revision and activation.publication_id == publication.id and activation.publication_version == revision.version and activation.billing_digest == revision.billing_digest
        )
    except (OSError, PublicationRevisionError, ValueError, TypeError):
        valid = False
    if not valid:
        _cancel_activation(db, job, activation, "pre_provider_rejected")
        return None
    plaintext = secrets.token_urlsafe(32)
    token.token_hash = hashlib.sha256(plaintext.encode("ascii")).hexdigest()
    token.expires_at = now + timedelta(hours=24)
    authorization.state, authorization.consumed_at = "consumed", now
    job.status = activation.status = "sending"
    db.commit()
    return ActivationDispatch(job, preference.phone_e164, plaintext)


def rollback_unleased_activation(db: Any, *, now: datetime | None = None) -> int:
    """Cancel only queued, unleased activation jobs and revoke their tokens."""
    now = now or datetime.utcnow()
    jobs = db.query(BillingNotificationJob).filter(
        BillingNotificationJob.channel == "whatsapp",
        BillingNotificationJob.intent_type == "activation_test",
        BillingNotificationJob.status == "queued",
        BillingNotificationJob.lease_owner.is_(None),
    ).all()
    ids = [job.id for job in jobs]
    for job in jobs:
        job.status = "cancelled"
        job.next_attempt_at = None
        project_activation_status(db, job, "activation_disabled")
    if ids:
        db.query(BillingMediaToken).filter(BillingMediaToken.job_id.in_(ids), BillingMediaToken.revoked_at.is_(None)).update({"revoked_at": now}, synchronize_session=False)
    db.commit()
    return len(ids)


def rollback_unleased(db: Any, *, now: datetime | None = None) -> int:
    """Legacy rollback: cancel every queued, unleased WhatsApp job."""
    now = now or datetime.utcnow()
    jobs = db.query(BillingNotificationJob).filter(BillingNotificationJob.channel == "whatsapp", BillingNotificationJob.status == "queued", BillingNotificationJob.lease_owner.is_(None)).all()
    for job in jobs:
        job.status, job.next_attempt_at = "cancelled", None
    if jobs:
        db.query(BillingMediaToken).filter(BillingMediaToken.job_id.in_([job.id for job in jobs]), BillingMediaToken.revoked_at.is_(None)).update({"revoked_at": now}, synchronize_session=False)
    db.commit()
    return len(jobs)


def _send(db: Any, runtime: OfficialWhatsAppRuntime, job: BillingNotificationJob | ActivationDispatch) -> Any:
    if isinstance(job, ActivationDispatch):
        return runtime.transport_job(job.job, phone_e164=job.recipient, media_token=job.media_token)
    preference = db.get(WhatsAppPreference, job.teacher_ci)
    token = db.query(BillingMediaToken).filter_by(job_id=job.id, revoked_at=None).first()
    if preference is None or token is None:
        from app.services.whatsapp_service import WhatsAppSendResult
        return WhatsAppSendResult(status="failed", error_code="official_media_or_recipient_unavailable")
    # The plaintext token exists only in this process and is never persisted or logged.
    import hashlib
    import secrets
    plaintext = secrets.token_urlsafe(32)
    token.token_hash = hashlib.sha256(plaintext.encode("ascii")).hexdigest()
    # A delayed lease must not publish a token that expired before Twilio fetches it.
    token.expires_at = datetime.utcnow() + timedelta(hours=24)
    db.commit()
    return runtime.transport_job(job, phone_e164=preference.phone_e164, media_token=plaintext)


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def _is_canonical_callback(value: str, base_url: str, expected_path: str) -> bool:
    try:
        callback, base = urlparse(value), urlparse(base_url)
        return (
            _is_https_url(value)
            and _is_https_url(base_url)
            and (callback.scheme, callback.hostname, callback.port or 443)
            == (base.scheme, base.hostname, base.port or 443)
            and callback.path == expected_path
            and not callback.params and not callback.query and not callback.fragment
            and base.path in ("", "/") and not base.params and not base.query and not base.fragment
        )
    except ValueError:
        return False


if __name__ == "__main__":
    if "--rollback-unleased" in os.sys.argv:
        db = SessionLocal()
        try:
            print(f"cancelled_unleased_jobs={rollback_unleased(db)}")
        finally:
            db.close()
    else:
        raise SystemExit(run())
