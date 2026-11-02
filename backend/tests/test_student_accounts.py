"""Student accounts: temporary passwords from staff, student login and isolated student auth (S1)."""
from __future__ import annotations

import hashlib

import pytest

from app.models.activity_log import ActivityLog
from app.models.user import User
from app.services.auth_service import auth_service
from tests.test_academic_history_import import _csv, _rows
from tests.test_academic_records_api import _apply

ADMIN = "/api/admin/academic-records"
PORTAL = "/api/student-portal"
RAIMUNDA_DOC = "I-11626046"
CARLOS_DOC = "7485000"


@pytest.fixture
def students(client, db_session):
    _apply(client, _csv(_rows()))
    found = client.get(f"{ADMIN}/students").json()["items"]
    return {row["document_number"]: row["id"] for row in found}


def _issue(client, student_id):
    response = client.post(f"{ADMIN}/students/{student_id}/account/temporary-password")
    assert response.status_code == 200, response.text
    return response.json()["temporary_password"]


def _login(client, document, password):
    authorization = client.headers.pop("Authorization", None)
    try:
        return client.post(f"{PORTAL}/auth/login", json={"document_number": document, "password": password})
    finally:
        if authorization:
            client.headers["Authorization"] = authorization


def _as(token):
    return {"Authorization": f"Bearer {token}"}


