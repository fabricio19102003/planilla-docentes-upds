"""Backend contracts for the UX clarity work (portal retention flag, dashboard split, Spanish audit text)."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.activity_log import ActivityLog
from app.models.planilla import PlanillaOutput
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.models.user import User
from app.routers import planilla as planilla_router
from app.services.auth_service import auth_service


def _login_docente(client, db_session, teacher: Teacher) -> None:
    user = User(
        ci=f"USR-{teacher.ci}",
        full_name=teacher.full_name,
        password_hash=auth_service.hash_password("Testpass123"),
        role="docente",
        teacher_ci=teacher.ci,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    token = auth_service.create_access_token(data={"sub": str(user.id), "role": "docente"})
    client.headers["Authorization"] = f"Bearer {token}"


@pytest.mark.parametrize(
    ("invoice_retention", "expected"),
    [("RETENCION", True), (" retencion ", True), ("FACTURA", False), (None, False), ("", False)],
)
def test_portal_profile_reports_retention_status(client, db_session, invoice_retention, expected):
    ci = f"UX-RET-{abs(hash((invoice_retention, expected))) % 10_000_000}"
    teacher = Teacher(ci=ci, full_name="Docente Retencion", invoice_retention=invoice_retention)
    db_session.add(teacher)
    db_session.commit()
    _login_docente(client, db_session, teacher)

    response = client.get("/api/portal/profile")

    assert response.status_code == 200
    assert response.json()["has_retention"] is expected


def test_dashboard_payment_split_separates_theory_and_practice(monkeypatch):
    regular = PlanillaOutput(month=10, year=2026, total_payment=Decimal("300.00"), calculation_snapshot={"k": 1})
    practice = PracticePlanillaOutput(month=10, year=2026, total_payment=Decimal("50.50"), calculation_snapshot={"k": 2})
    legacy = PlanillaOutput(month=10, year=2026, total_payment=Decimal("999.00"), calculation_snapshot=None)
    rows_by_snapshot = {
        1: [SimpleNamespace(final_payment=Decimal("100.00")), SimpleNamespace(final_payment=Decimal("200.00"))],
        2: [SimpleNamespace(final_payment=Decimal("50.50"))],
    }
    monkeypatch.setattr(
        planilla_router,
        "calculation_snapshot_rows",
        lambda snapshot, total: rows_by_snapshot[snapshot["k"]],
    )

    regular_total, practice_total = planilla_router._payment_totals_by_kind([regular, practice, legacy, None])

    assert regular_total == Decimal("300.00")
    assert practice_total == Decimal("50.50")


def test_dashboard_summary_exposes_split_fields(client):
    payload = client.get("/api/dashboard/summary").json()

    assert "total_regular_payment" in payload
    assert "total_practice_payment" in payload
    assert payload["total_regular_payment"] + payload["total_practice_payment"] == pytest.approx(payload["total_monthly_payment"])


def test_whatsapp_preference_audit_description_is_spanish(client, db_session):
    db_session.add(Teacher(ci="UX-WA-ES", full_name="Docente WhatsApp"))
    db_session.commit()

    response = client.put(
        "/api/teachers/UX-WA-ES/whatsapp-preference",
        json={
            "phone_e164": "+59170000001",
            "is_verified": True,
            "consent_evidence_reference": "consent-record-ux",
            "consent_source": "written_record",
            "consented_at": "2026-01-01T12:00:00+00:00",
        },
    )

    assert response.status_code == 200
    descriptions = [row.description for row in db_session.query(ActivityLog).filter_by(category="whatsapp")]
    assert descriptions
    assert all(description == "Preferencia de WhatsApp actualizada" for description in descriptions)
