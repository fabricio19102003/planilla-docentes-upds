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


def test_email_service_passes_only_exclusions_that_apply_to_docente():
    transport = RecordingTransport()
    service = EmailService(settings=_settings(), transport=transport)

    result = service.send_billing_published(_publication(), [_user()])

    assert result.sent == 1
    message = transport.messages[0]
    assert "Período de corte: 21/Abr/2026 al 20/May/2026" in message.text
    assert "Tarifa por hora académica: Bs 70.00" in message.text
    assert "Feriado institucional" in message.text
    assert "Clase magistral de anatomía" in message.text
    assert "Taller de anatomía" in message.text
    assert "Exclusión histórica" in message.text
    assert "Anatomía de segundo semestre" not in message.text
    assert "Anatomía de otro grupo" not in message.text
    assert "Práctica de cirugía" not in message.text
    assert "Clase magistral de pediatría" not in message.text


def test_email_service_keeps_global_exclusion_without_designations():
    service = EmailService(settings=_settings(), transport=RecordingTransport())
    excluded = {"date": "2026-04-21", "scope": "global", "reason": "Feriado"}

    assert service._filter_excluded_days_for_teacher(
        [excluded], {"designations": []}
    ) == [excluded]


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
            "start_date": "2026-04-21",
            "end_date": "2026-05-20",
            "rate_per_hour": 70.0,
            "excluded_days_json": [
                {"date": "2026-04-21", "scope": "global", "reason": "Feriado institucional"},
                {"date": "2026-04-30", "scope": "semester", "semester_id": "1", "reason": "Clase magistral de anatomía"},
                {"date": "2026-05-02", "scope": "semester", "semester_id": "9", "reason": "Práctica de cirugía"},
                {"date": "2026-05-08", "scope": "subject", "subject_id": "Anatomía", "group_id": "A", "semester_id": "1", "reason": "Taller de anatomía"},
                {"date": "2026-05-10", "scope": "subject", "subject_id": "Anatomía", "group_id": "A", "semester_id": "2", "reason": "Anatomía de segundo semestre"},
                {"date": "2026-05-11", "scope": "subject", "subject_id": "Anatomía", "group_id": "A", "reason": "Exclusión histórica"},
                {"date": "2026-05-12", "scope": "subject", "subject_id": "Anatomía", "group_id": "B", "semester_id": "1", "reason": "Anatomía de otro grupo"},
                {"date": "2026-05-09", "scope": "subject", "subject_id": "Pediatría", "group_id": "B", "reason": "Clase magistral de pediatría"},
            ],
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
