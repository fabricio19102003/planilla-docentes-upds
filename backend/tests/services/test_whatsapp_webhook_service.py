from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.models.billing_notification import BillingNotificationJob, WhatsAppEvent
from app.models.whatsapp_preference import WhatsAppPreference


AUTH_TOKEN = "test-auth-token"
STATUS_URL = "https://callbacks.example.invalid/api/twilio/whatsapp/status"
INBOUND_URL = "https://callbacks.example.invalid/api/twilio/whatsapp/inbound"
SID = "SM" + "a" * 32


def signature(url: str, form: list[tuple[str, str]]) -> str:
    payload = url + "".join(key + value for key, value in sorted(form))
    return base64.b64encode(hmac.new(AUTH_TOKEN.encode(), payload.encode(), hashlib.sha1).digest()).decode()


def service_session(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path}/webhooks.db")
    BillingNotificationJob.__table__.create(engine)
    WhatsAppEvent.__table__.create(engine)
    WhatsAppPreference.__table__.create(engine)
    return engine, sessionmaker(bind=engine)()


def test_signature_invalid_events_do_not_mutate_and_valid_events_are_monotonic(tmp_path):
    from app.services.whatsapp_webhook_service import WhatsAppWebhookService

    engine, db = service_session(tmp_path)
    db.add(BillingNotificationJob(id=1, batch_id=1, teacher_ci="teacher", channel="whatsapp", status="accepted", provider_sid=SID))
    db.commit()
    service = WhatsAppWebhookService(db, auth_token=AUTH_TOKEN, status_url=STATUS_URL, inbound_url=INBOUND_URL)
    form = [("MessageSid", SID), ("MessageStatus", "delivered")]

    assert service.process_status(form, "invalid", "") == "rejected"
    assert db.get(BillingNotificationJob, 1).status == "accepted"
    assert db.query(WhatsAppEvent).count() == 0

    valid = signature(STATUS_URL, form)
    assert service.process_status(form, valid, "") == "projected"
    assert service.process_status(form, valid, "") == "duplicate"
    assert db.get(BillingNotificationJob, 1).status == "delivered"
    assert db.query(WhatsAppEvent).count() == 1

    older = [("MessageSid", SID), ("MessageStatus", "sent")]
    assert service.process_status(older, signature(STATUS_URL, older), "") == "ignored"
    assert db.get(BillingNotificationJob, 1).status == "delivered"
    engine.dispose()


def test_stop_is_authenticated_idempotent_and_cancels_only_unsent_whatsapp_jobs(tmp_path):
    from app.services.whatsapp_webhook_service import WhatsAppWebhookService

    engine, db = service_session(tmp_path)
    preference = WhatsAppPreference(teacher_ci="teacher", phone_e164="+59170000000", is_verified=True, consent_evidence="evidence", consent_revision=1)
    db.add_all([
        preference,
        BillingNotificationJob(id=1, batch_id=1, teacher_ci="teacher", channel="whatsapp", status="queued"),
        BillingNotificationJob(id=2, batch_id=2, teacher_ci="teacher", channel="whatsapp", status="sending"),
    ])
    db.commit()
    service = WhatsAppWebhookService(db, auth_token=AUTH_TOKEN, status_url=STATUS_URL, inbound_url=INBOUND_URL, now=lambda: datetime(2026, 1, 1))
    form = [("From", "whatsapp:+59170000000"), ("Body", "STOP"), ("MessageSid", "MM" + "b" * 32)]
    valid = signature(INBOUND_URL, form)

    assert service.process_inbound(form, valid, "") == "opted_out"
    assert service.process_inbound(form, valid, "") == "duplicate"
    assert preference.opted_out_at == datetime(2026, 1, 1)
    assert db.get(BillingNotificationJob, 1).status == "cancelled"
    assert db.get(BillingNotificationJob, 2).status == "cancelled"
    assert db.query(WhatsAppEvent).count() == 1
    engine.dispose()


