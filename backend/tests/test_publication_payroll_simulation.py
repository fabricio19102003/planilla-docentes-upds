from __future__ import annotations

from app.models.academic_management import AcademicSchedulePublication, AcademicScheduleDraft
from app.models.app_setting import AppSetting
from app.models.designation import Designation
from app.models.teacher import Teacher
from tests.test_academic_schedule_publication import BASE, _assign, _seed


def _rates(db):
    for key, value in (("HOURLY_RATE", "70"), ("PRACTICE_HOURLY_RATE", "50")):
        existing = db.get(AppSetting, key)
        if existing is None:
            db.add(AppSetting(key=key, value=value, description="test"))
        else:
            existing.value = value
    db.flush()


def _simulate(client, draft_id, **body):
    payload = {"effective_from": "2027-02-01", "month": 3, "year": 2027}
    payload.update(body)
    return client.post(f"{BASE}/schedule-drafts/{draft_id}/payroll-simulation", json=payload)


def test_simulation_reports_bs_change_per_teacher_without_publishing(client, db_session):
    _rates(db_session)
    _program, _subject, _offering, _group, _room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    db_session.add(Teacher(ci="PUB-LEG", full_name="Legacy Teacher"))
    db_session.add(Designation(
        teacher_ci="PUB-LEG", subject="Publication Subject", semester="1", group_code="A",
        academic_period="I/2027", designation_type="regular",
        schedule_json=[{"dia": "martes", "hora_inicio": "08:00", "hora_fin": "09:30", "horas_academicas": 2}],
        monthly_hours=8, weekly_hours=2,
    ))
    db_session.flush()

    response = _simulate(client, draft["id"])
    assert response.status_code == 200, response.text
    assert response.json() == {
        "draft_id": draft["id"], "effective_from": "2027-02-01", "month": 3, "year": 2027,
        "teachers": [
            {"teacher_ci": "PUB-LEG", "teacher_name": "Legacy Teacher", "activity": "theory",
             "hours_before": 8, "hours_after": 0, "amount_before": 560.0, "amount_after": 0.0},
            {"teacher_ci": "PUB-T1", "teacher_name": "Publication Teacher", "activity": "theory",
             "hours_before": 0, "hours_after": 5, "amount_before": 0.0, "amount_after": 350.0},
        ],
        "total_before": 560.0, "total_after": 350.0,
    }
    db_session.expire_all()
    assert db_session.query(AcademicSchedulePublication).count() == 0
    assert db_session.get(AcademicScheduleDraft, draft["id"]).status == "draft"


def test_simulation_from_mid_month_only_moves_the_remaining_days(client, db_session):
    _rates(db_session)
    _program, _subject, _offering, _group, _room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    db_session.add(Teacher(ci="PUB-LEG", full_name="Legacy Teacher"))
    db_session.add(Designation(
        teacher_ci="PUB-LEG", subject="Publication Subject", semester="1", group_code="A",
        academic_period="I/2027", designation_type="regular",
        schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "08:45", "horas_academicas": 1}],
        monthly_hours=4, weekly_hours=1,
    ))
    db_session.flush()
    data = _simulate(client, draft["id"], effective_from="2027-03-15").json()
    # Legacy keeps Mondays 1 and 8; the publication pays 15, 22 and 29.
    assert [(t["teacher_ci"], t["hours_before"], t["hours_after"]) for t in data["teachers"]] == [
        ("PUB-LEG", 4, 2), ("PUB-T1", 0, 3),
    ]


def test_simulation_validates_input(client, db_session):
    _program, _subject, _offering, _group, _room, draft, _block, _teacher = _seed(client, db_session)
    assert _simulate(client, 999999).status_code == 404
    assert _simulate(client, draft["id"], month=13).status_code == 422


def test_simulation_rejects_a_draft_that_is_not_editable(client, db_session):
    _rates(db_session)
    _program, _subject, _offering, _group, _room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    db_session.get(AcademicScheduleDraft, draft["id"]).status = "published"
    db_session.flush()
    response = _simulate(client, draft["id"])
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Solo se puede simular un borrador editable."
