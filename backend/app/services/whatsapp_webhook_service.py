"""Authenticated, durable Twilio webhook projection for official billing WhatsApp."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime
from typing import Callable, Iterable
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.billing_notification import BillingNotificationJob, WhatsAppEvent
from app.models.billing_notification import BillingNotificationBatch
from app.models.billing_publication import BillingPublication
from app.models.user import User
from app.models.whatsapp_preference import WhatsAppPreference
from app.services.billing_notification_service import BillingNotificationService, SqlAlchemyAttemptStore


_VALID_TRANSITIONS = {
    "queued": {"accepted", "sent", "delivered", "read", "failed", "undelivered"},
    "accepted": {"sent", "delivered", "read", "failed", "undelivered"},
    "sent": {"delivered", "read", "failed", "undelivered"},
    "ambiguous": {"accepted", "sent", "delivered", "read", "failed", "undelivered"},
    "delivered": {"read"},
    "read": set(),
    "failed": set(),
    "undelivered": set(),
}
_TERMINAL = {"failed", "undelivered", "read"}
_VALID_STATUS = {status for targets in _VALID_TRANSITIONS.values() for status in targets} | {"queued"}


class WhatsAppWebhookService:
    def __init__(
        self,
        db: Session,
        *,
        auth_token: str | None,
        status_url: str | None,
        inbound_url: str | None,
        now: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        self.db = db
        self.auth_token = auth_token
        self.status_url = status_url
        self.inbound_url = inbound_url
        self.now = now

    def process_status(self, form: Iterable[tuple[str, str]], signature: str | None, raw_query: str) -> str:
        fields = list(form)
        if not self._valid(signature, self.status_url, fields, raw_query):
            return "rejected"
        provider_sid = _value(fields, "MessageSid") or _value(fields, "SmsSid")
        status = (_value(fields, "MessageStatus") or "").lower()
        event, duplicate = self._event("status", provider_sid, fields)
        if duplicate:
            return "duplicate"
        if not BillingNotificationJob.is_provider_sid(provider_sid) or status not in _VALID_STATUS:
            self.db.commit()
            return "ignored"
        job = self.db.query(BillingNotificationJob).filter_by(provider_sid=provider_sid).one_or_none()
        event.job_id = job.id if job else None
        if job is None:
            self.db.commit()
            return "unknown_sid"
        if status not in _VALID_TRANSITIONS.get(job.status, set()):
            self.db.commit()
            return "ignored"
        job.status = status
        job.lease_owner = None
        job.lease_expires_at = None
        job.next_attempt_at = None
        self.db.commit()
        if status in {"failed", "undelivered"}:
            self._send_terminal_email_alternative(job)
        return "projected"

    def reconcile(self, lookup: Callable[[str], str | None], *, limit: int = 100) -> int:
        """Bounded trusted lookup for jobs that retain a provider SID."""
        jobs = (
            self.db.query(BillingNotificationJob)
            .filter(
                BillingNotificationJob.provider_sid.is_not(None),
                BillingNotificationJob.status.in_(("ambiguous", "accepted", "sent")),
            )
            .order_by(BillingNotificationJob.id)
            .limit(limit)
            .all()
        )
        projected = 0
        terminal_jobs: list[BillingNotificationJob] = []
        for job in jobs:
            provider_status = lookup(job.provider_sid)
            if provider_status not in _VALID_STATUS:
                continue
            event, duplicate = self._event("reconciliation", job.provider_sid, [("MessageSid", job.provider_sid), ("MessageStatus", provider_status)])
            if duplicate or provider_status not in _VALID_TRANSITIONS.get(job.status, set()):
                continue
            event.job_id = job.id
            job.status = provider_status
            if provider_status in {"failed", "undelivered"}:
                terminal_jobs.append(job)
            projected += 1
        self.db.commit()
        for job in terminal_jobs:
            self._send_terminal_email_alternative(job)
        return projected

    def _send_terminal_email_alternative(self, job: BillingNotificationJob) -> None:
        """Use the existing durable email attempt key only after a verified terminal event."""
        if "billing_notification_batches" not in inspect(self.db.get_bind()).get_table_names():
            return
        batch = self.db.get(BillingNotificationBatch, job.batch_id)
        publication = self.db.get(BillingPublication, batch.publication_id) if batch else None
        user = self.db.query(User).filter(User.teacher_ci == job.teacher_ci, User.is_active == True).one_or_none()
        if publication is not None and user is not None:
            BillingNotificationService(store=SqlAlchemyAttemptStore(self.db))._send_email_one(publication, user)

    def process_inbound(self, form: Iterable[tuple[str, str]], signature: str | None, raw_query: str) -> str:
        fields = list(form)
        if not self._valid(signature, self.inbound_url, fields, raw_query):
            return "rejected"
        event, duplicate = self._event("inbound", _value(fields, "MessageSid"), fields)
        if duplicate:
            return "duplicate"
        body = (_value(fields, "Body") or "").strip().upper()
        opt_out_type = (_value(fields, "OptOutType") or "").strip().upper()
        sender = _canonical_sender(_value(fields, "From"))
        if body != "STOP" and opt_out_type != "STOP":
            self.db.commit()
            return "ignored"
        preference = (
            self.db.query(WhatsAppPreference)
            .filter(WhatsAppPreference.phone_e164 == sender)
            .one_or_none()
            if sender
            else None
        )
        if preference is None:
            self.db.commit()
            return "unknown_sender"
        event.job_id = None
        preference.opt_out_evidence = "validated_twilio_stop"
        preference.opted_out_at = self.now()
        preference.consent_revision += 1
        self.db.query(BillingNotificationJob).filter(
            BillingNotificationJob.teacher_ci == preference.teacher_ci,
            BillingNotificationJob.channel == "whatsapp",
            BillingNotificationJob.status.in_(("queued", "leased", "sending")),
        ).update(
            {
                "status": "cancelled",
                "lease_owner": None,
                "lease_expires_at": None,
                "next_attempt_at": None,
            },
            synchronize_session=False,
        )
        self.db.commit()
        return "opted_out"

    def _event(self, event_type: str, provider_sid: str | None, fields: list[tuple[str, str]]) -> tuple[WhatsAppEvent, bool]:
        dedupe_key = hashlib.sha256(
            (event_type + "\n" + "\n".join(f"{key}={value}" for key, value in sorted(fields))).encode()
        ).hexdigest()
        event = WhatsAppEvent(
            provider_sid=provider_sid if BillingNotificationJob.is_provider_sid(provider_sid) else None,
            dedupe_key=dedupe_key,
            event_type=event_type,
            facts={"field_names": sorted({key for key, _ in fields})},
            occurred_at=self.now(),
        )
        try:
            with self.db.begin_nested():
                self.db.add(event)
                self.db.flush()
        except IntegrityError:
            return event, True
        return event, False

    def _valid(self, signature: str | None, configured_url: str | None, fields: list[tuple[str, str]], raw_query: str) -> bool:
        if not self.auth_token or not signature or not configured_url:
            return False
        parsed = urlsplit(configured_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            return False
        url = configured_url + (f"?{raw_query}" if raw_query else "")
        payload = url + "".join(key + value for key, value in sorted(fields))
        expected = base64.b64encode(hmac.new(self.auth_token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
        return hmac.compare_digest(expected, signature)


def _value(fields: Iterable[tuple[str, str]], name: str) -> str | None:
    return next((value for key, value in fields if key == name), None)


def _canonical_sender(value: str | None) -> str | None:
    if not value:
        return None
    phone = value.removeprefix("whatsapp:").strip()
    return WhatsAppPreference.canonical_e164(phone)
