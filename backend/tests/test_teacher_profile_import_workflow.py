from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.teacher import TeacherCreate, TeacherUpdate


def envelope(*, ci: str = "9100001", name: str = "DOCENTE SINTETICA TITULAR") -> dict:
    return {
        "academic_period": "II/2026",
        "scope": {"population": "theory"},
        "contract": {"policy": "fill_empty_only", "source_revision": "synthetic-v1"},
        "rows": [
            {
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
            }
        ],
    }


def upload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()


def preview(client, payload: dict):
    return client.post(
        "/api/teachers/import/preview?academic_period=II/2026",
        files={"file": ("profiles.json", upload_bytes(payload), "application/json")},
    )


def apply(client, payload: dict, digest: str):
    return client.post(
        f"/api/teachers/import?academic_period=II/2026&confirmation_digest={digest}",
        files={"file": ("profiles.json", upload_bytes(payload), "application/json")},
    )


def seed_teacher(db_session, *, email=None):
    teacher = Teacher(ci="9100001", full_name="DOCENTE SINTETICA TITULAR", email=email)
    user = User(
        ci="9100001",
        full_name="Synthetic Teacher User",
        email="login@example.test",
        password_hash="unchanged-password-hash",
        role="docente",
        teacher_ci="9100001",
        is_active=True,
    )
    db_session.add_all([teacher, user, AppSetting(key="ACTIVE_ACADEMIC_PERIOD", value="I/2026")])
    db_session.commit()
    return teacher, user


def test_three_teacher_types_are_canonical_and_unknown_is_rejected():
    for value in ("EXTERNO", "PERMANENTE", "TITULAR", "titular"):
        assert TeacherCreate(ci="1", full_name="Synthetic", external_permanent=value).external_permanent == value.upper()
        assert TeacherUpdate(external_permanent=value).external_permanent == value.upper()
    with pytest.raises(ValidationError):
        TeacherCreate(ci="1", full_name="Synthetic", external_permanent="SERVICIOS PROFESIONALES")


def test_preview_and_apply_fill_all_empty_profile_fields_without_auth_or_period_mutation(client, db_session):
    teacher, user = seed_teacher(db_session)
    payload = envelope()
    response = preview(client, payload)
    assert response.status_code == 200
    plan = response.json()
    assert plan["parsed_format"] == "audit_envelope"
    assert plan["scope"] == "theory"
    assert plan["policy"] == "fill_empty_only"
    assert plan["identity"] == {"matched": 1, "missing": 0, "duplicates": 0, "conflicts": 0}
    assert plan["can_apply"] is True
    assert all(counts["fills"] == 1 for counts in plan["fields"].values())

    original_password = user.password_hash
    original_login_email = user.email
    applied = apply(client, payload, plan["digest"])
    assert applied.status_code == 201
    db_session.refresh(teacher)
    db_session.refresh(user)
    assert teacher.external_permanent == "TITULAR"
    assert teacher.invoice_retention == "RETENCION"
    assert teacher.account_number == "0012345001"
    assert teacher.academic_level == "MAESTRÍA"
    assert teacher.profession == "PROFESIÓN SINTÉTICA"
    assert teacher.specialty == "ESPECIALIDAD SINTÉTICA"
    assert teacher.sap_code == "SAP-SYN-01"
    assert user.password_hash == original_password
    assert user.email == original_login_email
    assert db_session.query(AppSetting).filter_by(key="ACTIVE_ACADEMIC_PERIOD").one().value == "I/2026"
    assert db_session.query(ActivityLog).filter_by(action="import_teacher_profiles").count() == 1

    repeated = preview(client, payload).json()
    assert repeated["can_apply"] is True
    assert all(counts["noops"] == 1 for counts in repeated["fields"].values())


def test_digest_drift_and_existing_conflicts_block_the_entire_apply(client, db_session):
    seed_teacher(db_session, email="existing@example.test")
    payload = envelope()
    plan = preview(client, payload).json()
    assert plan["can_apply"] is False
    assert plan["fields"]["email"]["conflicts"] == 1
    assert plan["fields"]["external_permanent"]["fills"] == 1
    rejected = apply(client, payload, plan["digest"])
    assert rejected.status_code == 400
    assert db_session.query(Teacher).one().external_permanent is None

    clean_payload = envelope()
    db_session.query(Teacher).one().email = None
    db_session.commit()
    clean_digest = preview(client, clean_payload).json()["digest"]
    changed = copy.deepcopy(clean_payload)
    changed["rows"][0]["profile"]["phone"] = "+591 70000002"
    drifted = apply(client, changed, clean_digest)
    assert drifted.status_code == 400
    assert "cambiaron" in drifted.json()["detail"]
    assert db_session.query(Teacher).one().phone is None


def test_missing_duplicate_and_malformed_identity_are_reported_without_writes(client, db_session, caplog):
    seed_teacher(db_session)
    missing = envelope(ci="9199999", name="DOCENTE AUSENTE SINTETICA")
    missing_plan = preview(client, missing).json()
    assert missing_plan["identity"]["missing"] == 1
    assert missing_plan["can_apply"] is False

    duplicate = envelope()
    duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
    duplicate_plan = preview(client, duplicate).json()
    assert duplicate_plan["identity"]["duplicates"] == 1
    assert duplicate_plan["can_apply"] is False

    mismatched = envelope(name="OTRA IDENTIDAD SINTETICA")
    mismatch_plan = preview(client, mismatched).json()
    assert mismatch_plan["identity"]["conflicts"] == 1
    assert mismatch_plan["can_apply"] is False

    malformed = envelope()
    malformed["rows"][0]["profile"]["account_number"] = 12345
    malformed["rows"][0]["profile"]["email"] = {"private": "value"}
    malformed_plan = preview(client, malformed).json()
    assert malformed_plan["can_apply"] is False
    assert malformed_plan["errors"]
    assert "private" not in caplog.text
    teacher = db_session.query(Teacher).filter_by(ci="9100001").one()
    assert teacher.account_number is None


