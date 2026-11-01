from __future__ import annotations

from app.models.academic_management import AcademicProgram, AcademicSubject
from app.models.academic_records import CurriculumPlan, CurriculumSubject
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.services.auth_service import auth_service

BASE = "/api/admin/academic-records"


def _load(client):
    response = client.post(f"{BASE}/curricula/default/load")
    assert response.status_code == 200, response.text
    return response.json()


def test_loading_the_bundled_curriculum_creates_ten_semesters_with_electives(client, db_session):
    plan = _load(client)

    assert plan["code"] == "510-01"
    assert plan["name"] == "Medicina 510-01"
    assert plan["program_code"] == "MED 510-01"
    assert [semester["semester"] for semester in plan["semesters"]] == list(range(1, 11))
    first = plan["semesters"][0]["subjects"][0]
    assert first == {
        "id": first["id"], "subject_id": first["subject_id"], "code": "MRF 0100",
        "name": "Anatomía Humana I", "theory_hours": 51, "practice_hours": 51, "credits": 5,
        "is_elective": False,
    }
    slots = [subject for semester in plan["semesters"] for subject in semester["subjects"]]
    assert len(slots) == 80
    electives = sorted(slot["name"] for slot in slots if slot["is_elective"])
    assert electives == ["Electiva 2", "Electiva 3", "Electiva 4", "Electiva I"]
    assert all(slot["code"] is None and slot["subject_id"] is None for slot in slots if slot["is_elective"])
    guarani = next(slot for slot in slots if slot["code"] == "GUA 0900")
    assert guarani["credits"] == 2
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "load_curriculum").count() == 1


def test_loading_twice_is_idempotent_and_reuses_existing_catalog_rows(client, db_session):
    program = AcademicProgram(code="MED 510-01", name="Medicina", active=True)
    subject = AcademicSubject(code="MRF 0100", name="Anatomy I", active=True)
    db_session.add_all([program, subject])
    db_session.flush()

    first = _load(client)
    second = _load(client)

    assert first == second
    assert db_session.query(AcademicProgram).filter(AcademicProgram.code == "MED 510-01").count() == 1
    assert db_session.query(AcademicSubject).filter(AcademicSubject.code == "MRF 0100").count() == 1
    assert db_session.get(AcademicSubject, subject.id).name == "Anatomy I"
    assert first["semesters"][0]["subjects"][0]["subject_id"] == subject.id
    assert first["semesters"][0]["subjects"][0]["name"] == "Anatomía Humana I"
    assert db_session.query(CurriculumPlan).count() == 1
    assert db_session.query(CurriculumSubject).count() == 80


def test_curriculum_list_and_detail(client):
    plan = _load(client)

    listed = client.get(f"{BASE}/curricula")
    assert listed.status_code == 200
    assert listed.json() == [{
        "id": plan["id"], "code": "510-01", "name": "Medicina 510-01",
        "program_code": "MED 510-01", "total_semesters": 10, "subject_count": 80,
    }]
    assert client.get(f"{BASE}/curricula/{plan['id']}").json() == plan
    missing = client.get(f"{BASE}/curricula/999999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Plan de estudio no encontrado"


def test_curriculum_endpoints_are_admin_only(client, db_session):
    authorization = client.headers.pop("Authorization")
    try:
        assert client.get(f"{BASE}/curricula").status_code == 401
        docente = User(
            ci="RECORDS-DOCENTE", full_name="Docente sin permisos",
            password_hash=auth_service.hash_password("testpass123"), role="docente", is_active=True,
        )
        db_session.add(docente)
        db_session.flush()
        token = auth_service.create_access_token(data={"sub": str(docente.id), "role": "docente"})
        client.headers["Authorization"] = f"Bearer {token}"
        assert client.get(f"{BASE}/curricula").status_code == 403
        assert client.post(f"{BASE}/curricula/default/load").status_code == 403
        assert db_session.query(CurriculumPlan).count() == 0
    finally:
        client.headers["Authorization"] = authorization
