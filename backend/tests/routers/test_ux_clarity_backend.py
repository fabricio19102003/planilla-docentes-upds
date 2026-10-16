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


ENGLISH_AUDIT_TEXTS = (
    "WhatsApp activation authorization expired",
    "Controlled WhatsApp activation created",
    "WhatsApp activation dispatch authorized",
    "WhatsApp activation cancelled",
    "Applied digest-bound designation bootstrap to a new schedule draft",
    "Applied digest-bound II/2026 historical assistential schedule import",
    "Medicine version {event_type}",
    "WhatsApp preference lifecycle updated",
)


def test_backend_writes_activity_log_descriptions_in_spanish():
    from pathlib import Path

    source = "\n".join(path.read_text(encoding="utf-8") for path in Path("app").rglob("*.py"))

    assert [text for text in ENGLISH_AUDIT_TEXTS if text in source] == []


def test_medicine_schedule_events_have_spanish_descriptions():
    from app.services.medicine_schedule_version_service import MEDICINE_EVENT_DESCRIPTIONS

    assert MEDICINE_EVENT_DESCRIPTIONS == {
        "upload": "Versión de horario de Medicina cargada",
        "correction": "Versión de horario de Medicina corregida",
        "warning_acceptance": "Advertencia de horario de Medicina aceptada",
        "activation": "Versión de horario de Medicina activada",
        "restore": "Versión de horario de Medicina restaurada",
    }


def _split_row(ci, amount):
    return SimpleNamespace(teacher_ci=ci, teacher_name=ci, payable_hours=1, final_payment=Decimal(amount))


@pytest.mark.parametrize(
    ("regular_rows", "practice_rows", "regular_legacy", "exp_regular", "exp_practice"),
    [
        ([("A", "0.10"), ("B", "585241.20")], [("A", "18487.00")], False, 585241.30, 18487.00),
        ([("A", "100.00")], None, False, 100.00, 0.0),
        (None, [("A", "0.20"), ("C", "0.10")], False, 0.0, 0.30),
        ([("A", "999.00")], [("A", "50.50")], True, 0.0, 50.50),
    ],
)
def test_dashboard_split_sums_to_total(client, db_session, monkeypatch, regular_rows, practice_rows,
                                       regular_legacy, exp_regular, exp_practice):
    rows = {}
    if regular_rows is not None:
        rows["r"] = [_split_row(*r) for r in regular_rows]
        db_session.add(PlanillaOutput(month=12, year=2099, total_payment=Decimal("1"),
                                      calculation_snapshot=None if regular_legacy else {"k": "r"}))
    if practice_rows is not None:
        rows["p"] = [_split_row(*r) for r in practice_rows]
        db_session.add(PracticePlanillaOutput(month=12, year=2099, total_payment=Decimal("1"),
                                              calculation_snapshot={"k": "p"}))
    db_session.commit()
    monkeypatch.setattr(planilla_router, "calculation_snapshot_rows", lambda snap, total: rows[snap["k"]])

    body = client.get("/api/dashboard/summary").json()

    assert body["total_regular_payment"] == pytest.approx(exp_regular)
    assert body["total_practice_payment"] == pytest.approx(exp_practice)
    assert round(body["total_regular_payment"] + body["total_practice_payment"], 2) == round(body["total_monthly_payment"], 2)