def test_reconciliation_is_bounded_to_known_sids_without_email_side_effects(tmp_path):
    from app.services.whatsapp_webhook_service import WhatsAppWebhookService

    engine, db = service_session(tmp_path)
    db.add(BillingNotificationJob(id=1, batch_id=1, teacher_ci="teacher", channel="whatsapp", status="ambiguous", provider_sid=SID))
    db.commit()
    calls = []
    service = WhatsAppWebhookService(db, auth_token=AUTH_TOKEN, status_url=STATUS_URL, inbound_url=INBOUND_URL)
    assert service.reconcile(lambda sid: calls.append(sid) or "delivered", limit=1) == 1
    assert calls == [SID]
    assert db.get(BillingNotificationJob, 1).status == "delivered"
    assert db.query(WhatsAppEvent).one().event_type == "reconciliation"
    engine.dispose()


def test_unknown_sender_and_malformed_status_are_safe_noops(tmp_path):
    from app.services.whatsapp_webhook_service import WhatsAppWebhookService

    engine, db = service_session(tmp_path)
    service = WhatsAppWebhookService(db, auth_token=AUTH_TOKEN, status_url=STATUS_URL, inbound_url=INBOUND_URL)
    unknown_stop = [("From", "whatsapp:+59179999999"), ("Body", "STOP")]
    assert service.process_inbound(unknown_stop, signature(INBOUND_URL, unknown_stop), "") == "unknown_sender"
    malformed = [("MessageSid", "not-a-provider-sid"), ("MessageStatus", "delivered")]
    assert service.process_status(malformed, signature(STATUS_URL, malformed), "") == "ignored"
    assert db.query(WhatsAppEvent).count() == 2
    engine.dispose()


def test_terminal_failures_are_valid_advances_but_delivered_and_terminal_never_regress(tmp_path):
    from app.services.whatsapp_webhook_service import WhatsAppWebhookService
    engine, db = service_session(tmp_path)
    db.add(BillingNotificationJob(id=1, batch_id=1, teacher_ci="teacher", channel="whatsapp", status="accepted", provider_sid=SID)); db.commit()
    service = WhatsAppWebhookService(db, auth_token=AUTH_TOKEN, status_url=STATUS_URL, inbound_url=INBOUND_URL)
    failed = [("MessageSid", SID), ("MessageStatus", "failed")]
    assert service.process_status(failed, signature(STATUS_URL, failed), "") == "projected"
    assert db.get(BillingNotificationJob, 1).status == "failed"
    delivered = [("MessageSid", SID), ("MessageStatus", "delivered")]
    assert service.process_status(delivered, signature(STATUS_URL, delivered), "") == "ignored"
    engine.dispose()

def test_router_uses_configured_url_with_actual_query_not_host_headers(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.database import get_db
    from app.routers.twilio_whatsapp import router

    engine, db = service_session(tmp_path)
    db.add(BillingNotificationJob(id=1, batch_id=1, teacher_ci="teacher", channel="whatsapp", status="accepted", provider_sid=SID)); db.commit()
    app = FastAPI(); app.include_router(router)
    def override(): yield db
    app.dependency_overrides[get_db] = override
    old = settings.TWILIO_AUTH_TOKEN, settings.TWILIO_STATUS_CALLBACK_URL, settings.TWILIO_INBOUND_CALLBACK_URL
    settings.TWILIO_AUTH_TOKEN, settings.TWILIO_STATUS_CALLBACK_URL, settings.TWILIO_INBOUND_CALLBACK_URL = AUTH_TOKEN, STATUS_URL, INBOUND_URL
    fields = [("MessageSid", SID), ("MessageStatus", "delivered")]; query = "trace=abc"
    try:
        with TestClient(app) as client:
            headers = {"X-Twilio-Signature": signature(f"{STATUS_URL}?{query}", fields), "Host": "evil.invalid", "X-Forwarded-Host": "evil.invalid", "content-type": "application/x-www-form-urlencoded"}
            assert client.post(f"/api/twilio/whatsapp/status?{query}", content="MessageSid=" + SID + "&MessageStatus=delivered", headers=headers).status_code == 204
            assert client.post("/api/twilio/whatsapp/status?trace=changed", content="MessageSid=" + SID + "&MessageStatus=delivered", headers=headers).status_code == 403
            assert client.post(f"/api/twilio/whatsapp/status?{query}", content="bad", headers=headers).status_code == 403
        assert db.get(BillingNotificationJob, 1).status == "delivered" and db.query(WhatsAppEvent).count() == 1
    finally:
        settings.TWILIO_AUTH_TOKEN, settings.TWILIO_STATUS_CALLBACK_URL, settings.TWILIO_INBOUND_CALLBACK_URL = old
        engine.dispose()
