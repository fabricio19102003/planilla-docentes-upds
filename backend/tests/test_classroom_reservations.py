"""Classroom and laboratory reservations from the teacher portal (odd/tasks/classroom-reservations.md S1-S8)."""
from __future__ import annotations

from datetime import date, datetime, time
from itertools import count

import pytest

from app.models.academic_management import (
    AcademicProgram, AcademicScheduleDraft, AcademicSchedulePublication, AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock, Classroom,
)
from app.models.classroom_reservation import ClassroomReservation
from app.models.teacher import Teacher
from app.services import app_settings_service, classroom_reservation_service
from app.services.reenrollment import BOLIVIA
from tests.routers.test_docente_portal_permissions import _set_docente_token

PORTAL = "/api/portal/classroom-reservations"
MONDAY = date(2027, 3, 1)
NOW = datetime(2027, 3, 1, 7, 0, tzinfo=BOLIVIA)

NOT_BOOKABLE = "El aula o laboratorio no está disponible para reservas."
PAST = "No se puede reservar en una fecha u hora pasada."
WINDOW = "La reserva debe quedar entre las 06:30 y las 23:05."
STEP = "La hora de inicio debe ser múltiplo de 5 minutos."

_ids = count(1)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    monkeypatch.setattr(classroom_reservation_service, "bolivia_now", lambda: NOW)


def _room(db_session, code, name, *, kind="classroom", active=True, capacity=54):
    room = Classroom(code=code, name=name, campus="Cobija", capacity=capacity,
                     classroom_type=kind, resources=[], active=active)
    db_session.add(room)
    db_session.flush()
    return room


@pytest.fixture
def world(client, db_session):
    teacher = Teacher(ci="RES-1", full_name="Docente Reserva")
    other = Teacher(ci="RES-2", full_name="Docente Otra")
    db_session.add_all([teacher, other])
    db_session.flush()
    rooms = {
        "a5": _room(db_session, "COB-ANTIGUO-P1-A5", "Antiguo / Piso 1 / Aula 5"),
        "a6": _room(db_session, "COB-ANTIGUO-P2-A6", "Antiguo / Piso 2 / Aula 6"),
        "lab": _room(db_session, "LAB-ANAT", "Laboratorio de Anatomía", kind="laboratory", capacity=30),
        "virtual": _room(db_session, "VIRT-1", "Aula virtual", kind="virtual", capacity=None),
        "closed": _room(db_session, "COB-OLD-X", "Aula cerrada", active=False),
    }
    _set_docente_token(client, db_session, teacher)
    return {"teacher": teacher, "other": other, "rooms": rooms}


def _publish_class(db_session, room, *, weekday="monday", start="08:00", end="09:30", subject="Bioquímica III"):
    n = next(_ids)
    program = AcademicProgram(code=f"RES-P{n}", name=f"Programa {n}")
    db_session.add(program)
    db_session.flush()
    period = app_settings_service.get_active_academic_period(db_session)
    draft = AcademicScheduleDraft(program_id=program.id, academic_period=period, name=f"d{n}",
                                  normalized_name=f"d{n}", status="published")
    db_session.add(draft)
    db_session.flush()
    publication = AcademicSchedulePublication(
        program_id=program.id, academic_period=period, effective_from=date(2027, 2, 1), sequence=1,
        content_digest="0" * 64, source_draft_id=draft.id,
    )
    db_session.add(publication)
    db_session.flush()
    block = AcademicSchedulePublishedBlock(
        publication_id=publication.id, source_block_id=n, source_offering_id=1, source_subject_id=0,
        source_group_id=n, source_classroom_id=room.id, subject_code=f"SUB {n}", subject_name=subject,
        group_code="M-01", semester=3, classroom_code=room.code, classroom_name=room.name,
        activity_type="theory", weekday=weekday,
        start_time=time.fromisoformat(start), end_time=time.fromisoformat(end),
    )
    db_session.add(block)
    db_session.flush()
    db_session.add(AcademicSchedulePublishedAssignment(
        publication_block_id=block.id, source_assignment_id=n, teacher_ci="RES-2",
        teacher_name="Docente Otra", effective_from=date(2027, 1, 1), effective_to=None,
    ))
    db_session.flush()


