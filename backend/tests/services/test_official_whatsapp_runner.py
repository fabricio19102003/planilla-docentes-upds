from types import SimpleNamespace

import httpx
import pytest


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


def _mock_readiness_client(monkeypatch, responses):
    from app.workers import official_whatsapp_runner as runner

    calls = []

    class Client:
        def __init__(self, *, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url, *, auth):
            calls.append((url, auth))
            return responses[url]

    monkeypatch.setattr(runner.httpx, "Client", Client)
    return calls


def _json_response(url, payload, *, status_code=200):
    return httpx.Response(status_code, request=httpx.Request("GET", url), json=payload)


def test_live_readiness_uses_exact_twilio_urls_and_accepts_approved_utility(monkeypatch):
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    runtime = OfficialWhatsAppRuntime.from_settings(settings())
    sender_url = f"https://messaging.twilio.com/v2/Channels/Senders/{runtime.sender_sid}"
    approval_url = f"https://content.twilio.com/v1/Content/{runtime.default_content_sid}/ApprovalRequests"
    calls = _mock_readiness_client(monkeypatch, {
        sender_url: _json_response(sender_url, {"status": "ONLINE"}),
        approval_url: _json_response(approval_url, {
            "whatsapp": {"status": "ApPrOvEd", "category": "UTILITY"},
        }),
    })

    assert runtime.live_readiness()["ready"] is True
    assert calls == [
        (sender_url, (runtime.api_key_sid, runtime.api_key_secret)),
        (approval_url, (runtime.api_key_sid, runtime.api_key_secret)),
    ]


@pytest.mark.parametrize("status,category", [
    ("pending", "UTILITY"),
    ("rejected", "UTILITY"),
    ("approved", "MARKETING"),
])
def test_live_readiness_rejects_unapproved_or_non_utility_template(monkeypatch, status, category):
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    runtime = OfficialWhatsAppRuntime.from_settings(settings())
    sender_url = f"https://messaging.twilio.com/v2/Channels/Senders/{runtime.sender_sid}"
    approval_url = f"https://content.twilio.com/v1/Content/{runtime.default_content_sid}/ApprovalRequests"
    _mock_readiness_client(monkeypatch, {
        sender_url: _json_response(sender_url, {"status": "ONLINE"}),
        approval_url: _json_response(approval_url, {
            "whatsapp": {"status": status, "category": category},
        }),
    })

    readiness = runtime.live_readiness()
    assert readiness["ready"] is False
    assert readiness["reason"] == "template_unapproved"


@pytest.mark.parametrize("failure", ["sender_http", "approval_http", "malformed_json", "malformed_payload"])
def test_live_readiness_classifies_provider_failures_as_unavailable(monkeypatch, failure):
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    runtime = OfficialWhatsAppRuntime.from_settings(settings())
    sender_url = f"https://messaging.twilio.com/v2/Channels/Senders/{runtime.sender_sid}"
    approval_url = f"https://content.twilio.com/v1/Content/{runtime.default_content_sid}/ApprovalRequests"
    responses = {
        sender_url: _json_response(sender_url, {"status": "ONLINE"}),
        approval_url: _json_response(approval_url, {
            "whatsapp": {"status": "approved", "category": "utility"},
        }),
    }
    if failure == "sender_http":
        responses[sender_url] = _json_response(sender_url, {"status": "ONLINE"}, status_code=401)
    elif failure == "approval_http":
        responses[approval_url] = _json_response(approval_url, {
            "whatsapp": {"status": "approved", "category": "utility"},
        }, status_code=404)
    elif failure == "malformed_json":
        responses[approval_url] = httpx.Response(
            200, request=httpx.Request("GET", approval_url), content=b"not-json",
        )
    else:
        responses[approval_url] = _json_response(approval_url, {"whatsapp": []})
    _mock_readiness_client(monkeypatch, responses)

    assert runtime.live_readiness() == {
        "ready": False,
        "reason": "provider_unavailable",
        "capacity": {"available": False},
    }


