from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.planilla import PlanillaOutput
from app.services.monetary_snapshot import build_calculation_snapshot

START, END = date(2026, 10, 21), date(2026, 11, 20)
QUERY = "start_date=2026-10-21&end_date=2026-11-20&discount_mode=full"


def _row(designation_id, ci, hours):
    return SimpleNamespace(
        designation_id=designation_id, teacher_ci=ci, teacher_name=f"Docente {ci}",
        has_biometric=True, has_retention=False, subject=f"Materia {designation_id}", group_code="A", semester="1",
        base_monthly_hours=hours, absent_hours=0, payable_hours=hours,
        rate_per_hour=Decimal("100"), calculated_payment=Decimal(hours * 100), retention_amount=Decimal("0"),
        retention_rate=Decimal("0"), phone="71234567", email=f"{ci}@test.invalid", nit="NIT", account_number="1",
        bank="Bank", sap_code="SAP", invoice_retention="",
    )


def _seed(db, overrides):
    rows = [_row(101, "T1", 4), _row(102, "T1", 4), _row(201, "T2", 5)]
    amounts = [Decimal("400"), Decimal("400"), Decimal("500")]
    snapshot = build_calculation_snapshot(
        rows=rows, row_amounts=amounts, month=11, year=2026, start_date=START, end_date=END,
        discount_mode="full", payment_overrides={}, excluded_days=[],
    )
    db.add(PlanillaOutput(
        month=11, year=2026, generated_at=datetime(2026, 11, 20, 12), total_teachers=2, total_hours=13,
        total_payment=Decimal("1300"), status="generated", discount_mode="full",
        start_date=START, end_date=END, calculation_snapshot=snapshot, payment_overrides_json=overrides,
    ))
    db.commit()


def test_detail_applies_stored_string_overrides_as_generator_saves_them(client, db_session):
    # The generator persists overrides as format(value, ".2f") strings.
    _seed(db_session, {"T1": "1000.40"})

    response = client.get(f"/api/planilla/11/2026/detail?{QUERY}")

    assert response.status_code == 200, response.text
    by_designation = {row["source_key"]: row["final_payment"] for row in response.json()["detail"]}
    assert by_designation == {"legacy:101": 500.2, "legacy:102": 500.2, "legacy:201": 500.0}
    totals = {item["teacher_ci"]: item["final_payment"] for item in response.json()["teacher_totals"]}
    assert Decimal(str(totals["T1"])) == Decimal("1000.40")
    assert Decimal(str(totals["T2"])) == Decimal("500")


def test_detail_applies_stored_string_row_overrides(client, db_session):
    _seed(db_session, {"T1": "1000.00", "T1:legacy:101": "700.00"})

    response = client.get(f"/api/planilla/11/2026/detail?{QUERY}")

    assert response.status_code == 200, response.text
    by_designation = {row["source_key"]: row["final_payment"] for row in response.json()["detail"]}
    assert by_designation == {"legacy:101": 700.0, "legacy:102": 300.0, "legacy:201": 500.0}


def test_detail_without_matching_dates_ignores_stored_overrides(client, db_session):
    _seed(db_session, {"T1": "1000.40"})

    response = client.get("/api/planilla/11/2026/detail?discount_mode=full")

    assert response.status_code == 200, response.text
    by_designation = {row["source_key"]: row["final_payment"] for row in response.json()["detail"]}
    assert by_designation == {"legacy:101": 400.0, "legacy:102": 400.0, "legacy:201": 500.0}


@pytest.mark.parametrize("overrides", [{"T1": "not-a-number"}, {"T1": "-5.00"}, {" bad key": "10.00"}])
def test_detail_reports_invalid_stored_overrides_as_conflict(client, db_session, overrides):
    _seed(db_session, overrides)

    response = client.get(f"/api/planilla/11/2026/detail?{QUERY}")

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "invalid_stored_overrides"
