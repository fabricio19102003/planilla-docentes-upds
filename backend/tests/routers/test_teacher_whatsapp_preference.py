from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.activity_log import ActivityLog
from app.models.teacher import Teacher
from app.models.user import User
from app.models.whatsapp_preference import WhatsAppConsentRevision, WhatsAppPreference
from app.services.auth_service import auth_service


PHONE = "+59170000000"
EVIDENCE = "consent-record-2026-01"


def payload(**overrides):
    value = {
        "phone_e164": PHONE,
        "is_verified": True,
        "consent_evidence_reference": EVIDENCE,
        "consent_source": "written_record",
        "consented_at": "2026-01-01T12:00:00+00:00",
    }
    value.update(overrides)
    return value


def test_admin_get_returns_masked_empty_state_and_404_after_authorization(client, db_session):
    db_session.add(Teacher(ci="WA-EMPTY", full_name="Empty"))
    db_session.commit()

    response = client.get("/api/teachers/WA-EMPTY/whatsapp-preference")
    assert response.status_code == 200
    assert response.json() == {
        "teacher_ci": "WA-EMPTY", "exists": False, "phone_masked": None,
        "is_verified": False, "eligible": False, "consent_revision": 0,
        "consent_source": None, "consented_at": None, "opted_out": False,
        "opted_out_at": None, "has_consent_evidence": False,
        "has_opt_out_evidence": False,
    }

    assert client.get("/api/teachers/missing/whatsapp-preference").json() == {
        "detail": {"code": "teacher_not_found"}
    }


def test_admin_put_and_opt_out_are_masked_and_audited(client, db_session):
    db_session.add(Teacher(ci="WA-MUTATE", full_name="Mutate"))
    db_session.commit()

    created = client.put("/api/teachers/WA-MUTATE/whatsapp-preference", json=payload())
    assert created.status_code == 200
    assert created.json()["phone_masked"] != PHONE
    assert "phone_e164" not in created.json()
    assert EVIDENCE not in str(created.json())
    assert created.json()["consent_revision"] == 1

    opt_out_evidence = "opt-out-record-2026-01"
    opted_out = client.post(
        "/api/teachers/WA-MUTATE/whatsapp-preference/opt-out",
        json={"opt_out_evidence_reference": opt_out_evidence},
    )
    assert opted_out.status_code == 200
    assert opted_out.json()["opted_out"] is True
    assert opted_out.json()["consent_revision"] == 2
    assert db_session.query(WhatsAppConsentRevision).count() == 2
    audit_text = str(db_session.query(ActivityLog).all())
    assert PHONE not in audit_text
    assert EVIDENCE not in audit_text
    assert opt_out_evidence not in audit_text


def test_docente_is_forbidden_before_teacher_disclosure(client, db_session):
    docente = User(
        ci="WA-DOCENTE", full_name="Docente", password_hash="unused", role="docente", is_active=True,
    )
    db_session.add(docente)
    db_session.commit()
    token = auth_service.create_access_token({"sub": str(docente.id), "role": "docente"})

    response = client.get(
        "/api/teachers/does-not-exist/whatsapp-preference",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert db_session.query(ActivityLog).count() == 0


def test_invalid_preference_returns_bounded_private_error(client, db_session):
    db_session.add(Teacher(ci="WA-INVALID", full_name="Invalid"))
    db_session.commit()
    secret = "super-secret-evidence"

    response = client.put(
        "/api/teachers/WA-INVALID/whatsapp-preference",
        json=payload(phone_e164="not-a-phone", consent_evidence_reference=secret),
    )
    assert response.status_code == 422
    assert secret not in str(response.json())
    assert PHONE not in str(response.json())
    assert db_session.query(WhatsAppPreference).count() == 0


def test_audit_flush_failure_rolls_back_mutation(client, db_session, monkeypatch):
    from app.services import whatsapp_preference_service

    db_session.add(Teacher(ci="WA-ROLLBACK", full_name="Rollback"))
    db_session.commit()
    original_flush = db_session.flush

    def fail_audit_flush(*args, **kwargs):
        raise RuntimeError("audit failure")

    monkeypatch.setattr(db_session, "flush", fail_audit_flush)
    response = client.put("/api/teachers/WA-ROLLBACK/whatsapp-preference", json=payload())
    monkeypatch.setattr(db_session, "flush", original_flush)

    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "whatsapp_preference_mutation_failed"}}
    assert db_session.query(WhatsAppPreference).count() == 0
    assert db_session.query(WhatsAppConsentRevision).count() == 0
    assert db_session.query(ActivityLog).count() == 0
