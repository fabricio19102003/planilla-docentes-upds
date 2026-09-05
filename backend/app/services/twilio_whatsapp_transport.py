"""Twilio WhatsApp transport using API Key authentication over HTTP."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.whatsapp_service import WhatsAppMessage, WhatsAppSendResult


logger = logging.getLogger(__name__)


class TwilioWhatsAppTransport:
    def __init__(
        self,
        *,
        account_sid: str,
        api_key_sid: str,
        api_key_secret: str,
        from_number: str,
        api_base_url: str = "https://api.twilio.com",
        timeout_seconds: float = 3.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.account_sid = account_sid
        self.api_key_sid = api_key_sid
        self.api_key_secret = api_key_secret
        self.from_number = from_number
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

    def send_message(self, message: WhatsAppMessage) -> WhatsAppSendResult:
        url = f"{self.api_base_url}/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        payload = {
            "From": f"whatsapp:{self.from_number}",
            "To": f"whatsapp:{message.to}",
            "Body": message.body,
        }
        try:
            if self.client is not None:
                response = self.client.post(url, auth=(self.api_key_sid, self.api_key_secret), data=payload)
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        url,
                        auth=(self.api_key_sid, self.api_key_secret),
                        data=payload,
                    )
        except httpx.ConnectError:
            logger.warning("Twilio WhatsApp request could not connect")
            return WhatsAppSendResult(status="failed", error_code="twilio_connect_error")
        except httpx.RequestError:
            # Once request dispatch begins, a timeout/write/read failure cannot
            # prove whether Twilio accepted the message. Treat it as ambiguous
            # rather than triggering an email that could duplicate delivery.
            logger.warning("Twilio WhatsApp request ended with an ambiguous network outcome")
            return WhatsAppSendResult(
                status="ambiguous", error_code="twilio_delivery_ambiguous"
            )

        if 200 <= response.status_code < 300:
            provider_message_id = _message_sid(response)
            return WhatsAppSendResult(status="sent", provider_message_id=provider_message_id)

        error_code = _provider_error_code(response)
        logger.warning(
            "Twilio WhatsApp provider failure status=%s code=%s",
            response.status_code,
            error_code,
        )
        return WhatsAppSendResult(status="failed", error_code=error_code)


def _message_sid(response: httpx.Response) -> str | None:
    try:
        value = response.json().get("sid")
    except (ValueError, AttributeError):
        return None
    return str(value)[:100] if value else None


def _provider_error_code(response: httpx.Response) -> str:
    code: Any = None
    try:
        code = response.json().get("code")
    except (ValueError, AttributeError):
        pass
    suffix = f"_{str(code)[:20]}" if code is not None else ""
    return f"twilio_http_{response.status_code}{suffix}"