def test_staff_issue_a_temporary_password_the_student_must_change(client, db_session, students):
    response = client.post(f"{ADMIN}/students/{students[RAIMUNDA_DOC]}/account/temporary-password")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["document_number"], body["full_name"]) == (RAIMUNDA_DOC, "Raimunda Jaisa Paiva Da Silva")
    password = body["temporary_password"]
    assert len(password) >= 10
    account = client.get(f"{ADMIN}/students/{students[RAIMUNDA_DOC]}").json()["account"]
    assert (account["is_active"], account["must_change_password"]) == (True, True)
    log = db_session.query(ActivityLog).filter(ActivityLog.action == "issue_student_temporary_password").one()
    assert password not in str(log.details) and password not in log.description

    login = _login(client, RAIMUNDA_DOC, password)
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert login.json()["must_change_password"] is True
    assert client.get(f"{PORTAL}/me", headers=_as(token)).json()["document_number"] == RAIMUNDA_DOC
    blocked = client.get(f"{PORTAL}/history", headers=_as(token))
    assert (blocked.status_code, blocked.json()["detail"]) == (403, "Debe cambiar su contraseña antes de continuar")

    weak = client.put(f"{PORTAL}/auth/change-password", headers=_as(token),
                      json={"current_password": password, "new_password": "corta"})
    assert weak.status_code == 422
    changed = client.put(f"{PORTAL}/auth/change-password", headers=_as(token),
                         json={"current_password": password, "new_password": "NuevaClave2026"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["must_change_password"] is False
    history = client.get(f"{PORTAL}/history", headers=_as(changed.json()["access_token"]))
    assert history.status_code == 200
    assert [entry["term"]["code"] for entry in history.json()["history"]] == ["INV/2024", "I/2023"]
    assert _login(client, RAIMUNDA_DOC, password).status_code == 401
    assert _login(client, RAIMUNDA_DOC, "NuevaClave2026").json()["must_change_password"] is False


def test_failed_logins_share_one_message_and_disabled_accounts_are_refused(client, students):
    password = _issue(client, students[RAIMUNDA_DOC])

    for document, attempt in ((RAIMUNDA_DOC, "incorrecta"), ("NO-EXISTE", password), (CARLOS_DOC, password)):
        response = _login(client, document, attempt)
        assert (response.status_code, response.json()["detail"]) == (401, "Documento o contraseña incorrectos")

    token = _login(client, RAIMUNDA_DOC, password).json()["access_token"]
    assert client.post(f"{ADMIN}/students/{students[RAIMUNDA_DOC]}/account/disable").status_code == 200
    disabled = _login(client, RAIMUNDA_DOC, password)
    assert (disabled.status_code, disabled.json()["detail"]) == (
        403, "Tu cuenta está deshabilitada. Acercate a Registro para habilitarla.",
    )
    assert client.get(f"{PORTAL}/me", headers=_as(token)).status_code == 401
    assert client.post(f"{ADMIN}/students/{students[RAIMUNDA_DOC]}/account/enable").status_code == 200
    assert _login(client, RAIMUNDA_DOC, password).status_code == 200


def test_a_new_temporary_password_ends_existing_sessions(client, students):
    first = _issue(client, students[RAIMUNDA_DOC])
    token = _login(client, RAIMUNDA_DOC, first).json()["access_token"]

    second = _issue(client, students[RAIMUNDA_DOC])

    assert client.get(f"{PORTAL}/me", headers=_as(token)).status_code == 401
    assert _login(client, RAIMUNDA_DOC, first).status_code == 401
    assert _login(client, RAIMUNDA_DOC, second).status_code == 200


def test_bulk_temporary_passwords(client, students):
    ids = [students[RAIMUNDA_DOC], students[CARLOS_DOC]]

    response = client.post(f"{ADMIN}/student-accounts/temporary-passwords", json={"student_ids": ids})

    assert response.status_code == 200, response.text
    credentials = response.json()["credentials"]
    assert [c["document_number"] for c in credentials] == [RAIMUNDA_DOC, CARLOS_DOC]
    for credential in credentials:
        assert _login(client, credential["document_number"], credential["temporary_password"]).status_code == 200
    unknown = client.post(f"{ADMIN}/student-accounts/temporary-passwords", json={"student_ids": [999999]})
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "Estudiantes no encontrados: 999999")
    too_many = client.post(f"{ADMIN}/student-accounts/temporary-passwords", json={"student_ids": list(range(1, 102))})
    assert too_many.status_code == 422


def test_student_and_staff_tokens_never_cross(client, db_session, students):
    password = _issue(client, students[RAIMUNDA_DOC])
    login = _login(client, RAIMUNDA_DOC, password).json()
    changed = client.put(f"{PORTAL}/auth/change-password", headers=_as(login["access_token"]),
                         json={"current_password": password, "new_password": "NuevaClave2026"}).json()
    student_token = changed["access_token"]

    assert client.get(f"{ADMIN}/students", headers=_as(student_token)).status_code == 401
    assert client.get("/api/auth/me", headers=_as(student_token)).status_code == 401
    assert client.get("/api/portal/profile", headers=_as(student_token)).status_code == 401
    # A student token whose subject equals a staff user id must not act as that user.
    admin = db_session.query(User).filter(User.role == "admin").first()
    forged = auth_service.create_access_token({"sub": str(admin.id), "scope": "student", "ver": 0})
    assert client.get(f"{ADMIN}/students", headers=_as(forged)).status_code == 401
    # Staff tokens never open the student portal.
    assert client.get(f"{PORTAL}/me").status_code == 401
    docente = User(ci="PORTAL-DOCENTE", full_name="Docente", role="docente", is_active=True,
                   password_hash=auth_service.hash_password("testpass123"))
    db_session.add(docente)
    db_session.flush()
    docente_token = auth_service.create_access_token({"sub": str(docente.id), "role": "docente"})
    assert client.get(f"{PORTAL}/history", headers=_as(docente_token)).status_code == 401


@pytest.mark.parametrize("method,path", [
    ("post", "/students/1/account/temporary-password"), ("post", "/students/1/account/disable"),
    ("post", "/students/1/account/enable"), ("post", "/student-accounts/temporary-passwords"),
])
def test_account_management_is_admin_only(client, db_session, method, path):
    from tests.test_academic_records_api import test_student_data_is_admin_only

    test_student_data_is_admin_only(client, db_session, method, path)


def test_the_portal_requires_a_student_session(client):
    authorization = client.headers.pop("Authorization")
    try:
        for path in ("/me", "/history"):
            assert client.get(f"{PORTAL}{path}").status_code == 401
    finally:
        client.headers["Authorization"] = authorization
