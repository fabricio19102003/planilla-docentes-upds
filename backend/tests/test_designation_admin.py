from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal

import pytest

from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.attendance import AttendanceRecord
from app.models.billing_publication import BillingPublication
from app.models.contract import ContractDocument, ContractLine
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher

URL = "/api/admin/designations"
PERIOD = "II/2026"
FUTURE_END = date.today() + timedelta(days=30)


@pytest.fixture
def seeded(db_session):
    for key, value in (("HOURLY_RATE", "70"), ("PRACTICE_HOURLY_RATE", "50"), ("ACTIVE_ACADEMIC_PERIOD", PERIOD)):
        existing = db_session.get(AppSetting, key)
        if existing is None:
            db_session.add(AppSetting(key=key, value=value, description="test"))
        else:
            existing.value = value
    db_session.add(Teacher(ci="ADM-T1", full_name="ANA PEREZ"))
    db_session.add(Teacher(ci="ADM-T2", full_name="BRUNO ROJAS"))
    db_session.flush()
    return db_session


def _designation(db, teacher_ci="ADM-T1", *, subject="ANATOMIA", group="M-1", kind="regular",
                 semester="PRIMERO", period=PERIOD, start=None, end=None):
    item = Designation(
        teacher_ci=teacher_ci, subject=subject, semester=semester, group_code=group,
        academic_period=period, designation_type=kind,
        schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30",
                        "duracion_minutos": 90, "horas_academicas": 2}],
        monthly_hours=8, weekly_hours=2, weekly_hours_calculated=2, semester_hours=40,
        schedule_raw="Lunes: 08:00-09:30", contract_start_date=start, contract_end_date=end,
    )
    db.add(item)
    db.flush()
    return item


def _attendance(db, designation, day, status="ATTENDED"):
    db.add(AttendanceRecord(
        teacher_ci=designation.teacher_ci, designation_id=designation.id, date=day,
        scheduled_start=time(8, 0), scheduled_end=time(9, 30), actual_entry=time(8, 0),
        actual_exit=time(9, 30), status=status, academic_hours=2, month=day.month, year=day.year,
    ))
    db.flush()


def _contract_line(db, designation):
    document = ContractDocument(
        public_id="00000000-0000-0000-0000-000000000001", teacher_ci=designation.teacher_ci,
        teacher_name="ANA PEREZ", teacher_snapshot={}, academic_period=PERIOD, period_snapshot={},
        document_kind="original", effective_date=date(2026, 8, 1), source_digest="0" * 64,
        template_version="test", department="PANDO", full_snapshot={}, artifact_filename="c.pdf",
        artifact_media_type="application/pdf", artifact_sha256="0" * 64, artifact_size=1,
        artifact_content=b"x",
    )
    db.add(document)
    db.flush()
    db.add(ContractLine(
        contract_id=document.id, line_number=1, activity_kind="theory", rate_class="regular",
        hourly_rate=Decimal("70"), hours=Decimal("40"), hour_basis="weekly",
        subject_label=designation.subject, group_label=designation.group_code,
        semester_label=designation.semester, schedule_label="Lunes", effective_from=date(2026, 8, 1),
        effective_to=date(2026, 12, 18), source_kind="legacy", source_id=designation.id,
        designation_id=designation.id, authority_effective_from=date(2026, 8, 1), change_kind="full",
    ))
    db.flush()


def _payload(**extra):
    body = {
        "teacher_ci": "ADM-T1", "subject": "  histologia  ", "semester": "segundo", "group_code": "t2",
        "academic_period": PERIOD,
        "schedule": [
            {"dia": "Martes", "hora_inicio": "06:30", "hora_fin": "08:00"},
            {"dia": "jueves", "hora_inicio": "10:00", "hora_fin": "11:30"},
        ],
        "monthly_hours": 16, "semester_hours": 80,
        "contract_start_date": "2026-08-10", "contract_end_date": "2026-12-18",
    }
    body.update(extra)
    return body


def _rows(db):
    db.expire_all()
    return sorted(
        (d.teacher_ci, d.subject, d.group_code, d.monthly_hours, d.contract_start_date, d.contract_end_date)
        for d in db.query(Designation).filter(Designation.academic_period == PERIOD)
    )


