from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal, Protocol

from app.config import settings as default_settings


WhatsAppStatus = Literal["sent", "failed", "skipped", "ambiguous"]
_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
_TWILIO_SANDBOX_NUMBER = "+14155238886"


@dataclass(frozen=True)
class WhatsAppMessage:
    to: str
    body: str


@dataclass(frozen=True)
class WhatsAppSendResult:
    status: WhatsAppStatus
    provider_message_id: str | None = None
    error_code: str | None = None


class WhatsAppTransport(Protocol):
    def send_message(self, message: WhatsAppMessage) -> WhatsAppSendResult: ...


class WhatsAppService:
    """Configuration-gated, provider-independent WhatsApp billing notifier."""

    def __init__(self, *, settings: Any = default_settings, transport: WhatsAppTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    def send_billing_published(self, publication: Any, user: Any) -> WhatsAppSendResult:
        if not getattr(self.settings, "WHATSAPP_ENABLED", False):
            return WhatsAppSendResult(status="skipped", error_code="whatsapp_disabled")
        if getattr(self.settings, "WHATSAPP_MODE", None) != "sandbox":
            return WhatsAppSendResult(status="skipped", error_code="unsupported_whatsapp_mode")

        sender = _clean_e164(getattr(self.settings, "TWILIO_WHATSAPP_SANDBOX_FROM", None))
        recipient = _clean_e164(
            getattr(self.settings, "TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT", None)
        )
        if sender != _TWILIO_SANDBOX_NUMBER:
            return WhatsAppSendResult(status="skipped", error_code="invalid_sandbox_sender")
        if recipient is None:
            return WhatsAppSendResult(status="skipped", error_code="sandbox_recipient_not_configured")
        if not self._has_credentials():
            return WhatsAppSendResult(status="skipped", error_code="missing_twilio_credentials")

        transport = self.transport or self._build_transport(sender)
        message = WhatsAppMessage(
            to=recipient,
            body=_billing_message(publication, user),
        )
        try:
            return transport.send_message(message)
        except Exception:
            # An unexpected exception may happen after the provider accepted
            # the request. Keep the outcome ambiguous so callers never send a
            # duplicate notification through a fallback channel.
            return WhatsAppSendResult(status="ambiguous", error_code="twilio_transport_exception")

    def _has_credentials(self) -> bool:
        return all(
            getattr(self.settings, field, None)
            for field in ("TWILIO_ACCOUNT_SID", "TWILIO_API_KEY_SID", "TWILIO_API_KEY_SECRET")
        )

    def _build_transport(self, sender: str) -> WhatsAppTransport:
        from app.services.twilio_whatsapp_transport import TwilioWhatsAppTransport

        return TwilioWhatsAppTransport(
            account_sid=getattr(self.settings, "TWILIO_ACCOUNT_SID"),
            api_key_sid=getattr(self.settings, "TWILIO_API_KEY_SID"),
            api_key_secret=getattr(self.settings, "TWILIO_API_KEY_SECRET"),
            from_number=sender,
            api_base_url=getattr(self.settings, "TWILIO_API_BASE_URL", "https://api.twilio.com"),
            timeout_seconds=getattr(self.settings, "WHATSAPP_TIMEOUT_SECONDS", 3.0),
        )


def _clean_e164(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if _E164_RE.fullmatch(cleaned) else None


def _billing_message(publication: Any, user: Any) -> str:
    month = _month_name(getattr(publication, "month", ""))
    year = getattr(publication, "year", "")
    name = str(getattr(user, "full_name", None) or "Docente").strip()
    planilla_type = getattr(publication, "planilla_type", "regular") or "regular"
    detail = " de prácticas" if planilla_type == "practice" else ""
    return (
        f"Hola {name}. Tu detalle de honorarios{detail} de {month} {year} "
        "ya está disponible en SIPAD. Ingresá al portal para revisarlo."
    )


def _month_name(value: Any) -> str:
    names = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
        7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
    }
    try:
        return names.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value)
