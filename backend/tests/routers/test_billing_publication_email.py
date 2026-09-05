from __future__ import annotations

from datetime import date, datetime
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.billing_publication import BillingPublication
from app.models.billing_notification import BillingNotificationBatch, BillingNotificationJob
from app.models.whatsapp_preference import WhatsAppPreference
from app.models.notification import Notification
from app.models.outbound_notification_attempt import OutboundNotificationAttempt
from app.models.planilla import PlanillaOutput
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service
from app.services.billing_notification_service import _attempt_key
from app.services.monetary_snapshot import build_calculation_snapshot


def test_publish_billing_sends_email_after_successful_commit(client, db_session, monkeypatch):
    import app.routers.billing_publication as billing_publication_router

    _seed_approved_planilla(db_session)
    active_docente = _seed_docente(db_session, ci="EMAIL-DOC-1", email="docente@example.com")
    _seed_docente(db_session, ci="EMAIL-DOC-INACTIVE", email="inactive@example.com", is_active=False)
    sent_calls = []

    class RecordingEmailService:
        def send_billing_published(self, publication, docente_users):
            sent_calls.append((publication, list(docente_users)))
            assert publication.id is not None
            assert publication.billing_snapshot["source"] == "planilla_output"
            assert publication.billing_snapshot["teacher_details"][0]["teacher_ci"] == active_docente.teacher_ci
            assert publication.billing_snapshot["calculation_snapshot_version"] == 1
            assert sum(
                row["net_payment"]
                for teacher in publication.billing_snapshot["teacher_details"]
                for row in teacher["designations"]
            ) == publication.billing_snapshot["total_payment"]
            return SimpleNamespace(eligible=1, sent=1, failed=0, skipped=0)

    monkeypatch.setattr(billing_publication_router, "EmailService", RecordingEmailService)

    response = client.post("/api/billing/publish", json={"month": 5, "year": 2026})

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert len(sent_calls) == 1
    assert [user.id for user in sent_calls[0][1]] == [active_docente.id]
    assert sent_calls[0][1][0].teacher.email == "docente@example.com"
    attempt = db_session.query(OutboundNotificationAttempt).one()
    assert attempt.channel == "email"
    assert attempt.provider == "resend"
    assert attempt.status == "sent"
    assert attempt.user_id == active_docente.id
    assert attempt.provider_message_id is None
    assert attempt.error_code is None


def test_publish_billing_survives_email_service_failure_and_keeps_notifications(client, db_session, monkeypatch):
    import app.routers.billing_publication as billing_publication_router

    _seed_approved_planilla(db_session)
    docente = _seed_docente(db_session, ci="EMAIL-DOC-1", email="docente2@example.com")

    class FailingEmailService:
        def send_billing_published(self, publication, docente_users):
            raise RuntimeError("provider down")

    monkeypatch.setattr(billing_publication_router, "EmailService", FailingEmailService)

    response = client.post("/api/billing/publish", json={"month": 5, "year": 2026})

    assert response.status_code == 200
    notification = (
        db_session.query(Notification)
        .filter(
            Notification.user_id == docente.id,
            Notification.notification_type == "billing_published",
            Notification.reference_month == 5,
            Notification.reference_year == 2026,
        )
        .one()
    )
    assert notification.title == "Facturación Mayo 2026 publicada"


def test_regular_publication_notifies_only_docentes_present_in_snapshot(client, db_session, monkeypatch):
    import app.routers.billing_publication as billing_publication_router

    _seed_approved_planilla(db_session)
    included = _seed_docente(db_session, ci="EMAIL-DOC-1", email="included@example.com")
    excluded = _seed_docente(db_session, ci="EMAIL-DOC-ABSENT", email="excluded@example.com")

    class RecordingEmailService:
        def send_billing_published(self, publication, docente_users):
            assert [user.id for user in docente_users] == [included.id]
            return SimpleNamespace(eligible=1, sent=1, failed=0, skipped=0)

    monkeypatch.setattr(billing_publication_router, "EmailService", RecordingEmailService)

    response = client.post("/api/billing/publish", json={"month": 5, "year": 2026})

    assert response.status_code == 200
    notified_ids = {
        notification.user_id
        for notification in db_session.query(Notification)
        .filter(Notification.notification_type == "billing_published")
        .all()
    }
    assert included.id in notified_ids
    assert excluded.id not in notified_ids


