from __future__ import annotations

from datetime import date, time

import pytest

from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.attendance import AttendanceRecord
from app.models.billing_publication import BillingPublication
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.services.planilla_generator import PlanillaGenerator

URL = "/api/admin/academic-management/designation-changes"
PERIOD = "I/2026"


@pytest.fixture
def seeded(db_session):
    for key, value in (("HOURLY_RATE", "70"), ("PRACTICE_HOURLY_RATE", "50"), ("ACTIVE_ACADEMIC_PERIOD", PERIOD)):
        existing = db_session.get(AppSetting, key)
        if existing is None:
            db_session.add(AppSetting(key=key, value=value, description="test"))
        else:
            existing.value = value
    for ci in ("CHG-T1", "CHG-T2", "CHG-T3"):
        db_session.add(Teacher(ci=ci, full_name=f"DOCENTE {ci}"))
    db_session.flush()
    return db_session


def _designation(db, teacher_ci="CHG-T1", *, subject="Anatomia", group="M-1", kind="regular",
                 start=None, end=None, weekday="lunes"):
    item = Designation(
        teacher_ci=teacher_ci, subject=subject, semester="1", group_code=group,
        academic_period=PERIOD, designation_type=kind,
        schedule_json=[{"dia": weekday, "hora_inicio": "08:00", "hora_fin": "09:30", "horas_academicas": 2}],
        monthly_hours=8, weekly_hours=2, schedule_raw="LUNES 08:00-09:30",
        contract_start_date=start, contract_end_date=end,
    )
    db.add(item)
    db.flush()
    return item


def _body(designation_id=None, **extra):
    body = {"academic_period": PERIOD, "effective_from": "2026-05-18", "incoming_teacher_ci": "CHG-T2"}
    if designation_id is not None:
        body.update({"scope": "designation", "designation_id": designation_id})
    body.update(extra)
    return body


def _snapshot(db):
    db.expire_all()
    return sorted(
        (d.teacher_ci, d.subject, d.contract_start_date, d.contract_end_date)
        for d in db.query(Designation).filter(Designation.academic_period == PERIOD)
    )


def test_preview_shows_monthly_pay_split_and_apply_splits_payroll(client, seeded):
    old = _designation(seeded)

    preview = client.post(f"{URL}/preview", json=_body(old.id))
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["can_apply"] is True
    assert data["blockers"] == []
    assert data["items"] == [{
        "designation_id": old.id, "subject": "Anatomia", "semester": "1", "group_code": "M-1",
        "designation_type": "regular", "outgoing_teacher_ci": "CHG-T1", "incoming_teacher_ci": "CHG-T2",
        "outgoing_until": "2026-05-17", "incoming_from": "2026-05-18", "incoming_until": None,
    }]
    assert data["impact"] == {
        "month": 5, "year": 2026,
        "teachers": [
            {"teacher_ci": "CHG-T1", "teacher_name": "DOCENTE CHG-T1", "activity": "theory",
             "hours_before": 8, "hours_after": 4, "amount_before": 560.0, "amount_after": 280.0},
            {"teacher_ci": "CHG-T2", "teacher_name": "DOCENTE CHG-T2", "activity": "theory",
             "hours_before": 0, "hours_after": 4, "amount_before": 0.0, "amount_after": 280.0},
        ],
    }
    # Preview never writes.
    assert _snapshot(seeded) == [("CHG-T1", "Anatomia", None, None)]

    applied = client.post(f"{URL}/apply", json=_body(old.id))
    assert applied.status_code == 201, applied.text
    result = applied.json()
    assert result["ended_designation_ids"] == [old.id]
    assert len(result["created_designation_ids"]) == 1
    assert result["regenerate"] == []
    assert _snapshot(seeded) == [
        ("CHG-T1", "Anatomia", None, date(2026, 5, 17)),
        ("CHG-T2", "Anatomia", date(2026, 5, 18), None),
    ]
    created = seeded.get(Designation, result["created_designation_ids"][0])
    assert (created.schedule_json, created.monthly_hours, created.weekly_hours, created.designation_type,
            created.semester, created.group_code, created.schedule_raw) == (
        old.schedule_json, 8, 2, "regular", "1", "M-1", "LUNES 08:00-09:30")

    rows = PlanillaGenerator()._build_planilla_data(seeded, 5, 2026, discount_mode="full")[0]
    assert sorted((row.teacher_ci, row.payable_hours) for row in rows) == [("CHG-T1", 4), ("CHG-T2", 4)]
    assert sum(row.final_payment for row in rows) == 8 * 70.0

    log = seeded.query(ActivityLog).filter(ActivityLog.action == "teacher_change_designation").one()
    assert log.category == "academic_management"
    assert log.details["ended_designation_ids"] == [old.id]
    assert log.details["effective_from"] == "2026-05-18"


