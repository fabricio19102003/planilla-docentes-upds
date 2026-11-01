"""Re-enrollment windows, student requests with group capacity, and the staff inbox (S2, S4, S5, S7-S9)."""
from __future__ import annotations

from datetime import date

import pytest

from app.models.academic_management import AcademicGroup
from app.models.academic_records import CurriculumPlan
from app.models.activity_log import ActivityLog
from app.models.student_portal import ReenrollmentRequest
from app.services import reenrollment
from tests.test_reenrollment_eligibility import I_2026, _load
from tests.test_student_accounts import _as, _login

ADMIN = "/api/admin/reenrollment"
PORTAL = "/api/student-portal"
TODAY = date(2026, 12, 10)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(reenrollment, "bolivia_today", lambda: TODAY)


def _student_token(client, student):
    issued = client.post(f"/api/admin/academic-records/students/{student.id}/account/temporary-password").json()
    token = _login(client, student.document_number, issued["temporary_password"]).json()["access_token"]
    changed = client.put(f"{PORTAL}/auth/change-password", headers=_as(token),
                         json={"current_password": issued["temporary_password"], "new_password": "NuevaClave2026"})
    return changed.json()["access_token"]


def _group(db_session, semester, code, shift="M", capacity=None, period="I/2027"):
    plan = db_session.query(CurriculumPlan).one()
    group = AcademicGroup(program_id=plan.program_id, academic_period=period, semester=semester,
                          shift=shift, code=code, expected_size=capacity)
    db_session.add(group)
    db_session.flush()
    return group


def _window(client, starts="2026-12-01", ends="2026-12-20", term="I/2027"):
    response = client.post(f"{ADMIN}/windows", json={"term_code": term, "starts_on": starts, "ends_on": ends})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def world(client, db_session):
    good = _load(db_session, "GOOD-API", [
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
    ])
    failing = _load(db_session, "FAIL-API", [
        ("Inglés Técnico I LIN-0130", "Reprobado", 40, I_2026),
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
    ])
    groups = {
        "M-01": _group(db_session, 3, "M-01", capacity=1),
        "N-01": _group(db_session, 3, "N-01", shift="N"),
        "S1-M-01": _group(db_session, 1, "M-01"),
        "OLD": _group(db_session, 3, "M-09", period="II/2026"),
    }
    return {"good": good, "failing": failing, "groups": groups}


# ── Windows ──────────────────────────────────────────────────────────────────

def test_windows_are_created_validated_and_listed(client):
    window = _window(client)
    assert (window["term_code"], window["is_open"]) == ("I/2027", True)

    duplicate = client.post(f"{ADMIN}/windows", json={"term_code": "I/2027", "starts_on": "2027-01-01",
                                                       "ends_on": "2027-01-02"})
    assert (duplicate.status_code, duplicate.json()["detail"]) == (409, "Ya existe una ventana de rematrícula para I/2027")
    backwards = client.post(f"{ADMIN}/windows", json={"term_code": "II/2027", "starts_on": "2027-06-10",
                                                       "ends_on": "2027-06-01"})
    assert backwards.status_code == 422
    bad_term = client.post(f"{ADMIN}/windows", json={"term_code": "2027-1", "starts_on": "2027-06-01",
                                                      "ends_on": "2027-06-10"})
    assert bad_term.status_code == 422

    moved = client.put(f"{ADMIN}/windows/{window['id']}", json={"starts_on": "2026-12-11", "ends_on": "2026-12-20"})
    assert (moved.status_code, moved.json()["is_open"]) == (200, False)
    assert [w["term_code"] for w in client.get(f"{ADMIN}/windows").json()] == ["I/2027"]


def test_the_portal_shows_the_window_eligibility_and_groups(client, db_session, world):
    _window(client)
    token = _student_token(client, world["good"])

    body = client.get(f"{PORTAL}/reenrollment", headers=_as(token)).json()

    assert (body["window"]["term_code"], body["window"]["is_open"]) == ("I/2027", True)
    assert body["eligibility"]["target_semester"] == 3
    assert [(g["code"], g["capacity"], g["free"], g["is_full"]) for g in body["main_groups"]] == [
        ("M-01", 1, 1, False), ("N-01", None, None, False),
    ]
    assert body["request"] is None


