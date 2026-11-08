"""Room importer for designations (odd/tasks/theory-classrooms.md S3, S5)."""
from __future__ import annotations

import io

import openpyxl
import pytest

from app.models.academic_management import Classroom
from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services.classroom_catalog_service import catalog_room
from tests.routers.test_docente_portal_permissions import _set_docente_token

PREVIEW = "/api/admin/designations/rooms/preview"
APPLY = "/api/admin/designations/rooms/apply"
PERIOD = "II/2026"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
STALE = "La vista previa cambió; volvé a generarla."
HEADER = ["N°", None, "MATERIAS", "SEMESTRE", "M-04", "AULA", "HORARIO", "CARGA HORARIA", "MES", "SEMANA", "REAL"]


def _classroom(db, number, *, active=True):
    room = catalog_room(number)
    row = Classroom(code=room.code, name=room.name, campus="Cobija", capacity=room.capacity,
                    classroom_type="classroom", resources=[], active=active)
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def world(db_session):
    existing = db_session.get(AppSetting, "ACTIVE_ACADEMIC_PERIOD")
    if existing is None:
        db_session.add(AppSetting(key="ACTIVE_ACADEMIC_PERIOD", value=PERIOD, description="test"))
    else:
        existing.value = PERIOD
    for ci, name in (("RI-1", "Ana María Pérez Rojas"), ("RI-2", "Bruno Rojas Díaz"), ("RI-3", "Carla Soto Vaca")):
        db_session.add(Teacher(ci=ci, full_name=name))
    db_session.flush()
    return {"rooms": {number: _classroom(db_session, number) for number in ("1", "20", "B")}, "db": db_session}


def _designation(db, ci, subject, *, group="M-1", semester="PRIMERO", period=PERIOD, kind="regular", room=None):
    item = Designation(
        teacher_ci=ci, subject=subject, semester=semester, group_code=group, academic_period=period,
        designation_type=kind, classroom_id=room.id if room else None,
        schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30", "horas_academicas": 2}],
        monthly_hours=8, weekly_hours=2, weekly_hours_calculated=2, semester_hours=40,
        schedule_raw="Lunes: 08:00-09:30",
    )
    db.add(item)
    db.flush()
    return item


def _workbook(rows, *, ci=True, sheet="DOCENTES TEORICOS"):
    """rows: (ci, teacher name, subject, semester, group, aula); ``ci=False`` is the real file layout."""
    workbook = openpyxl.Workbook()
    sheet_ = workbook.active
    sheet_.title = sheet
    sheet_.append(HEADER + (["CI"] if ci else []))
    for index, (teacher_ci, name, subject, semester, group, aula) in enumerate(rows, start=1):
        sheet_.append([index, name, subject, semester, group, aula, "", 40, 8, 2, 38] + ([teacher_ci] if ci else []))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _post(client, url, content, **form):
    return client.post(url, files={"file": ("designacion.xlsx", content, XLSX)}, data=form)


def _snapshot(db):
    db.expire_all()
    return {item.id: {c.name: getattr(item, c.name) for c in Designation.__table__.columns}
            for item in db.query(Designation)}


def _basic(world):
    db, rooms = world["db"], world["rooms"]
    one = _designation(db, "RI-1", "ANATOMIA")
    two = _designation(db, "RI-2", "HISTOLOGIA", group="T-2", room=rooms["20"])
    rows = [("RI-1", "Ana Maria Perez Rojas", "Anatomía", "Primero", "M-01", 1),
            ("RI-2", "Bruno Rojas Diaz", "HISTOLOGIA", "PRIMERO", "t-2", "20")]
    return one, two, _workbook(rows)


def test_preview_lists_changed_and_unchanged_matches_and_writes_nothing(client, world):
    one, two, content = _basic(world)
    before = _snapshot(world["db"])

    response = _post(client, PREVIEW, content)

    assert response.status_code == 200, response.text
    body = response.json()
    room1, room20 = world["rooms"]["1"], world["rooms"]["20"]
    assert body["academic_period"] == PERIOD
    assert body["matched"] == [
        {"designation_id": one.id, "teacher_ci": "RI-1", "teacher_name": "Ana María Pérez Rojas",
         "subject": "ANATOMIA", "semester": "PRIMERO", "group_code": "M-1", "current_classroom": None,
         "new_classroom": {"id": room1.id, "code": room1.code, "name": room1.name}, "changed": True},
        {"designation_id": two.id, "teacher_ci": "RI-2", "teacher_name": "Bruno Rojas Díaz",
         "subject": "HISTOLOGIA", "semester": "PRIMERO", "group_code": "T-2",
         "current_classroom": {"id": room20.id, "code": room20.code, "name": room20.name},
         "new_classroom": {"id": room20.id, "code": room20.code, "name": room20.name}, "changed": False},
    ]
    assert (body["unknown_rooms"], body["unmatched_rows"], body["designations_without_row"]) == ([], [], [])
    assert body["summary"] == {"matched": 2, "changed": 1, "unknown_rooms": 0, "unmatched_rows": 0,
                               "designations_without_row": 0}
    assert len(body["preview_digest"]) == 64
    assert _snapshot(world["db"]) == before
    assert world["db"].query(ActivityLog).count() == 0


