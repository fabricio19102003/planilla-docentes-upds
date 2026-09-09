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


def test_runtime_constructs_when_global_dispatch_is_off_and_readiness_is_flag_independent():
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    runtime = OfficialWhatsAppRuntime.from_settings(settings(
        OFFICIAL_WHATSAPP_ENABLED=False, WHATSAPP_DISPATCH_ENABLED=False,
    ))

    assert runtime is not None
    assert runtime.readiness_facts(sender_status="ONLINE", templates_approved=True)["ready"] is True


def test_runtime_readiness_reports_only_bounded_failure_reasons():
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    runtime = OfficialWhatsAppRuntime.from_settings(settings())
    assert runtime is not None
    cases = (
        ({"sender_status": "OFFLINE", "templates_approved": True}, "sender_unavailable"),
        ({"sender_status": "ONLINE", "templates_approved": False}, "template_unapproved"),
    )
    for facts, reason in cases:
        readiness = runtime.readiness_facts(**facts)
        assert readiness["ready"] is False
        assert readiness["reason"] == reason

    runtime.capacity["available"] = False
    assert runtime.readiness_facts(sender_status="ONLINE", templates_approved=True)["reason"] == "capacity_unavailable"
    assert OfficialWhatsAppRuntime.from_settings(settings(TWILIO_OFFICIAL_MEDIA_MPS=0)) is None


def test_recipient_hmac_key_is_optional_when_activation_is_off_and_required_when_either_gate_is_on():
    import pytest
    from pydantic import ValidationError
    from app.config import Settings

    defaults = {"_env_file": None, "DATABASE_URL": "sqlite:///test.db", "ASYNC_DATABASE_URL": "sqlite+aiosqlite:///test.db"}
    assert Settings(**defaults, WHATSAPP_RECIPIENT_HMAC_KEY="short").WHATSAPP_RECIPIENT_HMAC_KEY == "short"
    for gate in ("BILLING_WHATSAPP_ACTIVATION_API_ENABLED", "BILLING_WHATSAPP_ACTIVATION_DISPATCH_ENABLED"):
        with pytest.raises(ValidationError, match="WHATSAPP_RECIPIENT_HMAC_KEY"):
            Settings(**defaults, **{gate: True}, WHATSAPP_RECIPIENT_HMAC_KEY="short")


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


def test_runtime_transport_uses_numeric_media_path_variable():
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
        "content_variables": '{"1":"api/public/billing-media/opaque.pdf"}',
    }]


def test_activation_dispatch_uses_authorized_current_recipient():
    from app.workers.official_whatsapp_runner import ActivationDispatch, OfficialWhatsAppRuntime, _send
    calls = []
    runtime = OfficialWhatsAppRuntime.from_settings(settings(), transport=type("T", (), {"send": lambda _, **kwargs: calls.append(kwargs)})())
    dispatch = ActivationDispatch(SimpleNamespace(content_sid="HX" + "e" * 32), "+59170000000", "opaque")
    _send(None, runtime, dispatch)
    assert calls[0]["to"] == "+59170000000" and "opaque.pdf" in calls[0]["content_variables"]


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


def test_runner_ordinary_dispatch_authorization_uses_effective_enabled(monkeypatch):
    import pytest
    from app.workers import official_whatsapp_runner as runner

    class Runtime:
        def live_readiness(self):
            return {"ready": True, "capacity": {"available": True}}

    class Database:
        def commit(self):
            pass

        def close(self):
            pass

    class Worker:
        def __init__(self, _db, *, dispatch_allowed, **_kwargs):
            self.dispatch_allowed = dispatch_allowed

        def process_one(self):
            assert self.dispatch_allowed() is True
            raise KeyboardInterrupt

    monkeypatch.setattr(runner, "SessionLocal", Database)
    monkeypatch.setattr(runner, "BillingNotificationWorker", Worker)
    monkeypatch.setattr(runner, "mark_worker_heartbeat", lambda _db: None)
    monkeypatch.setattr(runner.OfficialWhatsAppRuntime, "from_settings", lambda *_args: Runtime())
    monkeypatch.setattr(runner, "status_from_readiness", lambda *_args, **_kwargs: {
        "readiness": {"ready": True}, "effective_enabled": True,
    })
    monkeypatch.setattr("app.config.settings", settings())

    with pytest.raises(KeyboardInterrupt):
        runner.run()
