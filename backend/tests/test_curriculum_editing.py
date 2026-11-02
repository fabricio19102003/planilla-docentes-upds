"""Editing the current curriculum (student-portal S11): subjects, hours, moves, order, electives, semesters."""
from __future__ import annotations

import pytest

from app.models.academic_management import AcademicSubject
from app.models.academic_records import StudentSubjectRecord
from app.models.activity_log import ActivityLog
from tests.test_academic_history_import import _csv, _rows
from tests.test_academic_records_api import _apply

BASE = "/api/admin/academic-records"


@pytest.fixture
def plan(client):
    return client.post(f"{BASE}/curricula/default/load").json()


def _semester(plan, number):
    return next(s["subjects"] for s in plan["semesters"] if s["semester"] == number)


def _slot(plan, code):
    return next(slot for s in plan["semesters"] for slot in s["subjects"] if slot["code"] == code)


def _logs(db_session):
    return [log.details for log in db_session.query(ActivityLog).filter(ActivityLog.action == "update_curriculum")]


def test_add_a_subject_at_the_end_of_a_semester(client, db_session, plan):
    response = client.post(f"{BASE}/curricula/{plan['id']}/slots", json={
        "semester": 3, "name": "Bioética", "code": "BIO 0300", "theory_hours": 2, "practice_hours": 0,
        "credits": 2, "is_elective": False,
    })

    assert response.status_code == 201, response.text
    third = _semester(response.json(), 3)
    assert (third[-1]["code"], third[-1]["name"], third[-1]["credits"]) == ("BIO 0300", "Bioética", 2)
    assert len(third) == len(_semester(plan, 3)) + 1
    assert _logs(db_session)[-1]["change"] == "add_subject"
    assert _logs(db_session)[-1]["after"]["code"] == "BIO 0300"


@pytest.mark.parametrize("payload,status,detail", [
    ({"code": "BIO-300"}, 422, None),
    ({"code": "MRF 0100"}, 409, "MRF 0100 ya está en la malla"),
    ({"code": None}, 422, "Una materia que no es electiva necesita sigla"),
    ({"semester": 11}, 422, "La malla tiene 10 semestres"),
    ({"theory_hours": 0, "practice_hours": 0}, 422, "La materia necesita al menos una hora teórica o práctica"),
])
def test_invalid_subjects_are_refused_and_change_nothing(client, db_session, plan, payload, status, detail):
    body = {"semester": 3, "name": "Bioética", "code": "BIO 0300", "theory_hours": 2, "practice_hours": 0,
            "credits": 2, "is_elective": False, **payload}

    response = client.post(f"{BASE}/curricula/{plan['id']}/slots", json=body)

    assert response.status_code == status
    if detail:
        assert response.json()["detail"] == detail
    assert client.get(f"{BASE}/curricula/{plan['id']}").json() == plan
    assert _logs(db_session) == []


def test_edit_name_code_and_hours(client, db_session, plan):
    slot = _slot(plan, "INF 0310")

    response = client.put(f"{BASE}/curricula/{plan['id']}/slots/{slot['id']}", json={
        "semester": 3, "name": "Informática Médica", "code": "INF 0315", "theory_hours": 1, "practice_hours": 3,
        "credits": 3, "is_elective": False,
    })

    assert response.status_code == 200, response.text
    edited = _slot(response.json(), "INF 0315")
    assert (edited["id"], edited["name"], edited["theory_hours"], edited["practice_hours"], edited["credits"]) == (
        slot["id"], "Informática Médica", 1, 3, 3,
    )
    # Renaming here is an explicit decision, so the catalog subject follows it.
    assert db_session.query(AcademicSubject).filter_by(code="INF 0315").one().name == "Informática Médica"
    change = _logs(db_session)[-1]
    assert (change["change"], change["before"]["code"], change["after"]["code"]) == ("update_subject", "INF 0310", "INF 0315")
    duplicate = client.put(f"{BASE}/curricula/{plan['id']}/slots/{slot['id']}", json={
        "semester": 3, "name": "X", "code": "MRF 0100", "theory_hours": 1, "practice_hours": 0, "credits": 1,
        "is_elective": False,
    })
    assert (duplicate.status_code, duplicate.json()["detail"]) == (409, "MRF 0100 ya está en la malla")


