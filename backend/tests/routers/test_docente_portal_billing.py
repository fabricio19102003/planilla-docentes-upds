from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.models.billing_publication import BillingPublication
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.routers.docente_portal import _designation_billing_from_snapshot, _snapshot_financials
from app.services import app_settings_service
from app.services.auth_service import auth_service


def _set_docente(client, db_session, *, ci: str = "BILLING-DOC-1") -> Teacher:
    teacher = Teacher(ci=ci, full_name="Docente Facturación", invoice_retention="RETENCION")
    user = User(
        ci=f"USER-{ci}",
        full_name=teacher.full_name,
        password_hash=auth_service.hash_password("CurrentPass1"),
        role="docente",
        teacher_ci=ci,
        is_active=True,
    )
    db_session.add_all([teacher, user])
    db_session.flush()
    _authenticate_docente(client, user)
    return teacher


def _authenticate_docente(client, user: User) -> None:
    token = auth_service.create_access_token(data={"sub": str(user.id), "role": "docente"})
    client.headers["Authorization"] = f"Bearer {token}"


@pytest.mark.parametrize(
    ("snapshot", "expected"),
    [
        pytest.param(
            {"has_retention": True, "gross_payment": 700, "retention_amount": 0, "payment": 650},
            (Decimal("700.00"), Decimal("0.13"), Decimal("91.00"), Decimal("41.00"), Decimal("650.00"), True),
            id="legacy-override-with-retention",
        ),
        pytest.param(
            {"has_retention": False, "gross_payment": 700, "retention_amount": 0, "payment": 650},
            (Decimal("700.00"), Decimal("0"), Decimal("0.00"), Decimal("-50.00"), Decimal("650.00"), True),
            id="legacy-override-without-retention",
        ),
        pytest.param(
            {
                "has_retention": True, "gross_payment": 700, "retention_rate": "0.10",
                "retention_amount": 70, "admin_adjustment": 20, "net_payment": 650,
                "has_admin_override": False,
            },
            (Decimal("700.00"), Decimal("0.10"), Decimal("70.00"), Decimal("20.00"), Decimal("650.00"), False),
            id="modern-explicit-financials",
        ),
    ],
)
def test_snapshot_financials_preserves_legacy_and_explicit_semantics(snapshot, expected):
    financials = _snapshot_financials(snapshot)
    designation = _designation_billing_from_snapshot(snapshot, snapshot["has_retention"])

    assert (
        financials["gross_payment"], financials["retention_rate"],
        financials["retention_amount"], financials["admin_adjustment"],
        financials["net_payment"], financials["has_admin_override"],
    ) == expected
    assert (
        designation.gross_payment, designation.retention_rate,
        designation.retention_amount, designation.admin_adjustment,
        designation.net_payment, designation.has_admin_override,
    ) == tuple(float(value) if isinstance(value, Decimal) else value for value in expected)
    assert designation.payment == designation.net_payment


def test_billing_history_exposes_retention_without_false_admin_override(client, db_session):
    teacher = _set_docente(client, db_session)
    publication = BillingPublication(
        month=4,
        year=2026,
        planilla_type="regular",
        status="published",
        version=1,
        total_teachers=1,
        total_payment=Decimal("609.00"),
        published_at=datetime(2026, 4, 30, 12, 0, 0),
        billing_snapshot={
            "rate_per_hour": 70,
            "teacher_details": [{
                "teacher_ci": teacher.ci,
                "has_retention": True,
                "total_hours": 10,
                "gross_payment": 700,
                "retention_amount": 91,
                "final_payment": 609,
                "total_payment": 609,
                "designations": [{
                    "subject": "Anatomía",
                    "semester": "I",
                    "group": "A",
                    "payable_hours": 10,
                    "gross_payment": 700,
                    "retention_amount": 91,
                    "payment": 609,
                }],
            }],
        },
    )
    db_session.add(publication)
    db_session.commit()

    response = client.get("/api/portal/billing/history")

    assert response.status_code == 200
    item = response.json()[0]
    assert item["data_status"] == "available"
    assert item["gross_payment"] == 700.0
    assert item["retention_amount"] == 91.0
    assert item["admin_adjustment"] == 0.0
    assert item["net_payment"] == 609.0
    assert item["has_admin_override"] is False
    assert item["adjusted_payment"] is None
    assert item["designations"][0]["semester"] == "I"
    assert item["designations"][0]["payment"] == item["designations"][0]["net_payment"]
    assert item["designations"][0]["has_admin_override"] is False


