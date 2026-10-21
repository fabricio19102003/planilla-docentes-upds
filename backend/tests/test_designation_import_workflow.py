from __future__ import annotations

import copy
import json

import pytest

from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import AuthService


def synthetic_envelope(*, monthly_hours: int = 8, period: str = "II/2026") -> dict:
    return {
        "academic_period": period,
        "contract": {"requires_preload_validation": True},
        "rows": [
            {
                "identity": {
                    "teacher_ci": "9000001",
                    "official_name_normalized": "DOCENTE SINTETICO UNO",
                    "match_method": "synthetic_exact",
                },
                "designation": {
                    "teacher_ci": "9000001",
                    "academic_period": period,
                    "designation_type": "regular",
                    "subject": "MATERIA SINTETICA",
                    "semester": "PRIMERO",
                    "group_code": "M-1",
                    "semester_hours": 40,
                    "monthly_hours": monthly_hours,
                    "weekly_hours": 2,
                    "weekly_hours_calculated": 2,
                    "schedule_raw": "LUNES 08:00-09:30",
                    "schedule_json": [
                        {
                            "dia": "lunes",
                            "hora_inicio": "08:00",
                            "hora_fin": "09:30",
                            "horas_academicas": 2,
                        }
                    ],
                },
                "contract": {"loaded": False, "status": "synthetic"},
                "source": {"row": 1},
            }
        ],
    }


def synthetic_official() -> list[dict]:
    return [
        {
            "CI": "9000100",
            "NOMBRE COMPLETO": "DOCENTE OFICIAL SINTETICO",
            "MATERIAS": "MATERIA OFICIAL SINTETICA",
            "SEMESTRE": "SEGUNDO",
            "GRUPO": "T-1",
            "CARGA HORARIA SEMESTRAL": 40,
            "CARGA HORARIA MENSUAL": 8,
            "CARGA HORARIA SEMANAL": 2,
            "HORARIO": "MARTES 10:00-11:30",
            "FECHA INICIO": "2026-08-01",
            "FECHA FIN": "2026-12-20",
        }
    ]


def payload_bytes(payload: dict | list) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()


def set_nested_value(payload: dict, path: tuple[str | int, ...], value) -> None:
    current = payload
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value


def preview(client, payload: dict | list, period: str = "II/2026"):
    content = payload_bytes(payload)
    return client.post(
        f"/api/uploads/designations/preview?academic_period={period}",
        files={"file": ("synthetic.json", content, "application/json")},
    )


def apply(client, payload: dict | list, digest: str, period: str = "II/2026"):
    content = payload_bytes(payload)
    return client.post(
        f"/api/uploads/designations?academic_period={period}&confirmation_digest={digest}",
        files={"file": ("synthetic.json", content, "application/json")},
    )


def test_audit_envelope_preview_apply_and_repeat_are_idempotent(client, db_session):
    payload = synthetic_envelope()
    first_preview = preview(client, payload)
    assert first_preview.status_code == 200
    first = first_preview.json()
    assert first["parsed_format"] == "audit_envelope"
    assert first["academic_period"] == "II/2026"
    assert first["total_rows"] == 1
    assert first["can_apply"] is True
    assert first["teachers"]["creates"] == 1
    assert first["designations"]["creates"] == 1
    assert first["users"]["creates"] == 1

    applied = apply(client, payload, first["digest"])
    assert applied.status_code == 201
    assert db_session.query(Teacher).filter_by(ci="9000001").count() == 1
    assert db_session.query(Designation).filter_by(academic_period="II/2026").count() == 1
    assert db_session.query(User).filter_by(ci="9000001", role="docente").count() == 1
    assert db_session.query(ActivityLog).filter_by(action="upload_designations").count() == 1

    repeat_preview = preview(client, payload).json()
    assert repeat_preview["teachers"]["noops"] == 1
    assert repeat_preview["designations"]["noops"] == 1
    assert repeat_preview["users"]["noops"] == 1
    repeated = apply(client, payload, repeat_preview["digest"])
    assert repeated.status_code == 201
    assert repeated.json()["designations"]["noops"] == 1
    assert db_session.query(Teacher).filter_by(ci="9000001").count() == 1
    assert db_session.query(Designation).filter_by(academic_period="II/2026").count() == 1
    assert db_session.query(User).filter_by(ci="9000001", role="docente").count() == 1


