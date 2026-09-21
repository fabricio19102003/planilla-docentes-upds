from __future__ import annotations

from datetime import date

from app.models.activity_log import ActivityLog
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service


BASE = "/api/admin/academic-management"


def _post(client, path, payload):
    response = client.post(f"{BASE}{path}", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _seed_catalog(client):
    program = _post(client, "/programs", {"code": "LAW", "name": "Derecho"})
    subject = _post(client, "/subjects", {"code": "LAW-101", "name": "Derecho I"})
    offering = _post(client, "/offerings", {
        "subject_id": subject["id"], "program_id": program["id"],
        "academic_period": "II/2026", "semester": 1,
        "theory_hours": 10, "practice_hours": 10,
    })
    group_a = _post(client, "/groups", {
        "program_id": program["id"], "academic_period": "II/2026", "semester": 1,
        "shift": "Mañana", "code": "A", "expected_size": 20,
    })
    group_b = _post(client, "/groups", {
        "program_id": program["id"], "academic_period": "II/2026", "semester": 1,
        "shift": "Mañana", "code": "B", "expected_size": 20,
    })
    room_a = _post(client, "/classrooms", {
        "code": "LAW-A", "name": "Aula A", "campus": "Central", "capacity": 30,
        "classroom_type": "classroom", "resources": [],
    })
    room_b = _post(client, "/classrooms", {
        "code": "LAW-B", "name": "Aula B", "campus": "Central", "capacity": 30,
        "classroom_type": "classroom", "resources": [],
    })
    draft = _post(client, "/schedule-drafts", {
        "program_id": program["id"], "academic_period": "II/2026", "name": "Principal",
    })
    return program, offering, group_a, group_b, room_a, room_b, draft


def _block(client, draft, offering, group, room, *, activity="theory", start="08:00", end="09:00"):
    return _post(client, f"/schedule-drafts/{draft['id']}/blocks", {
        "offering_id": offering["id"], "group_id": group["id"], "classroom_id": room["id"],
        "activity_type": activity, "weekday": "monday", "start_time": start, "end_time": end,
    })


def _teacher(db_session, client, ci, name, *, start="07:00", end="12:00"):
    db_session.add(Teacher(ci=ci, full_name=name))
    db_session.flush()
    response = client.post(f"{BASE}/availability", json={
        "teacher_ci": ci, "academic_period": "II/2026", "weekday": "monday",
        "start_time": start, "end_time": end,
    })
    assert response.status_code == 201, response.text


def _assign(client, draft_id, block_id, teacher_ci, start="2026-01-01", end=None):
    payload = {"teacher_ci": teacher_ci, "effective_from": start, "effective_to": end}
    return client.post(
        f"{BASE}/schedule-drafts/{draft_id}/blocks/{block_id}/assignments", json=payload
    )


def test_initial_assignment_replacement_cutover_and_history(client, db_session):
    _program, offering, group_a, _group_b, room_a, _room_b, draft = _seed_catalog(client)
    block = _block(client, draft, offering, group_a, room_a)
    _teacher(db_session, client, "ASSIGN-1", "Docente Inicial")
    _teacher(db_session, client, "ASSIGN-2", "Docente Reemplazo")

    initial = _assign(client, draft["id"], block["id"], "ASSIGN-1")
    assert initial.status_code == 201, initial.text
    unchanged = client.post(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments/replace",
        json={"teacher_ci": "ASSIGN-1", "effective_from": "2026-02-01", "effective_to": None},
    )
    assert unchanged.status_code == 409
    assert "ya es el docente vigente" in unchanged.json()["detail"]
    replaced = client.post(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments/replace",
        json={"teacher_ci": "ASSIGN-2", "effective_from": "2026-02-01", "effective_to": None},
    )
    assert replaced.status_code == 201, replaced.text
    history = client.get(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments"
    ).json()
    assert [(item["teacher_ci"], item["effective_from"], item["effective_to"]) for item in history] == [
        ("ASSIGN-2", "2026-02-01", None),
        ("ASSIGN-1", "2026-01-01", "2026-01-31"),
    ]
    same_start = client.post(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments/replace",
        json={"teacher_ci": "ASSIGN-1", "effective_from": "2026-02-01", "effective_to": None},
    )
    assert same_start.status_code == 409
    assert "corrija o elimine" in same_start.json()["detail"]
    assert db_session.query(ActivityLog).filter(
        ActivityLog.action == "replace_academic_schedule_assignment"
    ).count() == 1


def test_overlapping_assignment_and_availability_coverage(client, db_session):
    _program, offering, group_a, _group_b, room_a, _room_b, draft = _seed_catalog(client)
    block = _block(client, draft, offering, group_a, room_a)
    db_session.add(Teacher(ci="NO-AVAIL", full_name="Sin disponibilidad"))
    db_session.flush()
    missing = _assign(client, draft["id"], block["id"], "NO-AVAIL")
    assert missing.status_code == 409
    assert "disponibilidad" in missing.json()["detail"]

    _teacher(db_session, client, "PARTIAL", "Disponibilidad parcial", start="08:30", end="10:00")
    partial = _assign(client, draft["id"], block["id"], "PARTIAL")
    assert partial.status_code == 409
    _teacher(db_session, client, "COVERED", "Disponibilidad completa")
    assert _assign(client, draft["id"], block["id"], "COVERED", end="2026-03-31").status_code == 201
    overlap = _assign(client, draft["id"], block["id"], "COVERED", start="2026-03-31")
    assert overlap.status_code == 409
    assert "intervalo efectivo" in overlap.json()["detail"]


def test_double_booking_adjacency_disjoint_dates_and_draft_isolation(client, db_session):
    program, offering, group_a, group_b, room_a, room_b, draft = _seed_catalog(client)
    first = _block(client, draft, offering, group_a, room_a)
    overlap = _block(client, draft, offering, group_b, room_b)
    adjacent = _block(client, draft, offering, group_a, room_a, start="09:00", end="10:00")
    _teacher(db_session, client, "BUSY-1", "Docente Ocupado")
    assert _assign(client, draft["id"], first["id"], "BUSY-1", end="2026-01-31").status_code == 201
    assert _assign(client, draft["id"], overlap["id"], "BUSY-1", end="2026-01-15").status_code == 409
    assert _assign(client, draft["id"], overlap["id"], "BUSY-1", start="2026-02-01").status_code == 201
    assert _assign(client, draft["id"], adjacent["id"], "BUSY-1", start="2026-01-01").status_code == 201

    alternative = _post(client, "/schedule-drafts", {
        "program_id": program["id"], "academic_period": "II/2026", "name": "Alternativa",
    })
    alternative_block = _block(client, alternative, offering, group_a, room_a)
    assert _assign(client, alternative["id"], alternative_block["id"], "BUSY-1").status_code == 201


def test_correction_removal_and_archived_draft_guards(client, db_session):
    _program, offering, group_a, _group_b, room_a, _room_b, draft = _seed_catalog(client)
    block = _block(client, draft, offering, group_a, room_a)
    _teacher(db_session, client, "CORRECT-1", "Docente Corrección")
    assignment = _assign(client, draft["id"], block["id"], "CORRECT-1").json()
    corrected = client.put(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments/{assignment['id']}",
        json={"effective_from": "2026-01-02", "effective_to": "2026-06-30"},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["teacher_ci"] == "CORRECT-1"
    protected_delete = client.delete(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}"
    )
    assert protected_delete.status_code == 409
    assert "historial de asignaciones" in protected_delete.json()["detail"]
    assert client.post(f"{BASE}/schedule-drafts/{draft['id']}/archive").status_code == 200
    assert client.delete(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments/{assignment['id']}"
    ).status_code == 409
    assert client.put(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments/{assignment['id']}",
        json={"effective_from": "2026-01-03", "effective_to": None},
    ).status_code == 409


def test_compatible_teacher_filter_search_pagination_and_workload(client, db_session):
    _program, offering, group_a, group_b, room_a, room_b, draft = _seed_catalog(client)
    theory = _block(client, draft, offering, group_a, room_a, start="08:00", end="09:30")
    conflicting = _block(client, draft, offering, group_b, room_b, start="08:30", end="09:30")
    practice = _block(
        client, draft, offering, group_a, room_a,
        activity="practice", start="09:30", end="10:30",
    )
    _teacher(db_session, client, "FILTER-1", "Ana Compatible")
    _teacher(db_session, client, "FILTER-2", "Beatriz Ocupada")
    db_session.add(Teacher(ci="FILTER-3", full_name="Carla Sin Horario"))
    db_session.flush()
    assert _assign(client, draft["id"], conflicting["id"], "FILTER-2").status_code == 201

    response = client.get(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{theory['id']}/compatible-teachers",
        params={"effective_from": "2026-01-01", "search": "Ana", "page": 1, "per_page": 1},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [{"ci": "FILTER-1", "full_name": "Ana Compatible"}],
        "total": 1, "page": 1, "per_page": 1,
    }
    assert _assign(client, draft["id"], theory["id"], "FILTER-1").status_code == 201
    already_assigned = client.get(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{theory['id']}/compatible-teachers",
        params={"effective_from": "2026-01-01", "search": "Ana"},
    )
    assert already_assigned.status_code == 200, already_assigned.text
    assert already_assigned.json()["items"] == []
    assert _assign(client, draft["id"], practice["id"], "FILTER-1").status_code == 201
    workload = client.get(
        f"{BASE}/schedule-drafts/{draft['id']}/workload",
        params={"reference_date": "2026-02-01"},
    )
    assert workload.status_code == 200, workload.text
    ana = next(item for item in workload.json()["items"] if item["teacher_ci"] == "FILTER-1")
    assert ana == {
        "teacher_ci": "FILTER-1", "teacher_name": "Ana Compatible",
        "theory_minutes_week": 90, "practice_minutes_week": 60,
        "total_minutes_week": 150,
    }


def test_assignment_endpoints_require_admin(client, db_session):
    _program, offering, group_a, _group_b, room_a, _room_b, draft = _seed_catalog(client)
    block = _block(client, draft, offering, group_a, room_a)
    docente = User(
        ci="ASSIGN-DOCENTE", full_name="Docente sin permisos",
        password_hash=auth_service.hash_password("testpass123"), role="docente", is_active=True,
    )
    db_session.add(docente)
    db_session.flush()
    original = client.headers["Authorization"]
    client.headers["Authorization"] = "Bearer " + auth_service.create_access_token(
        data={"sub": str(docente.id), "role": "docente"}
    )
    try:
        response = client.get(
            f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments"
        )
        assert response.status_code == 403
    finally:
        client.headers["Authorization"] = original