def test_current_billing_exposes_explicit_admin_adjustment_contract(client, db_session):
    teacher = _set_docente(client, db_session, ci="BILLING-CURRENT-1")
    now = datetime.now()
    db_session.add(BillingPublication(
        month=now.month,
        year=now.year,
        planilla_type="regular",
        status="published",
        version=1,
        total_teachers=1,
        total_payment=Decimal("650.00"),
        published_at=now,
        billing_snapshot={
            "rate_per_hour": 70,
            "teacher_details": [{
                "teacher_ci": teacher.ci,
                "has_retention": True,
                "total_hours": 10,
                "gross_payment": 700,
                "retention_amount": 91,
                "final_payment": 650,
                "total_payment": 650,
                "designations": [{
                    "subject": "Cirugía",
                    "semester": "II",
                    "group": "B",
                    "payable_hours": 10,
                    "gross_payment": 700,
                    "retention_amount": 0,
                    "payment": 650,
                }],
            }],
        },
    ))
    db_session.commit()

    response = client.get("/api/portal/billing/current")

    assert response.status_code == 200
    billing = response.json()["regular"]
    assert billing["gross_payment"] == 700.0
    assert billing["retention_amount"] == 91.0
    assert billing["admin_adjustment"] == 41.0
    assert billing["net_payment"] == 650.0
    assert billing["has_admin_override"] is True
    assert billing["designations"][0]["semester"] == "II"
    for field in ("gross_payment", "retention_amount", "admin_adjustment", "net_payment"):
        assert sum(row[field] for row in billing["designations"]) == billing[field]
    assert billing["designations"][0]["admin_adjustment"] == 41.0
    assert billing["designations"][0]["payment"] == billing["designations"][0]["net_payment"]


@pytest.mark.parametrize("planilla_type", ["regular", "practice"])
def test_current_snapshotless_publication_is_typed_unavailable(client, db_session, planilla_type):
    _set_docente(client, db_session, ci=f"BILLING-UNAVAILABLE-{planilla_type}")
    now = datetime.now()
    db_session.add(BillingPublication(
        month=now.month,
        year=now.year,
        planilla_type=planilla_type,
        status="published",
        version=1,
        total_teachers=1,
        total_payment=Decimal("700.00"),
        published_at=now,
        billing_snapshot=None,
    ))
    db_session.commit()

    response = client.get("/api/portal/billing/current")

    assert response.status_code == 200
    billing = response.json()[planilla_type]
    assert billing["data_status"] == "published_unavailable"
    assert billing["gross_payment"] is None
    assert billing["net_payment"] is None
    assert billing["total_hours"] is None


def test_snapshotless_history_is_omitted_for_two_unverifiable_docentes(client, db_session, monkeypatch):
    import app.routers.docente_portal as docente_portal_router

    teachers = [
        _set_docente(client, db_session, ci="BILLING-LEGACY-1"),
        _set_docente(client, db_session, ci="BILLING-LEGACY-2"),
    ]
    db_session.add_all([
        Designation(
            teacher_ci=teacher.ci,
            subject=f"Materia actual {teacher.ci}",
            semester="I",
            group_code="A",
            academic_period="I/2026",
            designation_type="regular",
            schedule_json=[],
            monthly_hours=10,
        )
        for teacher in teachers
    ])
    db_session.add(BillingPublication(
        month=3,
        year=2025,
        planilla_type="regular",
        status="published",
        version=1,
        total_teachers=1,
        total_payment=Decimal("700.00"),
        published_at=datetime(2025, 3, 31, 12, 0, 0),
        billing_snapshot=None,
    ))
    app_settings_service.update_setting(db_session, "ACTIVE_ACADEMIC_PERIOD", "I/2026")
    db_session.commit()
    app_settings_service.invalidate_cache()
    monkeypatch.setattr(
        docente_portal_router,
        "_build_billing",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("legacy billing was recalculated")),
    )

    def history_by_teacher():
        result = {}
        for teacher in teachers:
            user = db_session.query(User).filter(User.teacher_ci == teacher.ci).one()
            _authenticate_docente(client, user)
            response = client.get("/api/portal/billing/history")
            assert response.status_code == 200
            result[teacher.ci] = response.json()
        return result

    before = history_by_teacher()

    app_settings_service.update_setting(db_session, "ACTIVE_ACADEMIC_PERIOD", "II/2026")
    db_session.commit()
    app_settings_service.invalidate_cache()
    after = history_by_teacher()

    assert before == after == {teacher.ci: [] for teacher in teachers}