def _reserve_as(db_session, teacher, room, day=MONDAY, start="10:00", end="10:45", status="confirmed"):
    row = ClassroomReservation(
        classroom_id=room.id, teacher_ci=teacher.ci, reservation_date=day,
        start_time=time.fromisoformat(start), end_time=time.fromisoformat(end),
        academic_periods=1, status=status,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _stored(db_session):
    return db_session.query(ClassroomReservation).count()


def _post(client, room, *, day="2027-03-01", start="10:00", periods=2):
    return client.post(PORTAL, json={"classroom_id": room.id, "date": day, "start_time": start, "periods": periods})


def test_bookable_rooms_are_the_active_classrooms_and_laboratories(client, world):
    response = client.get(f"{PORTAL}/classrooms")

    assert response.status_code == 200, response.text
    codes = [item["code"] for item in response.json()]
    assert codes == ["COB-ANTIGUO-P1-A5", "COB-ANTIGUO-P2-A6", "LAB-ANAT"]
    lab = response.json()[2]
    assert lab == {"id": world["rooms"]["lab"].id, "code": "LAB-ANAT", "name": "Laboratorio de Anatomía",
                   "capacity": 30, "classroom_type": "laboratory"}


def test_availability_labels_published_classes_as_occupied_and_shows_other_reservations(client, db_session, world):
    rooms = world["rooms"]
    _publish_class(db_session, rooms["a5"], start="08:00", end="09:30")
    _publish_class(db_session, rooms["a5"], weekday="tuesday", start="14:00", end="15:30")
    _publish_class(db_session, rooms["a6"], start="11:00", end="12:30")
    _reserve_as(db_session, world["other"], rooms["a5"], start="10:00", end="10:45")
    _reserve_as(db_session, world["teacher"], rooms["a5"], start="16:00", end="17:30")
    _reserve_as(db_session, world["other"], rooms["a5"], start="18:00", end="18:45", status="cancelled")
    _reserve_as(db_session, world["other"], rooms["a5"], day=date(2027, 3, 2), start="07:00", end="07:45")

    response = client.get(f"{PORTAL}/availability", params={"classroom_id": rooms["a5"].id, "date": "2027-03-01"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["classroom"]["code"] == "COB-ANTIGUO-P1-A5"
    assert body["date"] == "2027-03-01"
    assert body["academic_hour_minutes"] == 45
    assert (body["day_start"], body["day_end"]) == ("06:30", "23:05")
    assert body["busy"] == [
        {"start_time": "08:00", "end_time": "09:30", "kind": "class", "label": "Ocupada",
         "detail": "Bioquímica III", "mine": False},
        {"start_time": "10:00", "end_time": "10:45", "kind": "reservation", "label": "Reservada",
         "detail": None, "mine": False},
        {"start_time": "16:00", "end_time": "17:30", "kind": "reservation", "label": "Reservada",
         "detail": None, "mine": True},
    ]


def test_availability_of_a_room_that_cannot_be_booked_is_not_found(client, world):
    for room in ("virtual", "closed"):
        response = client.get(f"{PORTAL}/availability",
                              params={"classroom_id": world["rooms"][room].id, "date": "2027-03-01"})
        assert response.status_code == 404
        assert response.json()["detail"] == NOT_BOOKABLE


def test_a_free_range_is_reserved_and_confirmed_immediately(client, db_session, world):
    response = _post(client, world["rooms"]["lab"], start="10:00", periods=2)

    assert response.status_code == 201, response.text
    body = response.json()
    assert {key: body[key] for key in ("date", "start_time", "end_time", "academic_periods", "status",
                                       "teacher_ci", "teacher_name")} == {
        "date": "2027-03-01", "start_time": "10:00", "end_time": "11:30", "academic_periods": 2,
        "status": "confirmed", "teacher_ci": "RES-1", "teacher_name": "Docente Reserva",
    }
    assert body["classroom"]["code"] == "LAB-ANAT"
    stored = db_session.get(ClassroomReservation, body["id"])
    assert (stored.start_time, stored.end_time, stored.status) == (time(10, 0), time(11, 30), "confirmed")

    busy = client.get(f"{PORTAL}/availability",
                      params={"classroom_id": world["rooms"]["lab"].id, "date": "2027-03-01"}).json()["busy"]
    assert busy == [{"start_time": "10:00", "end_time": "11:30", "kind": "reservation", "label": "Reservada",
                     "detail": None, "mine": True}]


def test_the_period_length_follows_the_configured_academic_hour(client, db_session, world):
    app_settings_service.update_setting(db_session, app_settings_service.KEY_ACADEMIC_HOUR_MINUTES, "40")

    response = _post(client, world["rooms"]["a5"], start="07:30", periods=3)

    assert response.status_code == 201, response.text
    assert (response.json()["start_time"], response.json()["end_time"]) == ("07:30", "09:30")


def test_a_range_that_overlaps_a_published_class_is_rejected(client, db_session, world):
    _publish_class(db_session, world["rooms"]["a5"], start="08:00", end="09:30")

    response = _post(client, world["rooms"]["a5"], start="09:00", periods=1)

    assert response.status_code == 409
    assert response.json()["detail"] == "El aula está ocupada por una clase de 08:00 a 09:30."
    assert _stored(db_session) == 0


def test_a_range_that_overlaps_another_reservation_is_rejected_but_back_to_back_is_allowed(client, db_session, world):
    room = world["rooms"]["a5"]
    _reserve_as(db_session, world["other"], room, start="10:00", end="10:45")

    overlap = _post(client, room, start="09:30", periods=1)
    assert overlap.status_code == 409
    assert overlap.json()["detail"] == "El aula ya está reservada de 10:00 a 10:45."
    assert _stored(db_session) == 1

    before = _post(client, room, start="09:15", periods=1)
    after = _post(client, room, start="10:45", periods=1)
    assert (before.status_code, after.status_code) == (201, 201)
    assert _stored(db_session) == 3


def test_a_cancelled_reservation_does_not_block_the_room(client, db_session, world):
    _reserve_as(db_session, world["other"], world["rooms"]["a5"], start="10:00", end="10:45", status="cancelled")

    assert _post(client, world["rooms"]["a5"], start="10:00", periods=1).status_code == 201


@pytest.mark.parametrize(("day", "start"), [("2027-02-28", "10:00"), ("2027-03-01", "06:55")])
def test_a_past_date_or_time_is_rejected(client, db_session, world, day, start):
    response = _post(client, world["rooms"]["a5"], day=day, start=start, periods=1)

    assert response.status_code == 422
    assert response.json()["detail"] == PAST
    assert _stored(db_session) == 0


@pytest.mark.parametrize(("start", "periods", "message"), [
    ("06:25", 1, WINDOW), ("22:30", 1, WINDOW), ("22:20", 1, None), ("10:07", 1, STEP),
])
def test_the_range_must_fit_the_day_window_in_five_minute_steps(client, db_session, world, start, periods, message):
    response = _post(client, world["rooms"]["a5"], day="2027-03-02", start=start, periods=periods)

    if message is None:
        assert response.status_code == 201, response.text
        assert response.json()["end_time"] == "23:05"
    else:
        assert response.status_code == 422
        assert response.json()["detail"] == message
        assert _stored(db_session) == 0


def test_a_start_time_with_seconds_is_rejected(client, db_session, world):
    response = _post(client, world["rooms"]["a5"], day="2027-03-02", start="10:00:30")

    assert response.status_code == 422
    assert response.json()["detail"] == STEP
    assert _stored(db_session) == 0


def test_availability_never_reveals_who_reserved(client, db_session, world):
    _reserve_as(db_session, world["other"], world["rooms"]["a5"])

    response = client.get(f"{PORTAL}/availability", params={"classroom_id": world["rooms"]["a5"].id, "date": "2027-03-01"})

    assert "RES-2" not in response.text and "Docente Otra" not in response.text


@pytest.mark.parametrize("periods", [0, 9])
def test_the_number_of_periods_is_between_one_and_eight(client, db_session, world, periods):
    response = _post(client, world["rooms"]["a5"], day="2027-03-02", periods=periods)

    assert response.status_code == 422
    assert _stored(db_session) == 0


def test_a_room_that_cannot_be_booked_is_rejected(client, db_session, world):
    for room in ("virtual", "closed"):
        response = _post(client, world["rooms"][room], day="2027-03-02")
        assert response.status_code == 404
        assert response.json()["detail"] == NOT_BOOKABLE
    assert _stored(db_session) == 0


def test_portal_reservations_require_the_teacher_role(client, db_session, world, admin_token):
    client.headers["Authorization"] = f"Bearer {admin_token}"

    assert client.get(f"{PORTAL}/classrooms").status_code == 403
    assert _post(client, world["rooms"]["a5"], day="2027-03-02").status_code == 403
    assert _stored(db_session) == 0


ADMIN = "/api/admin/classroom-reservations"
NOT_FOUND = "Reserva no encontrada."
ALREADY_CANCELLED = "La reserva ya fue cancelada."
STARTED = "No se puede cancelar una reserva que ya comenzó."


def test_my_reservations_lists_my_upcoming_confirmed_reservations(client, db_session, world):
    rooms, me, other = world["rooms"], world["teacher"], world["other"]
    later = _reserve_as(db_session, me, rooms["a6"], day=date(2027, 3, 3), start="08:00", end="08:45")
    soon = _reserve_as(db_session, me, rooms["lab"], start="10:00", end="11:30")
    _reserve_as(db_session, me, rooms["a5"], day=date(2027, 2, 26))
    _reserve_as(db_session, me, rooms["a5"], day=date(2027, 3, 2), status="cancelled")
    _reserve_as(db_session, other, rooms["a5"], day=date(2027, 3, 2))

    response = client.get(f"{PORTAL}/mine")

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [soon.id, later.id]
    assert response.json()[0]["classroom"]["code"] == "LAB-ANAT"


def test_a_teacher_cancels_their_own_future_reservation_and_frees_the_room(client, db_session, world):
    room = world["rooms"]["a5"]
    mine = _reserve_as(db_session, world["teacher"], room, start="10:00", end="10:45")

    response = client.post(f"{PORTAL}/{mine.id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    db_session.refresh(mine)
    assert mine.status == "cancelled" and mine.cancelled_at is not None
    busy = client.get(f"{PORTAL}/availability", params={"classroom_id": room.id, "date": "2027-03-01"}).json()["busy"]
    assert busy == []
    assert _post(client, room, start="10:00", periods=1).status_code == 201


def test_a_teacher_cannot_cancel_someone_elses_reservation(client, db_session, world):
    theirs = _reserve_as(db_session, world["other"], world["rooms"]["a5"])

    response = client.post(f"{PORTAL}/{theirs.id}/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == NOT_FOUND
    db_session.refresh(theirs)
    assert (theirs.status, theirs.cancelled_at) == ("confirmed", None)


@pytest.mark.parametrize(("day", "start", "status", "code", "message"), [
    (date(2027, 3, 1), "06:30", "confirmed", 422, STARTED),
    (date(2027, 2, 26), "10:00", "confirmed", 422, STARTED),
    (date(2027, 3, 2), "10:00", "cancelled", 409, ALREADY_CANCELLED),
])
def test_started_or_cancelled_reservations_cannot_be_cancelled(client, db_session, world, day, start, status, code,
                                                               message):
    row = _reserve_as(db_session, world["teacher"], world["rooms"]["a5"], day=day, start=start, end="11:00",
                      status=status)

    response = client.post(f"{PORTAL}/{row.id}/cancel")

    assert response.status_code == code
    assert response.json()["detail"] == message
    db_session.refresh(row)
    assert row.status == status


def test_admin_lists_every_confirmed_reservation_of_the_range_with_the_bookable_rooms(client, db_session, world,
                                                                                     admin_token):
    rooms, me, other = world["rooms"], world["teacher"], world["other"]
    first = _reserve_as(db_session, other, rooms["a6"], start="08:00", end="08:45")
    second = _reserve_as(db_session, me, rooms["a5"], start="08:00", end="09:30")
    third = _reserve_as(db_session, me, rooms["lab"], day=date(2027, 3, 2), start="07:00", end="07:45")
    _reserve_as(db_session, me, rooms["a5"], day=date(2027, 3, 3))
    _reserve_as(db_session, other, rooms["a5"], start="12:00", end="12:45", status="cancelled")
    client.headers["Authorization"] = f"Bearer {admin_token}"

    response = client.get(ADMIN, params={"date_from": "2027-03-01", "date_to": "2027-03-02"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [room["code"] for room in body["classrooms"]] == ["COB-ANTIGUO-P1-A5", "COB-ANTIGUO-P2-A6", "LAB-ANAT"]
    assert [item["id"] for item in body["reservations"]] == [second.id, first.id, third.id]
    assert body["reservations"][1]["teacher_name"] == "Docente Otra"


def test_admin_listing_keeps_rooms_deactivated_after_being_reserved(client, db_session, world, admin_token):
    rooms = world["rooms"]
    _reserve_as(db_session, world["teacher"], rooms["closed"], start="08:00", end="08:45")
    _reserve_as(db_session, world["teacher"], rooms["virtual"], day=date(2027, 3, 5))
    client.headers["Authorization"] = f"Bearer {admin_token}"

    body = client.get(ADMIN, params={"date_from": "2027-03-01", "date_to": "2027-03-02"}).json()

    assert [room["code"] for room in body["classrooms"]] == [
        "COB-ANTIGUO-P1-A5", "COB-ANTIGUO-P2-A6", "LAB-ANAT", "COB-OLD-X"]
    assert [item["classroom"]["code"] for item in body["reservations"]] == ["COB-OLD-X"]


def test_the_admin_range_is_ordered_and_at_most_31_days(client, world, admin_token):
    client.headers["Authorization"] = f"Bearer {admin_token}"

    reversed_range = client.get(ADMIN, params={"date_from": "2027-03-02", "date_to": "2027-03-01"})
    too_long = client.get(ADMIN, params={"date_from": "2027-03-01", "date_to": "2027-04-01"})

    assert (reversed_range.status_code, reversed_range.json()["detail"]) == (
        422, "La fecha final no puede ser anterior a la inicial.")
    assert (too_long.status_code, too_long.json()["detail"]) == (422, "El rango no puede superar 31 días.")


def test_the_admin_listing_requires_the_admin_role(client, world):
    response = client.get(ADMIN, params={"date_from": "2027-03-01", "date_to": "2027-03-01"})

    assert response.status_code == 403
