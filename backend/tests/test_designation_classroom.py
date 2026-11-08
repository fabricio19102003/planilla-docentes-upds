"""Designation classroom: admin read/write, payroll untouched (odd/tasks/theory-classrooms.md S2, S4 backend)."""
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

from app.models.academic_management import Classroom
from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service
from app.services.effective_schedule_service import effective_schedule_slots
from app.services.payroll_schedule_source_service import payroll_schedule_sources
from app.services.planilla_generator import PlanillaGenerator
from tests.test_designation_admin import PERIOD, _contract_line, _logs, _payload, _rows

URL = "/api/admin/designations"
MISSING_ROOM = "El aula no existe o está inactiva."


@pytest.fixture
def seeded(db_session):
    for key, value in (("HOURLY_RATE", "70"), ("PRACTICE_HOURLY_RATE", "50"), ("ACTIVE_ACADEMIC_PERIOD", PERIOD)):
        existing = db_session.get(AppSetting, key)
        if existing is None:
            db_session.add(AppSetting(key=key, value=value, description="test"))
        else:
            existing.value = value
    db_session.add(Teacher(ci="ADM-T1", full_name="ANA PEREZ"))
    db_session.flush()
    return db_session


def _room(db, code, *, active=True):
    room = Classroom(code=code, name=f"Aula {code}", campus="Cobija", capacity=40,
                     classroom_type="classroom", resources=[], active=active)
    db.add(room)
    db.flush()
    return room


def _designation(db, *, classroom=None, start=None, end=None, teacher="ADM-T1", subject="ANATOMIA"):
    item = Designation(
        teacher_ci=teacher, subject=subject, semester="PRIMERO", group_code="M-1", academic_period=PERIOD,
        designation_type="regular", classroom_id=classroom.id if classroom else None,
        schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30",
                        "duracion_minutos": 90, "horas_academicas": 2}],
        monthly_hours=8, weekly_hours=2, weekly_hours_calculated=2, semester_hours=40,
        schedule_raw="Lunes: 08:00-09:30", contract_start_date=start, contract_end_date=end,
    )
    db.add(item)
    db.flush()
    return item


