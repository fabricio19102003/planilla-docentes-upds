"""Process entry point for the fail-closed official WhatsApp billing worker."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import httpx
import os
from dataclasses import dataclass
from time import sleep
from typing import Any
from urllib.parse import urljoin, urlparse

from app.database import SessionLocal
from app.models.billing_notification import BillingMediaToken, BillingNotificationJob
from app.models.whatsapp_preference import WhatsAppPreference
from app.services.twilio_content_transport import TwilioContentTransport
from app.services.twilio_readiness_adapter import TwilioReadinessAdapter
from app.workers.billing_notification_worker import BillingNotificationWorker

logger = logging.getLogger(__name__)


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
    def from_settings(cls, settings: Any, *, transport: Any | None = None) -> "OfficialWhatsAppRuntime | None":
        fields = (
            "TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET",
            "TWILIO_OFFICIAL_FROM", "TWILIO_OFFICIAL_SENDER_SID", "TWILIO_OFFICIAL_CONTENT_SID",
            "TWILIO_STATUS_CALLBACK_URL", "TWILIO_INBOUND_CALLBACK_URL", "TWILIO_AUTH_TOKEN",
            "BILLING_MEDIA_PUBLIC_BASE_URL",
        )
        if not all(getattr(settings, name, None) for name in fields):
            return None
        if not (getattr(settings, "OFFICIAL_WHATSAPP_ENABLED", False) and getattr(settings, "WHATSAPP_DISPATCH_ENABLED", False)):
            return None
        base_url = settings.BILLING_MEDIA_PUBLIC_BASE_URL
        if not _is_https_url(base_url) or not _is_canonical_callback(
            settings.TWILIO_STATUS_CALLBACK_URL, base_url, "/api/twilio/whatsapp/status"
        ) or not _is_canonical_callback(
            settings.TWILIO_INBOUND_CALLBACK_URL, base_url, "/api/twilio/whatsapp/inbound"
        ):
            return None
        capacity = {
            "available": True,
            "moving_recipient_limit": getattr(settings, "TWILIO_OFFICIAL_MOVING_RECIPIENT_LIMIT", 0),
            "media_mps": getattr(settings, "TWILIO_OFFICIAL_MEDIA_MPS", 0),
            "window_seconds": getattr(settings, "TWILIO_OFFICIAL_CAPACITY_WINDOW_SECONDS", 86400),
        }
        if not isinstance(capacity["moving_recipient_limit"], int) or capacity["moving_recipient_limit"] < 1:
            return None
        if not isinstance(capacity["media_mps"], (int, float)) or capacity["media_mps"] <= 0:
            return None
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
            "official_enabled": True, "dispatch_enabled": True,
            "sender_status": sender_status, "templates_approved": templates_approved,
            "credentials_valid": True, "canonical_callback": True, "capacity": self.capacity,
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
            return self.readiness_facts()

    def transport_job(self, job: BillingNotificationJob, *, phone_e164: str, media_token: str) -> Any:
        return self.transport.send(
            to=phone_e164,
            content_sid=job.content_sid or self.default_content_sid,
            content_variables=json.dumps({"twilio/media": urljoin(self.media_base_url + "/", f"api/public/billing-media/{media_token}")}, separators=(",", ":")),
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
            worker = BillingNotificationWorker(
                db,
                readiness=runtime.live_readiness,
                transport=lambda job: _send(db, runtime, job),
                owner=f"official-whatsapp-{os.getpid()}",
            )
            if worker.process_one() is None:
                sleep(1)
        except Exception:
            logger.exception("Official WhatsApp worker cycle failed")
            sleep(5)
        finally:
            db.close()


def rollback_unleased(db: Any, *, now: datetime | None = None) -> int:
    """Cancel only jobs no worker owns and revoke only their bound media tokens."""
    now = now or datetime.utcnow()
    jobs = db.query(BillingNotificationJob).filter(
        BillingNotificationJob.channel == "whatsapp",
        BillingNotificationJob.status == "queued",
        BillingNotificationJob.lease_owner.is_(None),
    ).all()
    ids = [job.id for job in jobs]
    for job in jobs:
        job.status = "cancelled"
        job.next_attempt_at = None
    if ids:
        db.query(BillingMediaToken).filter(BillingMediaToken.job_id.in_(ids), BillingMediaToken.revoked_at.is_(None)).update({"revoked_at": now}, synchronize_session=False)
    db.commit()
    return len(ids)


def _send(db: Any, runtime: OfficialWhatsAppRuntime, job: BillingNotificationJob) -> Any:
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
