from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.models.billing_publication import BillingPublication
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service

CLOSED_NOTE = "Sin clases en este período (designación finalizada el 20/09/2026)"
PLAIN_NOTE = "Sin clases en este período"


def _docente(client, db_session, ci: str) -> Teacher:
    teacher = Teacher(ci=ci, full_name="Docente Cierre", invoice_retention=None)
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
    token = auth_service.create_access_token(data={"sub": str(user.id), "role": "docente"})
    client.headers["Authorization"] = f"Bearer {token}"
    return teacher


def _designation(db_session, ci: str, group: str, contract_end: date | None) -> Designation:
    designation = Designation(
        teacher_ci=ci,
        academic_period="II/2026",
        subject="CASO BÁSICO CLÍNICO III",
        semester="3",
        group_code=group,
        designation_type="regular",
        schedule_json=[],
        monthly_hours=12,
        contract_start_date=date(2026, 8, 10),
        contract_end_date=contract_end,
    )
    db_session.add(designation)
    db_session.flush()
    return designation


def _snapshot(ci: str, rows: list[dict]) -> dict:
    return {
        "rate_per_hour": 70,
        "teacher_details": [{
            "teacher_ci": ci,
            "has_retention": False,
            "total_hours": 12,
            "gross_payment": 840,
            "retention_amount": 0,
            "final_payment": 840,
            "total_payment": 840,
            "designations": rows,
        }],
    }


def _row(designation_id: int, group: str, base: int, payable: int, amount: int) -> dict:
    return {
        "designation_id": designation_id,
        "subject": "CASO BÁSICO CLÍNICO III",
        "semester": "3",
        "group": group,
        "base_hours": base,
        "absent_hours": base - payable,
        "payable_hours": payable,
        "effective_from": "2026-09-21",
        "effective_to": "2026-10-20",
        "gross_payment": amount,
        "retention_amount": 0,
        "payment": amount,
    }


def _publish(db_session, ci: str, month: int, year: int, now: datetime | None = None) -> None:
    closed = _designation(db_session, ci, "N-3", date(2026, 9, 20))
    open_ended = _designation(db_session, ci, "N-4", None)
    absence = _designation(db_session, ci, "N-5", None)
    open_zero = _designation(db_session, ci, "N-6", None)
    db_session.add(BillingPublication(
        month=month,
        year=year,
        planilla_type="regular",
        status="published",
        version=1,
        total_teachers=1,
        total_payment=Decimal("840.00"),
        published_at=now or datetime(2026, 10, 25, 12, 0, 0),
        billing_snapshot=_snapshot(ci, [
            _row(closed.id, "N-3", 0, 0, 0),
            _row(open_ended.id, "EXTRA", 12, 12, 840),
            _row(absence.id, "N-5", 12, 0, 0),
            _row(open_zero.id, "N-6", 0, 0, 0),
        ]),
    ))
    db_session.commit()


def _assert_notes(designations: list[dict]) -> None:
    by_group = {row["group"]: row for row in designations}
    assert by_group["N-3"]["period_note"] == CLOSED_NOTE
    assert by_group["N-6"]["period_note"] == PLAIN_NOTE
    assert by_group["EXTRA"]["period_note"] is None
    assert by_group["N-5"]["period_note"] is None  # absence: base 12, payable 0
    # Display only: amounts and hours are exactly what the snapshot stored.
    assert (by_group["N-3"]["hours"], by_group["N-3"]["net_payment"], by_group["N-3"]["gross_payment"]) == (0, 0.0, 0.0)
    assert (by_group["EXTRA"]["hours"], by_group["EXTRA"]["net_payment"]) == (12, 840.0)
    assert (by_group["N-5"]["hours"], by_group["N-5"]["net_payment"]) == (0, 0.0)