def test_practice_publication_notifies_only_docentes_present_in_snapshot(client, db_session, monkeypatch):
    import app.routers.billing_publication as billing_publication_router

    _seed_approved_practice_planilla(db_session)
    included = _seed_docente(db_session, ci="PRACTICE-DOC-1", email="practice@example.com")
    excluded = _seed_docente(db_session, ci="PRACTICE-DOC-ABSENT", email="absent@example.com")

    class RecordingEmailService:
        def send_billing_published(self, publication, docente_users):
            assert [user.id for user in docente_users] == [included.id]
            return SimpleNamespace(eligible=1, sent=1, failed=0, skipped=0)

    monkeypatch.setattr(billing_publication_router, "EmailService", RecordingEmailService)

    response = client.post("/api/billing/practice/publish", json={"month": 5, "year": 2026})

    assert response.status_code == 200
    notified_ids = {
        notification.user_id
        for notification in db_session.query(Notification)
        .filter(Notification.notification_type == "practice_billing_published")
        .all()
    }
    assert included.id in notified_ids
    assert excluded.id not in notified_ids


def test_send_billing_emails_filters_selected_active_docentes(client, db_session, monkeypatch):
    import app.routers.billing_publication as billing_publication_router

    selected_docente = _seed_docente(db_session, ci="EMAIL-DOC-1", email="selected@example.com")
    _seed_docente(db_session, ci="EMAIL-DOC-2", email="other@example.com")
    _seed_docente(db_session, ci="EMAIL-DOC-INACTIVE", email="inactive@example.com", is_active=False)
    _seed_publication(db_session)
    sent_calls = []

    class RecordingEmailService:
        def send_billing_published(self, publication, docente_users):
            sent_calls.append((publication, list(docente_users)))
            return SimpleNamespace(eligible=1, sent=1, failed=0, skipped=0)

    monkeypatch.setattr(billing_publication_router, "EmailService", RecordingEmailService)

    response = client.post(
        "/api/billing/send-emails",
        json={"month": 5, "year": 2026, "teacher_cis": ["EMAIL-DOC-1", "EMAIL-DOC-INACTIVE"]},
    )

    assert response.status_code == 200
    assert response.json() == {"sent": 1, "failed": 0, "skipped": 0}
    assert len(sent_calls) == 1
    assert sent_calls[0][0].status == "published"
    assert [user.id for user in sent_calls[0][1]] == [selected_docente.id]
    assert sent_calls[0][1][0].teacher.email == "selected@example.com"


def test_send_billing_emails_reports_historical_success_as_skipped(
    client, db_session, monkeypatch
):
    import app.routers.billing_publication as billing_publication_router
    import app.services.billing_notification_service as notification_service

    user = _seed_docente(db_session, ci="EMAIL-DOC-1", email="selected@example.com")
    publication = _seed_publication(db_session)
    monkeypatch.setattr(notification_service.default_settings, "WHATSAPP_ENABLED", False)

    class MustNotSendEmail:
        def send_billing_published(self, _publication, _users):
            raise AssertionError("historical success must not call Resend")

    monkeypatch.setattr(billing_publication_router, "EmailService", MustNotSendEmail)
    db_session.add(
        OutboundNotificationAttempt(
            idempotency_key=_attempt_key(publication, user.id, "email", "resend"),
            publication_id=publication.id,
            publication_version=publication.version,
            user_id=user.id,
            channel="email",
            provider="resend",
            mode="fallback",
            status="sent",
        )
    )
    db_session.commit()

    response = client.post(
        "/api/billing/send-emails",
        json={"month": 5, "year": 2026, "teacher_cis": ["EMAIL-DOC-1"]},
    )

    assert response.status_code == 200
    assert response.json() == {"sent": 0, "failed": 0, "skipped": 1}