def test_outside_the_window_the_portal_only_shows_status(client, world):
    _window(client, starts="2026-12-15", ends="2026-12-20")
    token = _student_token(client, world["good"])

    body = client.get(f"{PORTAL}/reenrollment", headers=_as(token)).json()
    assert body["window"]["is_open"] is False
    submit = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token),
                         json={"main_group_id": world["groups"]["M-01"].id, "items": []})
    assert (submit.status_code, submit.json()["detail"]) == (409, "La rematrícula no está abierta")


# ── Requests and capacity ────────────────────────────────────────────────────

def test_a_request_takes_a_place_and_a_full_group_is_blocked(client, db_session, world):
    _window(client)
    good, failing = _student_token(client, world["good"]), _student_token(client, world["failing"])
    m01 = world["groups"]["M-01"].id

    first = client.post(f"{PORTAL}/reenrollment/request", headers=_as(good), json={"main_group_id": m01, "items": []})
    assert first.status_code == 200, first.text
    assert (first.json()["status"], first.json()["main_group"]["code"]) == ("pendiente", "M-01")

    full = client.post(f"{PORTAL}/reenrollment/request", headers=_as(failing), json={"main_group_id": m01, "items": []})
    assert (full.status_code, full.json()["detail"]) == (409, "El grupo M-01 ya no tiene cupos")
    groups = client.get(f"{PORTAL}/reenrollment", headers=_as(failing)).json()["main_groups"]
    assert [(g["code"], g["free"], g["is_full"]) for g in groups] == [("M-01", 0, True), ("N-01", None, False)]
    # Editing one's own request does not count one's own place twice.
    again = client.post(f"{PORTAL}/reenrollment/request", headers=_as(good), json={"main_group_id": m01, "items": []})
    assert again.status_code == 200
    assert db_session.query(ReenrollmentRequest).count() == 1