def test_history_adds_period_note_to_rows_without_classes(client, db_session):
    teacher = _docente(client, db_session, "NOTE-HIST-1")
    _publish(db_session, teacher.ci, 10, 2026)

    response = client.get("/api/portal/billing/history")

    assert response.status_code == 200
    item = response.json()[0]
    assert item["net_payment"] == 840.0
    _assert_notes(item["designations"])


def test_current_billing_adds_period_note_to_rows_without_classes(client, db_session):
    teacher = _docente(client, db_session, "NOTE-CURR-1")
    now = datetime.now()
    _publish(db_session, teacher.ci, now.month, now.year, now)

    response = client.get("/api/portal/billing/current")

    assert response.status_code == 200
    billing = response.json()["regular"]
    assert billing["net_payment"] == 840.0
    _assert_notes(billing["designations"])


def test_snapshot_rows_without_base_hours_get_no_note(client, db_session):
    teacher = _docente(client, db_session, "NOTE-LEGACY-1")
    db_session.add(BillingPublication(
        month=4, year=2026, planilla_type="regular", status="published", version=1,
        total_teachers=1, total_payment=Decimal("0.00"),
        published_at=datetime(2026, 4, 30, 12, 0, 0),
        billing_snapshot=_snapshot(teacher.ci, [{
            "subject": "Anatomía", "semester": "I", "group": "A",
            "payable_hours": 0, "gross_payment": 0, "retention_amount": 0, "payment": 0,
        }]),
    ))
    db_session.commit()

    response = client.get("/api/portal/billing/history")

    assert response.status_code == 200
    assert response.json()[0]["designations"][0]["period_note"] is None


def test_admin_planilla_detail_adds_period_note(client, db_session, admin_token):
    from app.models.app_setting import AppSetting

    db_session.add_all([
        AppSetting(key="HOURLY_RATE", value="70", description="test"),
        AppSetting(key="ACTIVE_ACADEMIC_PERIOD", value="II/2026", description="test"),
        Teacher(ci="NOTE-ADMIN-1", full_name="Docente Admin", invoice_retention=None),
    ])
    db_session.flush()
    _designation(db_session, "NOTE-ADMIN-1", "N-3", date(2026, 4, 30))
    open_ended = Designation(
        teacher_ci="NOTE-ADMIN-1", academic_period="II/2026", subject="Materia", semester="1",
        group_code="A", designation_type="regular",
        schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "10:00", "horas_academicas": 2}],
        monthly_hours=8, weekly_hours=2,
    )
    db_session.add(open_ended)
    db_session.commit()

    response = client.get(
        "/api/planilla/5/2026/detail?discount_mode=full",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    by_group = {row["group_code"]: row for row in response.json()["detail"]}
    assert by_group["N-3"]["period_note"] == "Sin clases en este período (designación finalizada el 30/04/2026)"
    assert (by_group["N-3"]["payable_hours"], by_group["N-3"]["final_payment"]) == (0, 0)
    assert by_group["A"]["period_note"] is None
    assert by_group["A"]["payable_hours"] > 0


def test_admin_practice_planilla_detail_adds_period_note(client, db_session, admin_token):
    from app.models.app_setting import AppSetting

    db_session.add_all([
        AppSetting(key="PRACTICE_HOURLY_RATE", value="50", description="test"),
        AppSetting(key="ACTIVE_ACADEMIC_PERIOD", value="II/2026", description="test"),
        Teacher(ci="NOTE-PRAC-1", full_name="Docente Practica", invoice_retention=None),
    ])
    db_session.flush()
    closed = _designation(db_session, "NOTE-PRAC-1", "P-3", date(2026, 4, 30))
    closed.designation_type = "practice"
    db_session.commit()

    response = client.get(
        "/api/practice-planilla/5/2026/detail?discount_mode=full",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    by_group = {row["group_code"]: row for row in rows}
    assert by_group["P-3"]["period_note"] == "Sin clases en este período (designación finalizada el 30/04/2026)"
    assert by_group["P-3"]["final_payment"] == 0