def _logs(db, action):
    return db.query(ActivityLog).filter(ActivityLog.action == action).count()


def _codes(response):
    return [item["code"] for item in response.json()["detail"]["blockers"]]


# ── T1: list ─────────────────────────────────────────────────────────────────

def test_list_returns_period_items_with_teacher_status_and_actions(client, seeded):
    active = _designation(seeded, subject="ANATOMIA", end=FUTURE_END)
    ended = _designation(seeded, "ADM-T2", subject="BIOQUIMICA", end=date(2026, 8, 31))
    _designation(seeded, subject="OTRO PERIODO", period="I/2026")
    _attendance(seeded, ended, date(2026, 8, 3))

    response = client.get(URL, params={"academic_period": PERIOD})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["academic_period"] == PERIOD
    assert data["periods"] == ["II/2026", "I/2026"]
    assert [(item["id"], item["teacher_name"], item["status"]) for item in data["items"]] == [
        (active.id, "ANA PEREZ", "active"),
        (ended.id, "BRUNO ROJAS", "finalized"),
    ]
    first = data["items"][0]
    assert first["schedule_json"][0]["dia"] == "lunes"
    assert first["has_contract"] is False and first["attendance_count"] == 0
    assert first["actions"] == {
        "edit": {"allowed": True, "reason": None},
        "edit_dates": {"allowed": True, "reason": None},
        "finalize": {"allowed": True, "reason": None},
        "delete": {"allowed": True, "reason": None},
    }
    second = data["items"][1]
    assert second["attendance_count"] == 1
    assert second["actions"]["finalize"] == {"allowed": False, "reason": "La designación ya está finalizada."}
    assert second["actions"]["delete"] == {"allowed": False, "reason": "Tiene asistencia registrada; usá Finalizar."}


def test_list_defaults_to_active_period_and_filters(client, seeded):
    _designation(seeded, subject="ANATOMIA")
    _designation(seeded, "ADM-T2", subject="PRACTICA CLINICA", kind="practice", semester="QUINTO")

    assert [i["subject"] for i in client.get(URL).json()["items"]] == ["ANATOMIA", "PRACTICA CLINICA"]
    assert [i["subject"] for i in client.get(URL, params={"q": "bruno"}).json()["items"]] == ["PRACTICA CLINICA"]
    assert [i["subject"] for i in client.get(URL, params={"q": "anat"}).json()["items"]] == ["ANATOMIA"]
    assert [i["subject"] for i in client.get(URL, params={"designation_type": "practice"}).json()["items"]] == [
        "PRACTICA CLINICA"]
    assert [i["subject"] for i in client.get(URL, params={"semester": "QUINTO"}).json()["items"]] == [
        "PRACTICA CLINICA"]
    assert [i["subject"] for i in client.get(URL, params={"teacher_ci": "ADM-T1"}).json()["items"]] == ["ANATOMIA"]
    assert client.get(URL, params={"status": "finalized"}).json()["items"] == []


def test_list_locks_edit_and_delete_when_payroll_is_approved(client, seeded):
    item = _designation(seeded, start=date(2026, 8, 1))
    seeded.add(PlanillaOutput(month=9, year=2026, status="approved"))
    seeded.flush()

    actions = client.get(URL).json()["items"][0]["actions"]

    reason = "La planilla de teoría 9/2026 ya está aprobada."
    assert actions["edit"] == {"allowed": False, "reason": reason}
    assert actions["edit_dates"] == {"allowed": False, "reason": reason}
    assert actions["delete"] == {"allowed": False, "reason": reason}
    assert actions["finalize"]["allowed"] is True
    assert item.id


def test_list_locks_dates_when_a_contract_was_issued(client, seeded):
    item = _designation(seeded)
    _contract_line(seeded, item)

    row = client.get(URL).json()["items"][0]

    assert row["has_contract"] is True
    assert row["actions"]["edit"] == {"allowed": True, "reason": None}
    assert row["actions"]["edit_dates"] == {
        "allowed": False,
        "reason": "Las fechas quedaron fijadas en el contrato emitido. Para cambiarlas, emití una adenda desde Contratos.",
    }
    assert row["actions"]["delete"]["allowed"] is False


