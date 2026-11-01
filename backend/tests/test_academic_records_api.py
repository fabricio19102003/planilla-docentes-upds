from __future__ import annotations

import gzip
import hashlib

import pytest

from app.models.academic_records import AcademicHistoryImport, Student
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.services.auth_service import auth_service
from tests.test_academic_history_import import _csv, _rows

BASE = "/api/admin/academic-records"


def _file(content: bytes, name="gestion-2023.csv", content_type="text/csv"):
    return {"file": (name, content, content_type)}


def _apply(client, content: bytes, name="gestion-2023.csv"):
    response = client.post(
        f"{BASE}/imports/apply", files=_file(content, name),
        data={"expected_sha256": hashlib.sha256(content).hexdigest()},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_then_apply_through_the_api(client, db_session):
    content = _csv(_rows())

    preview = client.post(f"{BASE}/imports/preview", files=_file(content))
    assert preview.status_code == 200, preview.text
    assert preview.json()["counts"]["records_new"] == 5
    assert db_session.query(Student).count() == 0

    applied = _apply(client, content)
    assert applied["counts"]["records_new"] == 5
    assert applied["import_id"] == db_session.query(AcademicHistoryImport).one().id
    log = db_session.query(ActivityLog).filter(ActivityLog.action == "apply_academic_history_import").one()
    assert log.details["file_sha256"] == hashlib.sha256(content).hexdigest()

    receipts = client.get(f"{BASE}/imports").json()
    assert [(r["file_name"], r["counts"]["records_new"], r["actor_name"]) for r in receipts] == [
        ("gestion-2023.csv", 5, "Test Admin"),
    ]


def test_a_gzip_upload_is_the_same_import_as_the_plain_csv(client):
    content = _csv(_rows())
    compressed = gzip.compress(content)

    preview = client.post(
        f"{BASE}/imports/preview", files=_file(compressed, "gestion-2023.csv.gz", "application/gzip"),
    ).json()

    assert preview["file_sha256"] == hashlib.sha256(content).hexdigest()
    assert preview["file_name"] == "gestion-2023.csv"
    response = client.post(
        f"{BASE}/imports/apply", files=_file(compressed, "gestion-2023.csv.gz", "application/gzip"),
        data={"expected_sha256": preview["file_sha256"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["counts"]["records_new"] == 5


def test_apply_conflict_and_format_errors(client, db_session):
    content = _csv(_rows())

    conflict = client.post(f"{BASE}/imports/apply", files=_file(content), data={"expected_sha256": "0" * 64})
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "El archivo cambió después de la vista previa"

    invalid = client.post(f"{BASE}/imports/preview", files=_file(b"a,b\n1,2\n"))
    assert invalid.status_code == 422
    assert invalid.json()["detail"].startswith("Faltan columnas: EstudianteNombre")

    empty = client.post(f"{BASE}/imports/preview", files=_file(b""))
    assert empty.status_code == 400
    assert empty.json()["detail"] == "El archivo está vacío"
    assert db_session.query(Student).count() == 0
    assert db_session.query(AcademicHistoryImport).count() == 0


def test_terms_and_students_list_with_search_and_filters(client):
    _apply(client, _csv(_rows()))

    terms = client.get(f"{BASE}/terms").json()
    assert [(t["code"], t["name"], t["is_intensive"], t["record_count"]) for t in terms] == [
        ("II/2026", "Segundo Semestre 2026", False, 1),
        ("II/2025", "Segundo Semestre 2025", False, 1),
        ("INV/2024", "Invierno 2024", True, 1),
        ("I/2023", "Primer Semestre 2023", False, 2),
    ]

    listed = client.get(f"{BASE}/students").json()
    assert listed["total"] == 2
    assert [s["full_name"] for s in listed["items"]] == ["Carlos Mamani Quispe", "Raimunda Jaisa Paiva Da Silva"]
    raimunda = listed["items"][1]
    assert raimunda == {
        "id": raimunda["id"], "document_number": "I-11626046", "full_name": "Raimunda Jaisa Paiva Da Silva",
        "nationality": "Brasileña", "is_foreign": True, "legacy_enrollment_status": "Antiguo",
        "last_term": "INV/2024", "record_count": 3,
    }
    assert client.get(f"{BASE}/students", params={"search": "paiva"}).json()["total"] == 1
    assert client.get(f"{BASE}/students", params={"search": "7485000"}).json()["items"][0]["full_name"] == (
        "Carlos Mamani Quispe"
    )
    assert client.get(f"{BASE}/students", params={"foreign": "false"}).json()["total"] == 1
    assert client.get(f"{BASE}/students", params={"status": "Desertor"}).json()["total"] == 0
    page = client.get(f"{BASE}/students", params={"page": 2, "page_size": 1}).json()
    assert (page["total"], page["page"], [s["document_number"] for s in page["items"]]) == (2, 2, ["I-11626046"])


def test_student_detail_groups_history_by_term_newest_first(client):
    _apply(client, _csv(_rows()))
    student_id = client.get(f"{BASE}/students", params={"search": "I-11626046"}).json()["items"][0]["id"]

    detail = client.get(f"{BASE}/students/{student_id}").json()

    assert detail["student"]["document_type"] == "CEDULA DE EXTRANJERIA"
    assert detail["student"]["birth_date"] == "1993-12-25"
    assert detail["student"]["academic_email"] == "co.raimunda.paiva.d@upds.net.bo"
    assert detail["student"]["curriculum_plan"] == "Medicina 510-01"
    assert [term["term"]["code"] for term in detail["history"]] == ["INV/2024", "I/2023"]
    first_term = detail["history"][1]
    assert first_term["records"] == [
        {
            "legacy_registration_id": 5254, "subject_code": "MRF 0100", "subject_name": "Anatomía Humana I",
            "group_code": "Q", "shift": "Noche", "teacher_name": "Lesly Guerrero Ortega",
            "status": "reprobado", "grade": 0, "in_curriculum": True,
        },
        {
            "legacy_registration_id": 5253, "subject_code": "LIN 0130", "subject_name": "Inglés Técnico I",
            "group_code": "Q", "shift": "Noche", "teacher_name": "Lesly Guerrero Ortega",
            "status": "aprobado", "grade": 73, "in_curriculum": True,
        },
    ]
    assert detail["history"][0]["records"][0]["in_curriculum"] is False
    missing = client.get(f"{BASE}/students/999999")
    assert (missing.status_code, missing.json()["detail"]) == (404, "Estudiante no encontrado")


@pytest.mark.parametrize("method,path", [
    ("get", "/students"), ("get", "/students/1"), ("get", "/terms"), ("get", "/imports"),
    ("post", "/imports/preview"), ("post", "/imports/apply"),
])
def test_student_data_is_admin_only(client, db_session, method, path):
    authorization = client.headers.pop("Authorization")
    try:
        assert getattr(client, method)(f"{BASE}{path}").status_code == 401
        docente = User(
            ci="RECORDS-API-DOCENTE", full_name="Docente", role="docente", is_active=True,
            password_hash=auth_service.hash_password("testpass123"),
        )
        db_session.add(docente)
        db_session.flush()
        client.headers["Authorization"] = "Bearer " + auth_service.create_access_token(
            data={"sub": str(docente.id), "role": "docente"}
        )
        assert getattr(client, method)(f"{BASE}{path}").status_code == 403
    finally:
        client.headers["Authorization"] = authorization
