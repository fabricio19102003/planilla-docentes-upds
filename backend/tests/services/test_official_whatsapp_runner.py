from types import SimpleNamespace


def settings(**overrides):
    values = {
        "OFFICIAL_WHATSAPP_ENABLED": True,
        "WHATSAPP_DISPATCH_ENABLED": True,
        "TWILIO_ACCOUNT_SID": "AC" + "a" * 32,
        "TWILIO_API_KEY_SID": "SK" + "b" * 32,
        "TWILIO_API_KEY_SECRET": "private",
        "TWILIO_OFFICIAL_FROM": "+14155550123",
        "TWILIO_OFFICIAL_SENDER_SID": "XE" + "a" * 32,
        "TWILIO_OFFICIAL_CONTENT_SID": "HX" + "c" * 32,
        "TWILIO_STATUS_CALLBACK_URL": "https://sipad.example/api/twilio/whatsapp/status",
        "TWILIO_INBOUND_CALLBACK_URL": "https://sipad.example/api/twilio/whatsapp/inbound",
        "TWILIO_AUTH_TOKEN": "signing-secret",
        "BILLING_MEDIA_PUBLIC_BASE_URL": "https://sipad.example",
        "TWILIO_OFFICIAL_MEDIA_MPS": 2.0,
        "TWILIO_OFFICIAL_MOVING_RECIPIENT_LIMIT": 20,
        "TWILIO_OFFICIAL_CAPACITY_WINDOW_SECONDS": 86400,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_runtime_config_is_fail_closed_and_never_exposes_secrets():
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    assert OfficialWhatsAppRuntime.from_settings(settings(TWILIO_API_KEY_SECRET=None)) is None
    assert OfficialWhatsAppRuntime.from_settings(settings(BILLING_MEDIA_PUBLIC_BASE_URL="http://sipad.example")) is None
    assert OfficialWhatsAppRuntime.from_settings(settings(TWILIO_OFFICIAL_MEDIA_MPS=0)) is None
    assert OfficialWhatsAppRuntime.from_settings(settings(
        TWILIO_STATUS_CALLBACK_URL="https://sipad.example.evil/api/twilio/whatsapp/status"
    )) is None
    assert OfficialWhatsAppRuntime.from_settings(settings(
        TWILIO_INBOUND_CALLBACK_URL="https://sipad.example/api/twilio/whatsapp/status"
    )) is None

    runtime = OfficialWhatsAppRuntime.from_settings(settings())
    assert runtime is not None
    facts = runtime.readiness_facts(sender_status="ONLINE", templates_approved=True)
    assert facts["ready"] is True
    assert facts["capacity"]["moving_recipient_limit"] == 20
    assert "private" not in repr(runtime)


def test_runtime_transport_uses_content_contract_and_public_media_url():
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    calls = []

    class Transport:
        def send(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status="sent", provider_message_id="SM" + "d" * 32)

    runtime = OfficialWhatsAppRuntime.from_settings(settings(), transport=Transport())
    job = SimpleNamespace(content_sid="HX" + "e" * 32, teacher_ci="teacher")
    result = runtime.transport_job(job, phone_e164="+59170000000", media_token="opaque")

    assert result.status == "sent"
    assert calls == [{
        "to": "+59170000000",
        "content_sid": "HX" + "e" * 32,
        "content_variables": '{"twilio/media":"https://sipad.example/api/public/billing-media/opaque"}',
    }]


def test_runtime_rejects_malformed_callback_ports_fail_closed():
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    assert OfficialWhatsAppRuntime.from_settings(settings(
        TWILIO_STATUS_CALLBACK_URL="https://sipad.example:99999/api/twilio/whatsapp/status"
    )) is None
    assert OfficialWhatsAppRuntime.from_settings(settings(
        BILLING_MEDIA_PUBLIC_BASE_URL="https://sipad.example:99999"
    )) is None


def test_runtime_rejects_query_and_effective_port_mismatches():
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    assert OfficialWhatsAppRuntime.from_settings(settings(
        TWILIO_STATUS_CALLBACK_URL="https://sipad.example/api/twilio/whatsapp/status?trace=1"
    )) is None
    assert OfficialWhatsAppRuntime.from_settings(settings(
        BILLING_MEDIA_PUBLIC_BASE_URL="https://sipad.example:444"
    )) is None
    assert OfficialWhatsAppRuntime.from_settings(settings(
        TWILIO_INBOUND_CALLBACK_URL="https://sipad.example:invalid/api/twilio/whatsapp/inbound"
    )) is None
