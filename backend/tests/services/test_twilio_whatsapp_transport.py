from __future__ import annotations

import base64
from urllib.parse import parse_qs

import httpx

from app.services.twilio_whatsapp_transport import TwilioWhatsAppTransport
from app.services.whatsapp_service import WhatsAppMessage


def test_transport_uses_api_key_basic_auth_and_twilio_form_contract():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["form"] = parse_qs(request.content.decode())
        return httpx.Response(201, json={"sid": "SM123"})

    transport = TwilioWhatsAppTransport(
        account_sid="AC123",
        api_key_sid="SK123",
        api_key_secret="secret-value",
        from_number="+14155238886",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = transport.send_message(
        WhatsAppMessage(to="+59170000000", body="Mensaje de prueba")
    )

    expected_auth = base64.b64encode(b"SK123:secret-value").decode()
    assert result.status == "sent"
    assert result.provider_message_id == "SM123"
    assert captured["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    assert captured["authorization"] == f"Basic {expected_auth}"
    assert captured["form"] == {
        "From": ["whatsapp:+14155238886"],
        "To": ["whatsapp:+59170000000"],
        "Body": ["Mensaje de prueba"],
    }


def test_transport_maps_provider_error_without_persisting_response_body():
    transport = TwilioWhatsAppTransport(
        account_sid="AC123",
        api_key_sid="SK123",
        api_key_secret="secret-value",
        from_number="+14155238886",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    400,
                    json={"code": 63015, "message": "contains private destination data"},
                )
            )
        ),
    )

    result = transport.send_message(WhatsAppMessage(to="+59170000000", body="Hola"))

    assert result.status == "failed"
    assert result.error_code == "twilio_http_400_63015"
    assert "private" not in result.error_code


def test_transport_maps_network_error_to_stable_safe_code():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private network details", request=request)

    transport = TwilioWhatsAppTransport(
        account_sid="AC123",
        api_key_sid="SK123",
        api_key_secret="secret-value",
        from_number="+14155238886",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = transport.send_message(WhatsAppMessage(to="+59170000000", body="Hola"))

    assert result.status == "failed"
    assert result.error_code == "twilio_network_error"
