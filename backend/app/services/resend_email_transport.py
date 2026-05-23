"""Resend HTTP email transport."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.email_service import EmailMessage, EmailSendResult

logger = logging.getLogger(__name__)


class ResendEmailTransport:
    """Small Resend transport using direct HTTP via httpx."""

    def __init__(
        self,
        *,
        api_key: str,
        from_email: str,
        api_url: str = "https://api.resend.com",
        timeout_seconds: float = 3.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.from_email = from_email
        self.api_url = api_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

    def send_email(self, message: EmailMessage) -> EmailSendResult:
        """Send one email through Resend and map errors to safe results."""

        payload: dict[str, Any] = {
            "from": self.from_email,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            if self.client is not None:
                response = self.client.post(
                    f"{self.api_url}/emails",
                    headers=headers,
                    json=payload,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        f"{self.api_url}/emails",
                        headers=headers,
                        json=payload,
                    )
        except httpx.RequestError as exc:
            logger.warning("Resend email request failed: %s", exc)
            return EmailSendResult(status="failed", error=str(exc))

        if 200 <= response.status_code < 300:
            return EmailSendResult(status="sent")

        error = _provider_error(response)
        logger.warning("Resend email provider failure status=%s error=%s", response.status_code, error)
        return EmailSendResult(status="failed", error=error)


def _provider_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text
    return f"resend_status={response.status_code}: {body}"
