from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi.encoders import jsonable_encoder

import app.services.planilla_generator as regular_generator
import app.services.report_generator as report_module
from app.models.planilla import PlanillaOutput
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.app_setting import AppSetting
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services.report_generator import ReportGenerator
from tests.test_snapshot_consumers import _seed


def _seed_both(db):
    _seed(db, PlanillaOutput, "REG-REPORT")
    _seed(db, PracticePlanillaOutput, "PRA-REPORT")


@pytest.mark.parametrize(
    ("model", "teacher_ci", "planilla_type"),
    [(PlanillaOutput, "REG-ONLY", "regular"), (PracticePlanillaOutput, "PRA-ONLY", "practice")],
)
def test_financial_preview_and_pdf_accept_one_available_snapshot(
    client, db_session, monkeypatch, tmp_path, model, teacher_ci, planilla_type
):
    _seed(db_session, model, teacher_ci)
    _forbid_live_money(monkeypatch)
    preview = client.get("/api/reports/preview?report_type=financial&month=5&year=2026")
    assert preview.status_code == 200, preview.text
    assert {row["planilla_type"] for row in preview.json()["rows"]} == {planilla_type}

    generator = ReportGenerator()
    monkeypatch.setattr(report_module, "_output_dir", lambda: tmp_path)
    report = generator.generate_financial_report(db_session, month=5, year=2026)
    assert report.status == "generated"
    assert preview.json() == jsonable_encoder(generator.build_financial_dataset(db_session, 5, 2026))


def test_financial_preview_and_pdf_require_at_least_one_snapshot(client, db_session):
    query = "report_type=financial&month=5&year=2026"
    preview = client.get(f"/api/reports/preview?{query}")
    pdf = client.post(f"/api/reports/generate?{query}")
    assert (preview.status_code, preview.json()["detail"]["code"]) == (409, "snapshot_missing")
    assert (pdf.status_code, pdf.json()["detail"]["code"]) == (409, "snapshot_missing")


def _forbid_live_money(monkeypatch):
    fail = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("live money"))
    monkeypatch.setattr(regular_generator.PlanillaGenerator, "_build_planilla_data", fail)
    monkeypatch.setattr(report_module.PracticePlanillaGenerator, "_build_planilla_data", fail)


def test_preview_and_pdf_share_the_same_regular_and_practice_dataset(
    client, db_session, monkeypatch, tmp_path
):
    _seed_both(db_session)
    teacher = db_session.query(Teacher).filter_by(ci="REG-REPORT").one()
    teacher.full_name = "Mutable live teacher"
    designation = Designation(
        teacher_ci=teacher.ci, subject="Mutable live subject", semester="1",
        group_code="A", schedule_json=[], designation_type="regular",
    )
    db_session.add(designation)
    rate = db_session.query(AppSetting).filter(AppSetting.key == "HOURLY_RATE").first()
    if rate is None:
        rate = AppSetting(key="HOURLY_RATE", value="70")
        db_session.add(rate)
    db_session.commit()
    _forbid_live_money(monkeypatch)
    preview = client.get("/api/reports/preview?report_type=financial&month=5&year=2026")
    assert preview.status_code == 200, preview.text

    generator = ReportGenerator()
    original = generator.build_financial_dataset
    captured = {}

    def record(*args, **kwargs):
        captured.update(original(*args, **kwargs))
        return captured

    monkeypatch.setattr(generator, "build_financial_dataset", record)
    monkeypatch.setattr(report_module, "_output_dir", lambda: tmp_path)
    teacher.full_name = "Changed after preview"
    designation.subject = "Changed after preview"
    rate.value = "9999"
    db_session.commit()
    generator.generate_financial_report(db_session, month=5, year=2026)

    assert preview.json() == jsonable_encoder(captured)
    assert {row["planilla_type"] for row in captured["rows"]} == {"regular", "practice"}
    assert sum(row["final_payment"] for row in captured["rows"]) == captured["total_payment"]
    assert captured["total_payment"] == Decimal("240.00")


def test_financial_filters_apply_identically_to_shared_snapshot_rows(client, db_session):
    _seed_both(db_session)
    params = {
        "report_type": "financial", "month": 5, "year": 2026, "teacher_ci": "PRA-REPORT",
        "semester": "1", "group_code": "A", "subject": "snapshot",
    }

    preview = client.get("/api/reports/preview", params=params)
    dataset = ReportGenerator().build_financial_dataset(
        db_session, month=5, year=2026, teacher_ci="PRA-REPORT",
        semester="1", group_code="A", subject="snapshot",
    )

    assert preview.json() == jsonable_encoder(dataset)
    assert [row["planilla_type"] for row in dataset["rows"]] == ["practice"]
    assert dataset["total_payment"] == Decimal("120.00")


@pytest.mark.parametrize("state", ["missing", "mismatch"])
def test_financial_preview_and_pdf_block_invalid_snapshot(client, db_session, state):
    _seed_both(db_session)
    practice = db_session.query(PracticePlanillaOutput).one()
    if state == "missing":
        practice.calculation_snapshot = None
    else:
        snapshot = deepcopy(practice.calculation_snapshot)
        snapshot["designations"][0]["teacher_name"] = "live drift"
        practice.calculation_snapshot = snapshot
    db_session.commit()
    query = "report_type=financial&month=5&year=2026"

    preview = client.get(f"/api/reports/preview?{query}")
    pdf = client.post(f"/api/reports/generate?{query}")

    expected = "snapshot_missing" if state == "missing" else "snapshot_mismatch"
    assert (preview.status_code, preview.json()["detail"]["code"]) == (409, expected)
    assert (pdf.status_code, pdf.json()["detail"]["code"]) == (409, expected)
