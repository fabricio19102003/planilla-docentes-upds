from __future__ import annotations

from types import SimpleNamespace

from app.services.billing_notification_service import (
    AttemptClaim,
    BillingNotificationService,
)
from app.services.email_service import EmailAttemptResult, EmailBatchResult, EmailRecipient
from app.services.whatsapp_service import WhatsAppSendResult


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.claims = []

    def claim(self, **values):
        key = values["idempotency_key"]
        self.claims.append(values)
        if key in self.rows:
            return AttemptClaim(owned=False, status=self.rows[key]["status"])
        self.rows[key] = {**values, "status": "pending"}
        return AttemptClaim(owned=True, status="pending")

    def finish(self, key, **values):
        self.rows[key].update(values)


class StubWhatsAppService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def send_billing_published(self, publication, user):
        self.calls.append((publication, user))
        return self.result


class StubEmailService:
    def __init__(self, *, status="sent"):
        self.status = status
        self.calls = []

    def send_billing_published(self, publication, users):
        self.calls.append((publication, users))
        user = users[0]
        recipient = EmailRecipient(
            user_id=user.id,
            name=user.full_name,
            email="redacted@example.invalid",
            teacher_ci=user.teacher_ci,
        )
        error = "provider response with private data" if self.status == "failed" else None
        return EmailBatchResult(
            eligible=1,
            sent=1 if self.status == "sent" else 0,
            failed=1 if self.status == "failed" else 0,
            attempts=(EmailAttemptResult(recipient=recipient, status=self.status, error=error),),
        )


def test_sandbox_sends_one_whatsapp_and_does_not_duplicate_with_email():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(WhatsAppSendResult(status="sent", provider_message_id="SM1"))
    email = StubEmailService()
    users = [_user(1), _user(2)]
    service = _service(store, whatsapp, email, enabled=True)

    result = service.send_billing_published(_publication(), users)

    assert result.sent == 1
    assert result.whatsapp_sent == 1
    assert result.email_sent == 0
    assert result.skipped == 1
    assert len(whatsapp.calls) == 1
    assert email.calls == []
    row = next(iter(store.rows.values()))
    assert row["status"] == "sent"
    assert row["provider_message_id"] == "SM1"
    assert "recipient" not in row


def test_sandbox_failure_falls_back_only_for_representative_and_sanitizes_audit():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(
        WhatsAppSendResult(status="failed", error_code="twilio_http_500")
    )
    email = StubEmailService(status="failed")
    users = [_user(1), _user(2), _user(3)]

    result = _service(store, whatsapp, email, enabled=True).send_billing_published(
        _publication(), users
    )

    assert result.failed == 1
    assert result.skipped == 2
    assert len(email.calls) == 1
    assert email.calls[0][1] == [users[0]]
    errors = {row.get("error_code") for row in store.rows.values()}
    assert errors == {"twilio_http_500", "email_provider_failed"}
    assert all("private" not in (error or "") for error in errors)


def test_completed_sandbox_claim_is_reused_without_second_provider_call():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(WhatsAppSendResult(status="sent", provider_message_id="SM1"))
    email = StubEmailService()
    service = _service(store, whatsapp, email, enabled=True)

    first = service.send_billing_published(_publication(), [_user(1)])
    second = service.send_billing_published(_publication(), [_user(1)])

    assert first.sent == second.sent == 1
    assert len(whatsapp.calls) == 1
    assert email.calls == []


def test_pending_sandbox_claim_is_not_retried_or_fallen_back():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(WhatsAppSendResult(status="sent"))
    email = StubEmailService()
    service = _service(store, whatsapp, email, enabled=True)
    publication = _publication()

    key = service._send_whatsapp(publication, _user(1))[0]
    assert key.status == "sent"
    stored_key = next(iter(store.rows))
    store.rows[stored_key]["status"] = "pending"
    whatsapp.calls.clear()

    result = service.send_billing_published(publication, [_user(1)])

    assert result.sent == 0
    assert result.skipped == 1
    assert result.attempts[0].error_code == "ambiguous_prior_attempt"
    assert whatsapp.calls == []
    assert email.calls == []


def test_whatsapp_disabled_preserves_resend_for_each_user_with_idempotency():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(WhatsAppSendResult(status="sent"))
    email = StubEmailService()
    service = _service(store, whatsapp, email, enabled=False)
    users = [_user(1), _user(2)]

    first = service.send_billing_published(_publication(), users)
    second = service.send_billing_published(_publication(), users)

    assert first.sent == second.sent == 2
    assert first.email_sent == second.email_sent == 2
    assert len(email.calls) == 2
    assert whatsapp.calls == []


def _service(store, whatsapp, email, *, enabled):
    return BillingNotificationService(
        store=store,
        settings=SimpleNamespace(WHATSAPP_ENABLED=enabled),
        whatsapp_service=whatsapp,
        email_service=email,
    )


def _publication():
    return SimpleNamespace(id=9, version=3, month=8, year=2026, planilla_type="regular")


def _user(identifier):
    return SimpleNamespace(
        id=identifier,
        full_name=f"Docente {identifier}",
        teacher_ci=str(identifier),
    )
