from __future__ import annotations

import json

import httpx

from app.services.email_service import EmailMessage
from app.services.resend_email_transport import ResendEmailTransport


def test_resend_transport_posts_payload_and_auth_header():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"id": "email_123"})

    transport = ResendEmailTransport(
        api_key="test-key",
        from_email="UPDS <facturacion@example.com>",
        api_url="https://api.resend.com/",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = transport.send_email(
        EmailMessage(
            to="docente@example.com",
            subject="Detalle de honorarios",
            html="<p>Hola</p>",
            text="Hola",
        )
    )

    assert result.status == "sent"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"] == {
        "from": "UPDS <facturacion@example.com>",
        "to": ["docente@example.com"],
        "subject": "Detalle de honorarios",
        "html": "<p>Hola</p>",
        "text": "Hola",
    }


def test_resend_transport_maps_provider_failure_to_failed_result():
    transport = ResendEmailTransport(
        api_key="test-key",
        from_email="facturacion@example.com",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(500, json={"message": "boom"}))
        ),
    )

    result = transport.send_email(_message())

    assert result.status == "failed"
    assert "resend_status=500" in result.error
    assert "boom" in result.error


def test_resend_transport_maps_network_failure_to_failed_result():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    transport = ResendEmailTransport(
        api_key="test-key",
        from_email="facturacion@example.com",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = transport.send_email(_message())


    assert result.status == "failed"
    assert "network down" in result.error


def _message() -> EmailMessage:
    return EmailMessage(
        to="docente@example.com",
        subject="Detalle de honorarios",
        html="<p>Hola</p>",
        text="Hola",
    )
