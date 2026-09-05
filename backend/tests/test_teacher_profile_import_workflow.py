from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from app.models.teacher import Teacher
from app.schemas.teacher import TeacherCreate, TeacherUpdate


def envelope(*, ci: str = "9100001", name: str = "DOCENTE SINTETICA TITULAR") -> dict:
    return {
        "academic_period": "II/2026",
        "scope": {"population": "theory"},
        "contract": {"policy": "fill_empty_only", "source_revision": "synthetic-v1"},
        "rows": [{
            "identity": {"teacher_ci": ci, "official_name_normalized": name},
            "profile": {
                "email": "docente.sintetica@example.test",
                "phone": "+591 70000001",
                "gender": "FEMENINO",
                "external_permanent": "titular",
                "academic_level": "MAESTRÍA",
                "profession": "PROFESIÓN SINTÉTICA",
                "specialty": "ESPECIALIDAD SINTÉTICA",
                "bank": "BANCO SINTÉTICO",
                "account_number": "0012345001",
                "nit": "99000001",
                "sap_code": "SAP-SYN-01",
                "invoice_retention": "RETENCIÓN",
            },
            "source": {"file": "synthetic.xlsx", "sheet": "teachers", "row": 2, "sha256": "0" * 64},
        }],
    }


def upload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()


def preview(client, payload: dict):
    return client.post(
        "/api/teachers/import/preview?academic_period=II/2026",
        files={"file": ("profiles.json", upload_bytes(payload), "application/json")},
    )


def seed_teacher(db_session):
    teacher = Teacher(ci="9100001", full_name="DOCENTE SINTETICA TITULAR")
    db_session.add(teacher)
    db_session.commit()
    return teacher


def test_three_teacher_types_are_canonical_and_unknown_is_rejected():
    for value in ("EXTERNO", "PERMANENTE", "TITULAR", "titular"):
        assert TeacherCreate(ci="1", full_name="Synthetic", external_permanent=value).external_permanent == value.upper()
        assert TeacherUpdate(external_permanent=value).external_permanent == value.upper()
    with pytest.raises(ValidationError):
        TeacherCreate(ci="1", full_name="Synthetic", external_permanent="SERVICIOS PROFESIONALES")


def test_preview_plans_fill_empty_fields_without_writes(client, db_session):
    teacher = seed_teacher(db_session)
    response = preview(client, envelope())
    assert response.status_code == 200
    plan = response.json()
    assert plan["parsed_format"] == "audit_envelope"
    assert plan["scope"] == "theory"
    assert plan["policy"] == "fill_empty_only"
    assert plan["identity"] == {"matched": 1, "missing": 0, "duplicates": 0, "conflicts": 0}
    assert plan["can_apply"] is True
    assert all(counts["fills"] == 1 for counts in plan["fields"].values())
    db_session.refresh(teacher)
    assert teacher.email is None
    assert teacher.external_permanent is None


def test_missing_duplicate_and_malformed_identity_are_reported_without_writes(client, db_session, caplog):
    seed_teacher(db_session)
    missing = envelope(ci="9199999", name="DOCENTE AUSENTE SINTETICA")
    assert preview(client, missing).json()["identity"]["missing"] == 1
    duplicate = envelope()
    duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
    assert preview(client, duplicate).json()["identity"]["duplicates"] == 1
    mismatched = envelope(name="OTRA IDENTIDAD SINTETICA")
    assert preview(client, mismatched).json()["identity"]["conflicts"] == 1
    malformed = envelope()
    malformed["rows"][0]["profile"]["account_number"] = 12345
    malformed["rows"][0]["profile"]["email"] = {"private": "value"}
    body = preview(client, malformed).json()
    assert body["can_apply"] is False and body["errors"]
    assert "private" not in caplog.text


def test_audit_envelope_and_source_provenance_are_strict_and_redacted(client, db_session, caplog):
    seed_teacher(db_session)
    payload = envelope()
    payload["rows"][0]["source"] = {"file": "synthetic.xlsx", "sheet": "teachers", "row": 0, "sha256": "not-a-sha"}
    body = preview(client, payload).json()
    assert body["can_apply"] is False
    assert any("source.row" in error for error in body["errors"])
    assert any("source.sha256" in error for error in body["errors"])
    assert "not-a-sha" not in caplog.text


def test_preview_rejects_empty_wrong_extension_and_oversize_files(client):
    empty = client.post("/api/teachers/import/preview?academic_period=II/2026", files={"file": ("profiles.json", b"", "application/json")})
    assert empty.status_code == 400
    wrong = client.post("/api/teachers/import/preview?academic_period=II/2026", files={"file": ("profiles.xlsx", b"synthetic", "application/octet-stream")})
    assert wrong.status_code == 400
    oversized = client.post("/api/teachers/import/preview?academic_period=II/2026", files={"file": ("profiles.json", b"x" * (10 * 1024 * 1024 + 1), "application/json")})
    assert oversized.status_code == 413
