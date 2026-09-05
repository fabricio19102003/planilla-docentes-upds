from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import logging
from typing import Any, Literal, Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings as default_settings
from app.models.outbound_notification_attempt import OutboundNotificationAttempt
from app.services.email_service import EmailService
from app.services.whatsapp_service import WhatsAppSendResult, WhatsAppService


logger = logging.getLogger(__name__)
NotificationStatus = Literal["sent", "failed", "skipped"]


@dataclass(frozen=True)
class NotificationAttempt:
    channel: str
    status: NotificationStatus
    error_code: str | None = None


@dataclass(frozen=True)
class NotificationBatchResult:
    eligible: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    whatsapp_sent: int = 0
    email_sent: int = 0
    attempts: tuple[NotificationAttempt, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AttemptClaim:
    owned: bool
    status: str


class AttemptStore(Protocol):
    def claim(
        self,
        *,
        idempotency_key: str,
        publication: Any,
        user_id: int | None,
        channel: str,
        provider: str,
        mode: str,
    ) -> AttemptClaim: ...

    def finish(
        self,
        idempotency_key: str,
        *,
        status: NotificationStatus,
        provider_message_id: str | None = None,
        error_code: str | None = None,
    ) -> None: ...


class SqlAlchemyAttemptStore:
    """Durable at-most-once claims; pending rows remain ambiguous and are never retried."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def claim(
        self,
        *,
        idempotency_key: str,
        publication: Any,
        user_id: int | None,
        channel: str,
        provider: str,
        mode: str,
    ) -> AttemptClaim:
        existing = self._get(idempotency_key)
        if existing is not None:
            return AttemptClaim(owned=False, status=existing.status)

        attempt = OutboundNotificationAttempt(
            idempotency_key=idempotency_key,
            publication_id=int(publication.id),
            publication_version=int(publication.version),
            user_id=user_id,
            channel=channel,
            provider=provider,
            mode=mode,
            status="pending",
        )
        self.db.add(attempt)
        try:
            self.db.commit()
            return AttemptClaim(owned=True, status="pending")
        except IntegrityError:
            self.db.rollback()
            concurrent = self._get(idempotency_key)
            if concurrent is None:
                raise
            return AttemptClaim(owned=False, status=concurrent.status)

    def finish(
        self,
        idempotency_key: str,
        *,
        status: NotificationStatus,
        provider_message_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        attempt = self._get(idempotency_key)
        if attempt is None or attempt.status != "pending":
            raise RuntimeError("outbound_attempt_not_pending")
        attempt.status = status
        attempt.provider_message_id = provider_message_id
        attempt.error_code = error_code
        self.db.commit()

    def _get(self, idempotency_key: str) -> OutboundNotificationAttempt | None:
        return (
            self.db.query(OutboundNotificationAttempt)
            .filter(OutboundNotificationAttempt.idempotency_key == idempotency_key)
            .first()
        )


class BillingNotificationService:
    """WhatsApp-first billing notifications with audited, at-most-once email fallback."""

    def __init__(
        self,
        *,
        store: AttemptStore,
        settings: Any = default_settings,
        whatsapp_service: WhatsAppService | None = None,
        email_service: EmailService | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.whatsapp_service = whatsapp_service or WhatsAppService(settings=settings)
        self.email_service = email_service or EmailService(settings=settings)

    def send_billing_published(self, publication: Any, docente_users: list[Any]) -> NotificationBatchResult:
        if not docente_users:
            return NotificationBatchResult()

        if not getattr(self.settings, "WHATSAPP_ENABLED", False):
            return self._send_email_batch(publication, docente_users)

        # Sandbox is a single explicitly joined test destination. Only one
        # representative teacher may be sent or fall back to email per batch.
        representative = docente_users[0]
        whatsapp_attempt, prior_pending = self._send_whatsapp(publication, representative)
        attempts = [whatsapp_attempt]
        remainder = max(0, len(docente_users) - 1)

        if whatsapp_attempt.status == "sent":
            return NotificationBatchResult(
                eligible=1,
                sent=1,
                skipped=remainder,
                whatsapp_sent=1,
                attempts=tuple(attempts),
            )
        if prior_pending:
            return NotificationBatchResult(
                eligible=1,
                skipped=len(docente_users),
                attempts=tuple(attempts),
            )

        fallback = self._send_email_one(publication, representative)
        attempts.extend(fallback.attempts)
        return NotificationBatchResult(
            eligible=max(1, fallback.eligible),
            sent=fallback.sent,
            failed=fallback.failed,
            skipped=fallback.skipped + remainder,
            email_sent=fallback.email_sent,
            attempts=tuple(attempts),
        )

    def _send_whatsapp(self, publication: Any, user: Any) -> tuple[NotificationAttempt, bool]:
        key = _attempt_key(publication, None, "whatsapp", "sandbox")
        claim = self.store.claim(
            idempotency_key=key,
            publication=publication,
            user_id=int(getattr(user, "id", 0) or 0) or None,
            channel="whatsapp",
            provider="twilio",
            mode="sandbox",
        )
        if not claim.owned:
            if claim.status == "sent":
                return NotificationAttempt(channel="whatsapp", status="sent"), False
            if claim.status == "pending":
                return NotificationAttempt(
                    channel="whatsapp", status="skipped", error_code="ambiguous_prior_attempt"
                ), True
            return NotificationAttempt(
                channel="whatsapp", status="failed", error_code="prior_whatsapp_failure"
            ), False

        result = self.whatsapp_service.send_billing_published(publication, user)
        self.store.finish(
            key,
            status=result.status,
            provider_message_id=result.provider_message_id,
            error_code=result.error_code,
        )
        return NotificationAttempt(
            channel="whatsapp", status=result.status, error_code=result.error_code
        ), False

    def _send_email_batch(self, publication: Any, users: list[Any]) -> NotificationBatchResult:
        totals = NotificationBatchResult()
        attempts: list[NotificationAttempt] = []
        for user in users:
            result = self._send_email_one(publication, user)
            totals = NotificationBatchResult(
                eligible=totals.eligible + result.eligible,
                sent=totals.sent + result.sent,
                failed=totals.failed + result.failed,
                skipped=totals.skipped + result.skipped,
                email_sent=totals.email_sent + result.email_sent,
            )
            attempts.extend(result.attempts)
        return NotificationBatchResult(
            eligible=totals.eligible,
            sent=totals.sent,
            failed=totals.failed,
            skipped=totals.skipped,
            email_sent=totals.email_sent,
            attempts=tuple(attempts),
        )

    def _send_email_one(self, publication: Any, user: Any) -> NotificationBatchResult:
        user_id = int(getattr(user, "id", 0) or 0) or None
        key = _attempt_key(publication, user_id, "email", "resend")
        claim = self.store.claim(
            idempotency_key=key,
            publication=publication,
            user_id=user_id,
            channel="email",
            provider="resend",
            mode="fallback",
        )
        if not claim.owned:
            if claim.status == "sent":
                return NotificationBatchResult(
                    eligible=1,
                    sent=1,
                    email_sent=1,
                    attempts=(NotificationAttempt(channel="email", status="sent"),),
                )
            return NotificationBatchResult(
                eligible=1,
                skipped=1,
                attempts=(NotificationAttempt(
                    channel="email", status="skipped", error_code="prior_email_attempt"
                ),),
            )

        email_result = self.email_service.send_billing_published(publication, [user])
        email_attempts = getattr(email_result, "attempts", ())
        email_attempt = email_attempts[0] if email_attempts else None
        status: NotificationStatus
        if email_result.sent:
            status = "sent"
        elif email_result.failed:
            status = "failed"
        else:
            status = "skipped"
        error_code = _safe_email_error_code(email_attempt.error if email_attempt else None, status)
        self.store.finish(key, status=status, error_code=error_code)
        return NotificationBatchResult(
            eligible=email_result.eligible,
            sent=email_result.sent,
            failed=email_result.failed,
            skipped=email_result.skipped,
            email_sent=email_result.sent,
            attempts=(NotificationAttempt(channel="email", status=status, error_code=error_code),),
        )


def _attempt_key(publication: Any, user_id: int | None, channel: str, mode: str) -> str:
    raw = ":".join(
        (
            "billing",
            str(getattr(publication, "id", "")),
            str(getattr(publication, "version", "")),
            str(getattr(publication, "planilla_type", "regular") or "regular"),
            str(user_id or "batch"),
            channel,
            mode,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_email_error_code(error: str | None, status: NotificationStatus) -> str | None:
    safe_codes = {
        "missing_recipient_email",
        "missing_billing_snapshot",
        "missing_billing_rows",
        "test_mode_already_sent",
    }
    if error in safe_codes:
        return error
    if status == "failed":
        return "email_provider_failed"
    if status == "skipped":
        return "email_unavailable"
    return None