def test_late_activity_failure_rolls_back_every_profile_field(client, db_session, monkeypatch, caplog):
    teacher, _ = seed_teacher(db_session)
    payload = envelope()
    digest = preview(client, payload).json()["digest"]

    def fail_activity(*args, **kwargs):
        raise RuntimeError("synthetic late failure")

    monkeypatch.setattr("app.routers.teachers.log_activity", fail_activity)
    response = apply(client, payload, digest)
    assert response.status_code == 500
    db_session.refresh(teacher)
    assert teacher.email is None
    assert teacher.external_permanent is None
    assert db_session.query(ActivityLog).filter_by(action="import_teacher_profiles").count() == 0
    assert "9100001" not in caplog.text
    assert "docente.sintetica" not in caplog.text


def test_legacy_direct_upload_is_retired_and_non_admin_is_rejected(client):
    retired = client.post(
        "/api/teachers/upload",
        files={"file": ("legacy.xlsx", b"not-used", "application/octet-stream")},
    )
    assert retired.status_code == 410
    assert "Generar vista previa" in retired.json()["detail"]

    authorization = client.headers.pop("Authorization")
    try:
        unauthorized = client.post(
            "/api/teachers/import/preview?academic_period=II/2026",
            files={"file": ("profiles.json", upload_bytes(envelope()), "application/json")},
        )
        assert unauthorized.status_code == 401
    finally:
        client.headers["Authorization"] = authorization


def test_profile_upload_rejects_empty_wrong_extension_and_oversize_files(client):
    empty = client.post(
        "/api/teachers/import/preview?academic_period=II/2026",
        files={"file": ("profiles.json", b"", "application/json")},
    )
    assert empty.status_code == 400
    wrong = client.post(
        "/api/teachers/import/preview?academic_period=II/2026",
        files={"file": ("profiles.xlsx", b"synthetic", "application/octet-stream")},
    )
    assert wrong.status_code == 400
    oversized = client.post(
        "/api/teachers/import/preview?academic_period=II/2026",
        files={"file": ("profiles.json", b"x" * (10 * 1024 * 1024 + 1), "application/json")},
    )
    assert oversized.status_code == 413


def test_audit_envelope_rejects_unknown_nested_keys_without_echoing_them(client, caplog):
    cases = [
        ((), "private-top-level-value"),
        (("scope",), "private-scope-value"),
        (("rows", 0), "private-row-value"),
        (("rows", 0, "identity"), "private-identity-value"),
        (("rows", 0, "profile"), "private-profile-value"),
        (("rows", 0, "source"), "private-source-value"),
    ]
    for path, sentinel in cases:
        payload = envelope()
        target = payload
        for part in path:
            target = target[part]
        target[sentinel] = "submitted-private-value"
        response = preview(client, payload)
        assert response.status_code == 200
        body = response.json()
        assert body["can_apply"] is False
        assert body["errors"]
        assert sentinel not in response.text
        assert "submitted-private-value" not in response.text
        assert sentinel not in caplog.text
        assert "submitted-private-value" not in caplog.text


def test_source_provenance_is_mandatory_strict_and_redacted(client, caplog):
    cases = [
        ({}, "source"),
        ({"file": None, "sheet": "teachers", "row": 2, "sha256": "0" * 64}, "source.file"),
        ({"file": {"private": "value"}, "sheet": "teachers", "row": 2, "sha256": "0" * 64}, "source.file"),
        ({"file": "synthetic.xlsx", "sheet": "", "row": 2, "sha256": "0" * 64}, "source.sheet"),
        ({"file": "synthetic.xlsx", "sheet": "teachers", "row": 0, "sha256": "0" * 64}, "source.row"),
        ({"file": "synthetic.xlsx", "sheet": "teachers", "row": True, "sha256": "0" * 64}, "source.row"),
        ({"file": "synthetic.xlsx", "sheet": "teachers", "row": "2", "sha256": "0" * 64}, "source.row"),
        ({"file": "synthetic.xlsx", "sheet": "teachers", "row": 2, "sha256": None}, "source.sha256"),
        ({"file": "synthetic.xlsx", "sheet": "teachers", "row": 2, "sha256": "not-a-sha"}, "source.sha256"),
        ({"file": "synthetic.xlsx", "sheet": "teachers", "row": 2, "sha256": {"private": "value"}}, "source.sha256"),
    ]
    for source, expected_field in cases:
        payload = envelope()
        payload["rows"][0]["source"] = source
        response = preview(client, payload)
        assert response.status_code == 200
        body = response.json()
        assert body["can_apply"] is False
        assert any(expected_field in error for error in body["errors"])
        assert "submitted-private-value" not in response.text
        assert "\"private\"" not in response.text
        assert "not-a-sha" not in response.text
        assert "private" not in caplog.text