def test_recursado_groups_amounts_and_validation(client, world):
    _window(client)
    token = _student_token(client, world["failing"])
    groups = world["groups"]

    wrong_semester = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token),
                                 json={"main_group_id": groups["S1-M-01"].id, "items": []})
    assert (wrong_semester.status_code, wrong_semester.json()["detail"]) == (
        422, "El grupo elegido no corresponde a tu semestre",
    )
    other_term = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token),
                             json={"main_group_id": groups["OLD"].id, "items": []})
    assert other_term.status_code == 422
    not_offered = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token), json={
        "main_group_id": groups["N-01"].id, "items": [{"subject_code": "MRF 0100", "group_id": groups["S1-M-01"].id}],
    })
    assert (not_offered.status_code, not_offered.json()["detail"]) == (422, "MRF 0100 no está entre tus materias a recursar")
    wrong_group = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token), json={
        "main_group_id": groups["N-01"].id, "items": [{"subject_code": "LIN 0130", "group_id": groups["N-01"].id}],
    })
    assert (wrong_group.status_code, wrong_group.json()["detail"]) == (
        422, "El grupo de LIN 0130 debe ser del semestre 1",
    )

    # Amounts follow the chosen recursado subjects, not every one offered.
    without = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token),
                          json={"main_group_id": groups["N-01"].id, "items": []})
    assert without.json()["snapshot"]["recursado_fee"] == {
        "per_subject": 1200, "subjects": 0, "charged_subjects": 0, "total": 0,
    }

    response = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token), json={
        "main_group_id": groups["N-01"].id, "items": [{"subject_code": "LIN 0130", "group_id": groups["S1-M-01"].id}],
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert [(i["kind"], i["subject_code"], i["semester"], i["group"]["code"]) for i in body["items"]] == [
        ("recursado", "LIN 0130", 1, "M-01"),
    ]
    assert body["snapshot"]["scholarship"]["category"] == "sin_beca"
    assert body["snapshot"]["recursado_fee"]["total"] == 1200


# ── Staff inbox ──────────────────────────────────────────────────────────────

def test_staff_observe_and_complete_requests_and_the_student_sees_it(client, db_session, world):
    _window(client)
    token = _student_token(client, world["failing"])
    request_id = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token), json={
        "main_group_id": world["groups"]["N-01"].id,
        "items": [{"subject_code": "LIN 0130", "group_id": world["groups"]["S1-M-01"].id}],
    }).json()["id"]

    inbox = client.get(f"{ADMIN}/requests", params={"status": "pendiente"}).json()
    assert [(r["id"], r["document_number"], r["main_group_code"], r["recursado_count"]) for r in inbox["items"]] == [
        (request_id, "FAIL-API", "N-01", 1),
    ]
    assert client.get(f"{ADMIN}/requests", params={"status": "realizada"}).json()["items"] == []
    detail = client.get(f"{ADMIN}/requests/{request_id}").json()
    assert detail["student"]["document_number"] == "FAIL-API"
    assert detail["items"][0]["subject_code"] == "LIN 0130"

    short = client.post(f"{ADMIN}/requests/{request_id}/observe", json={"reason": "pago_pendiente", "message": "x"})
    assert short.status_code == 422
    observed = client.post(f"{ADMIN}/requests/{request_id}/observe", json={
        "reason": "pago_pendiente", "message": "Falta el pago del recursado de Inglés Técnico I en caja.",
    })
    assert observed.status_code == 200, observed.text
    seen = client.get(f"{PORTAL}/reenrollment", headers=_as(token)).json()["request"]
    assert (seen["status"], seen["observation_reason"], seen["observation_message"]) == (
        "observada", "pago_pendiente", "Falta el pago del recursado de Inglés Técnico I en caja.",
    )

    # Fixing it in the portal sends it back to Pendiente without the old observation.
    resubmitted = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token), json={
        "main_group_id": world["groups"]["N-01"].id,
        "items": [{"subject_code": "LIN 0130", "group_id": world["groups"]["S1-M-01"].id}],
    }).json()
    assert (resubmitted["status"], resubmitted["observation_message"]) == ("pendiente", None)

    done = client.post(f"{ADMIN}/requests/{request_id}/complete")
    assert (done.status_code, done.json()["status"]) == (200, "realizada")
    locked = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token),
                         json={"main_group_id": world["groups"]["N-01"].id, "items": []})
    assert (locked.status_code, locked.json()["detail"]) == (409, "Tu rematrícula ya fue realizada")
    reopened = client.post(f"{ADMIN}/requests/{request_id}/reopen")
    assert reopened.json()["status"] == "pendiente"
    actions = [log.action for log in db_session.query(ActivityLog).filter(ActivityLog.category == "reenrollment")]
    assert actions == [
        "create_reenrollment_window", "submit_reenrollment_request", "observe_reenrollment_request",
        "submit_reenrollment_request", "complete_reenrollment_request", "reopen_reenrollment_request",
    ]


@pytest.mark.parametrize("method,path", [
    ("get", "/windows"), ("post", "/windows"), ("put", "/windows/1"), ("get", "/requests"),
    ("get", "/requests/1"), ("post", "/requests/1/complete"), ("post", "/requests/1/observe"),
    ("post", "/requests/1/reopen"),
])
def test_the_inbox_is_admin_only(client, db_session, method, path):
    from app.models.user import User
    from app.services.auth_service import auth_service

    authorization = client.headers.pop("Authorization")
    try:
        assert getattr(client, method)(f"{ADMIN}{path}").status_code == 401
        docente = User(ci="INBOX-DOCENTE", full_name="Docente", role="docente", is_active=True,
                       password_hash=auth_service.hash_password("testpass123"))
        db_session.add(docente)
        db_session.flush()
        client.headers["Authorization"] = "Bearer " + auth_service.create_access_token(
            {"sub": str(docente.id), "role": "docente"})
        assert getattr(client, method)(f"{ADMIN}{path}").status_code == 403
    finally:
        client.headers["Authorization"] = authorization


def test_a_student_token_never_opens_the_inbox(client, world):
    token = _student_token(client, world["good"])
    assert client.get(f"{ADMIN}/requests", headers=_as(token)).status_code == 401