def test_preview_reports_rooms_that_are_not_usable_without_matching_them(client, world):
    db = world["db"]
    _classroom(db, "3", active=False)  # inactive; room 4 is in the catalog but not in the system
    for subject in ("ANATOMIA", "HISTOLOGIA", "FISIOLOGIA", "QUIMICA"):
        _designation(db, "RI-1", subject)
    content = _workbook([
        ("RI-1", "x", "ANATOMIA", "PRIMERO", "M-1", 99),
        ("RI-1", "x", "HISTOLOGIA", "PRIMERO", "M-1", 3),
        ("RI-1", "x", "FISIOLOGIA", "PRIMERO", "M-1", 4),
        ("RI-1", "x", "QUIMICA", "PRIMERO", "M-1", None),
    ])

    body = _post(client, PREVIEW, content).json()

    assert body["matched"] == []
    assert [(item["row"], item["subject"], item["group_code"], item["aula"], item["teacher"])
            for item in body["unknown_rooms"]] == [
        (2, "ANATOMIA", "M-1", "99", "RI-1"), (3, "HISTOLOGIA", "M-1", "3", "RI-1"),
        (4, "FISIOLOGIA", "M-1", "4", "RI-1"), (5, "QUIMICA", "M-1", "", "RI-1")]
    assert all(item["reason"] for item in body["unknown_rooms"])
    assert body["unmatched_rows"] == [] and body["designations_without_row"] == []
    assert body["summary"]["unknown_rooms"] == 4


def test_preview_reports_unmatched_rows_and_designations_without_a_row(client, world):
    db = world["db"]
    lonely = _designation(db, "RI-3", "FARMACOLOGIA", group="N-3")
    _designation(db, "RI-1", "ANATOMIA")
    content = _workbook([
        ("RI-1", "x", "ANATOMIA", "PRIMERO", "M-1", 1),
        ("RI-9", "x", "ANATOMIA", "PRIMERO", "T-9", 1),
        ("RI-2", "x", "BIOLOGIA", "SEGUNDO", "M-2", "B"),
    ])

    body = _post(client, PREVIEW, content).json()

    assert body["unmatched_rows"] == [
        {"row": 3, "teacher": "RI-9", "subject": "ANATOMIA", "semester": "PRIMERO", "group_code": "T-9", "aula": "1"},
        {"row": 4, "teacher": "RI-2", "subject": "BIOLOGIA", "semester": "SEGUNDO", "group_code": "M-2", "aula": "B"}]
    assert body["designations_without_row"] == [
        {"designation_id": lonely.id, "teacher_name": "Carla Soto Vaca", "subject": "FARMACOLOGIA", "group_code": "N-3"}]
    assert body["summary"] == {"matched": 1, "changed": 1, "unknown_rooms": 0, "unmatched_rows": 2,
                               "designations_without_row": 1}


def test_a_designation_with_rows_in_different_rooms_is_reported_and_not_assigned(client, world):
    _designation(world["db"], "RI-1", "ANATOMIA")
    _designation(world["db"], "RI-2", "HISTOLOGIA")
    content = _workbook([
        ("RI-1", "x", "ANATOMIA", "PRIMERO", "M-1", 1),
        ("RI-1", "x", "ANATOMIA", "PRIMERO", "M-1", 20),
        ("RI-2", "x", "HISTOLOGIA", "PRIMERO", "M-1", "B"),
        ("RI-2", "x", "HISTOLOGIA", "PRIMERO", "M-1", "B"),
    ])

    body = _post(client, PREVIEW, content).json()

    assert [item["subject"] for item in body["matched"]] == ["HISTOLOGIA"]
    assert [(item["row"], item["subject"], item["aula"]) for item in body["unknown_rooms"]] == [(2, "ANATOMIA", "1 / 20")]
    assert "distintas" in body["unknown_rooms"][0]["reason"]
    assert body["unmatched_rows"] == [] and body["designations_without_row"] == []


def test_only_regular_designations_of_the_active_period_are_matched(client, world):
    db = world["db"]
    _designation(db, "RI-1", "ANATOMIA", period="I/2026")
    _designation(db, "RI-1", "HISTOLOGIA", kind="practice")
    content = _workbook([("RI-1", "x", "ANATOMIA", "PRIMERO", "M-1", 1)])

    body = _post(client, PREVIEW, content).json()

    assert body["matched"] == [] and body["designations_without_row"] == []
    assert [item["subject"] for item in body["unmatched_rows"]] == ["ANATOMIA"]


