"""Generate a period's subject offerings from the curriculum (student-portal S12)."""
from __future__ import annotations

import pytest

from app.models.academic_management import SubjectOffering
from app.models.activity_log import ActivityLog

BASE = "/api/admin/academic-records"


@pytest.fixture
def plan(client):
    return client.post(f"{BASE}/curricula/default/load").json()


def _offerings(db_session, period):
    return {(o.subject.code, o.semester, o.theory_hours, o.practice_hours)
            for o in db_session.query(SubjectOffering).filter_by(academic_period=period)}


def test_offerings_come_from_the_curriculum_and_skip_electives(client, db_session, plan):
    slots = [slot for s in plan["semesters"] for slot in s["subjects"]]
    coded = [slot for slot in slots if slot["code"]]

    response = client.post(f"{BASE}/curricula/{plan['id']}/offerings", json={"academic_period": "I/2027"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["academic_period"], len(body["created"]), body["existing"]) == ("I/2027", len(coded), [])
    assert sorted(item["name"] for item in body["skipped"]) == ["Electiva 2", "Electiva 3", "Electiva 4", "Electiva I"]
    assert {item["reason"] for item in body["skipped"]} == {"Electiva sin materia asignada"}
    first = next(slot for slot in coded if slot["code"] == "MRF 0100")
    assert ("MRF 0100", 1, first["theory_hours"], first["practice_hours"]) in _offerings(db_session, "I/2027")
    log = db_session.query(ActivityLog).filter(ActivityLog.action == "generate_offerings_from_curriculum").one()
    assert log.details["created"] == len(coded)


def test_generating_again_keeps_existing_offerings_and_their_manual_changes(client, db_session, plan):
    client.post(f"{BASE}/curricula/{plan['id']}/offerings", json={"academic_period": "I/2027"})
    edited = db_session.query(SubjectOffering).filter_by(academic_period="I/2027").first()
    edited.theory_hours = 99
    db_session.flush()
    before = db_session.query(SubjectOffering).count()

    again = client.post(f"{BASE}/curricula/{plan['id']}/offerings", json={"academic_period": "I/2027"}).json()

    assert again["created"] == []
    assert len(again["existing"]) == before
    assert db_session.query(SubjectOffering).count() == before
    db_session.refresh(edited)
    assert edited.theory_hours == 99


def test_the_period_must_be_valid(client, plan):
    response = client.post(f"{BASE}/curricula/{plan['id']}/offerings", json={"academic_period": "2027-1"})
    assert response.status_code == 422


def test_generating_offerings_is_admin_only(client, db_session):
    from tests.test_academic_records_api import test_student_data_is_admin_only

    test_student_data_is_admin_only(client, db_session, "post", "/curricula/1/offerings")