def test_list_requires_admin(client, seeded):
    response = client.get(URL, headers={"Authorization": "Bearer invalid"})
    assert response.status_code in (401, 403)


# ── T2: create and edit ──────────────────────────────────────────────────────

def test_create_normalizes_and_derives_hours_and_logs(client, seeded):
    response = client.post(URL, json=_payload())

    assert response.status_code == 201, response.text
    data = response.json()
    assert (data["subject"], data["semester"], data["group_code"], data["designation_type"]) == (
        "HISTOLOGIA", "SEGUNDO", "T-2", "regular")
    assert data["schedule_json"] == [
        {"dia": "martes", "hora_inicio": "06:30", "hora_fin": "08:00", "duracion_minutos": 90, "horas_academicas": 2},
        {"dia": "jueves", "hora_inicio": "10:00", "hora_fin": "11:30", "duracion_minutos": 90, "horas_academicas": 2},
    ]
    assert (data["weekly_hours"], data["weekly_hours_calculated"], data["monthly_hours"], data["semester_hours"]) == (
        4, 4, 16, 80)
    assert data["schedule_raw"] == "Martes: 06:30-08:00\nJueves: 10:00-11:30"
    assert data["teacher_name"] == "ANA PEREZ"
    assert data["regenerate"] == []
    log = seeded.query(ActivityLog).filter(ActivityLog.action == "create_designation").one()
    assert log.category == "designations"
    assert log.details["designation_id"] == data["id"]


def test_create_detects_practice_and_keeps_unknown_group_codes(client, seeded):
    response = client.post(URL, json=_payload(subject="Práctica Clínica I", group_code=" extra "))

    assert response.status_code == 201, response.text
    assert (response.json()["designation_type"], response.json()["group_code"]) == ("practice", "EXTRA")


def test_create_rejects_invalid_schedule_without_writing(client, seeded):
    response = client.post(URL, json=_payload(schedule=[{"dia": "lunes", "hora_inicio": "10:00", "hora_fin": "09:00"}]))

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"] == "Revisá los datos de la designación."
    assert detail["errors"] == ["Horario 1: las horas deben usar HH:MM y finalizar después del inicio."]
    assert _rows(seeded) == [] and _logs(seeded, "create_designation") == 0


def test_create_rejects_end_before_start(client, seeded):
    response = client.post(URL, json=_payload(contract_start_date="2026-09-10", contract_end_date="2026-09-01"))

    assert response.status_code == 422
    assert response.json()["detail"]["errors"] == ["La fecha de fin no puede ser anterior a la fecha de inicio."]
    assert _rows(seeded) == []


def test_create_unknown_teacher_is_404(client, seeded):
    response = client.post(URL, json=_payload(teacher_ci="NOPE"))

    assert response.status_code == 404
    assert response.json()["detail"] == "Docente no encontrado"
    assert _rows(seeded) == []


def test_create_duplicate_is_409(client, seeded):
    _designation(seeded, subject="HISTOLOGIA", semester="SEGUNDO", group="T-2")
    before = _rows(seeded)

    response = client.post(URL, json=_payload())

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == (
        "Ya existe una designación de esa materia, semestre y grupo para este docente en el período.")
    assert _codes(response) == ["duplicate_designation"]
    assert _rows(seeded) == before and _logs(seeded, "create_designation") == 0


def test_create_inside_approved_month_is_blocked_but_later_start_is_allowed(client, seeded):
    seeded.add(PlanillaOutput(month=9, year=2026, status="approved"))
    seeded.add(PlanillaOutput(month=10, year=2026, status="generated"))
    seeded.flush()

    blocked = client.post(URL, json=_payload())
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["message"] == "No se puede guardar porque ya se pagó con estos datos."
    assert _codes(blocked) == ["payroll_approved"]
    assert _rows(seeded) == []

    allowed = client.post(URL, json=_payload(contract_start_date="2026-10-01"))
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["regenerate"] == [{"planilla": "regular", "month": 10, "year": 2026, "status": "generated"}]