def test_preview_reports_explicit_update_without_deleting_missing_rows(client, db_session):
    initial = synthetic_envelope(monthly_hours=8)
    initial_preview = preview(client, initial).json()
    assert apply(client, initial, initial_preview["digest"]).status_code == 201

    second_payload = copy.deepcopy(initial)
    second_payload["rows"].append(
        {
            **copy.deepcopy(second_payload["rows"][0]),
            "designation": {
                **copy.deepcopy(second_payload["rows"][0]["designation"]),
                "subject": "OTRA MATERIA SINTETICA",
                "group_code": "T-1",
            },
        }
    )
    second_preview = preview(client, second_payload).json()
    assert second_preview["designations"]["creates"] == 1
    assert apply(client, second_payload, second_preview["digest"]).status_code == 201

    changed = synthetic_envelope(monthly_hours=12)
    changed_preview = preview(client, changed).json()
    assert changed_preview["designations"]["updates"] == 1
    assert changed_preview["designations"]["creates"] == 0
    assert apply(client, changed, changed_preview["digest"]).status_code == 201
    assert db_session.query(Designation).filter_by(academic_period="II/2026").count() == 2
    updated = db_session.query(Designation).filter_by(subject="MATERIA SINTETICA").one()
    assert updated.monthly_hours == 12


def test_unknown_and_zero_row_objects_are_rejected_during_preview(client):
    unknown_payload = {"unexpected": []}
    unknown = preview(client, unknown_payload).json()
    assert unknown["can_apply"] is False
    assert unknown["total_rows"] == 0
    assert unknown["errors"]

    empty = preview(
        client,
        {"academic_period": "II/2026", "contract": {}, "rows": []},
    ).json()
    assert empty["can_apply"] is False
    assert empty["total_rows"] == 0
    assert empty["errors"]
    rejected_apply = apply(client, unknown_payload, unknown["digest"])
    assert rejected_apply.status_code == 400