def test_teacher_scope_moves_every_active_designation(client, seeded):
    first = _designation(seeded, subject="Anatomia")
    second = _designation(seeded, subject="Histologia", weekday="martes")
    _designation(seeded, subject="Ended", end=date(2026, 4, 30))
    _designation(seeded, "CHG-T3", subject="Other")

    body = _body(scope="teacher", outgoing_teacher_ci="CHG-T1")
    preview = client.post(f"{URL}/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert [item["designation_id"] for item in preview.json()["items"]] == [first.id, second.id]

    applied = client.post(f"{URL}/apply", json=body)
    assert applied.status_code == 201, applied.text
    assert applied.json()["ended_designation_ids"] == [first.id, second.id]
    assert _snapshot(seeded) == [
        ("CHG-T1", "Anatomia", None, date(2026, 5, 17)),
        ("CHG-T1", "Ended", None, date(2026, 4, 30)),
        ("CHG-T1", "Histologia", None, date(2026, 5, 17)),
        ("CHG-T2", "Anatomia", date(2026, 5, 18), None),
        ("CHG-T2", "Histologia", date(2026, 5, 18), None),
        ("CHG-T3", "Other", None, None),
    ]


def _assert_blocked(client, db, body, code):
    before = _snapshot(db)
    logs_before = db.query(ActivityLog).count()
    preview = client.post(f"{URL}/preview", json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["can_apply"] is False
    blockers = preview.json()["blockers"]
    assert code in [item["code"] for item in blockers]
    applied = client.post(f"{URL}/apply", json=body)
    assert applied.status_code == 409, applied.text
    assert code in [item["code"] for item in applied.json()["detail"]["blockers"]]
    assert _snapshot(db) == before
    assert db.query(ActivityLog).count() == logs_before
    return blockers


def test_approved_payroll_blocks_with_explanation(client, seeded):
    old = _designation(seeded)
    seeded.add(PlanillaOutput(month=5, year=2026, file_path="x.xlsx", total_teachers=1,
                              total_hours=8, total_payment=560, status="approved"))
    seeded.flush()
    blockers = _assert_blocked(client, seeded, _body(old.id), "payroll_approved")
    assert blockers[0]["message"] == (
        "La planilla de teoría 5/2026 ya está aprobada y cubre la fecha del cambio. "
        "Rechazala o elegí una fecha posterior."
    )


def test_published_billing_blocks(client, seeded):
    old = _designation(seeded)
    seeded.add(BillingPublication(month=5, year=2026, planilla_type="regular", status="published"))
    seeded.flush()
    _assert_blocked(client, seeded, _body(old.id), "billing_published")


def test_generated_payroll_is_allowed_and_asks_for_regeneration(client, seeded):
    old = _designation(seeded)
    seeded.add(PlanillaOutput(month=5, year=2026, file_path="x.xlsx", total_teachers=1,
                              total_hours=8, total_payment=560, status="generated"))
    seeded.add(PracticePlanillaOutput(month=5, year=2026, file_path="p.xlsx", total_teachers=1,
                                      total_hours=8, total_payment=400, status="approved"))
    seeded.flush()
    preview = client.post(f"{URL}/preview", json=_body(old.id)).json()
    assert preview["can_apply"] is True
    assert preview["regenerate"] == [{"planilla": "regular", "month": 5, "year": 2026, "status": "generated"}]
    applied = client.post(f"{URL}/apply", json=_body(old.id))
    assert applied.status_code == 201, applied.text
    assert applied.json()["regenerate"] == preview["regenerate"]


def test_practice_designation_checks_practice_payroll(client, seeded):
    old = _designation(seeded, kind="practice")
    seeded.add(PracticePlanillaOutput(month=5, year=2026, file_path="p.xlsx", total_teachers=1,
                                      total_hours=8, total_payment=400, status="approved"))
    seeded.flush()
    blockers = _assert_blocked(client, seeded, _body(old.id), "payroll_approved")
    assert blockers[0]["message"].startswith("La planilla de práctica 5/2026 ya está aprobada")


def test_outgoing_attendance_after_change_blocks_and_lists_dates(client, seeded):
    old = _designation(seeded)
    for day, status in ((date(2026, 5, 11), "ATTENDED"), (date(2026, 5, 18), "ABSENT"), (date(2026, 5, 25), "LATE")):
        seeded.add(AttendanceRecord(
            teacher_ci="CHG-T1", designation_id=old.id, date=day,
            scheduled_start=time(8, 0), scheduled_end=time(9, 30),
            actual_entry=None if status == "ABSENT" else time(8, 0),
            actual_exit=None if status == "ABSENT" else time(9, 30),
            status=status, academic_hours=2, month=day.month, year=day.year,
        ))
    seeded.flush()
    blockers = _assert_blocked(client, seeded, _body(old.id), "outgoing_attendance_after_change")
    item = next(b for b in blockers if b["code"] == "outgoing_attendance_after_change")
    assert item["dates"] == ["2026-05-25"]


@pytest.mark.parametrize(
    ("setup", "incoming", "effective_from", "code"),
    [
        ({}, "CHG-T1", "2026-05-18", "same_teacher"),
        ({"start": date(2026, 5, 18)}, "CHG-T2", "2026-05-18", "before_contract_start"),
        ({"end": date(2026, 5, 10)}, "CHG-T2", "2026-05-18", "after_contract_end"),
        ({"incoming_holds": True}, "CHG-T2", "2026-05-18", "incoming_has_designation"),
    ],
)
def test_invalid_changes_are_blocked(client, seeded, setup, incoming, effective_from, code):
    old = _designation(seeded, start=setup.get("start"), end=setup.get("end"))
    if setup.get("incoming_holds"):
        _designation(seeded, "CHG-T2")
    _assert_blocked(
        client, seeded,
        _body(old.id, incoming_teacher_ci=incoming, effective_from=effective_from), code,
    )


def test_unknown_teacher_and_designation_are_404(client, seeded):
    old = _designation(seeded)
    missing_teacher = client.post(f"{URL}/preview", json=_body(old.id, incoming_teacher_ci="NOPE"))
    assert missing_teacher.status_code == 404
    assert missing_teacher.json()["detail"] == "Docente entrante no encontrado"
    missing_designation = client.post(f"{URL}/preview", json=_body(999999))
    assert missing_designation.status_code == 404
    assert missing_designation.json()["detail"] == "Designación no encontrada en el período"
    empty = client.post(f"{URL}/preview", json=_body(scope="teacher", outgoing_teacher_ci="CHG-T3"))
    assert empty.status_code == 404
    assert empty.json()["detail"] == "El docente saliente no tiene designaciones activas en esa fecha"


def test_scope_requires_matching_identifier(client, seeded):
    response = client.post(f"{URL}/preview", json=_body(scope="designation"))
    assert response.status_code == 422
    response = client.post(f"{URL}/preview", json=_body(scope="teacher"))
    assert response.status_code == 422


def test_lists_teacher_designations_for_the_wizard(client, seeded):
    active = _designation(seeded, subject="Anatomia")
    ended = _designation(seeded, subject="Ended", end=date(2026, 4, 30))
    _designation(seeded, "CHG-T3", subject="Other")
    response = client.get(f"{URL}/designations", params={"academic_period": PERIOD, "teacher_ci": "CHG-T1"})
    assert response.status_code == 200, response.text
    assert response.json() == [
        {"id": active.id, "teacher_ci": "CHG-T1", "subject": "Anatomia", "semester": "1", "group_code": "M-1",
         "designation_type": "regular", "monthly_hours": 8, "weekly_hours": 2, "schedule_raw": "LUNES 08:00-09:30",
         "contract_start_date": None, "contract_end_date": None},
        {"id": ended.id, "teacher_ci": "CHG-T1", "subject": "Ended", "semester": "1", "group_code": "M-1",
         "designation_type": "regular", "monthly_hours": 8, "weekly_hours": 2, "schedule_raw": "LUNES 08:00-09:30",
         "contract_start_date": None, "contract_end_date": "2026-04-30"},
    ]
    assert client.get(f"{URL}/designations", params={"academic_period": PERIOD}).status_code == 422