def test_the_real_workbook_layout_without_ci_matches_by_teacher_name(client, world):
    one, two, _content = _basic(world)
    content = _workbook([
        ("", "PEREZ ROJAS, Ana Maria", "Anatomía", "Primero", "M-01", 1),
        ("", "Bruno  Rojas Díaz", "HISTOLOGIA", "PRIMERO", "T-2", 20),
    ], ci=False)

    body = _post(client, PREVIEW, content).json()

    assert [(item["designation_id"], item["changed"]) for item in body["matched"]] == [(one.id, True), (two.id, False)]
    assert body["unmatched_rows"] == [] and body["designations_without_row"] == []


def test_a_row_of_another_teacher_still_gives_its_room_when_the_group_has_one_room(client, world):
    one = _designation(world["db"], "RI-1", "ANATOMIA")
    content = _workbook([("RI-2", "x", "ANATOMIA", "PRIMERO", "M-1", 20)])

    body = _post(client, PREVIEW, content).json()

    assert [item["designation_id"] for item in body["matched"]] == [one.id]
    assert body["unmatched_rows"] == []


def test_apply_sets_only_the_classroom_of_changed_designations_and_logs_once(client, world):
    db, rooms = world["db"], world["rooms"]
    one, two, content = _basic(world)
    third = _designation(db, "RI-3", "FARMACOLOGIA", group="N-3", room=rooms["B"])
    before = _snapshot(db)
    digest = _post(client, PREVIEW, content).json()["preview_digest"]

    response = _post(client, APPLY, content, preview_digest=digest)

    assert response.status_code == 200, response.text
    assert response.json()["summary"] == {"matched": 2, "changed": 1, "unknown_rooms": 0, "unmatched_rows": 0,
                                          "designations_without_row": 1}
    assert response.json()["changed_designation_ids"] == [one.id]
    after = _snapshot(db)
    assert after[one.id]["classroom_id"] == rooms["1"].id
    assert after[two.id]["classroom_id"] == rooms["20"].id
    assert after[third.id]["classroom_id"] == rooms["B"].id  # no row: untouched, never cleared
    for designation_id, columns in before.items():
        assert {k: v for k, v in after[designation_id].items() if k != "classroom_id"} == {
            k: v for k, v in columns.items() if k != "classroom_id"}
    log = db.query(ActivityLog).one()
    assert (log.action, log.category) == ("apply_designation_rooms", "designations")
    assert log.details["changed_designation_ids"] == [one.id]
    assert log.details["summary"]["changed"] == 1 and log.details["academic_period"] == PERIOD
    assert db.query(Classroom).count() == 3

    again = _post(client, PREVIEW, content).json()
    assert again["summary"]["changed"] == 0


def test_apply_with_a_stale_digest_is_refused_without_writing(client, world):
    db = world["db"]
    one, _two, content = _basic(world)
    digest = _post(client, PREVIEW, content).json()["preview_digest"]
    one.classroom_id = world["rooms"]["B"].id  # someone edited the designation after the preview
    db.flush()
    before = _snapshot(db)

    for wrong in (digest, "0" * 64):
        response = _post(client, APPLY, content, preview_digest=wrong)
        assert response.status_code == 409
        assert response.json()["detail"] == STALE
    assert _snapshot(db) == before
    assert db.query(ActivityLog).count() == 0


def test_only_admins_can_use_the_importer(client, world):
    _one, _two, content = _basic(world)
    teacher = world["db"].get(Teacher, "RI-1")
    before = _snapshot(world["db"])
    _set_docente_token(client, world["db"], teacher)

    assert _post(client, PREVIEW, content).status_code == 403
    assert _post(client, APPLY, content, preview_digest="0" * 64).status_code == 403
    assert _snapshot(world["db"]) == before


@pytest.mark.parametrize("content, message", [
    (b"not a workbook", "El archivo no es un Excel válido."),
    (_workbook([], sheet="OTRA"), "El Excel debe tener la hoja DOCENTES TEORICOS."),
])
def test_an_unreadable_workbook_is_a_422_with_the_loader_message(client, world, content, message):
    for url, form in ((PREVIEW, {}), (APPLY, {"preview_digest": "0" * 64})):
        response = _post(client, url, content, **form)
        assert response.status_code == 422
        assert response.json()["detail"] == message


def test_a_sheet_without_the_needed_columns_is_a_422(client, world):
    workbook = openpyxl.Workbook()
    workbook.active.title = "DOCENTES TEORICOS"
    workbook.active.append(["MATERIAS", "SEMESTRE"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    response = _post(client, PREVIEW, buffer.getvalue())

    assert response.status_code == 422
    assert response.json()["detail"].startswith("La hoja debe tener las columnas MATERIAS, SEMESTRE, AULA")


def test_apply_requires_the_digest_and_the_file(client, world):
    _one, _two, content = _basic(world)

    assert _post(client, APPLY, content).status_code == 422
    assert client.post(PREVIEW).status_code == 422
