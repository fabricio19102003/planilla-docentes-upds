from __future__ import annotations

from types import SimpleNamespace

from app.services.whatsapp_service import WhatsAppSendResult, WhatsAppService


class RecordingTransport:
    def __init__(self):
        self.messages = []

    def send_message(self, message):
        self.messages.append(message)
        return WhatsAppSendResult(status="sent", provider_message_id="SM1")


def test_service_builds_sandbox_message_for_configured_joined_recipient():
    transport = RecordingTransport()
    service = WhatsAppService(settings=_settings(), transport=transport)

    result = service.send_billing_published(_publication(), _user())

    assert result.status == "sent"
    assert len(transport.messages) == 1
    assert transport.messages[0].to == "+59170000000"
    assert transport.messages[0].body == (
        "Hola Dra. Ana Pérez. Tu detalle de honorarios de mayo 2026 ya está "
        "disponible en SIPAD. Ingresá al portal para revisarlo."
    )


def test_service_rejects_non_sandbox_sender_without_calling_transport():
    transport = RecordingTransport()
    settings = _settings()
    settings.TWILIO_WHATSAPP_SANDBOX_FROM = "+59170000001"

    result = WhatsAppService(settings=settings, transport=transport).send_billing_published(
        _publication(), _user()
    )

    assert result.status == "skipped"
    assert result.error_code == "invalid_sandbox_sender"
    assert transport.messages == []


def test_service_rejects_invalid_e164_recipient_without_calling_transport():
    transport = RecordingTransport()
    settings = _settings()
    settings.TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT = "7000000"

    result = WhatsAppService(settings=settings, transport=transport).send_billing_published(
        _publication(), _user()
    )

    assert result.status == "skipped"
    assert result.error_code == "sandbox_recipient_not_configured"
    assert transport.messages == []


def test_service_requires_api_key_credentials_not_master_auth_token():
    transport = RecordingTransport()
    settings = _settings()
    settings.TWILIO_API_KEY_SECRET = None
    settings.TWILIO_AUTH_TOKEN = "must-not-be-used"

    result = WhatsAppService(settings=settings, transport=transport).send_billing_published(
        _publication(), _user()
    )

    assert result.status == "skipped"
    assert result.error_code == "missing_twilio_credentials"
    assert transport.messages == []


def _settings():
    return SimpleNamespace(
        WHATSAPP_ENABLED=True,
        WHATSAPP_MODE="sandbox",
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_API_KEY_SID="SK123",
        TWILIO_API_KEY_SECRET="secret",
        TWILIO_WHATSAPP_SANDBOX_FROM="+14155238886",
        TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT="+59170000000",
    )


def _publication():
    return SimpleNamespace(month=5, year=2026, planilla_type="regular")


def _user():
    return SimpleNamespace(full_name="Dra. Ana Pérez")