def test_official_policy_blocks_legacy_email_for_pending_or_ambiguous_but_allows_verified_failure(db_session):
    from app.routers.billing_publication import _email_eligible_users

    user = _seed_docente(db_session, ci="EMAIL-DOC-1", email="selected@example.com")
    publication = _seed_publication(db_session)
    preference = WhatsAppPreference(teacher_ci=user.teacher_ci, phone_e164="+59170000000", is_verified=True, consent_evidence="evidence", consent_revision=1)
    batch = BillingNotificationBatch(publication_id=publication.id, publication_version=publication.version, digest="f" * 64, readiness_snapshot={"ready": True}, status="queued")
    db_session.add_all([preference, batch]); db_session.flush()
    job = BillingNotificationJob(batch_id=batch.id, teacher_ci=user.teacher_ci, channel="whatsapp", status="pending")
    db_session.add(job); db_session.commit()

    assert _email_eligible_users(db_session, publication, [user]) == []
    job.status = "ambiguous"; db_session.commit()
    assert _email_eligible_users(db_session, publication, [user]) == []
    job.status = "undelivered"; db_session.commit()
    assert _email_eligible_users(db_session, publication, [user]) == [user]


@pytest.mark.parametrize("states", [("undelivered", "ambiguous"), ("ambiguous", "undelivered")])
def test_official_policy_ambiguous_job_dominates_terminal_job_regardless_of_row_order(db_session, states):
    from app.routers.billing_publication import _email_eligible_users
    user = _seed_docente(db_session, ci="EMAIL-DOC-1", email="selected@example.com")
    publication = _seed_publication(db_session)
    db_session.add(WhatsAppPreference(teacher_ci=user.teacher_ci, phone_e164="+59170000000", is_verified=True, consent_evidence="evidence", consent_revision=1))
    for index, state in enumerate(states):
        batch = BillingNotificationBatch(publication_id=publication.id, publication_version=publication.version, digest=str(index) * 64, readiness_snapshot={"ready": True}, status="queued")
        db_session.add(batch); db_session.flush()
        db_session.add(BillingNotificationJob(batch_id=batch.id, teacher_ci=user.teacher_ci, channel="whatsapp", status=state))
    db_session.commit()
    assert _email_eligible_users(db_session, publication, [user]) == []