def _same_body(**extra):
    body = dict(subject="ANATOMIA", semester="PRIMERO", group_code="M-1", monthly_hours=8, semester_hours=40,
                contract_start_date=None, contract_end_date=None,
                schedule=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30"}])
    return _payload(**{**body, **extra})


def _columns(db, item):
    db.expire_all()
    row = db.get(Designation, item.id)
    return {column.name: getattr(row, column.name) for column in Designation.__table__.columns
            if column.name != "classroom_id"}


def test_list_exposes_the_classroom_or_null(client, seeded):
    room = _room(seeded, "T-A1")
    _designation(seeded, classroom=room)
    _designation(seeded, subject="HISTOLOGIA")

    items = {item["subject"]: item for item in client.get(URL).json()["items"]}

    assert items["ANATOMIA"]["classroom"] == {"id": room.id, "code": "T-A1", "name": "Aula T-A1"}
    assert items["HISTOLOGIA"]["classroom"] is None


def test_create_with_a_classroom_stores_it_and_returns_it(client, seeded):
    room = _room(seeded, "T-A1")

    response = client.post(URL, json=_payload(classroom_id=room.id))

    assert response.status_code == 201, response.text
    assert response.json()["classroom"] == {"id": room.id, "code": "T-A1", "name": "Aula T-A1"}
    assert seeded.get(Designation, response.json()["id"]).classroom_id == room.id
    assert "classroom_id" in seeded.query(ActivityLog).filter(
        ActivityLog.action == "create_designation").one().details["designation"]


def test_create_without_classroom_leaves_it_empty(client, seeded):
    response = client.post(URL, json=_payload())

    assert response.status_code == 201, response.text
    assert response.json()["classroom"] is None


@pytest.mark.parametrize("kind", ["missing", "inactive"])
def test_a_missing_or_inactive_classroom_is_rejected_without_writing(client, seeded, kind):
    item = _designation(seeded)
    before = _rows(seeded)
    classroom_id = 999999 if kind == "missing" else _room(seeded, "T-OFF", active=False).id

    created = client.post(URL, json=_payload(classroom_id=classroom_id))
    updated = client.put(f"{URL}/{item.id}", json=_same_body(classroom_id=classroom_id))

    for response in (created, updated):
        assert response.status_code == 422
        assert response.json()["detail"]["errors"] == [MISSING_ROOM]
    assert _rows(seeded) == before
    assert seeded.get(Designation, item.id).classroom_id is None
    assert _logs(seeded, "create_designation") == _logs(seeded, "update_designation") == 0


def test_update_sets_changes_and_clears_the_classroom_and_logs_before_after(client, seeded):
    room = _room(seeded, "T-A1")
    item = _designation(seeded)

    response = client.put(f"{URL}/{item.id}", json=_same_body(classroom_id=room.id))

    assert response.status_code == 200, response.text
    assert response.json()["classroom"]["code"] == "T-A1"
    log = seeded.query(ActivityLog).filter(ActivityLog.action == "update_designation").one()
    assert log.details["changes"] == {"classroom_id": {"before": None, "after": room.id}}

    cleared = client.put(f"{URL}/{item.id}", json=_same_body(classroom_id=None))

    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["classroom"] is None
    assert _logs(seeded, "update_designation") == 2


def test_update_that_omits_the_classroom_keeps_it(client, seeded):
    room = _room(seeded, "T-A1")
    item = _designation(seeded, classroom=room)

    response = client.put(f"{URL}/{item.id}", json=_same_body(monthly_hours=12))

    assert response.status_code == 200, response.text
    assert response.json()["classroom"]["id"] == room.id
    assert seeded.get(Designation, item.id).classroom_id == room.id


def test_editing_only_the_classroom_has_no_payroll_or_contract_side_effects(client, seeded):
    room = _room(seeded, "T-A1")
    item = _designation(seeded, start=date(2026, 8, 1))
    _contract_line(seeded, item)
    seeded.add(PlanillaOutput(month=9, year=2026, status="approved"))
    seeded.flush()
    before = _columns(seeded, item)

    blocked = client.put(f"{URL}/{item.id}", json=_same_body(monthly_hours=99, contract_start_date="2026-08-01"))
    response = client.put(f"{URL}/{item.id}/classroom", json={"classroom_id": room.id})

    assert blocked.status_code == 409
    assert response.status_code == 200, response.text
    assert response.json()["regenerate"] == [] and response.json()["warnings"] == []
    assert response.json()["classroom"]["id"] == room.id
    assert _columns(seeded, item) == before
    assert seeded.get(Designation, item.id).classroom_id == room.id
    assert seeded.query(PlanillaOutput).one().status == "approved"


def _paid_imported(db):
    """An Excel-imported designation (raw HORARIO text) with a contract line in an approved payroll month."""
    item = _designation(db, start=date(2026, 8, 1))
    item.schedule_raw = "LUNES 08:00-09:30"
    _contract_line(db, item)
    db.add(PlanillaOutput(month=9, year=2026, status="approved"))
    db.flush()
    return item


def test_dedicated_endpoint_sets_only_the_classroom_of_a_paid_imported_designation(client, seeded):
    room = _room(seeded, "T-A1")
    item = _paid_imported(seeded)
    before = _columns(seeded, item)

    response = client.put(f"{URL}/{item.id}/classroom", json={"classroom_id": room.id})

    assert response.status_code == 200, response.text
    assert response.json()["classroom"] == {"id": room.id, "code": "T-A1", "name": "Aula T-A1"}
    assert response.json()["schedule_raw"] == "LUNES 08:00-09:30"
    assert response.json()["regenerate"] == [] and response.json()["warnings"] == []
    assert _columns(seeded, item) == before
    assert seeded.get(Designation, item.id).classroom_id == room.id
    assert seeded.query(PlanillaOutput).one().status == "approved"
    log = seeded.query(ActivityLog).filter(ActivityLog.action == "update_designation").one()
    assert log.details["changes"] == {"classroom_id": {"before": None, "after": room.id}}

    cleared = client.put(f"{URL}/{item.id}/classroom", json={"classroom_id": None})

    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["classroom"] is None
    assert _columns(seeded, item) == before
    assert seeded.get(Designation, item.id).classroom_id is None


def test_dedicated_endpoint_with_the_same_classroom_changes_and_logs_nothing(client, seeded):
    room = _room(seeded, "T-A1")
    item = _designation(seeded, classroom=room)

    response = client.put(f"{URL}/{item.id}/classroom", json={"classroom_id": room.id})

    assert response.status_code == 200, response.text
    assert _logs(seeded, "update_designation") == 0


@pytest.mark.parametrize("kind", ["missing", "inactive"])
def test_dedicated_endpoint_rejects_a_missing_or_inactive_classroom(client, seeded, kind):
    item = _paid_imported(seeded)
    before = _rows(seeded)
    classroom_id = 999999 if kind == "missing" else _room(seeded, "T-OFF", active=False).id

    response = client.put(f"{URL}/{item.id}/classroom", json={"classroom_id": classroom_id})

    assert response.status_code == 422
    assert response.json()["detail"]["errors"] == [MISSING_ROOM]
    assert _rows(seeded) == before
    assert seeded.get(Designation, item.id).classroom_id is None
    assert _logs(seeded, "update_designation") == 0


def test_dedicated_endpoint_404_for_a_missing_designation_and_422_without_the_field(client, seeded):
    room = _room(seeded, "T-A1")
    item = _designation(seeded)

    assert client.put(f"{URL}/999999/classroom", json={"classroom_id": room.id}).status_code == 404
    assert client.put(f"{URL}/{item.id}/classroom", json={}).status_code == 422
    assert _logs(seeded, "update_designation") == 0


def test_dedicated_endpoint_is_admin_only(client, seeded):
    user = User(ci="NOT-ADMIN-1", full_name="Docente", password_hash=auth_service.hash_password("testpass123"),
                role="teacher", is_active=True)
    seeded.add(user)
    seeded.flush()
    token = auth_service.create_access_token(data={"sub": str(user.id), "role": "teacher"})
    non_admin_headers = {"Authorization": f"Bearer {token}"}
    room = _room(seeded, "T-A1")
    item = _designation(seeded)

    response = client.put(f"{URL}/{item.id}/classroom", json={"classroom_id": room.id}, headers=non_admin_headers)

    assert response.status_code == 403
    assert seeded.get(Designation, item.id).classroom_id is None


def test_a_generic_edit_under_a_payroll_lock_stays_locked_even_when_only_the_classroom_changes(client, seeded):
    room = _room(seeded, "T-A1")
    item = _paid_imported(seeded)

    response = client.put(f"{URL}/{item.id}", json=_same_body(contract_start_date="2026-08-01", classroom_id=room.id))

    assert response.status_code == 409
    assert seeded.get(Designation, item.id).classroom_id is None


def test_an_unrelated_edit_still_works_after_the_classroom_was_deactivated(client, seeded):
    room = _room(seeded, "T-A1")
    item = _designation(seeded, classroom=room)
    room.active = False
    seeded.flush()

    response = client.put(f"{URL}/{item.id}", json=_same_body(monthly_hours=12, classroom_id=room.id))

    assert response.status_code == 200, response.text
    assert response.json()["monthly_hours"] == 12
    assert seeded.get(Designation, item.id).classroom_id == room.id
    # Moving to a different inactive room is still refused.
    other = _room(seeded, "T-OFF", active=False)
    refused = client.put(f"{URL}/{item.id}", json=_same_body(monthly_hours=12, classroom_id=other.id))
    assert refused.status_code == 422
    assert refused.json()["detail"]["errors"] == [MISSING_ROOM]


def test_teacher_change_keeps_the_classroom_on_the_replacement_designation(client, seeded):
    seeded.add(Teacher(ci="ADM-T2", full_name="LUIS GOMEZ"))
    room = _room(seeded, "T-A1")
    old = _designation(seeded, classroom=room)

    applied = client.post(
        "/api/admin/academic-management/designation-changes/apply",
        json={"academic_period": PERIOD, "effective_from": "2026-05-18", "incoming_teacher_ci": "ADM-T2",
              "scope": "designation", "designation_id": old.id},
    )

    assert applied.status_code == 201, applied.text
    created = seeded.get(Designation, applied.json()["created_designation_ids"][0])
    assert created.teacher_ci == "ADM-T2"
    assert created.classroom_id == room.id
    assert seeded.get(Designation, old.id).classroom_id == room.id


def test_payroll_outputs_are_identical_with_and_without_a_classroom(client, seeded):
    room = _room(seeded, "T-A1")
    item = _designation(seeded)

    def snapshot():
        seeded.expire_all()
        slots = effective_schedule_slots(seeded, PERIOD, date(2026, 9, 7), include_practice=True)
        sources = payroll_schedule_sources(
            seeded, academic_period=PERIOD, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
            activity_kind="theory")
        rows, detail, warnings = PlanillaGenerator(output_dir="unused")._build_planilla_data(
            seeded, month=9, year=2026, discount_mode="full")
        return slots, [asdict(source) for source in sources], rows, detail, warnings

    without = snapshot()
    item.classroom_id = room.id
    seeded.flush()
    with_room = snapshot()

    assert without[0] and without[1] and without[2]
    assert with_room == without


def test_no_payroll_attendance_contract_or_billing_module_references_a_classroom():
    app = Path(__file__).parents[1] / "app"
    pattern = re.compile(r"payroll|planilla|contract|billing|attendance|practice_(?:attendance|planilla)", re.I)
    modules = [path for folder in ("services", "routers", "models", "schemas") for path in (app / folder).glob("*.py")
               if pattern.search(path.name)]

    assert modules
    assert [path.name for path in modules if "classroom" in path.read_text(encoding="utf-8").lower()] == []
