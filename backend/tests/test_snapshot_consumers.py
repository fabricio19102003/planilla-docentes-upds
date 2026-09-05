from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from app.models.planilla import PlanillaOutput
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.services.monetary_snapshot import build_calculation_snapshot, calculation_snapshot_digest
CASES = [(PlanillaOutput, "planilla", "REG"), (PracticePlanillaOutput, "practice_planilla", "PRA")]

def _seed(db, model, ci, snapshot=True):
    designation_id = 101 if model is PlanillaOutput else 201
    row = SimpleNamespace(
        designation_id=designation_id, teacher_ci=ci, teacher_name=f"Snapshot {ci}",
        has_biometric=True, has_retention=True, subject="Snapshot subject", group_code="A", semester="1",
        base_monthly_hours=8, absent_hours=1, payable_hours=7,
        rate_per_hour=Decimal("70" if model is PlanillaOutput else "50"),
        calculated_payment=Decimal("100"), retention_amount=Decimal("13"), retention_rate=Decimal("0.13"),
        phone="71234567", email=f"{ci.lower()}@snapshot.test", nit="NIT-123",
        account_number="100200300", bank="Snapshot Bank", sap_code="SAP-9",
        invoice_retention="RETENCION",
    )
    value = build_calculation_snapshot(
        rows=[row], row_amounts=[Decimal("120")], month=5, year=2026,
        start_date=date(2026, 5, 1), end_date=date(2026, 5, 31), discount_mode="full",
        payment_overrides={f"{ci}:{designation_id}": Decimal("120")}, excluded_days=[],
    ) if snapshot else None
    output = model(
        month=5, year=2026, generated_at=datetime(2026, 5, 31, 12), total_teachers=1,
        total_hours=7, total_payment=Decimal("120"), status="approved", discount_mode="full",
        calculation_snapshot=value,
    )
    db.add_all([output, Teacher(
        ci=ci, full_name=f"Live {ci}", phone="70000000", email="live@test.invalid",
        nit="LIVE-NIT", account_number="999", bank="Live Bank", sap_code="LIVE-SAP",
    )])
    db.commit()

@pytest.mark.parametrize(("model", "router_name", "kind"), CASES)
def test_detail_and_history_use_snapshot_without_live_recalculation(
    client, db_session, monkeypatch, model, router_name, kind
):
    ci = f"{kind}-SNAPSHOT"
    _seed(db_session, model, ci)
    teacher = db_session.query(Teacher).filter_by(ci=ci).one()
    teacher.phone = "78888888"
    teacher.email = "mutated@test.invalid"
    teacher.nit = "MUTATED-NIT"
    teacher.account_number = "888"
    teacher.bank = "Mutated Bank"
    db_session.commit()
    router = __import__(f"app.routers.{router_name}", fromlist=[router_name])
    generator = router.PlanillaGenerator if model is PlanillaOutput else router.PracticePlanillaGenerator
    monkeypatch.setattr(generator, "_build_planilla_data", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("live")))
    prefix = "/api/planilla" if model is PlanillaOutput else "/api/practice-planilla"
    detail, history = client.get(f"{prefix}/5/2026/detail").json(), client.get(f"{prefix}/history").json()
    rows = detail.get("detail", detail.get("rows"))
    assert (rows[0]["teacher_ci"], Decimal(str(rows[0]["final_payment"]))) == (ci, Decimal("120"))
    assert Decimal(str(detail.get("total_payment", detail.get("total_net")))) == Decimal("120")
    assert (history[0]["data_status"], Decimal(str(history[0]["total_payment"]))) == ("available", Decimal("120"))

@pytest.mark.parametrize(("model", "router_name", "kind"), CASES)
def test_legacy_history_is_explicit_and_detail_is_blocked(client, db_session, model, router_name, kind):
    _seed(db_session, model, "LEGACY", snapshot=False)
    prefix = "/api/planilla" if model is PlanillaOutput else "/api/practice-planilla"
    detail, history = client.get(f"{prefix}/5/2026/detail"), client.get(f"{prefix}/history").json()
    assert (detail.status_code, detail.json()["detail"]["code"]) == (409, "snapshot_missing")
    assert (history[0]["data_status"], history[0]["total_payment"]) == ("legacy_unavailable", None)


@pytest.mark.parametrize(("model", "router_name", "kind"), CASES)
def test_salary_xlsx_uses_exact_snapshot_money(client, db_session, monkeypatch, tmp_path, model, router_name, kind):
    ci = f"{kind}-XLSX"
    _seed(db_session, model, ci)
    router = __import__(f"app.routers.{router_name}", fromlist=[router_name])
    generator = router.PlanillaGenerator if model is PlanillaOutput else router.PracticePlanillaGenerator
    monkeypatch.setattr(generator, "_build_planilla_data", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("live")))
    monkeypatch.setattr(router, "_output_dir", lambda: tmp_path)
    url = "/api/planilla/salary-report" if model is PlanillaOutput else "/api/practice-planilla/salary-report"
    response = client.post(url, json={"month": 5, "year": 2026})
    assert response.status_code == 200, response.text
    sheet = load_workbook(BytesIO(response.content), data_only=False).active
    assert [sheet[f"{column}7"].value for column in "EJKL"] == [ci, 100, 13, 120]
    assert (sheet["L8"].value, sheet["M7"].value) == ("=SUBTOTAL(9,L7:L7)", "NIT-123")
    assert [sheet[f"{column}7"].value for column in ("C", "D", "N", "O")] == [
        71234567, f"{ci.lower()}@snapshot.test", 100200300, "Snapshot Bank",
    ]
    snapshot = db_session.query(model).one().calculation_snapshot
    assert snapshot["profiles"][0]["sap_code"] == "SAP-9"


@pytest.mark.parametrize(("model", "router_name", "kind"), CASES)
def test_salary_xlsx_rejects_snapshot_without_payroll_profile(
    client, db_session, model, router_name, kind
):
    _seed(db_session, model, f"{kind}-LEGACY-PROFILE")
    output = db_session.query(model).one()
    snapshot = dict(output.calculation_snapshot)
    snapshot.pop("profiles", None)
    snapshot["digest"] = calculation_snapshot_digest(snapshot)
    output.calculation_snapshot = snapshot
    db_session.commit()
    url = "/api/planilla/salary-report" if model is PlanillaOutput else "/api/practice-planilla/salary-report"
    response = client.post(url, json={"month": 5, "year": 2026})
    assert (response.status_code, response.json()["detail"]["code"]) == (409, "snapshot_profile_missing")