def test_send_billing_emails_requires_published_publication(client, db_session):
    _seed_publication(db_session, status="draft")

    response = client.post(
        "/api/billing/send-emails",
        json={"month": 5, "year": 2026, "teacher_cis": ["EMAIL-DOC-1"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "La facturación no está publicada para este período"


@pytest.mark.parametrize(
    ("endpoint", "seed"),
    [
        ("/api/billing/publish", "regular"),
        ("/api/billing/practice/publish", "practice"),
    ],
)
@pytest.mark.parametrize("snapshot_state", ["missing", "mutated"])
def test_publication_rejects_invalid_approved_snapshot(client, db_session, endpoint, seed, snapshot_state):
    output = _seed_approved_planilla(db_session) if seed == "regular" else _seed_approved_practice_planilla(db_session)
    if snapshot_state == "missing":
        output.calculation_snapshot = None
    else:
        snapshot = deepcopy(output.calculation_snapshot)
        snapshot["designations"][0]["teacher_name"] = "Mutated after approval"
        output.calculation_snapshot = snapshot
    db_session.commit()

    response = client.post(endpoint, json={"month": 5, "year": 2026})

    assert response.status_code == 409
    expected_code = "snapshot_missing" if snapshot_state == "missing" else "snapshot_mismatch"
    assert response.json()["detail"]["code"] == expected_code


def test_publication_rejects_duplicate_snapshot(client, db_session, monkeypatch):
    import app.routers.billing_publication as billing_publication_router

    _seed_approved_planilla(db_session)
    _seed_docente(db_session, ci="EMAIL-DOC-1", email="docente@example.com")
    monkeypatch.setattr(
        billing_publication_router.EmailService,
        "send_billing_published",
        lambda *args: SimpleNamespace(eligible=1, sent=1, failed=0, skipped=0),
    )

    assert client.post("/api/billing/publish", json={"month": 5, "year": 2026}).status_code == 200
    response = client.post("/api/billing/publish", json={"month": 5, "year": 2026})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "snapshot_already_published"


def _seed_approved_planilla(db_session):
    rows = _fake_planilla_rows(None, None, 5, 2026)[0]
    output = PlanillaOutput(
        month=5,
        year=2026,
        generated_at=datetime(2026, 5, 31, 12, 0, 0),
        total_teachers=1,
        total_hours=8,
        total_payment=Decimal("560.00"),
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        status="approved",
        discount_mode="attendance",
        calculation_snapshot=_calculation_snapshot(rows, Decimal("560.00")),
    )
    db_session.add(output)
    db_session.commit()
    return output


def _seed_publication(db_session, *, status="published"):
    publication = BillingPublication(
        month=5,
        year=2026,
        status=status,
        version=1,
        total_teachers=1,
        total_payment=Decimal("560.00"),
        published_at=datetime(2026, 5, 31, 12, 0, 0) if status == "published" else None,
        billing_snapshot={
            "source": "planilla_output",
            "teacher_details": [
                {
                    "teacher_ci": "EMAIL-DOC-1",
                    "teacher_name": "Docente EMAIL-DOC-1",
                    "designations": [{"subject": "Anatomía", "group": "A", "semester": "1", "payment": 560.0}],
                }
            ],
        },
    )
    db_session.add(publication)
    db_session.commit()
    return publication


def _seed_approved_practice_planilla(db_session):
    rows = _fake_practice_planilla_rows(None, None, 5, 2026)[0]
    output = PracticePlanillaOutput(
        month=5,
        year=2026,
        generated_at=datetime(2026, 5, 31, 12, 0, 0),
        total_teachers=1,
        total_hours=8,
        total_payment=Decimal("400.00"),
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        status="approved",
        discount_mode="attendance",
        calculation_snapshot=_calculation_snapshot(rows, Decimal("400.00")),
    )
    db_session.add(output)
    db_session.commit()
    return output


def _seed_docente(db_session, *, ci: str, email: str, is_active: bool = True):
    teacher = Teacher(ci=ci, full_name=f"Docente {ci}", email=email)
    user = User(
        ci=f"USER-{ci}",
        full_name=f"Docente {ci}",
        email=None,
        password_hash=auth_service.hash_password("testpass123"),
        role="docente",
        teacher_ci=ci,
        is_active=is_active,
    )
    db_session.add_all([teacher, user])
    db_session.commit()
    return user


def _calculation_snapshot(rows, total: Decimal):
    return build_calculation_snapshot(
        rows=rows,
        row_amounts=[total],
        month=5,
        year=2026,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        discount_mode="attendance",
        payment_overrides={},
        excluded_days=[],
    )


def _fake_planilla_rows(self, db, month, year, start_date=None, end_date=None, discount_mode=None, excluded_days=None):
    return (
        [
            SimpleNamespace(
                teacher_ci="EMAIL-DOC-1" if month == 5 else "UNKNOWN",
                teacher_name="Docente EMAIL-DOC-1",
                designation_id=101,
                subject="Anatomía",
                group_code="A",
                semester="1",
                base_monthly_hours=8,
                absent_hours=0,
                payable_hours=8,
                rate_per_hour=70,
                calculated_payment=560.0,
                retention_amount=0.0,
                final_payment=560.0,
                has_biometric=True,
                has_retention=False,
                retention_rate=0.0,
            )
        ],
        [],
        [],
    )


def _fake_practice_planilla_rows(
    self,
    db,
    month,
    year,
    start_date=None,
    end_date=None,
    discount_mode=None,
    excluded_days=None,
):
    return (
        [
            SimpleNamespace(
                teacher_ci="PRACTICE-DOC-1",
                teacher_name="Docente PRACTICE-DOC-1",
                designation_id=201,
                subject="Práctica Clínica",
                group_code="P-1",
                semester="2",
                base_monthly_hours=8,
                absent_hours=0,
                payable_hours=8,
                rate_per_hour=50,
                calculated_payment=400.0,
                retention_rate=0.0,
                retention_amount=0.0,
                final_payment=400.0,
                has_biometric=True,
                has_retention=False,
            )
        ],
        [],
    )


def test_whatsapp_preview_masks_numbers_and_returns_a_digest(client, db_session):
    from app.models.whatsapp_preference import WhatsAppPreference

    publication = _seed_publication(db_session)
    snapshot = deepcopy(publication.billing_snapshot)
    snapshot["teacher_details"][0]["teacher_ci"] = "WHATSAPP-DOC-1"
    publication.billing_snapshot = snapshot
    db_session.add(publication)
    _seed_docente(db_session, ci="WHATSAPP-DOC-1", email="whatsapp@example.com")
    db_session.add(WhatsAppPreference(teacher_ci="WHATSAPP-DOC-1", phone_e164="+59170000000", is_verified=True, consent_evidence="signed-consent", consent_revision=3))
    db_session.commit()

    response = client.post("/api/billing/notifications/preview", json={"month": 5, "year": 2026, "teacher_cis": ["WHATSAPP-DOC-1"]})

    assert response.status_code == 200
    body = response.json()
    assert len(body["digest"]) == 64
    assert body["recipients"] == [{"teacher_ci": "WHATSAPP-DOC-1", "phone_masked": "+591*****000", "channel": "whatsapp", "reason": "evidenced_consent"}]
    assert body["readiness"]["ready"] is False
    assert "+59170000000" not in response.text


def test_whatsapp_confirm_rejects_stale_digest_without_creating_jobs(client, db_session):
    from app.models.billing_notification import BillingNotificationBatch, BillingNotificationJob

    _seed_publication(db_session)
    _seed_docente(db_session, ci="WHATSAPP-DOC-1", email="whatsapp@example.com")
    preview = client.post("/api/billing/notifications/preview", json={"month": 5, "year": 2026, "teacher_cis": ["WHATSAPP-DOC-1"]})
    assert preview.status_code == 200

    response = client.post("/api/billing/notifications/confirm", json={"month": 5, "year": 2026, "teacher_cis": ["WHATSAPP-DOC-1"], "digest": "0" * 64})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_notification_plan"
    assert db_session.query(BillingNotificationBatch).count() == 0
    assert db_session.query(BillingNotificationJob).count() == 0


def test_notification_plan_confirm_creates_one_durable_intent_when_ready(db_session):
    from app.models.billing_notification import BillingNotificationBatch, BillingNotificationJob
    from app.services.billing_notification_preview import BillingNotificationPreviewService

    publication = _seed_publication(db_session)
    plan_service = BillingNotificationPreviewService(db_session, readiness={"ready": True, "capacity": {"available": True, "remaining": 1}})
    plan = plan_service.preview(publication, ["EMAIL-DOC-1"])
    batch = plan_service.confirm(publication, ["EMAIL-DOC-1"], plan.digest)
    db_session.commit()

    assert db_session.query(BillingNotificationBatch).filter_by(id=batch.id).one().digest == plan.digest
    assert db_session.query(BillingNotificationJob).filter_by(batch_id=batch.id).count() == 1


@pytest.mark.parametrize(
    ("readiness", "expected"),
    [
        ({"ready": True, "capacity": {"available": True, "remaining": 2}}, {"available": True, "requested": 1, "remaining": 2, "exceeded": False}),
        ({"ready": True, "capacity": {"available": True, "remaining": 0}}, {"available": True, "requested": 1, "remaining": 0, "exceeded": True}),
        ({"ready": False}, {"available": False, "requested": 1, "remaining": None, "exceeded": None}),
    ],
)
def test_notification_preview_reports_fail_closed_capacity_forecast(db_session, readiness, expected):
    from app.services.billing_notification_preview import BillingNotificationPreviewService

    from app.models.whatsapp_preference import WhatsAppPreference

    publication = _seed_publication(db_session)
    _seed_docente(db_session, ci="EMAIL-DOC-1", email="capacity@example.com")
    db_session.add(WhatsAppPreference(teacher_ci="EMAIL-DOC-1", phone_e164="+59170000000", is_verified=True, consent_evidence="capacity-consent", consent_revision=1))
    db_session.commit()
    plan = BillingNotificationPreviewService(db_session, readiness=readiness).preview(
        publication, ["EMAIL-DOC-1"]
    )

    assert plan.readiness["capacity"] == expected
