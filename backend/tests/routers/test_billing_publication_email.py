from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.models.billing_publication import BillingPublication
from app.models.notification import Notification
from app.models.planilla import PlanillaOutput
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service


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
            return SimpleNamespace(eligible=1, sent=1, failed=0, skipped=0)

    monkeypatch.setattr(billing_publication_router.PlanillaGenerator, "_build_planilla_data", _fake_planilla_rows)
    monkeypatch.setattr(billing_publication_router.app_settings_service, "get_hourly_rate", lambda db: 70.0)
    monkeypatch.setattr(billing_publication_router, "EmailService", RecordingEmailService)

    response = client.post("/api/billing/publish", json={"month": 5, "year": 2026})

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert len(sent_calls) == 1
    assert [user.id for user in sent_calls[0][1]] == [active_docente.id]
    assert sent_calls[0][1][0].teacher.email == "docente@example.com"


def test_publish_billing_survives_email_service_failure_and_keeps_notifications(client, db_session, monkeypatch):
    import app.routers.billing_publication as billing_publication_router

    _seed_approved_planilla(db_session)
    docente = _seed_docente(db_session, ci="EMAIL-DOC-2", email="docente2@example.com")

    class FailingEmailService:
        def send_billing_published(self, publication, docente_users):
            raise RuntimeError("provider down")

    monkeypatch.setattr(billing_publication_router.PlanillaGenerator, "_build_planilla_data", _fake_planilla_rows)
    monkeypatch.setattr(billing_publication_router.app_settings_service, "get_hourly_rate", lambda db: 70.0)
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


def test_send_billing_emails_requires_published_publication(client, db_session):
    _seed_publication(db_session, status="draft")

    response = client.post(
        "/api/billing/send-emails",
        json={"month": 5, "year": 2026, "teacher_cis": ["EMAIL-DOC-1"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "La facturación no está publicada para este período"


def _seed_approved_planilla(db_session):
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
                calculated_payment=560.0,
                retention_amount=0.0,
                final_payment=560.0,
                has_biometric=True,
                has_retention=False,
            )
        ],
        [],
        [],
    )