def test_audit_envelope_rejects_non_text_and_malformed_nesting_without_writes(
    client, db_session, caplog
):
    malformed_cases = [
        (("academic_period",), {"secret": "top-period"}, "academic_period"),
        (("rows", 0, "identity"), ["invalid"], "identity"),
        (("rows", 0, "identity", "teacher_ci"), 9000001, "identity.teacher_ci"),
        (("rows", 0, "identity", "official_name_normalized"), {"secret": "name"}, "identity.official_name_normalized"),
        (("rows", 0, "identity", "match_method"), True, "identity.match_method"),
        (("rows", 0, "identity", "canonical_name"), ["invalid"], "identity.canonical_name"),
        (("rows", 0, "designation"), ["invalid"], "designation"),
        (("rows", 0, "designation", "teacher_ci"), {"secret": "ci"}, "designation.teacher_ci"),
        (("rows", 0, "designation", "academic_period"), 2026, "designation.academic_period"),
        (("rows", 0, "designation", "designation_type"), False, "designation.designation_type"),
        (("rows", 0, "designation", "subject"), {"secret": "subject"}, "designation.subject"),
        (("rows", 0, "designation", "semester"), ["PRIMERO"], "designation.semester"),
        (("rows", 0, "designation", "group_code"), 1, "designation.group_code"),
        (("rows", 0, "designation", "schedule_raw"), {"secret": "schedule"}, "designation.schedule_raw"),
        (("rows", 0, "designation", "schedule_raw_original"), ["invalid"], "designation.schedule_raw_original"),
        (("rows", 0, "designation", "load_basis"), {"secret": "basis"}, "designation.load_basis"),
        (("rows", 0, "designation", "schedule_json", 0, "dia"), {"secret": "day"}, "horario 1.dia"),
        (("rows", 0, "designation", "schedule_json", 0, "hora_inicio"), ["08:00"], "horario 1.hora_inicio"),
        (("rows", 0, "designation", "schedule_json", 0, "hora_fin"), False, "horario 1.hora_fin"),
        (("rows", 0, "contract"), "invalid", "contract"),
        (("rows", 0, "contract", "status"), {"secret": "status"}, "contract.status"),
        (("rows", 0, "source"), "invalid", "source"),
        (("rows", 0, "source", "file"), {"secret": "source"}, "source.file"),
        (("rows", 0, "source", "sheet"), ["invalid"], "source.sheet"),
        (("rows", 0, "source", "sha256"), True, "source.sha256"),
    ]

    last_payload = None
    last_preview = None
    for path, invalid_value, expected_field in malformed_cases:
        payload = synthetic_envelope()
        set_nested_value(payload, path, invalid_value)
        response = preview(client, payload)
        assert response.status_code == 200
        result = response.json()
        assert result["can_apply"] is False
        assert result["errors"]
        assert any(expected_field in error for error in result["errors"])
        assert db_session.query(Teacher).filter_by(ci="9000001").count() == 0
        assert db_session.query(Designation).count() == 0
        assert db_session.query(User).filter_by(ci="9000001").count() == 0
        last_payload = payload
        last_preview = result

    assert last_payload is not None and last_preview is not None
    rejected = apply(client, last_payload, last_preview["digest"])
    assert rejected.status_code == 400
    assert db_session.query(Teacher).filter_by(ci="9000001").count() == 0
    assert db_session.query(Designation).count() == 0
    assert db_session.query(User).filter_by(ci="9000001").count() == 0
    assert "secret" not in caplog.text


def test_official_format_preview_preserves_real_identity_and_contract_dates(client):
    official = synthetic_official()
    response = preview(client, official)
    assert response.status_code == 200
    result = response.json()
    assert result["parsed_format"] == "upds_official"
    assert result["can_apply"] is True
    assert result["teachers"]["creates"] == 1
    assert result["designations"]["creates"] == 1


def test_official_optional_text_fields_reject_nested_values(client, db_session):
    for field_name, invalid_value in (
        ("CORREO", {"secret": "email"}),
        ("NÚMERO DE TELÉFONO", ["invalid"]),
        ("BANCO", True),
        ("NÚMERO CUENTA BANCARIA", {"secret": "account"}),
        ("NIT", ["invalid"]),
        ("FECHA INICIO", {"secret": "date"}),
    ):
        official = synthetic_official()
        official[0][field_name] = invalid_value
        result = preview(client, official).json()
        assert result["can_apply"] is False
        assert any(field_name in error for error in result["errors"])
        assert db_session.query(Teacher).filter_by(ci="9000100").count() == 0
        assert db_session.query(Designation).count() == 0


def test_digest_binds_exact_file_and_period(client, db_session):
    payload = synthetic_envelope()
    digest = preview(client, payload).json()["digest"]
    changed = synthetic_envelope(monthly_hours=12)
    response = apply(client, changed, digest)
    assert response.status_code == 400
    assert "cambiaron" in response.json()["detail"]
    assert db_session.query(Teacher).filter_by(ci="9000001").count() == 0
    assert db_session.query(Designation).filter_by(academic_period="II/2026").count() == 0



def test_digest_rejects_a_changed_period(client, db_session):
    payload = synthetic_envelope()
    digest = preview(client, payload).json()["digest"]
    period_response = apply(client, payload, digest, period="I/2026")
    assert period_response.status_code == 400
    assert db_session.query(Designation).count() == 0


