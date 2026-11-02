"""Migration documents of foreign students: catalog, records, regularizado and the re-enrollment block (phase 3 S5)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.activity_log import ActivityLog
from app.models.migration_documents import MigrationDocumentType, StudentMigrationDocument
from app.models.student_portal import ReenrollmentRequest
from app.services import migration_documents as service
from app.services import reenrollment
from tests.test_reenrollment_api import ADMIN as REENROLLMENT, _group, _student_token, _window
from tests.test_reenrollment_eligibility import I_2026, _load
from tests.test_student_accounts import _as

ADMIN = "/api/admin/migration-documents"
PORTAL = "/api/student-portal/migration-documents"
PORTAL_ROOT = "/api/student-portal"
TODAY = date(2026, 12, 10)
YESTERDAY = TODAY - timedelta(days=1)
BLOCKED = "Documentos migratorios pendientes: "


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(reenrollment, "bolivia_today", lambda: TODAY)


def _foreign(db_session, document="FOR-1"):
    student = _load(db_session, document, [
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
    ])
    student.is_foreign = True
    db_session.flush()
    return student


def _type(client, name, requires_expiry=False):
    response = client.post(f"{ADMIN}/types", json={"name": name, "requires_expiry": requires_expiry})
    assert response.status_code == 201, response.text
    return response.json()


def _record(client, student, type_id, expires_on=None, notes=None):
    return client.put(f"{ADMIN}/students/{student.id}/documents/{type_id}",
                      json={"expires_on": expires_on, "notes": notes})


@pytest.fixture
def types(client):
    return {
        "pasaporte": _type(client, "Pasaporte"),
        "visa": _type(client, "Visa", requires_expiry=True),
        "certificado": _type(client, "Certificado de nacimiento"),
    }


# ── Status rules ─────────────────────────────────────────────────────────────

def test_a_foreign_student_is_regularizado_only_with_every_active_document_valid(client, db_session, types):
    student = _foreign(db_session)

    empty = service.status(db_session, student, TODAY)
    assert (empty["applies"], empty["regularizado"]) == (True, False)
    assert empty["missing"] == ["Pasaporte", "Visa", "Certificado de nacimiento"]
    assert empty["expired"] == []

    assert _record(client, student, types["pasaporte"]["id"]).status_code == 200
    assert _record(client, student, types["certificado"]["id"]).status_code == 200
    # Expiring exactly today is still valid; the day after it is not.
    assert _record(client, student, types["visa"]["id"], TODAY.isoformat()).status_code == 200
    valid = service.status(db_session, student, TODAY)
    assert (valid["regularizado"], valid["missing"], valid["expired"]) == (True, [], [])
    tomorrow = service.status(db_session, student, TODAY + timedelta(days=1))
    assert (tomorrow["regularizado"], tomorrow["missing"], tomorrow["expired"]) == (
        False, [], [{"name": "Visa", "expires_on": TODAY}])

    assert _record(client, student, types["visa"]["id"], YESTERDAY.isoformat()).status_code == 200
    expired = service.status(db_session, student, TODAY)
    assert (expired["regularizado"], expired["expired"]) == (False, [{"name": "Visa", "expires_on": YESTERDAY}])
    assert [(d["name"], d["state"], d["expires_on"]) for d in expired["documents"]] == [
        ("Pasaporte", "present", None), ("Visa", "expired", YESTERDAY), ("Certificado de nacimiento", "present", None),
    ]


def test_a_document_that_needs_an_expiry_without_one_counts_as_missing(client, db_session, types):
    student = _foreign(db_session)
    db_session.add(StudentMigrationDocument(student_id=student.id, document_type_id=types["visa"]["id"]))
    db_session.flush()

    result = service.status(db_session, student, TODAY)

    assert "Visa" in result["missing"]
    assert [d["state"] for d in result["documents"]] == ["missing", "missing", "missing"]


def test_inactive_types_are_ignored(client, db_session, types):
    student = _foreign(db_session)
    for key in ("visa", "certificado"):
        assert client.post(f"{ADMIN}/types/{types[key]['id']}/deactivate").status_code == 200
    assert _record(client, student, types["pasaporte"]["id"]).status_code == 200

    result = service.status(db_session, student, TODAY)

    assert (result["regularizado"], result["missing"]) == (True, [])
    assert [d["name"] for d in result["documents"]] == ["Pasaporte"]


def test_students_who_are_not_foreign_never_need_documents(client, db_session, types):
    student = _foreign(db_session)
    student.is_foreign = False
    db_session.flush()

    result = service.status(db_session, student, TODAY)

    assert result["applies"] is False and result["regularizado"] is True
    assert (result["missing"], result["expired"], result["documents"]) == ([], [], [])


def test_without_active_types_everyone_is_regularizado(db_session):
    student = _foreign(db_session)

    result = service.status(db_session, student, TODAY)

    assert (result["applies"], result["regularizado"], result["documents"]) == (True, True, [])


# ── Catalog ──────────────────────────────────────────────────────────────────

def test_types_are_created_renamed_reordered_and_deactivated(client, db_session):
    first, second, third = _type(client, "Pasaporte"), _type(client, "Visa", True), _type(client, "Antecedentes")
    assert [first["position"], second["position"], third["position"]] == [0, 1, 2]
    assert (first["active"], first["requires_expiry"], second["requires_expiry"]) == (True, False, True)

    renamed = client.put(f"{ADMIN}/types/{first['id']}", json={"name": "  Pasaporte vigente ", "requires_expiry": True})
    assert (renamed.status_code, renamed.json()["name"], renamed.json()["requires_expiry"]) == (
        200, "Pasaporte vigente", True)

    moved = client.put(f"{ADMIN}/types/{third['id']}", json={"position": 0})
    assert moved.status_code == 200
    listed = client.get(f"{ADMIN}/types").json()
    assert [(t["name"], t["position"]) for t in listed] == [
        ("Antecedentes", 0), ("Pasaporte vigente", 1), ("Visa", 2)]

    deactivated = client.post(f"{ADMIN}/types/{second['id']}/deactivate")
    assert (deactivated.status_code, deactivated.json()["active"]) == (200, False)
    again = client.post(f"{ADMIN}/types/{second['id']}/deactivate")
    assert (again.status_code, again.json()["detail"]) == (409, "El tipo de documento ya está inactivo")
    # Deactivated types stay listed (with their documents) and can come back.
    assert [t["active"] for t in client.get(f"{ADMIN}/types").json()] == [True, True, False]
    back = client.put(f"{ADMIN}/types/{second['id']}", json={"active": True})
    assert back.json()["active"] is True
    assert db_session.query(MigrationDocumentType).count() == 3


def test_deactivating_keeps_the_documents_already_recorded(client, db_session, types):
    student = _foreign(db_session)
    assert _record(client, student, types["pasaporte"]["id"]).status_code == 200

    assert client.post(f"{ADMIN}/types/{types['pasaporte']['id']}/deactivate").status_code == 200

    assert db_session.query(StudentMigrationDocument).count() == 1


def test_type_validation_messages(client, types):
    cases = [
        ({"name": "   ", "requires_expiry": False}, 422, "El nombre del documento es obligatorio"),
        ({"name": "x" * 121, "requires_expiry": False}, 422, "El nombre del documento no puede superar los 120 caracteres"),
        ({"name": "pasaporte", "requires_expiry": False}, 409, "Ya existe un documento con ese nombre"),
    ]
    for body, status, detail in cases:
        response = client.post(f"{ADMIN}/types", json=body)
        assert (response.status_code, response.json()["detail"]) == (status, detail), body
    clash = client.put(f"{ADMIN}/types/{types['visa']['id']}", json={"name": "Pasaporte"})
    assert (clash.status_code, clash.json()["detail"]) == (409, "Ya existe un documento con ese nombre")
    same = client.put(f"{ADMIN}/types/{types['visa']['id']}", json={"name": "Visa"})
    assert same.status_code == 200
    assert client.put(f"{ADMIN}/types/9999", json={"name": "Otro"}).status_code == 404
    assert client.post(f"{ADMIN}/types/9999/deactivate").status_code == 404
    assert [t["name"] for t in client.get(f"{ADMIN}/types").json()] == [
        "Pasaporte", "Visa", "Certificado de nacimiento"]


# ── Student documents ────────────────────────────────────────────────────────

def test_documents_are_recorded_updated_and_removed(client, db_session, types):
    student = _foreign(db_session)
    visa = types["visa"]["id"]

    saved = _record(client, student, visa, "2027-03-01", "Trámite en curso")
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["applies"], body["regularizado"], body["missing"]) == (
        True, False, ["Pasaporte", "Certificado de nacimiento"])
    visa_row = next(d for d in body["documents"] if d["name"] == "Visa")
    assert (visa_row["state"], visa_row["expires_on"], visa_row["notes"]) == ("present", "2027-03-01", "Trámite en curso")

    # Saving again updates the single record of that type.
    assert _record(client, student, visa, "2028-03-01").status_code == 200
    assert db_session.query(StudentMigrationDocument).count() == 1
    assert client.get(f"{ADMIN}/students/{student.id}").json()["documents"][1]["expires_on"] == "2028-03-01"

    removed = client.delete(f"{ADMIN}/students/{student.id}/documents/{visa}")
    assert removed.status_code == 200
    assert "Visa" in removed.json()["missing"]
    assert db_session.query(StudentMigrationDocument).count() == 0
    again = client.delete(f"{ADMIN}/students/{student.id}/documents/{visa}")
    assert (again.status_code, again.json()["detail"]) == (404, "El estudiante no tiene ese documento registrado")


def test_a_document_that_does_not_expire_drops_a_given_expiry(client, db_session, types):
    student = _foreign(db_session)

    response = _record(client, student, types["pasaporte"]["id"], "2030-01-01")

    assert response.status_code == 200
    assert response.json()["documents"][0]["expires_on"] is None


def test_document_validation_messages(client, db_session, types):
    student = _foreign(db_session)
    visa = types["visa"]["id"]

    missing_expiry = _record(client, student, visa)
    assert (missing_expiry.status_code, missing_expiry.json()["detail"]) == (
        422, "La fecha de vencimiento es obligatoria para este documento")
    assert db_session.query(StudentMigrationDocument).count() == 0
    long_notes = _record(client, student, visa, "2027-01-01", "n" * 1001)
    assert long_notes.status_code == 422
    assert _record(client, student, 9999).status_code == 404
    assert _record(client, type("S", (), {"id": 9999}), visa, "2027-01-01").status_code == 404
    assert client.get(f"{ADMIN}/students/9999").status_code == 404

    client.post(f"{ADMIN}/types/{types['pasaporte']['id']}/deactivate")
    inactive = _record(client, student, types["pasaporte"]["id"])
    assert (inactive.status_code, inactive.json()["detail"]) == (409, "El tipo de documento está inactivo")

    student.is_foreign = False
    db_session.flush()
    not_foreign = _record(client, student, visa, "2027-01-01")
    assert (not_foreign.status_code, not_foreign.json()["detail"]) == (409, "El estudiante no es extranjero")
    assert client.delete(f"{ADMIN}/students/{student.id}/documents/{visa}").status_code == 409
    assert db_session.query(StudentMigrationDocument).count() == 0
    # Reading is allowed for anyone: the status just says it does not apply.
    assert client.get(f"{ADMIN}/students/{student.id}").json()["applies"] is False


# ── Re-enrollment ────────────────────────────────────────────────────────────

@pytest.fixture
def foreign_request(client, db_session, types):
    student = _foreign(db_session)
    group = _group(db_session, 3, "M-01")
    _window(client)
    token = _student_token(client, student)
    submitted = client.post(f"{PORTAL_ROOT}/reenrollment/request", headers=_as(token),
                            json={"main_group_id": group.id, "items": []})
    assert submitted.status_code == 200, submitted.text
    return {"student": student, "request_id": submitted.json()["id"], "token": token}


def _complete(client, request_id):
    return client.post(f"{REENROLLMENT}/requests/{request_id}/complete")


def test_a_foreign_student_without_documents_cannot_be_marked_realizada(client, db_session, types, foreign_request):
    student, request_id = foreign_request["student"], foreign_request["request_id"]
    assert _record(client, student, types["visa"]["id"], YESTERDAY.isoformat()).status_code == 200
    # Position order rules the message, whatever the kind of problem.
    assert client.put(f"{ADMIN}/types/{types['certificado']['id']}", json={"position": 0}).status_code == 200
    before = db_session.query(ReenrollmentRequest).get(request_id)
    handled = (before.status, before.handled_by, before.handled_at)
    logs = db_session.query(ActivityLog).filter(ActivityLog.category == "reenrollment").count()

    blocked = _complete(client, request_id)

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == (
        BLOCKED + "Certificado de nacimiento, Pasaporte, Visa (vencido el 09/12/2026)")
    db_session.expire_all()
    after = db_session.query(ReenrollmentRequest).get(request_id)
    assert (after.status, after.handled_by, after.handled_at) == handled == ("pendiente", None, None)
    assert db_session.query(ActivityLog).filter(ActivityLog.category == "reenrollment").count() == logs
    # Only "realizada" is guarded.
    observed = client.post(f"{REENROLLMENT}/requests/{request_id}/observe", json={
        "reason": "documentos_migracion", "message": "Falta presentar documentos migratorios."})
    assert observed.status_code == 200
    reopened = client.post(f"{REENROLLMENT}/requests/{request_id}/reopen")
    assert reopened.status_code == 200


def test_the_request_can_be_completed_once_the_student_is_regularizado(client, db_session, types, foreign_request):
    student, request_id = foreign_request["student"], foreign_request["request_id"]
    assert _complete(client, request_id).status_code == 409
    assert _record(client, student, types["pasaporte"]["id"]).status_code == 200
    assert _record(client, student, types["certificado"]["id"]).status_code == 200
    assert _record(client, student, types["visa"]["id"], TODAY.isoformat()).status_code == 200

    done = _complete(client, request_id)

    assert (done.status_code, done.json()["status"]) == (200, "realizada")


def test_students_who_are_not_foreign_complete_without_documents(client, db_session, types, foreign_request):
    foreign_request["student"].is_foreign = False
    db_session.flush()

    assert _complete(client, foreign_request["request_id"]).status_code == 200


def test_completing_a_request_already_done_keeps_its_own_conflict(client, db_session, foreign_request):
    request_id = foreign_request["request_id"]
    request = db_session.query(ReenrollmentRequest).get(request_id)
    request.status = "realizada"
    db_session.flush()

    again = _complete(client, request_id)

    assert (again.status_code, again.json()["detail"]) == (409, "La solicitud ya está en ese estado")


def test_the_inbox_and_the_detail_carry_the_regularizado_status(client, db_session, types, foreign_request):
    student, request_id = foreign_request["student"], foreign_request["request_id"]

    row = client.get(f"{REENROLLMENT}/requests").json()["items"][0]
    assert (row["is_foreign"], row["migration_regularizado"]) == (True, False)
    detail = client.get(f"{REENROLLMENT}/requests/{request_id}").json()
    assert detail["migration"]["applies"] is True and detail["migration"]["regularizado"] is False
    assert detail["migration"]["missing"] == ["Pasaporte", "Visa", "Certificado de nacimiento"]

    for key, expiry in (("pasaporte", None), ("certificado", None), ("visa", "2027-01-01")):
        assert _record(client, student, types[key]["id"], expiry).status_code == 200
    assert client.get(f"{REENROLLMENT}/requests").json()["items"][0]["migration_regularizado"] is True
    assert client.get(f"{REENROLLMENT}/requests/{request_id}").json()["migration"]["regularizado"] is True

    student.is_foreign = False
    db_session.flush()
    row = client.get(f"{REENROLLMENT}/requests").json()["items"][0]
    assert (row["is_foreign"], row["migration_regularizado"]) == (False, None)
    assert client.get(f"{REENROLLMENT}/requests/{request_id}").json()["migration"]["applies"] is False


# ── Student portal ───────────────────────────────────────────────────────────

def test_the_student_sees_only_their_own_missing_and_expired_documents(client, db_session, types):
    mine, other = _foreign(db_session, "FOR-1"), _foreign(db_session, "FOR-2")
    assert _record(client, mine, types["visa"]["id"], YESTERDAY.isoformat(), "Nota interna").status_code == 200
    assert _record(client, other, types["pasaporte"]["id"]).status_code == 200
    token = _student_token(client, mine)

    response = client.get(PORTAL, headers=_as(token))

    assert response.status_code == 200, response.text
    assert response.json() == {
        "applies": True, "regularizado": False, "missing": ["Pasaporte", "Certificado de nacimiento"],
        "expired": [{"name": "Visa", "expires_on": "2026-12-09"}],
    }
    assert "Nota interna" not in response.text


def test_the_portal_status_of_a_student_who_is_not_foreign(client, db_session, types):
    student = _foreign(db_session)
    student.is_foreign = False
    db_session.flush()
    token = _student_token(client, student)

    assert client.get(PORTAL, headers=_as(token)).json() == {
        "applies": False, "regularizado": True, "missing": [], "expired": []}


def test_the_portal_route_needs_a_student_session(client):
    # The staff token set on the client is not a student session.
    assert client.get(PORTAL).status_code == 401
    authorization = client.headers.pop("Authorization")
    try:
        assert client.get(PORTAL).status_code == 401
    finally:
        client.headers["Authorization"] = authorization


# ── Access ───────────────────────────────────────────────────────────────────

ROUTES = [
    ("get", "/types"), ("post", "/types"), ("put", "/types/1"), ("post", "/types/1/deactivate"),
    ("get", "/students/1"), ("put", "/students/1/documents/1"), ("delete", "/students/1/documents/1"),
]


@pytest.mark.parametrize("method,path", ROUTES)
def test_the_admin_api_is_admin_only(client, db_session, method, path):
    from app.models.user import User
    from app.services.auth_service import auth_service

    authorization = client.headers.pop("Authorization")
    try:
        assert getattr(client, method)(f"{ADMIN}{path}").status_code == 401
        docente = User(ci="MD-DOCENTE", full_name="Docente", role="docente", is_active=True,
                       password_hash=auth_service.hash_password("testpass123"))
        db_session.add(docente)
        db_session.flush()
        client.headers["Authorization"] = "Bearer " + auth_service.create_access_token(
            {"sub": str(docente.id), "role": "docente"})
        assert getattr(client, method)(f"{ADMIN}{path}").status_code == 403
    finally:
        client.headers["Authorization"] = authorization


def test_a_student_token_never_opens_the_admin_routes(client, db_session):
    token = _student_token(client, _foreign(db_session))
    for method, path in (("get", "/types"), ("get", "/students/1"), ("delete", "/students/1/documents/1")):
        assert getattr(client, method)(f"{ADMIN}{path}", headers=_as(token)).status_code == 401


# ── Logging ──────────────────────────────────────────────────────────────────

def test_every_write_is_logged_with_before_and_after_and_short_notes(client, db_session):
    visa = _type(client, "Visa", True)
    student = _foreign(db_session)
    client.put(f"{ADMIN}/types/{visa['id']}", json={"name": "Visa de estudiante"})
    long_notes = "n" * 400
    assert _record(client, student, visa["id"], "2027-01-01", long_notes).status_code == 200
    assert _record(client, student, visa["id"], "2028-01-01").status_code == 200
    client.delete(f"{ADMIN}/students/{student.id}/documents/{visa['id']}")
    client.post(f"{ADMIN}/types/{visa['id']}/deactivate")

    logs = db_session.query(ActivityLog).filter(ActivityLog.category == "migration_documents").order_by(
        ActivityLog.id).all()

    assert [log.action for log in logs] == [
        "create_migration_document_type", "update_migration_document_type", "save_migration_document",
        "save_migration_document", "remove_migration_document", "deactivate_migration_document_type",
    ]
    rename = logs[1].details
    assert (rename["before"]["name"], rename["after"]["name"]) == ("Visa", "Visa de estudiante")
    first, second = logs[2].details, logs[3].details
    assert first["before"] is None and first["after"]["expires_on"] == "2027-01-01"
    assert len(first["after"]["notes"]) == 200
    assert second["before"]["expires_on"] == "2027-01-01" and second["after"]["expires_on"] == "2028-01-01"
    assert logs[4].details["before"]["expires_on"] == "2028-01-01" and logs[4].details["after"] is None
    assert all(long_notes not in str(log.details) for log in logs)
    assert logs[2].user_ci is not None and logs[2].details["student_id"] == student.id
    recorded = db_session.query(StudentMigrationDocument).count()
    assert recorded == 0