def test_update_changes_fields_and_logs_before_after(client, seeded):
    item = _designation(seeded)

    response = client.put(f"{URL}/{item.id}", json=_payload(subject="Anatomia", semester="primero", group_code="M-1",
                                                           monthly_hours=12))

    assert response.status_code == 200, response.text
    assert response.json()["monthly_hours"] == 12
    assert response.json()["weekly_hours"] == 4
    log = seeded.query(ActivityLog).filter(ActivityLog.action == "update_designation").one()
    assert log.details["designation_id"] == item.id
    assert log.details["changes"]["monthly_hours"] == {"before": 8, "after": 12}


def test_update_without_changes_does_not_log(client, seeded):
    item = _designation(seeded, start=date(2026, 8, 10), end=date(2026, 12, 18))
    body = _payload(subject="ANATOMIA", semester="PRIMERO", group_code="M-1", monthly_hours=8, semester_hours=40,
                    schedule=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30"}])

    response = client.put(f"{URL}/{item.id}", json=body)

    assert response.status_code == 200, response.text
    assert _logs(seeded, "update_designation") == 0


def test_update_blocked_by_published_billing_leaves_row_unchanged(client, seeded):
    item = _designation(seeded, start=date(2026, 8, 1))
    seeded.add(BillingPublication(month=8, year=2026, planilla_type="regular", status="published"))
    seeded.flush()
    before = _rows(seeded)

    response = client.put(f"{URL}/{item.id}", json=_payload(subject="ANATOMIA", monthly_hours=99))

    assert response.status_code == 409
    assert _codes(response) == ["billing_published"]
    assert response.json()["detail"]["blockers"][0]["message"] == "La facturación de teoría 8/2026 ya está publicada."
    assert _rows(seeded) == before and _logs(seeded, "update_designation") == 0


def test_update_dates_locked_by_contract(client, seeded):
    item = _designation(seeded, start=date(2026, 8, 10), end=date(2026, 12, 18))
    _contract_line(seeded, item)

    response = client.put(f"{URL}/{item.id}", json=_payload(subject="ANATOMIA", semester="PRIMERO", group_code="M-1",
                                                           contract_end_date="2026-11-30"))

    assert response.status_code == 409
    assert _codes(response) == ["contract_dates_locked"]
    assert _rows(seeded)[0][5] == date(2026, 12, 18)


def test_update_into_existing_key_is_409(client, seeded):
    _designation(seeded, subject="HISTOLOGIA", semester="SEGUNDO", group="T-2")
    other = _designation(seeded, subject="ANATOMIA")

    response = client.put(f"{URL}/{other.id}", json=_payload())

    assert response.status_code == 409
    assert _codes(response) == ["duplicate_designation"]


def test_update_missing_is_404(client, seeded):
    assert client.put(f"{URL}/999999", json=_payload()).json()["detail"] == "Designación no encontrada"


# ── T3: finalize and delete ──────────────────────────────────────────────────

def test_finalize_sets_end_date_and_logs(client, seeded):
    item = _designation(seeded, start=date(2026, 8, 10), end=date(2026, 12, 18))
    _attendance(seeded, item, date(2026, 10, 5))

    response = client.post(f"{URL}/{item.id}/finalize", json={"end_date": "2026-10-31"})

    assert response.status_code == 200, response.text
    assert response.json()["contract_end_date"] == "2026-10-31"
    assert response.json()["warnings"] == []
    assert _rows(seeded)[0][5] == date(2026, 10, 31)
    assert _logs(seeded, "finalize_designation") == 1


def test_finalize_with_contract_warns(client, seeded):
    item = _designation(seeded, start=date(2026, 8, 10), end=date(2026, 12, 18))
    _contract_line(seeded, item)

    response = client.post(f"{URL}/{item.id}/finalize", json={"end_date": "2026-11-15"})

    assert response.status_code == 200, response.text
    assert response.json()["warnings"] == [
        "El contrato emitido no cambia; si corresponde, emití una adenda desde Contratos."]


@pytest.mark.parametrize(("end_date", "code"), [
    ("2026-08-01", "before_contract_start"),
    ("2026-12-31", "after_contract_end"),
    ("2026-10-01", "attendance_after_end"),
])
def test_finalize_blockers_leave_row_unchanged(client, seeded, end_date, code):
    item = _designation(seeded, start=date(2026, 8, 10), end=date(2026, 12, 18))
    _attendance(seeded, item, date(2026, 10, 5))
    _attendance(seeded, item, date(2026, 10, 6), status="ABSENT")

    response = client.post(f"{URL}/{item.id}/finalize", json={"end_date": end_date})

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "No se puede finalizar en esa fecha."
    assert _codes(response) == [code]
    if code == "attendance_after_end":
        assert response.json()["detail"]["blockers"][0]["dates"] == ["2026-10-05"]
    assert _rows(seeded)[0][5] == date(2026, 12, 18)
    assert _logs(seeded, "finalize_designation") == 0


def test_finalize_blocked_by_approved_month_after_end(client, seeded):
    item = _designation(seeded, start=date(2026, 8, 10), end=date(2026, 12, 18))
    seeded.add(PlanillaOutput(month=11, year=2026, status="approved"))
    seeded.flush()

    blocked = client.post(f"{URL}/{item.id}/finalize", json={"end_date": "2026-10-31"})
    assert _codes(blocked) == ["payroll_approved"]

    allowed = client.post(f"{URL}/{item.id}/finalize", json={"end_date": "2026-11-30"})
    assert allowed.status_code == 200, allowed.text


def test_delete_removes_a_mistaken_designation_and_logs(client, seeded):
    item = _designation(seeded)
    item_id = item.id

    response = client.delete(f"{URL}/{item_id}")

    assert response.status_code == 204
    assert _rows(seeded) == []
    log = seeded.query(ActivityLog).filter(ActivityLog.action == "delete_designation").one()
    assert log.details["designation"]["subject"] == "ANATOMIA"


def test_delete_blocked_by_attendance_contract_or_override(client, seeded):
    with_attendance = _designation(seeded, subject="A")
    seeded.add(PracticeAttendanceLog(
        teacher_ci="ADM-T1", designation_id=with_attendance.id, date=date(2026, 8, 3),
        scheduled_start=time(8, 0), scheduled_end=time(9, 30), academic_hours=2, status="absent",
    ))
    with_contract = _designation(seeded, subject="B")
    _contract_line(seeded, with_contract)
    with_override = _designation(seeded, subject="C")
    seeded.add(PlanillaOutput(month=10, year=2026, status="generated",
                              payment_overrides_json={f"ADM-T1:legacy:{with_override.id}": 10}))
    seeded.flush()
    before = _rows(seeded)

    for item, code in ((with_attendance, "has_attendance"), (with_contract, "has_contract"),
                       (with_override, "payment_override")):
        response = client.delete(f"{URL}/{item.id}")
        assert response.status_code == 409, item.subject
        assert response.json()["detail"]["message"] == "No se puede eliminar esta designación."
        assert code in _codes(response)

    assert _rows(seeded) == before and _logs(seeded, "delete_designation") == 0


def test_delete_missing_is_404(client, seeded):
    assert client.delete(f"{URL}/999999").status_code == 404


# ── Regressions from independent verification ────────────────────────────────

def test_delete_blocked_by_any_payroll_output_covering_it(client, seeded):  # S4 / D1
    item = _designation(seeded)
    seeded.add(PlanillaOutput(month=9, year=2026, status="generated"))
    seeded.flush()
    assert client.get(URL).json()["items"][0]["actions"]["delete"] == {
        "allowed": False, "reason": "La planilla de teoría 9/2026 ya se generó con esta designación; usá Finalizar."}
    response = client.delete(f"{URL}/{item.id}")
    assert response.status_code == 409 and _codes(response) == ["payroll_generated"]
    assert len(_rows(seeded)) == 1


def test_undated_designation_locked_by_approved_month_after_period_bounds(client, seeded):  # S4/S5 / D2
    item = _designation(seeded)
    seeded.add(PlanillaOutput(month=1, year=2027, status="approved"))
    seeded.flush()
    before = _rows(seeded)
    assert client.delete(f"{URL}/{item.id}").status_code == 409
    assert client.put(f"{URL}/{item.id}", json=_payload(subject="ANATOMIA", semester="PRIMERO", group_code="M-1",
                      contract_start_date=None, contract_end_date=None, monthly_hours=99)).status_code == 409
    assert client.post(f"{URL}/{item.id}/finalize", json={"end_date": "2026-12-01"}).status_code == 409
    assert _rows(seeded) == before


def test_update_rejects_period_change(client, seeded):  # D3
    item = _designation(seeded, subject="ANATOMIA")
    body = _payload(subject="ANATOMIA", semester="PRIMERO", group_code="M-1",
                    schedule=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30"}],
                    monthly_hours=10, contract_start_date=None, contract_end_date=None, academic_period="I/2027")
    response = client.put(f"{URL}/{item.id}", json=body)
    assert response.status_code == 422
    assert response.json()["detail"]["errors"] == [
        "El período de una designación no se puede cambiar; finalizala y creá una nueva en el otro período."]
    assert _rows(seeded)[0][3] == 8 and _logs(seeded, "update_designation") == 0


@pytest.mark.parametrize("status", ["ABSENT", "ATTENDED", "LATE", "NO_EXIT"])
def test_delete_blocked_by_attendance_of_any_status(client, seeded, status):  # S4
    item = _designation(seeded)
    _attendance(seeded, item, date(2026, 8, 3), status=status)
    response = client.delete(f"{URL}/{item.id}")
    assert response.status_code == 409 and "has_attendance" in _codes(response)


@pytest.mark.parametrize("fmt", ["{ci}:{id}", "{ci}:legacy:{id}"])
def test_delete_blocked_by_practice_override_keys(client, seeded, fmt):  # S4
    item = _designation(seeded, subject="B PRACTICA", kind="practice")
    seeded.add(PracticePlanillaOutput(month=3, year=2025, status="generated",
               payment_overrides_json={fmt.format(ci="ADM-T1", id=item.id): 5}))
    seeded.flush()
    assert "payment_override" in _codes(client.delete(f"{URL}/{item.id}"))


def test_delete_respects_custom_payroll_cutoff(client, seeded):  # S4
    inside = _designation(seeded, subject="A", start=date(2026, 10, 25), end=date(2026, 10, 31))
    outside = _designation(seeded, subject="B", start=date(2026, 11, 25), end=date(2026, 11, 30))
    seeded.add(PlanillaOutput(month=11, year=2026, status="approved",
               start_date=date(2026, 10, 21), end_date=date(2026, 11, 20)))
    seeded.flush()
    assert client.delete(f"{URL}/{inside.id}").status_code == 409
    assert client.delete(f"{URL}/{outside.id}").status_code == 204


def test_update_kind_change_checks_new_kind_payroll(client, seeded):  # S5
    item = _designation(seeded, subject="ANATOMIA", start=date(2026, 8, 1), end=date(2026, 8, 31))
    seeded.add(PracticePlanillaOutput(month=8, year=2026, status="approved"))
    seeded.flush()
    body = _payload(subject="ANATOMIA", semester="PRIMERO", group_code="M-1", designation_type="practice",
                    schedule=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30"}], monthly_hours=8,
                    contract_start_date="2026-08-01", contract_end_date="2026-08-31")
    assert "payroll_approved" in _codes(client.put(f"{URL}/{item.id}", json=body))


def test_finalize_ignores_absences_but_not_presence_after_end(client, seeded):  # finalize
    item = _designation(seeded, start=date(2026, 8, 1), end=date(2026, 12, 18))
    _attendance(seeded, item, date(2026, 11, 2), status="ABSENT")
    _attendance(seeded, item, date(2026, 11, 9), status="LATE")
    assert "attendance_after_end" in _codes(client.post(f"{URL}/{item.id}/finalize", json={"end_date": "2026-11-01"}))
    assert client.post(f"{URL}/{item.id}/finalize", json={"end_date": "2026-11-09"}).status_code == 200
