"""Flexible block times and editable academic hours (designation module v2, P1)."""
from __future__ import annotations

from datetime import date, time

import pytest

from app.models.academic_management import AcademicScheduleBlock, AcademicSchedulePublishedBlock
from app.models.app_setting import AppSetting
from app.models.teacher import Teacher
from app.services import academic_schedule_publication_service as pub
from app.services.effective_schedule_service import effective_schedule_slots
from app.services.planilla_generator import PlanillaGenerator
from tests.test_academic_management import BASE, _schedule_fixture


def _block(client, draft, offering, group, classroom, **overrides):
    payload = {
        "offering_id": offering["id"], "group_id": group["id"], "classroom_id": classroom["id"],
        "activity_type": "theory", "weekday": "monday", "start_time": "08:05", "end_time": "08:50",
        **overrides,
    }
    return client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json=payload)


def test_blocks_accept_any_five_minute_time_between_0600_and_2330(client):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    for start, end in (("06:00", "06:45"), ("08:05", "08:50"), ("09:50", "12:05"), ("22:00", "23:30")):
        response = _block(client, draft, offering, group, classroom, start_time=start, end_time=end)
        assert response.status_code == 201, (start, end, response.text)


def test_blocks_reject_times_outside_the_rules(client):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    cases = [
        ("05:55", "06:40", "El bloque debe estar entre las 06:00 y las 23:30."),
        ("23:00", "23:35", "El bloque debe estar entre las 06:00 y las 23:30."),
        ("08:03", "08:50", "Las horas deben usar intervalos de 5 minutos."),
        ("08:00", "08:10", "El bloque debe durar entre 15 minutos y 6 horas."),
        ("06:00", "12:05", "El bloque debe durar entre 15 minutos y 6 horas."),
    ]
    for start, end, message in cases:
        response = _block(client, draft, offering, group, classroom, start_time=start, end_time=end)
        assert response.status_code == 422, (start, end)
        assert response.json()["detail"] == message


