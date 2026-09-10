from __future__ import annotations

from datetime import datetime

import pytest

from app.models.app_setting import AppSetting
from app.models.billing_notification import BillingNotificationJob, BillingWhatsAppActivationTest
from app.models.user import User
from app.services import app_settings_service
from app.services.auth_service import auth_service
from tests.services.test_whatsapp_activation_service import _activation_setup


SID = "HX" + "a" * 32


def _ready(*, global_on: bool = False) -> dict:
    return {
        "provider_configuration": {"ready": True, "reason": None},
        "provider_live": {"ready": True, "reason": None, "capacity": {"available": True}},
        "worker": {"ready": True, "reason": None, "heartbeat_at": datetime.utcnow()},
        "process_gates": {"official": True, "dispatch": True},
        "global_delivery": {"requested": global_on, "effective": global_on},
        "activation": {"api_enabled": True, "dispatch_enabled": True, "capable": not global_on, "blocking_reasons": []},
    }


def _payload(revision_id: int, **changes: object) -> dict:
    return {
        "teacher_ci": "EMAIL-DOC-1",
        "recipient_e164": "+59170000000",
        "consent_revision": 1,
        "publication_revision_id": revision_id,
        **changes,
    }


@pytest.fixture
def activation_media_dir(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "BILLING_MEDIA_DIR", str(tmp_path))
    yield tmp_path
    for artifact in tmp_path.glob("*.pdf"):
        artifact.unlink()


def _configure_ready(monkeypatch):
    import app.routers.admin_whatsapp as router
    from app.config import settings

    monkeypatch.setattr(router, "current_delivery_status", lambda _db: _ready())
    monkeypatch.setattr(settings, "TWILIO_OFFICIAL_CONTENT_SID", SID)
    monkeypatch.setattr(settings, "WHATSAPP_RECIPIENT_HMAC_KEY", "k" * 32)


def test_routes_are_admin_only_and_readiness_is_sanitized_nonmutating(client, db_session, monkeypatch):
    _configure_ready(monkeypatch)
    before = db_session.query(AppSetting).count()
    response = client.get("/api/admin/whatsapp/readiness")
    assert response.status_code == 200
    assert response.json()["activation"]["capable"] is True
    assert "content_sid" not in str(response.json()).lower()
    assert db_session.query(AppSetting).count() == before

    docente = User(ci="DOCENTE-A", full_name="Docente", password_hash="x", role="docente")
    db_session.add(docente); db_session.flush()
    token = auth_service.create_access_token(data={"sub": str(docente.id), "role": "docente"})
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/admin/whatsapp/readiness").status_code == 403
    client.headers.pop("Authorization")
    assert client.get("/api/admin/whatsapp/readiness").status_code == 401


def test_create_validates_header_before_rows_and_never_calls_transport(client, db_session, tmp_path, monkeypatch, activation_media_dir):
    _, _, _, revision = _activation_setup(client, db_session, tmp_path, monkeypatch)
    _configure_ready(monkeypatch)
    before = db_session.query(BillingWhatsAppActivationTest).count()
    transport_calls = []
    monkeypatch.setattr(
        "app.services.twilio_content_transport.TwilioContentTransport.send",
        lambda *_args, **_kwargs: transport_calls.append(True),
    )
    for key in (None, "short", "a" * 129):
        headers = {} if key is None else {"Idempotency-Key": key}
        response = client.post("/api/admin/whatsapp/activation-tests", json=_payload(revision.id), headers=headers)
        assert response.status_code == 422
    malformed = client.post(
        "/api/admin/whatsapp/activation-tests",
        json=_payload(revision.id, recipient_e164="not-a-phone"),
        headers={"Idempotency-Key": "a" * 16},
    )
    assert malformed.status_code == 422
    assert "not-a-phone" not in str(malformed.json())
    assert "EMAIL-DOC-1" not in str(malformed.json())
    assert db_session.query(BillingWhatsAppActivationTest).count() == before
    assert transport_calls == []


def test_create_replay_conflict_and_readiness_rejections_are_row_free(client, db_session, tmp_path, monkeypatch, activation_media_dir):
    _, _, _, revision = _activation_setup(client, db_session, tmp_path, monkeypatch)
    _configure_ready(monkeypatch)
    headers = {"Idempotency-Key": "a" * 16}
    created = client.post("/api/admin/whatsapp/activation-tests", json=_payload(revision.id), headers=headers)
    assert created.status_code == 201
    assert not any(marker in str(created.json()).lower() for marker in ("content_sid", "billing_digest", "hash", "token", "artifact", "provider"))
    replay = client.post("/api/admin/whatsapp/activation-tests", json=_payload(revision.id), headers=headers)
    assert replay.status_code == 200 and replay.json()["replayed"] is True
    conflict = client.post("/api/admin/whatsapp/activation-tests", json=_payload(revision.id, consent_revision=2), headers=headers)
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "activation_idempotency_conflict"
    assert db_session.query(BillingWhatsAppActivationTest).count() == 1

    import app.routers.admin_whatsapp as router
    monkeypatch.setattr(router, "current_delivery_status", lambda _db: _ready(global_on=True))
    rejected = client.post("/api/admin/whatsapp/activation-tests", json=_payload(revision.id), headers={"Idempotency-Key": "b" * 16})
    assert rejected.status_code == 409
    disabled = _ready(); disabled["activation"]["capable"] = False
    monkeypatch.setattr(router, "current_delivery_status", lambda _db: disabled)
    rejected = client.post("/api/admin/whatsapp/activation-tests", json=_payload(revision.id), headers={"Idempotency-Key": "c" * 16})
    assert rejected.status_code == 409
    assert db_session.query(BillingWhatsAppActivationTest).count() == 1


def test_status_is_admin_only_and_checks_authorization_before_existence(client, db_session, tmp_path, monkeypatch, activation_media_dir):
    _, _, _, revision = _activation_setup(client, db_session, tmp_path, monkeypatch)
    _configure_ready(monkeypatch)
    created = client.post("/api/admin/whatsapp/activation-tests", json=_payload(revision.id), headers={"Idempotency-Key": "a" * 16})
    activation_id = created.json()["id"]
    from app.config import settings
    activation = db_session.get(BillingWhatsAppActivationTest, activation_id)
    job = db_session.get(BillingNotificationJob, activation.job_id)
    job.status = activation.status = "delivered"
    db_session.commit()
    monkeypatch.setattr(settings, "WHATSAPP_RECIPIENT_HMAC_KEY", None)
    response = client.get(f"/api/admin/whatsapp/activation-tests/{activation_id}")
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["job_status"]) == ("delivered", "delivered")
    assert client.get("/api/admin/whatsapp/activation-tests/999999").status_code == 404

    docente = User(ci="DOCENTE-B", full_name="Docente", password_hash="x", role="docente")
    db_session.add(docente); db_session.flush()
    client.headers["Authorization"] = f"Bearer {auth_service.create_access_token(data={'sub': str(docente.id)})}"
    assert client.get("/api/admin/whatsapp/activation-tests/999999").status_code == 403
