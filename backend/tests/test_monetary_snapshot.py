from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base
from app.models.planilla import PlanillaOutput
from app.models.practice_planilla import PracticePlanillaOutput
from app.routers import planilla, practice_planilla
from app.services.monetary_snapshot import (
    SnapshotReconciliationError,
    build_calculation_snapshot,
    reconcile_calculation_snapshot,
)


def _row(designation_id: int, teacher_ci: str, amount: str):
    return SimpleNamespace(
        designation_id=designation_id,
        teacher_ci=teacher_ci,
        teacher_name="Snapshot Teacher",
        has_biometric=True,
        has_retention=False,
        subject="Snapshot Subject",
        group_code="A",
        semester="1",
        base_monthly_hours=10,
        absent_hours=1,
        payable_hours=9,
        rate_per_hour=70,
        calculated_payment=Decimal(amount),
        retention_amount=0,
        retention_rate=0,
    )


def _snapshot(amount: str = "10.005") -> dict:
    return build_calculation_snapshot(
        rows=[_row(1, "123", amount)],
        row_amounts=[Decimal(amount)],
        month=8,
        year=2026,
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 20),
        discount_mode="attendance",
        payment_overrides={"123:1": Decimal(amount)},
        excluded_days=[{"date": "2026-08-12", "scope": "global"}],
    )


def test_snapshot_is_canonical_serializable_and_detached_from_live_rows():
    row = _row(1, "123", "10.005")
    snapshot = build_calculation_snapshot(
        rows=[row],
        row_amounts=[Decimal("10.005")],
        month=8,
        year=2026,
        start_date=None,
        end_date=None,
        discount_mode="full",
        payment_overrides={"123:1": Decimal("10.005")},
        excluded_days=[],
    )

    row.calculated_payment = Decimal("9999")

    assert snapshot["schema_version"] == 1
    assert snapshot["period"] == {"month": 8, "year": 2026, "start": "2026-08-01", "end": "2026-08-31"}
    assert snapshot["designations"][0]["amount"] == "10.01"
    assert snapshot["teachers"][0]["total"] == "10.01"
    assert snapshot["total"] == "10.01"
    assert snapshot["overrides"] == {"123:1": "10.01"}
    assert snapshot["designations"][0]["teacher_ci"] == "123"
    assert len(snapshot["digest"]) == 64
    assert "123" not in snapshot["designations"][0]["teacher_ref"]
    reconcile_calculation_snapshot(snapshot, Decimal("10.01"))


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value["designations"][0].update(amount="9.00"), "teacher_total_mismatch"),
        (lambda value: value.update(total="9.00"), "planilla_total_mismatch"),
        (lambda value: value.update(total="NaN"), "invalid_money"),
        (lambda value: value.update(total="-1.00"), "invalid_money"),
        (lambda value: value["designations"][0].update(payable_hours=-1), "invalid_value"),
    ],
)
def test_reconciliation_fails_closed_with_actionable_codes(mutation, code):
    snapshot = _snapshot()
    mutation(snapshot)

    with pytest.raises(SnapshotReconciliationError) as exc_info:
        reconcile_calculation_snapshot(snapshot, Decimal("10.01"))

    assert exc_info.value.code == code
    assert exc_info.value.sample


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.mark.parametrize(
    ("model", "approve", "router_module"),
    [
        (PlanillaOutput, planilla.approve_planilla, planilla),
        (PracticePlanillaOutput, practice_planilla.approve_practice_planilla, practice_planilla),
    ],
)
@pytest.mark.parametrize("state", ["missing", "mismatch", "valid"])
def test_approval_requires_a_reconciled_snapshot(db, monkeypatch, model, approve, router_module, state):
    monkeypatch.setattr(router_module, "log_activity", lambda *args, **kwargs: None)
    snapshot = None if state == "missing" else _snapshot()
    output = model(
        month=8,
        year=2026,
        total_teachers=1,
        total_hours=9,
        total_payment=Decimal("11.00") if state == "mismatch" else Decimal("10.01"),
        status="generated",
        calculation_snapshot=snapshot,
    )
    db.add(output)
    db.commit()

    if state == "valid":
        response = approve(request=None, planilla_id=output.id, current_user=SimpleNamespace(), db=db)
        assert response["status"] == "approved"
        return

    with pytest.raises(HTTPException) as exc_info:
        approve(request=None, planilla_id=output.id, current_user=SimpleNamespace(), db=db)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == f"snapshot_{state}"
    db.refresh(output)
    assert output.status == ("snapshot_missing" if state == "missing" else "generated")