def test_academic_hours_are_prefilled_from_the_duration_and_editable(client):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    forty_five = _block(client, draft, offering, group, classroom).json()
    ninety = _block(client, draft, offering, group, classroom, weekday="tuesday",
                    start_time="08:00", end_time="09:30").json()
    hundred = _block(client, draft, offering, group, classroom, weekday="wednesday",
                     start_time="10:35", end_time="12:15").json()
    edited = _block(client, draft, offering, group, classroom, weekday="thursday",
                    start_time="08:00", end_time="09:30", academic_hours=3).json()
    assert [forty_five["academic_hours"], ninety["academic_hours"], hundred["academic_hours"],
            edited["academic_hours"]] == [1, 2, 2, 3]
    updated = client.put(f"{BASE}/schedule-drafts/{draft['id']}/blocks/{ninety['id']}", json={
        "offering_id": offering["id"], "group_id": group["id"], "classroom_id": classroom["id"],
        "activity_type": "theory", "weekday": "tuesday", "start_time": "08:00", "end_time": "09:30",
        "academic_hours": 1,
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["academic_hours"] == 1


def test_academic_hours_must_be_between_one_and_twelve(client):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    for hours in (0, 13):
        assert _block(client, draft, offering, group, classroom, academic_hours=hours).status_code == 422


def test_academic_hour_length_is_configurable(client, db_session):
    db_session.add(AppSetting(key="ACADEMIC_HOUR_MINUTES", value="40", description="test"))
    db_session.commit()
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    block = _block(client, draft, offering, group, classroom, start_time="08:00", end_time="09:20").json()
    assert block["academic_hours"] == 2


def _publish_one(client, db_session, *, start="08:00", end="09:30", hours=None):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    db_session.add(Teacher(ci="HRS-T1", full_name="Hours Teacher"))
    db_session.flush()
    assert client.post(f"{BASE}/availability", json={
        "teacher_ci": "HRS-T1", "academic_period": "II/2026", "weekday": "monday",
        "start_time": "06:00", "end_time": "23:30",
    }).status_code == 201
    payload = {"start_time": start, "end_time": end}
    if hours is not None:
        payload["academic_hours"] = hours
    block = _block(client, draft, offering, group, classroom, **payload).json()
    assert client.post(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments",
        json={"teacher_ci": "HRS-T1", "effective_from": "2026-08-01", "effective_to": None},
    ).status_code == 201
    preview = client.post(f"{BASE}/schedule-drafts/{draft['id']}/publication-preview",
                          json={"effective_from": "2027-01-04"}).json()
    published = client.post(f"{BASE}/schedule-drafts/{draft['id']}/publish", json={
        "effective_from": "2027-01-04", "preview_digest": preview["digest"],
    })
    assert published.status_code == 201, published.text
    return published.json()


def test_published_blocks_keep_and_pay_their_academic_hours(client, db_session, monkeypatch):
    publication = _publish_one(client, db_session, hours=3)
    assert publication["blocks"][0]["academic_hours"] == 3
    slots = effective_schedule_slots(db_session, "II/2026", date(2027, 1, 4))
    assert [slot.academic_hours for slot in slots] == [3]
    monkeypatch.setattr("app.services.app_settings_service.get_active_academic_period", lambda _db: "II/2026")
    rows = PlanillaGenerator()._build_planilla_data(db_session, month=1, year=2027, discount_mode="full",
                                                   start_date=date(2027, 1, 4), end_date=date(2027, 1, 25))[0]
    # Mondays 4, 11, 18, 25 at 3 academic hours each.
    assert [(row.teacher_ci, row.payable_hours) for row in rows] == [("HRS-T1", 12)]


def test_blocks_without_stored_hours_keep_the_previous_rule(client, db_session):
    _publish_one(client, db_session, start="08:00", end="09:30", hours=2)
    published = db_session.query(AcademicSchedulePublishedBlock).one()
    published.academic_hours = None  # rows published before this change
    db_session.commit()
    slots = effective_schedule_slots(db_session, "II/2026", date(2027, 1, 4))
    assert [slot.academic_hours for slot in slots] == [2]  # max(1, 90 // 45)


def test_draft_blocks_without_stored_hours_report_the_previous_rule(client, db_session):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    block = _block(client, draft, offering, group, classroom, start_time="08:00", end_time="09:10").json()
    stored = db_session.get(AcademicScheduleBlock, block["id"])
    stored.academic_hours = None
    db_session.commit()
    listed = client.get(f"{BASE}/schedule-drafts/{draft['id']}/blocks").json()
    assert listed[0]["academic_hours"] is None
    assert listed[0]["paid_hours"] == 1  # max(1, 70 // 45)
    assert stored.start_time == time(8, 0)


def _put_same(client, draft, offering, group, classroom, block_id, **extra):
    return client.put(f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block_id}", json={
        "offering_id": offering["id"], "group_id": group["id"], "classroom_id": classroom["id"],
        "activity_type": "theory", "weekday": "monday", "start_time": "08:00", "end_time": "10:00", **extra})


def test_editing_a_block_without_stored_hours_keeps_its_pay(client, db_session):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    block = _block(client, draft, offering, group, classroom, start_time="08:00", end_time="10:00").json()
    stored = db_session.get(AcademicScheduleBlock, block["id"])
    stored.academic_hours = None  # e.g. cloned from a publication made before hours existed
    db_session.commit()
    edited = _put_same(client, draft, offering, group, classroom, block["id"])
    assert edited.status_code == 200, edited.text
    assert (edited.json()["academic_hours"], edited.json()["paid_hours"]) == (None, 2)


def test_editing_a_block_without_hours_keeps_manually_set_hours(client):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    block = _block(client, draft, offering, group, classroom, start_time="08:00", end_time="10:00",
                   academic_hours=5).json()
    edited = _put_same(client, draft, offering, group, classroom, block["id"])
    assert edited.json()["academic_hours"] == 5


@pytest.mark.parametrize("start,end,code", [
    ("06:00", "06:15", 201), ("23:15", "23:30", 201), ("07:00", "13:00", 201),
    ("07:00", "13:05", 422), ("06:00", "06:10", 422), ("05:55", "06:30", 422),
    ("23:20", "23:35", 422), ("07:12", "08:00", 422),
])
def test_block_rule_boundaries(client, start, end, code):
    _program, offering, group, classroom, draft = _schedule_fixture(client, theory_hours=10)
    assert _block(client, draft, offering, group, classroom, start_time=start, end_time=end).status_code == code


def test_publication_digest_omits_hours_for_blocks_without_them(client, db_session):
    _publish_one(client, db_session, hours=2)
    published = db_session.query(AcademicSchedulePublishedBlock).one()
    assert pub._publication_block_dict(published)["academic_hours"] == 2
    published.academic_hours = None
    assert "academic_hours" not in pub._publication_block_dict(published)
