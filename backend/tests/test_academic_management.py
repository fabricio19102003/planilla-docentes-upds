from __future__ import annotations

from app.models.activity_log import ActivityLog
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service

BASE = "/api/admin/academic-management"


def _program(client, code="sis"):
    response = client.post(f"{BASE}/programs", json={"code": code, "name": "Ingeniería de Sistemas"})
    assert response.status_code == 201, response.text
    return response.json()


def _subject(client, code="mat-101"):
    response = client.post(f"{BASE}/subjects", json={"code": code, "name": "Matemática I"})
    assert response.status_code == 201, response.text
    return response.json()


def test_catalog_crud_normalized_uniqueness_and_deactivation_guards(client, db_session):
    program = _program(client)
    assert program["code"] == "SIS"
    assert client.post(f"{BASE}/programs", json={"code": "  sis ", "name": "Duplicado"}).status_code == 409

    updated = client.put(
        f"{BASE}/programs/{program['id']}", json={"code": "sis", "name": "Sistemas Actualizado"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Sistemas Actualizado"

    subject = _subject(client)
    offering = client.post(
        f"{BASE}/offerings",
        json={
            "subject_id": subject["id"], "program_id": program["id"],
            "academic_period": "II/2026", "semester": 1, "theory_hours": 4, "practice_hours": 0,
        },
    )
    assert offering.status_code == 201, offering.text
    assert client.post(f"{BASE}/programs/{program['id']}/deactivate").status_code == 409
    assert client.post(f"{BASE}/subjects/{subject['id']}/deactivate").status_code == 409

    assert client.post(f"{BASE}/offerings/{offering.json()['id']}/deactivate").status_code == 200
    assert client.post(f"{BASE}/subjects/{subject['id']}/deactivate").json()["active"] is False
    actions = {row.action for row in db_session.query(ActivityLog).filter(ActivityLog.category == "academic_management")}
    assert {"create_academic_program", "update_academic_program", "deactivate_academic_subject"}.issubset(actions)


def test_offering_hour_rules_and_group_identity(client):
    program = _program(client, "med")
    subject = _subject(client, "bio-101")
    invalid = client.post(
        f"{BASE}/offerings",
        json={
            "subject_id": subject["id"], "program_id": program["id"],
            "academic_period": "II/2026", "semester": 1, "theory_hours": 0, "practice_hours": 0,
        },
    )
    assert invalid.status_code == 422
    assert "al menos una hora" in invalid.text

    group = {
        "program_id": program["id"], "academic_period": "II/2026", "semester": 2,
        "shift": "Noche", "code": " n-1 ", "expected_size": 30,
    }
    created = client.post(f"{BASE}/groups", json=group)
    assert created.status_code == 201
    assert created.json()["code"] == "N-1"
    duplicate = client.post(f"{BASE}/groups", json={**group, "shift": "Mañana", "code": "N-1"})
    assert duplicate.status_code == 409
    other_period = client.post(f"{BASE}/groups", json={**group, "academic_period": "I/2027"})
    assert other_period.status_code == 201


def test_classroom_validation_resource_normalization_and_deactivation(client):
    invalid = client.post(
        f"{BASE}/classrooms",
        json={"code": "L-1", "name": "Laboratorio", "campus": "Central", "capacity": 0,
              "classroom_type": "laboratory", "resources": []},
    )
    assert invalid.status_code == 422

    created = client.post(
        f"{BASE}/classrooms",
        json={"code": " lab-1 ", "name": "Laboratorio 1", "campus": "Central", "capacity": 25,
              "classroom_type": "laboratory", "resources": [" Proyector ", "proyector", "Pizarra"]},
    )
    assert created.status_code == 201, created.text
    assert created.json()["resources"] == ["proyector", "pizarra"]
    assert client.post(f"{BASE}/classrooms/{created.json()['id']}/deactivate").json()["active"] is False


def test_availability_overlap_adjacency_period_scope_and_compatibility(client, db_session):
    for ci, name in (("AVAIL-1", "Docente Uno"), ("AVAIL-2", "Docente Dos")):
        db_session.add(Teacher(ci=ci, full_name=name))
    db_session.flush()

    first = {
        "teacher_ci": "AVAIL-1", "academic_period": "II/2026", "weekday": "monday",
        "start_time": "08:00", "end_time": "10:00",
    }
    created = client.post(f"{BASE}/availability", json=first)
    assert created.status_code == 201
    first_id = created.json()["id"]
    self_update = client.put(f"{BASE}/availability/{first_id}", json=first)
    assert self_update.status_code == 200, self_update.text
    overlap = client.post(f"{BASE}/availability", json={**first, "start_time": "09:00", "end_time": "11:00"})
    assert overlap.status_code == 409
    assert "superpone" in overlap.json()["detail"]
    assert client.post(f"{BASE}/availability", json={**first, "start_time": "10:00", "end_time": "11:00"}).status_code == 201
    assert client.post(f"{BASE}/availability", json={**first, "academic_period": "I/2027"}).status_code == 201

    assert client.post(f"{BASE}/availability/{first_id}/deactivate").status_code == 200
    recreated = client.post(f"{BASE}/availability", json=first)
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["id"] != first_id

    assert client.post(
        f"{BASE}/availability",
        json={**first, "teacher_ci": "AVAIL-2", "start_time": "07:00", "end_time": "12:00"},
    ).status_code == 201
    compatible = client.get(
        f"{BASE}/availability/compatible-teachers",
        params={"academic_period": "II/2026", "weekday": "monday", "start_time": "08:30", "end_time": "09:30"},
    )
    assert compatible.status_code == 200, compatible.text
    assert [item["ci"] for item in compatible.json()] == ["AVAIL-2", "AVAIL-1"]

    listed = client.get(f"{BASE}/availability", params={"teacher_ci": "AVAIL-1", "academic_period": "II/2026"})
    assert listed.status_code == 200
    assert len(listed.json()) == 3
    assert sum(item["active"] for item in listed.json()) == 2


def test_availability_rejects_timezone_aware_and_mixed_times_with_422(client, db_session):
    db_session.add(Teacher(ci="AVAIL-TZ", full_name="Docente Zona Horaria"))
    db_session.flush()
    base = {
        "teacher_ci": "AVAIL-TZ", "academic_period": "II/2026", "weekday": "tuesday",
    }
    for payload in (
        {**base, "start_time": "08:00:00+01:00", "end_time": "10:00:00"},
        {**base, "start_time": "08:00:00+01:00", "end_time": "10:00:00+01:00"},
    ):
        response = client.post(f"{BASE}/availability", json=payload)
        assert response.status_code == 422, response.text
        assert "zona horaria" in response.text

    compatibility = client.get(
        f"{BASE}/availability/compatible-teachers",
        params={
            "academic_period": "II/2026", "weekday": "tuesday",
            "start_time": "08:00:00+01:00", "end_time": "10:00:00",
        },
    )
    assert compatibility.status_code == 422, compatibility.text


def test_admin_authorization_required(client, db_session):
    authorization = client.headers.pop("Authorization")
    try:
        response = client.get(f"{BASE}/programs")
    finally:
        client.headers["Authorization"] = authorization
    assert response.status_code in (401, 403)

    docente = User(
        ci="ACADEMIC-DOCENTE", full_name="Docente sin permisos",
        password_hash=auth_service.hash_password("testpass123"), role="docente", is_active=True,
    )
    db_session.add(docente)
    db_session.flush()
    docente_token = auth_service.create_access_token(data={"sub": str(docente.id), "role": "docente"})
    client.headers["Authorization"] = f"Bearer {docente_token}"
    try:
        assert client.get(f"{BASE}/programs").status_code == 403
    finally:
        client.headers["Authorization"] = authorization


def _schedule_fixture(client, *, theory_hours=4, practice_hours=2, expected_size=25, capacity=30):
    program = _program(client, "arq")
    subject = _subject(client, "dis-101")
    offering = client.post(f"{BASE}/offerings", json={
        "subject_id": subject["id"], "program_id": program["id"],
        "academic_period": "II/2026", "semester": 1,
        "theory_hours": theory_hours, "practice_hours": practice_hours,
    }).json()
    group = client.post(f"{BASE}/groups", json={
        "program_id": program["id"], "academic_period": "II/2026", "semester": 1,
        "shift": "Mañana", "code": "A", "expected_size": expected_size,
    }).json()
    classroom_response = client.post(f"{BASE}/classrooms", json={
        "code": "A-101", "name": "Aula 101", "campus": "Central", "capacity": capacity,
        "classroom_type": "classroom", "resources": [],
    })
    assert classroom_response.status_code == 201, classroom_response.text
    classroom = classroom_response.json()
    draft_response = client.post(f"{BASE}/schedule-drafts", json={
        "program_id": program["id"], "academic_period": "II/2026", "name": "Horario base",
    })
    assert draft_response.status_code == 201, draft_response.text
    return program, offering, group, classroom, draft_response.json()


def test_schedule_draft_normalized_active_name_and_archive_immutability(client):
    program, _offering, _group, _classroom, draft = _schedule_fixture(client)
    duplicate = client.post(f"{BASE}/schedule-drafts", json={
        "program_id": program["id"], "academic_period": "II/2026", "name": "  HORARIO   BASE ",
    })
    assert duplicate.status_code == 409

    archived = client.post(f"{BASE}/schedule-drafts/{draft['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert client.put(f"{BASE}/schedule-drafts/{draft['id']}", json={
        "program_id": program["id"], "academic_period": "II/2026", "name": "Otro",
    }).status_code == 409
    replacement = client.post(f"{BASE}/schedule-drafts", json={
        "program_id": program["id"], "academic_period": "II/2026", "name": "HORARIO BASE",
    })
    assert replacement.status_code == 201, replacement.text


def test_schedule_blocks_validate_grid_scope_capacity_hours_and_overlap(client):
    _program, offering, group, classroom, draft = _schedule_fixture(client)
    base = {
        "offering_id": offering["id"], "group_id": group["id"], "classroom_id": classroom["id"],
        "activity_type": "theory", "weekday": "monday", "start_time": "07:00", "end_time": "09:00",
    }
    created = client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json=base)
    assert created.status_code == 201, created.text

    adjacent = client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json={
        **base, "start_time": "09:00", "end_time": "11:00",
    })
    assert adjacent.status_code == 201, adjacent.text
    assert client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json={
        **base, "start_time": "08:30", "end_time": "09:30",
    }).status_code == 409
    assert client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json={
        **base, "weekday": "tuesday", "start_time": "07:15", "end_time": "08:15",
    }).status_code == 422
    assert client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json={
        **base, "weekday": "tuesday", "start_time": "21:30", "end_time": "22:30",
    }).status_code == 422
    assert client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json={
        **base, "weekday": "tuesday", "start_time": "07:00", "end_time": "07:30",
    }).status_code == 409

    listed = client.get(f"{BASE}/schedule-drafts/{draft['id']}/blocks")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
    assert client.delete(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{created.json()['id']}"
    ).status_code == 204


def test_schedule_blocks_reject_insufficient_capacity_and_archived_edits(client):
    _program, offering, group, classroom, draft = _schedule_fixture(
        client, expected_size=40, capacity=30
    )
    payload = {
        "offering_id": offering["id"], "group_id": group["id"], "classroom_id": classroom["id"],
        "activity_type": "practice", "weekday": "friday", "start_time": "10:00", "end_time": "11:00",
    }
    response = client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json=payload)
    assert response.status_code == 409
    assert "capacidad" in response.json()["detail"]
    assert client.post(f"{BASE}/schedule-drafts/{draft['id']}/archive").status_code == 200
    assert client.post(f"{BASE}/schedule-drafts/{draft['id']}/blocks", json=payload).status_code == 409