def test_production_delivery_and_activation_gates_default_false():
    from app.config import Settings

    settings = Settings(_env_file=None, DATABASE_URL="sqlite:///test.db", ASYNC_DATABASE_URL="sqlite+aiosqlite:///test.db")
    assert all(getattr(settings, name) is False for name in (
        "WHATSAPP_ENABLED", "OFFICIAL_WHATSAPP_ENABLED", "WHATSAPP_DISPATCH_ENABLED",
        "BILLING_WHATSAPP_ACTIVATION_API_ENABLED", "BILLING_WHATSAPP_ACTIVATION_DISPATCH_ENABLED",
    ))


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
    monkeypatch.setattr(runner, "sweep_expired_activations", lambda _db: 0)
    monkeypatch.setattr(runner.OfficialWhatsAppRuntime, "from_settings", lambda *_args: Runtime())
    monkeypatch.setattr(runner, "status_from_readiness", lambda *_args, **_kwargs: {
        "readiness": {"ready": True}, "effective_enabled": True,
    })
    monkeypatch.setattr("app.config.settings", settings())

    with pytest.raises(KeyboardInterrupt):
        runner.run()


def test_runner_forwards_content_sid_for_activation_only_intent(monkeypatch):
    import pytest
    from app.workers import official_whatsapp_runner as runner

    configured = settings(
        BILLING_WHATSAPP_ACTIVATION_API_ENABLED=True,
        BILLING_WHATSAPP_ACTIVATION_DISPATCH_ENABLED=True,
        WHATSAPP_RECIPIENT_HMAC_KEY="h" * 32,
        TWILIO_OFFICIAL_CONTENT_SID="HX" + "c" * 32,
    )
    captured = {}

    class Runtime:
        def live_readiness(self):
            return {"ready": True, "capacity": {"available": True}}

    class Database:
        def commit(self):
            pass

        def close(self):
            pass

    class Worker:
        def __init__(self, _db, *, claim_intent, **_kwargs):
            captured["claim_intent"] = claim_intent

        def process_one(self):
            assert captured["claim_intent"]() == "activation_test"
            raise KeyboardInterrupt

    def readiness(*_args, **kwargs):
        captured["readiness"] = kwargs
        return {
            "readiness": {"ready": False},
            "effective_enabled": False,
            "global_delivery": {"requested": False, "effective": False},
            "activation": {"capable": True},
        }

    monkeypatch.setattr(runner, "SessionLocal", Database)
    monkeypatch.setattr(runner, "BillingNotificationWorker", Worker)
    monkeypatch.setattr(runner, "mark_worker_heartbeat", lambda _db: None)
    monkeypatch.setattr(runner, "sweep_expired_activations", lambda _db: 0)
    monkeypatch.setattr(runner.OfficialWhatsAppRuntime, "from_settings", lambda *_args: Runtime())
    monkeypatch.setattr(runner, "status_from_readiness", readiness)
    monkeypatch.setattr("app.config.settings", configured)

    with pytest.raises(KeyboardInterrupt):
        runner.run()

    assert captured["readiness"]["configured_content_sid"] == configured.TWILIO_OFFICIAL_CONTENT_SID


def test_expiry_sweep_clamps_limit(monkeypatch):
    from app.workers import official_whatsapp_runner as runner

    class Query:
        def join(self, *_): return self
        def filter(self, *_): return self
        def order_by(self, *_): return self
        def limit(self, value): self.value = value; return self
        def all(self): return []

    query = Query()
    db = type("DB", (), {"query": lambda *_: query, "rollback": lambda *_: None})()
    monkeypatch.setattr(runner, "expire_activation", lambda *_args, **_kwargs: False)
    assert runner.sweep_expired_activations(db, limit=101) == 0
    assert query.value == 100
    assert runner.sweep_expired_activations(db, limit=0) == 0
    assert query.value == 1
