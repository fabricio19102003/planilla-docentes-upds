from __future__ import annotations

from types import SimpleNamespace

from app.services.email_service import EmailSendResult, EmailService


class RecordingTransport:
    def __init__(self, result: EmailSendResult | None = None, *, raise_error: Exception | None = None):
        self.result = result or EmailSendResult(status="sent")
        self.raise_error = raise_error
        self.messages = []

    def send_email(self, message):
        self.messages.append(message)
        if self.raise_error:
            raise self.raise_error
        return self.result


def test_email_service_skips_without_transport_when_disabled():
    transport = RecordingTransport()
    service = EmailService(settings=_settings(enabled=False), transport=transport)

    result = service.send_billing_published(_publication(), [_user()])

    assert result.skipped == 1
    assert result.eligible == 0
    assert transport.messages == []


def test_email_service_skips_without_transport_when_provider_config_is_missing():
    transport = RecordingTransport()
    service = EmailService(settings=_settings(api_key=None), transport=transport)

    result = service.send_billing_published(_publication(), [_user()])

    assert result.skipped == 1
    assert result.eligible == 0
    assert transport.messages == []


def test_email_service_skips_missing_recipient_email():
    transport = RecordingTransport()
    service = EmailService(settings=_settings(), transport=transport)
    user = _user(email="", teacher_email="")

    result = service.send_billing_published(_publication(), [user])

    assert result.skipped == 1
    assert result.eligible == 0
    assert result.attempts[0].error == "missing_recipient_email"
    assert transport.messages == []


def test_email_service_sends_billing_email_from_snapshot_and_teacher_email_fallback():
    transport = RecordingTransport()
    service = EmailService(settings=_settings(), transport=transport)
    user = _user(email=None, teacher_email="teacher@example.com")

    result = service.send_billing_published(_publication(), [user])

    assert result.eligible == 1
    assert result.sent == 1
    assert result.failed == 0
    assert result.skipped == 0
    assert len(transport.messages) == 1
    message = transport.messages[0]
    assert message.to == "teacher@example.com"
    assert message.subject == "Detalle de honorarios docentes - Mayo 2026"
    assert "Anatomía" in message.html
    assert "Bs 123.45" in message.text


def test_email_service_aggregates_provider_failure_without_raising():
    transport = RecordingTransport(EmailSendResult(status="failed", error="provider down"))
    service = EmailService(settings=_settings(), transport=transport)

    result = service.send_billing_published(_publication(), [_user()])

    assert result.eligible == 1
    assert result.sent == 0
    assert result.failed == 1
    assert result.skipped == 0
    assert result.attempts[0].error == "provider down"


def test_email_service_treats_transport_exception_as_failed_attempt():
    transport = RecordingTransport(raise_error=RuntimeError("boom"))
    service = EmailService(settings=_settings(), transport=transport)

    result = service.send_billing_published(_publication(), [_user()])

    assert result.failed == 1
    assert result.attempts[0].status == "failed"
    assert result.attempts[0].error == "boom"


def _settings(enabled=True, api_key="test-key", from_email="facturacion@example.com"):
    return SimpleNamespace(
        EMAIL_ENABLED=enabled,
        RESEND_API_KEY=api_key,
        RESEND_FROM_EMAIL=from_email,
        RESEND_API_URL="https://api.resend.com",
        EMAIL_TIMEOUT_SECONDS=3.0,
    )


def _user(email="user@example.com", teacher_email="teacher@example.com"):
    return SimpleNamespace(
        id=7,
        full_name="Dra. Ana Pérez",
        email=email,
        teacher_ci="123",
        teacher=SimpleNamespace(ci="123", full_name="Dra. Ana Pérez", email=teacher_email),
    )


def _publication():
    return SimpleNamespace(
        month=5,
        year=2026,
        billing_snapshot={
            "teacher_details": [
                {
                    "teacher_ci": "123",
                    "designations": [
                        {
                            "subject": "Anatomía",
                            "payment": "123.45",
                            "group": "A",
                            "semester": "1",
                        }
                    ],
                }
            ]
        },
    )