def test_duplicate_business_key_and_identity_conflicts_never_mutate(client, db_session):
    duplicate = synthetic_envelope()
    duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
    duplicate_preview = preview(client, duplicate).json()
    assert duplicate_preview["can_apply"] is False
    assert duplicate_preview["designations"]["conflicts"] == 1

    conflicting = synthetic_envelope()
    conflicting["rows"].append(copy.deepcopy(conflicting["rows"][0]))
    conflicting["rows"][1]["identity"]["teacher_ci"] = "9000002"
    conflicting["rows"][1]["designation"]["teacher_ci"] = "9000002"
    conflicting["rows"][1]["designation"]["subject"] = "SEGUNDA MATERIA"
    conflicting_preview = preview(client, conflicting).json()
    assert conflicting_preview["can_apply"] is False
    assert conflicting_preview["teachers"]["conflicts"] >= 1
    assert db_session.query(Designation).count() == 0


def test_apply_rolls_back_teachers_designations_users_and_activity_on_failure(
    client, db_session, monkeypatch, caplog
):
    payload = synthetic_envelope()
    digest = preview(client, payload).json()["digest"]

    def fail_password_hash(self, password):
        raise RuntimeError("synthetic hash failure")

    monkeypatch.setattr(AuthService, "hash_password", fail_password_hash)
    response = apply(client, payload, digest)
    assert response.status_code == 500
    assert db_session.query(Teacher).filter_by(ci="9000001").count() == 0
    assert db_session.query(Designation).filter_by(academic_period="II/2026").count() == 0
    assert db_session.query(User).filter_by(ci="9000001").count() == 0
    assert db_session.query(ActivityLog).filter_by(action="upload_designations").count() == 0
    assert "9000001" not in caplog.text
    assert "DOCENTE SINTETICO UNO" not in caplog.text


def test_import_does_not_activate_selected_period(client, db_session):
    setting = db_session.query(AppSetting).filter_by(key="ACTIVE_ACADEMIC_PERIOD").first()
    if setting is None:
        setting = AppSetting(key="ACTIVE_ACADEMIC_PERIOD", value="I/2026")
        db_session.add(setting)
    else:
        setting.value = "I/2026"
    db_session.commit()
    payload = synthetic_envelope(period="II/2026")
    preview_payload = preview(client, payload, period="II/2026").json()
    assert apply(client, payload, preview_payload["digest"], period="II/2026").status_code == 201
    persisted_setting = db_session.query(AppSetting).filter_by(key="ACTIVE_ACADEMIC_PERIOD").one()
    assert persisted_setting.value == "I/2026"


def with_contract_dates(payload: dict, start: str | None, end: str | None) -> dict:
    designation = payload["rows"][0]["designation"]
    if start is not None:
        designation["contract_start_date"] = start
    if end is not None:
        designation["contract_end_date"] = end
    return payload


def test_audit_envelope_imports_contract_dates(client, db_session):
    payload = with_contract_dates(synthetic_envelope(), "2026-09-21", "2026-12-18")
    result = preview(client, payload).json()
    assert result["can_apply"] is True
    assert result["errors"] == []
    assert apply(client, payload, result["digest"]).status_code == 201
    stored = db_session.query(Designation).filter_by(subject="MATERIA SINTETICA").one()
    assert stored.contract_start_date.isoformat() == "2026-09-21"
    assert stored.contract_end_date.isoformat() == "2026-12-18"


def test_reimport_without_contract_dates_keeps_existing_dates(client, db_session):
    dated = with_contract_dates(synthetic_envelope(), "2026-08-10", "2026-10-28")
    first = preview(client, dated).json()
    assert apply(client, dated, first["digest"]).status_code == 201

    undated = synthetic_envelope()
    second = preview(client, undated).json()
    assert second["can_apply"] is True
    assert second["designations"]["noops"] == 1
    assert second["designations"]["updates"] == 0
    assert apply(client, undated, second["digest"]).status_code == 201
    stored = db_session.query(Designation).filter_by(subject="MATERIA SINTETICA").one()
    assert stored.contract_start_date.isoformat() == "2026-08-10"
    assert stored.contract_end_date.isoformat() == "2026-10-28"