def test_move_to_another_semester_and_reorder(client, plan):
    slot = _slot(plan, "LIN 0330")
    moved = client.put(f"{BASE}/curricula/{plan['id']}/slots/{slot['id']}", json={
        "semester": 4, "name": slot["name"], "code": "LIN 0330", "theory_hours": slot["theory_hours"],
        "practice_hours": slot["practice_hours"], "credits": slot["credits"], "is_elective": False,
    }).json()
    assert _semester(moved, 4)[-1]["code"] == "LIN 0330"
    assert "LIN 0330" not in [s["code"] for s in _semester(moved, 3)]

    ids = [s["id"] for s in _semester(moved, 3)]
    reordered = client.put(f"{BASE}/curricula/{plan['id']}/semesters/3/order", json={"slot_ids": ids[::-1]})
    assert reordered.status_code == 200, reordered.text
    assert [s["id"] for s in _semester(reordered.json(), 3)] == ids[::-1]
    partial = client.put(f"{BASE}/curricula/{plan['id']}/semesters/3/order", json={"slot_ids": ids[:-1]})
    assert (partial.status_code, partial.json()["detail"]) == (422, "El orden debe incluir todas las materias del semestre")


def test_remove_a_subject_keeps_the_students_history(client, db_session, plan):
    _apply(client, _csv(_rows()))
    records = db_session.query(StudentSubjectRecord).count()
    slot = _slot(plan, "LIN 0130")

    response = client.delete(f"{BASE}/curricula/{plan['id']}/slots/{slot['id']}")

    assert response.status_code == 200, response.text
    assert "LIN 0130" not in [s["code"] for s in _semester(response.json(), 1)]
    assert db_session.query(StudentSubjectRecord).count() == records
    assert _logs(db_session)[-1]["change"] == "remove_subject"


def test_electives_and_semesters(client, plan):
    elective = client.post(f"{BASE}/curricula/{plan['id']}/slots", json={
        "semester": 9, "name": "Electiva 5", "code": None, "theory_hours": 2, "practice_hours": 0, "credits": 2,
        "is_elective": True,
    })
    assert elective.status_code == 201, elective.text
    assert _semester(elective.json(), 9)[-1]["is_elective"] is True

    added = client.post(f"{BASE}/curricula/{plan['id']}/semesters")
    assert added.json()["total_semesters"] == 11
    assert _semester(added.json(), 11) == []
    not_last = client.delete(f"{BASE}/curricula/{plan['id']}/semesters/10")
    assert (not_last.status_code, not_last.json()["detail"]) == (
        409, "Solo se puede quitar el último semestre y tiene que estar vacío",
    )
    removed = client.delete(f"{BASE}/curricula/{plan['id']}/semesters/11")
    assert (removed.status_code, removed.json()["total_semesters"]) == (200, 10)


def test_an_import_after_editing_keeps_the_edits(client, plan):
    slot = _slot(plan, "INF 0310")
    client.put(f"{BASE}/curricula/{plan['id']}/slots/{slot['id']}", json={
        "semester": 3, "name": slot["name"], "code": "INF 0310", "theory_hours": 9, "practice_hours": 9,
        "credits": 9, "is_elective": False,
    })
    client.delete(f"{BASE}/curricula/{plan['id']}/slots/{_slot(plan, 'LIN 0130')['id']}")

    _apply(client, _csv(_rows()))
    client.post(f"{BASE}/curricula/default/load")

    after = client.get(f"{BASE}/curricula/{plan['id']}").json()
    assert _slot(after, "INF 0310")["theory_hours"] == 9
    assert "LIN 0130" not in [s["code"] for s in _semester(after, 1)]


@pytest.mark.parametrize("method,path", [
    ("post", "/curricula/1/slots"), ("put", "/curricula/1/slots/1"), ("delete", "/curricula/1/slots/1"),
    ("put", "/curricula/1/semesters/1/order"), ("post", "/curricula/1/semesters"),
    ("delete", "/curricula/1/semesters/10"),
])
def test_curriculum_editing_is_admin_only(client, db_session, method, path):
    from tests.test_academic_records_api import test_student_data_is_admin_only

    test_student_data_is_admin_only(client, db_session, method, path)