def test_reimport_with_new_end_date_updates_only_that_date(client, db_session):
    dated = with_contract_dates(synthetic_envelope(), "2026-08-10", "2026-12-18")
    first = preview(client, dated).json()
    assert apply(client, dated, first["digest"]).status_code == 201

    closed = with_contract_dates(synthetic_envelope(), None, "2026-09-20")
    second = preview(client, closed).json()
    assert second["designations"]["updates"] == 1
    assert apply(client, closed, second["digest"]).status_code == 201
    stored = db_session.query(Designation).filter_by(subject="MATERIA SINTETICA").one()
    assert stored.contract_start_date.isoformat() == "2026-08-10"
    assert stored.contract_end_date.isoformat() == "2026-09-20"


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-12-18", "2026-08-10", "Fila 1: la fecha de fin del contrato no puede ser anterior a la de inicio."),
        ("21/09/2026", None, "Fila 1: 'designation.contract_start_date' debe usar el formato AAAA-MM-DD."),
    ],
)
def test_audit_envelope_rejects_invalid_contract_dates_without_writes(client, db_session, start, end, expected):
    payload = with_contract_dates(synthetic_envelope(), start, end)
    result = preview(client, payload).json()
    assert result["can_apply"] is False
    assert expected in result["errors"]
    assert apply(client, payload, result["digest"]).status_code == 400
    assert db_session.query(Designation).count() == 0
    assert db_session.query(Teacher).filter_by(ci="9000001").count() == 0


def test_official_rows_with_rejected_schedule_blocks_are_listed_and_nothing_is_written(client, db_session):
    official = synthetic_official()
    second = dict(official[0], CI="9000101", **{"NOMBRE COMPLETO": "OTRO DOCENTE OFICIAL"})
    second["HORARIO"] = "MARTES 10:00-11:30\nJUEVES: 08: 55 am- 11: 20 pm"
    third = dict(official[0], CI="9000102", **{"NOMBRE COMPLETO": "TERCER DOCENTE OFICIAL"})
    third["HORARIO"] = "VIERNES: 19: 10n pm- 19: 55 pm"
    payload = [official[0], second, third]

    result = preview(client, payload).json()
    assert result["can_apply"] is False
    assert result["errors"] == [
        "Fila 2: horario inválido: El bloque 'JUEVES: 08: 55 AM- 11: 20 PM' dura más de 6 horas",
        "Fila 3: horario inválido: No se pudo leer el bloque 'VIERNES: 19: 10N PM- 19: 55 PM'",
        "Fila 3: el horario debe contener al menos un bloque.",
    ]
    assert apply(client, payload, result["digest"]).status_code == 400
    assert db_session.query(Designation).count() == 0
    assert db_session.query(Teacher).filter(Teacher.ci.in_(["9000100", "9000101", "9000102"])).count() == 0


def test_reimport_with_start_after_stored_end_is_rejected(client, db_session):
    first = with_contract_dates(synthetic_envelope(), "2026-08-10", "2026-09-17")
    assert apply(client, first, preview(client, first).json()["digest"]).status_code == 201

    later = with_contract_dates(synthetic_envelope(), "2026-10-06", None)
    result = preview(client, later).json()
    assert result["can_apply"] is False
    assert (
        "Fila 1: la fecha de fin del contrato (2026-09-17) quedaría anterior a la de inicio (2026-10-06)."
        in result["errors"]
    )
    assert apply(client, later, result["digest"]).status_code == 400
    db_session.expire_all()
    stored = db_session.query(Designation).filter_by(subject="MATERIA SINTETICA").one()
    assert stored.contract_start_date.isoformat() == "2026-08-10"
    assert stored.contract_end_date.isoformat() == "2026-09-17"


def excel_upload_bytes(horario: str) -> bytes:
    from io import BytesIO

    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["N°", "DOCENTE", "MATERIAS", "SEMESTRE", "GRUPO", "SAADS", "AULA", "HORARIO",
                  "CARGA HORARIA", "TOTAL", "MES", "SEMANA", "REAL"])
    sheet.append([1, "DOCENTE EXCEL SINTETICO", "MATERIA EXCEL SINTETICA", "PRIMERO", "M-01", None, None,
                  horario, 40, None, 12, 3, None])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def excel_preview(client, content: bytes):
    return client.post(
        "/api/uploads/designations/preview?academic_period=II/2026",
        files={"file": ("designacion.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def excel_apply(client, content: bytes, digest: str):
    return client.post(
        f"/api/uploads/designations?academic_period=II/2026&confirmation_digest={digest}",
        files={"file": ("designacion.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def add_excel_teacher(db_session) -> None:
    db_session.add(Teacher(ci="9000200", full_name="DOCENTE EXCEL SINTETICO"))
    db_session.commit()


def test_excel_upload_reads_several_days_on_one_line(client, db_session):
    add_excel_teacher(db_session)
    content = excel_upload_bytes("Miercoles: 11: 20 am- 12: 00 pm      Jueves: 08 10 am- 10: 35 am")
    result = excel_preview(client, content).json()
    assert result["can_apply"] is True
    assert result["errors"] == []
    assert result["designations"]["creates"] == 1
    assert excel_apply(client, content, result["digest"]).status_code == 201
    stored = db_session.query(Designation).filter_by(subject="MATERIA EXCEL SINTETICA").one()
    assert [(s["dia"], s["hora_inicio"], s["hora_fin"]) for s in stored.schedule_json] == [
        ("miercoles", "11:20", "12:00"),
        ("jueves", "08:10", "10:35"),
    ]


def test_excel_upload_rejects_impossible_blocks_and_writes_nothing(client, db_session):
    add_excel_teacher(db_session)
    content = excel_upload_bytes("Lunes: 06: 30 am- 08: 00 am\nJueves: 06: 30 am- 08: 00 pm")
    result = excel_preview(client, content).json()
    assert result["can_apply"] is False
    assert result["errors"] == [
        "Fila 2: horario inválido: El bloque 'JUEVES: 06: 30 AM- 08: 00 PM' dura más de 6 horas",
        "El archivo no contiene designaciones.",
    ]
    assert excel_apply(client, content, result["digest"]).status_code == 400
    assert db_session.query(Designation).count() == 0


def test_excel_upload_lists_every_rejected_block_and_warns_on_empty_schedule(client, db_session):
    from io import BytesIO

    import openpyxl

    add_excel_teacher(db_session)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["N°", "DOCENTE", "MATERIAS", "SEMESTRE", "GRUPO", "SAADS", "AULA", "HORARIO",
                  "CARGA HORARIA", "TOTAL", "MES", "SEMANA", "REAL"])
    sheet.append([1, "DOCENTE EXCEL SINTETICO", "MATERIA VALIDA", "PRIMERO", "M-01", None, None,
                  "/Lunes: 08:00 - 09:30h", 40, None, 8, 2, None])
    sheet.append([2, "DOCENTE EXCEL SINTETICO", "MATERIA INVALIDA", "PRIMERO", "M-02", None, None,
                  "Jueves: 25:00-26:00\nViernes: X", 40, None, 8, 2, None])
    sheet.append([3, "DOCENTE EXCEL SINTETICO", "MATERIA SIN HORARIO", "PRIMERO", "M-03", None, None,
                  None, 40, None, 8, 2, None])
    buffer = BytesIO()
    workbook.save(buffer)
    content = buffer.getvalue()

    result = excel_preview(client, content).json()
    assert result["can_apply"] is False
    assert result["errors"] == [
        "Fila 3: horario inválido: El bloque 'JUEVES: 25:00-26:00' tiene una hora inválida",
        "Fila 3: horario inválido: No se pudo leer el bloque 'VIERNES: X'",
    ]
    assert "Fila 4: 'DOCENTE EXCEL SINTETICO' no tiene horario; la fila se omite." in result["warnings"]
    assert excel_apply(client, content, result["digest"]).status_code == 400
    assert db_session.query(Designation).count() == 0
