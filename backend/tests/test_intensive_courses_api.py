"""Intensive (summer/winter) courses: open, enroll with capacity, price and close (academic-phase3 S1, S2)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.activity_log import ActivityLog
from app.models.intensive_courses import IntensiveCourse, IntensiveEnrollment
from app.models.teacher import Teacher
from app.services import academic_records_service, intensive_courses
from tests.test_reenrollment_api import _student_token
from tests.test_reenrollment_eligibility import I_2025, I_2026, _load
from tests.test_student_accounts import _as

ADMIN = "/api/admin/intensive-courses"
PORTAL = "/api/student-portal/intensive-courses"
TODAY = date(2026, 12, 10)
NOT_CONFIGURED = "Configurá las tarifas de cursos intensivos antes de abrir un curso"


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(intensive_courses, "bolivia_today", lambda: TODAY)


@pytest.fixture
def catalog(db_session):
    academic_records_service.load_default_curriculum(db_session)
    db_session.add(Teacher(ci="T-100", full_name="Docente Cien"))
    db_session.add(Teacher(ci="T-200", full_name="Docente Doscientos"))
    db_session.flush()


def _settings(client, theory=100, practice=60, factor=1.10, minimum=1200, maximum=1600):
    return client.put(f"{ADMIN}/settings", json={
        "theory_hourly_rate": theory, "practice_hourly_rate": practice, "margin_factor": factor,
        "min_price": minimum, "max_price": maximum,
    })


@pytest.fixture
def configured(client, catalog):
    assert _settings(client).status_code == 200


def _payload(**overrides):
    body = {"term_code": "VER/2027", "subject_code": "LIN 0130", "teacher_ci": "T-100", "capacity": 2,
            "enrollment_starts_on": "2026-12-01", "enrollment_ends_on": "2026-12-20"}
    return {**body, **overrides}


def _create(client, **overrides):
    response = client.post(ADMIN, json=_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def _snapshot(db_session):
    db_session.expire_all()
    courses = [(c.id, c.capacity, c.status, c.final_enrolled, c.final_price, c.teacher_ci,
                c.enrollment_starts_on, c.enrollment_ends_on, c.theory_hours, c.practice_hours)
               for c in db_session.query(IntensiveCourse).order_by(IntensiveCourse.id)]
    enrollments = [(e.course_id, e.student_id) for e in db_session.query(IntensiveEnrollment)
                   .order_by(IntensiveEnrollment.id)]
    return courses, enrollments


@pytest.fixture
def world(client, db_session, configured):
    failing = _load(db_session, "IC-FAIL", [
        ("Inglés Técnico I LIN-0130", "Reprobado", 40, I_2026),
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
    ])
    failing2 = _load(db_session, "IC-FAIL2", [
        ("Inglés Técnico I LIN-0130", "Reprobado", 30, I_2026),
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
    ])
    failing2.is_foreign = True
    retired = _load(db_session, "IC-RETIRED", [
        ("Anatomía Humana I MRF-0100", "Aprobado", 80, I_2025),
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica y Biología Molecular II FUN-0200", "Aprobado", 70, I_2026),
        ("Caso Básico Clínico Integrador II CBC-0200", "Retirado", 0, I_2026),
    ])
    # Failed first, approved later: never eligible.
    recovered = _load(db_session, "IC-RECOVERED", [
        ("Inglés Técnico I LIN-0130", "Reprobado", 40, I_2025),
        ("Inglés Técnico I LIN-0130", "Aprobado", 65, I_2026),
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
    ])
    db_session.flush()
    return {"failing": failing, "failing2": failing2, "retired": retired, "recovered": recovered}


# ── Price ────────────────────────────────────────────────────────────────────

def test_the_price_is_clamped_and_rounded_half_up():
    price = intensive_courses.compute_price
    pay, factor = Decimal("4000"), Decimal("1.10")
    assert price(pay, 1, factor, 1200, 1600) == 1600        # 4400 -> clamped high
    assert price(pay, 3, factor, 1200, 1600) == 1467        # 1466.67 -> rounded
    assert price(pay, 4, factor, 1200, 1600) == 1200        # 1100 -> clamped low
    assert price(pay, 40, factor, 1200, 1600) == 1200
    assert price(Decimal("2350"), 2, factor, 1200, 1600) == 1293  # 1292.5 rounds up, not to even
    assert price(pay, 0, factor, 1200, 1600) == price(pay, 1, factor, 1200, 1600)  # no one enrolled yet


# ── Settings ─────────────────────────────────────────────────────────────────

def test_the_settings_start_unconfigured_and_block_opening_courses(client, catalog):
    body = client.get(f"{ADMIN}/settings").json()
    assert body == {"theory_hourly_rate": None, "practice_hourly_rate": None, "margin_factor": 1.1,
                    "min_price": 1200, "max_price": 1600, "is_configured": False}

    blocked = client.post(ADMIN, json=_payload())
    assert (blocked.status_code, blocked.json()["detail"]) == (409, NOT_CONFIGURED)
    assert client.get(ADMIN).json() == []


def test_the_settings_are_saved_and_every_change_logs_before_and_after(client, db_session, catalog):
    saved = _settings(client, theory=80.5, practice=45, factor=1.2, minimum=1000, maximum=1800)
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"theory_hourly_rate": 80.5, "practice_hourly_rate": 45.0, "margin_factor": 1.2,
                            "min_price": 1000, "max_price": 1800, "is_configured": True}
    assert client.get(f"{ADMIN}/settings").json() == saved.json()

    _settings(client, theory=90)
    logs = (db_session.query(ActivityLog).filter(ActivityLog.action == "update_intensive_course_settings")
            .order_by(ActivityLog.id).all())
    assert [log.category for log in logs] == ["intensive_courses", "intensive_courses"]
    assert logs[0].details["before"]["theory_hourly_rate"] is None
    assert logs[0].details["after"]["theory_hourly_rate"] == 80.5
    assert logs[1].details["before"]["theory_hourly_rate"] == 80.5
    assert logs[1].details["after"]["theory_hourly_rate"] == 90.0


@pytest.mark.parametrize("change,field", [
    ({"theory_hourly_rate": 0}, "theory_hourly_rate"), ({"theory_hourly_rate": -5}, "theory_hourly_rate"),
    ({"practice_hourly_rate": 0}, "practice_hourly_rate"), ({"margin_factor": 0.99}, "margin_factor"),
    ({"min_price": 0}, "min_price"), ({"min_price": 1700}, "min_price"), ({"max_price": 1100}, "max_price"),
    ({"theory_hourly_rate": None}, "theory_hourly_rate"),
])
def test_invalid_settings_are_rejected_and_change_nothing(client, db_session, catalog, change, field):
    assert _settings(client).status_code == 200
    before = client.get(f"{ADMIN}/settings").json()
    logs = db_session.query(ActivityLog).filter(ActivityLog.action == "update_intensive_course_settings").count()
    body = {"theory_hourly_rate": 100, "practice_hourly_rate": 60, "margin_factor": 1.1,
            "min_price": 1200, "max_price": 1600, **change}

    response = client.put(f"{ADMIN}/settings", json=body)

    assert response.status_code == 422, (field, response.text)
    assert client.get(f"{ADMIN}/settings").json() == before
    assert db_session.query(ActivityLog).filter(
        ActivityLog.action == "update_intensive_course_settings").count() == logs


def test_the_payroll_rates_never_feed_the_intensive_price(client, db_session, catalog):
    from app.services import app_settings_service as payroll

    payroll.update_setting(db_session, payroll.KEY_HOURLY_RATE, "999")
    payroll.update_setting(db_session, payroll.KEY_PRACTICE_HOURLY_RATE, "999")
    assert client.post(ADMIN, json=_payload()).status_code == 409  # still unconfigured
    _settings(client, theory=100, practice=60)

    course = _create(client, theory_hours=40, practice_hours=0)

    assert course["teacher_pay"] == 4000.0
    assert course["price"] == {"amount": 1600, "is_final": False}


def test_the_estimate_follows_the_settings_until_the_course_is_closed(client, world):
    course = _create(client, theory_hours=40, practice_hours=0, capacity=6)
    for key in ("failing", "failing2"):
        token = _student_token(client, world[key])
        assert client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(token)).status_code == 200
    assert client.get(f"{ADMIN}/{course['id']}").json()["price"]["amount"] == 1600   # 4400 / 2 = 2200 -> max

    _settings(client, theory=100, practice=60, factor=1.25, minimum=1000, maximum=3000)
    assert client.get(f"{ADMIN}/{course['id']}").json()["price"]["amount"] == 2500   # 4000 * 1.25 / 2
    closed = client.post(f"{ADMIN}/{course['id']}/close").json()
    assert closed["price"] == {"amount": 2500, "is_final": True}

    _settings(client, theory=500, practice=60, factor=1.10, minimum=1200, maximum=1600)
    assert client.get(f"{ADMIN}/{course['id']}").json()["price"] == {"amount": 2500, "is_final": True}


# ── Opening a course ─────────────────────────────────────────────────────────

def test_a_course_prefills_the_hours_from_the_curriculum_and_is_logged(client, db_session, configured):
    course = _create(client)

    assert (course["term_code"], course["status"], course["capacity"]) == ("VER/2027", "open", 2)
    assert course["subject"]["code"] == "LIN 0130"
    assert course["subject"]["name"] == "Inglés Técnico I"
    assert course["teacher"] == {"ci": "T-100", "full_name": "Docente Cien"}
    assert (course["theory_hours"], course["practice_hours"]) == (34, 34)
    assert (course["enrollment_starts_on"], course["enrollment_ends_on"]) == ("2026-12-01", "2026-12-20")
    assert (course["is_enrollment_open"], course["enrolled"], course["free"]) == (True, 0, 2)
    assert course["teacher_pay"] == 34 * 100 + 34 * 60
    # Nobody enrolled yet: the price shown is the one for a single student.
    assert course["price"] == {"amount": 1600, "is_final": False}
    log = db_session.query(ActivityLog).filter(ActivityLog.action == "create_intensive_course").one()
    assert log.category == "intensive_courses" and log.details["course_id"] == course["id"]

    only_practice = _create(client, term_code="INV/2027", subject_code="CBC 0200")
    assert (only_practice["theory_hours"], only_practice["practice_hours"]) == (0, 17)
    edited = _create(client, term_code="INV/2028", theory_hours=10, practice_hours=5)
    assert (edited["theory_hours"], edited["practice_hours"]) == (10, 5)
    partial = _create(client, term_code="VER/2028", theory_hours=10)
    assert (partial["theory_hours"], partial["practice_hours"]) == (10, 34)


@pytest.mark.parametrize("override,status,detail", [
    ({"term_code": "I/2027"}, 422, None), ({"term_code": "VER/27"}, 422, None),
    ({"term_code": "ver/2027"}, 422, None), ({"capacity": 0}, 422, None),
    ({"enrollment_ends_on": "2026-11-30"}, 422, None),
    ({"theory_hours": -1}, 422, None),
    ({"theory_hours": 0, "practice_hours": 0}, 422, "Las horas de teoría y práctica no pueden ser ambas cero"),
    ({"subject_code": "XXX 9999"}, 422, "La materia XXX 9999 no existe en el catálogo"),
    ({"teacher_ci": "NOPE"}, 422, "El docente NOPE no existe"),
])
def test_invalid_courses_are_rejected_and_nothing_is_created(client, db_session, configured, override, status, detail):
    response = client.post(ADMIN, json=_payload(**override))

    assert response.status_code == status, response.text
    if detail:
        assert response.json()["detail"] == detail
    assert _snapshot(db_session) == ([], [])
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "create_intensive_course").count() == 0


def test_a_subject_has_one_course_per_term(client, db_session, configured):
    _create(client)
    before = _snapshot(db_session)

    duplicate = client.post(ADMIN, json=_payload(capacity=9))

    assert (duplicate.status_code, duplicate.json()["detail"]) == (
        409, "Ya existe un curso intensivo de LIN 0130 para VER/2027")
    assert _snapshot(db_session) == before
    _create(client, term_code="INV/2027")  # another term is fine


def test_a_subject_outside_the_plan_needs_explicit_hours(client, db_session, configured):
    from app.models.academic_management import AcademicSubject

    db_session.add(AcademicSubject(code="EXT 0001", name="Fuera del plan"))
    db_session.flush()

    missing = client.post(ADMIN, json=_payload(subject_code="EXT 0001"))
    assert (missing.status_code, missing.json()["detail"]) == (
        422, "La materia EXT 0001 no está en el plan de estudios; indicá las horas")
    assert _create(client, subject_code="EXT 0001", theory_hours=8, practice_hours=0)["theory_hours"] == 8


def test_the_list_shows_enrolled_count_and_the_current_price(client, world):
    course = _create(client, theory_hours=40, practice_hours=0, capacity=5)
    other = _create(client, term_code="INV/2027", theory_hours=20, practice_hours=0)
    token = _student_token(client, world["failing"])
    client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(token))

    rows = {row["id"]: row for row in client.get(ADMIN).json()}

    assert (rows[course["id"]]["enrolled"], rows[course["id"]]["price"]) == (1, {"amount": 1600, "is_final": False})
    assert rows[other["id"]]["enrolled"] == 0
    assert [r["id"] for r in client.get(ADMIN, params={"term_code": "INV/2027"}).json()] == [other["id"]]
    assert [r["id"] for r in client.get(ADMIN, params={"status": "closed"}).json()] == []


# ── Updating ─────────────────────────────────────────────────────────────────

def test_an_open_course_can_be_updated_and_it_is_logged(client, db_session, configured):
    course = _create(client)

    response = client.put(f"{ADMIN}/{course['id']}", json={
        "teacher_ci": "T-200", "capacity": 8, "enrollment_starts_on": "2026-12-05",
        "enrollment_ends_on": "2026-12-15", "theory_hours": 20, "practice_hours": 0,
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["teacher"]["ci"], body["capacity"], body["theory_hours"], body["practice_hours"]) == (
        "T-200", 8, 20, 0)
    assert (body["enrollment_starts_on"], body["enrollment_ends_on"]) == ("2026-12-05", "2026-12-15")
    assert body["teacher_pay"] == 2000.0
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "update_intensive_course").count() == 1


@pytest.mark.parametrize("change,status,detail", [
    ({"teacher_ci": "NOPE"}, 422, "El docente NOPE no existe"),
    ({"capacity": 0}, 422, None),
    ({"enrollment_ends_on": "2026-11-30"}, 422, "La fecha de fin debe ser igual o posterior a la de inicio"),
    ({"enrollment_starts_on": "2026-12-30"}, 422, "La fecha de fin debe ser igual o posterior a la de inicio"),
    ({"theory_hours": 0, "practice_hours": 0}, 422, "Las horas de teoría y práctica no pueden ser ambas cero"),
])
def test_invalid_updates_change_nothing(client, db_session, configured, change, status, detail):
    course = _create(client)
    before = _snapshot(db_session)

    response = client.put(f"{ADMIN}/{course['id']}", json=change)

    assert response.status_code == status, response.text
    if detail:
        assert response.json()["detail"] == detail
    assert _snapshot(db_session) == before
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "update_intensive_course").count() == 0


def test_capacity_cannot_go_below_the_students_already_enrolled(client, db_session, world):
    course = _create(client, capacity=3)
    for key in ("failing", "failing2"):
        token = _student_token(client, world[key])
        assert client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(token)).status_code == 200
    before = _snapshot(db_session)

    refused = client.put(f"{ADMIN}/{course['id']}", json={"capacity": 1})

    assert (refused.status_code, refused.json()["detail"]) == (
        409, "La capacidad no puede ser menor a los 2 inscritos")
    assert _snapshot(db_session) == before
    assert client.put(f"{ADMIN}/{course['id']}", json={"capacity": 2}).status_code == 200


def test_unknown_courses_are_not_found(client, configured):
    for call in (lambda: client.get(f"{ADMIN}/999"), lambda: client.put(f"{ADMIN}/999", json={"capacity": 3}),
                 lambda: client.post(f"{ADMIN}/999/close")):
        response = call()
        assert (response.status_code, response.json()["detail"]) == (404, "Curso intensivo no encontrado")


# ── Detail and closing ───────────────────────────────────────────────────────

def test_the_detail_lists_the_enrolled_students(client, world):
    course = _create(client)
    for key in ("failing", "failing2"):
        token = _student_token(client, world[key])
        client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(token))

    body = client.get(f"{ADMIN}/{course['id']}").json()

    assert body["enrolled"] == 2
    assert {s["document_number"]: (s["full_name"], s["is_foreign"]) for s in body["students"]} == {
        "IC-FAIL": ("Est IC-FAIL", False), "IC-FAIL2": ("Est IC-FAIL2", True),
    }


def test_closing_fixes_the_enrolled_count_and_price_and_freezes_the_course(client, db_session, world):
    course = _create(client, theory_hours=40, practice_hours=0, capacity=5)
    token = _student_token(client, world["failing"])
    other = _student_token(client, world["failing2"])
    for who in (token, other, _student_token(client, world["retired"])):
        client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(who))  # the retired one is not eligible
    assert client.get(f"{ADMIN}/{course['id']}").json()["enrolled"] == 2

    closed = client.post(f"{ADMIN}/{course['id']}/close")

    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert (body["status"], body["enrolled"], body["price"]) == ("closed", 2, {"amount": 1600, "is_final": True})
    db_session.expire_all()
    stored = db_session.get(IntensiveCourse, course["id"])
    assert (stored.final_enrolled, stored.final_price, stored.status) == (2, 1600, "closed")
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "close_intensive_course").count() == 1

    before = _snapshot(db_session)
    closed_message = "El curso intensivo está cerrado"
    for response in (
        client.post(f"{ADMIN}/{course['id']}/close"), client.put(f"{ADMIN}/{course['id']}", json={"capacity": 9}),
        client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(_student_token(client, world["recovered"]))),
        client.post(f"{PORTAL}/{course['id']}/cancel", headers=_as(token)),
    ):
        assert (response.status_code, response.json()["detail"]) == (409, closed_message)
    assert _snapshot(db_session) == before
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "close_intensive_course").count() == 1


def test_closing_without_students_fixes_the_price_for_one_student(client, configured):
    course = _create(client, theory_hours=40, practice_hours=0)

    body = client.post(f"{ADMIN}/{course['id']}/close").json()

    assert (body["enrolled"], body["price"]) == (0, {"amount": 1600, "is_final": True})


def test_the_price_follows_the_enrolled_count_through_clamp_and_middle(client, db_session, world):
    course = _create(client, theory_hours=40, practice_hours=0, capacity=6)  # pay 4000, with margin 4400
    students = [world["failing"], world["failing2"]]
    for index in range(3, 6):  # only the count matters for the price, so these join directly
        students.append(_load(db_session, f"IC-EXTRA-{index}", [
            ("Inglés Técnico I LIN-0130", "Reprobado", 30, I_2026),
            ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ]))

    prices = {}
    for count, student in enumerate(students, start=1):
        db_session.add(IntensiveEnrollment(course_id=course["id"], student_id=student.id))
        db_session.flush()
        shown = client.get(f"{ADMIN}/{course['id']}").json()
        assert shown["enrolled"] == count
        prices[count] = shown["price"]["amount"]

    # 4400 -> max, 2200 -> max, 1466.67 -> 1467 (middle), 1100 and 880 -> min.
    assert prices == {1: 1600, 2: 1600, 3: 1467, 4: 1200, 5: 1200}


# ── Student enrollment ───────────────────────────────────────────────────────

def test_the_student_sees_only_the_courses_they_may_take_with_the_current_price(client, world):
    failing_course = _create(client, theory_hours=40, practice_hours=0, capacity=3)
    pending_course = _create(client, subject_code="CBC 0200", teacher_ci="T-200")
    _create(client, subject_code="MRF 0200")  # the student approved it: not offered
    closed = _create(client, subject_code="FUN 0200")
    client.post(f"{ADMIN}/{closed['id']}/close")

    failing = client.get(PORTAL, headers=_as(_student_token(client, world["failing"]))).json()
    assert [c["subject"]["code"] for c in failing["courses"]] == ["LIN 0130"]
    row = failing["courses"][0]
    assert (row["id"], row["term_code"], row["capacity"], row["enrolled"], row["free"], row["is_full"]) == (
        failing_course["id"], "VER/2027", 3, 0, 3, False)
    assert (row["is_enrollment_open"], row["price"], row["teacher_name"]) == (
        True, {"amount": 1600, "is_final": False}, "Docente Cien")
    assert (row["theory_hours"], row["practice_hours"]) == (40, 0)
    assert "teacher_pay" not in row and failing["enrollments"] == []

    retired = client.get(PORTAL, headers=_as(_student_token(client, world["retired"]))).json()
    assert [c["subject"]["code"] for c in retired["courses"]] == ["CBC 0200"]
    assert retired["courses"][0]["id"] == pending_course["id"]

    recovered = client.get(PORTAL, headers=_as(_student_token(client, world["recovered"]))).json()
    assert recovered["courses"] == []


def test_a_student_enrolls_sees_the_enrollment_and_cancels(client, db_session, world):
    course = _create(client, theory_hours=40, practice_hours=0, capacity=3)
    token = _student_token(client, world["failing"])

    enrolled = client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(token))

    assert enrolled.status_code == 200, enrolled.text
    assert (enrolled.json()["id"], enrolled.json()["enrolled"], enrolled.json()["free"]) == (course["id"], 1, 2)
    mine = client.get(PORTAL, headers=_as(token)).json()
    assert mine["courses"] == []
    assert [(e["id"], e["subject"]["code"], e["price"], e["status"]) for e in mine["enrollments"]] == [
        (course["id"], "LIN 0130", {"amount": 1600, "is_final": False}, "open")]
    log = db_session.query(ActivityLog).filter(ActivityLog.action == "enroll_intensive_course").one()
    assert log.category == "intensive_courses"
    assert log.details == {"course_id": course["id"], "student_id": world["failing"].id}

    cancelled = client.post(f"{PORTAL}/{course['id']}/cancel", headers=_as(token))
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["enrolled"] == 0
    assert client.get(PORTAL, headers=_as(token)).json()["enrollments"] == []
    assert [c["id"] for c in client.get(PORTAL, headers=_as(token)).json()["courses"]] == [course["id"]]
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "cancel_intensive_course").count() == 1
    assert _snapshot(db_session)[1] == []


def test_a_pending_retired_subject_can_be_taken(client, world):
    course = _create(client, subject_code="CBC 0200")
    token = _student_token(client, world["retired"])

    assert client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(token)).status_code == 200


def test_the_enrollment_price_follows_the_enrolled_count_then_stays_fixed(client, world):
    course = _create(client, theory_hours=40, practice_hours=0, capacity=6)
    first = _student_token(client, world["failing"])
    client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(first))
    assert client.get(PORTAL, headers=_as(first)).json()["enrollments"][0]["price"]["amount"] == 1600
    _settings(client, theory=100, practice=60, factor=1.10, minimum=1000, maximum=1600)
    second = _student_token(client, world["failing2"])
    client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(second))
    assert client.get(PORTAL, headers=_as(first)).json()["enrollments"][0]["price"] == {
        "amount": 1600, "is_final": False}                 # 4400 / 2 = 2200 -> 1600

    client.post(f"{PORTAL}/{course['id']}/cancel", headers=_as(second))
    _settings(client, theory=40, practice=60, factor=1.10, minimum=1000, maximum=1600)
    closed = client.post(f"{ADMIN}/{course['id']}/close").json()
    assert closed["price"] == {"amount": 1600, "is_final": True}  # 1760 for one student
    row = client.get(PORTAL, headers=_as(first)).json()["enrollments"][0]
    assert (row["status"], row["price"]) == ("closed", {"amount": 1600, "is_final": True})
    assert client.get(PORTAL, headers=_as(second)).json()["courses"] == []  # a closed course is no longer offered


def test_the_course_must_be_in_the_enrollment_dates(client, db_session, world):
    early = _create(client, term_code="INV/2027", enrollment_starts_on="2026-12-11", enrollment_ends_on="2026-12-20")
    late = _create(client, term_code="INV/2028", enrollment_starts_on="2026-12-01", enrollment_ends_on="2026-12-09")
    last_day = _create(client, term_code="VER/2028", enrollment_starts_on="2026-12-10", enrollment_ends_on="2026-12-10")
    token = _student_token(client, world["failing"])
    before = _snapshot(db_session)

    for course in (early, late):
        refused = client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(token))
        assert (refused.status_code, refused.json()["detail"]) == (
            409, "La inscripción al curso intensivo no está abierta")
    assert _snapshot(db_session) == before
    assert client.post(f"{PORTAL}/{last_day['id']}/enroll", headers=_as(token)).status_code == 200


def test_a_student_cannot_take_a_subject_they_are_not_failing_or_pending(client, db_session, world):
    approved = _create(client, subject_code="MRF 0200")
    never_taken = _create(client, subject_code="FUN 0300")
    before = _snapshot(db_session)

    for course, student, code in ((approved, "failing", "MRF 0200"), (never_taken, "failing", "FUN 0300"),
                                  (approved, "recovered", "MRF 0200")):
        refused = client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(_student_token(client, world[student])))
        assert (refused.status_code, refused.json()["detail"]) == (
            422, f"{code} no está entre tus materias a recursar o pendientes")
    lin = _create(client)
    recovered = client.post(f"{PORTAL}/{lin['id']}/enroll", headers=_as(_student_token(client, world["recovered"])))
    assert (recovered.status_code, recovered.json()["detail"]) == (
        422, "LIN 0130 no está entre tus materias a recursar o pendientes")
    assert _snapshot(db_session)[1] == before[1] == []
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "enroll_intensive_course").count() == 0


def test_a_full_course_and_a_second_enrollment_are_refused(client, db_session, world):
    course = _create(client, capacity=1)
    first = _student_token(client, world["failing"])
    second = _student_token(client, world["failing2"])
    assert client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(first)).status_code == 200

    again = client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(first))
    assert (again.status_code, again.json()["detail"]) == (409, "Ya estás inscrito en este curso intensivo")
    before = _snapshot(db_session)
    full = client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(second))
    assert (full.status_code, full.json()["detail"]) == (409, "El curso intensivo ya no tiene cupos")
    assert _snapshot(db_session) == before
    assert len(before[1]) == 1
    seen = client.get(PORTAL, headers=_as(second)).json()["courses"][0]
    assert (seen["free"], seen["is_full"]) == (0, True)

    client.post(f"{PORTAL}/{course['id']}/cancel", headers=_as(first))  # the place goes back to the pool
    assert client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(second)).status_code == 200


def test_cancelling_without_an_enrollment_is_refused(client, db_session, world):
    course = _create(client)
    token = _student_token(client, world["failing"])

    refused = client.post(f"{PORTAL}/{course['id']}/cancel", headers=_as(token))

    assert (refused.status_code, refused.json()["detail"]) == (409, "No estás inscrito en este curso intensivo")
    assert db_session.query(ActivityLog).filter(ActivityLog.action == "cancel_intensive_course").count() == 0
    missing = client.post(f"{PORTAL}/999/enroll", headers=_as(token))
    assert (missing.status_code, missing.json()["detail"]) == (404, "Curso intensivo no encontrado")
    assert client.post(f"{PORTAL}/999/cancel", headers=_as(token)).status_code == 404


# ── Access ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("get", ""), ("post", ""), ("get", "/1"), ("put", "/1"), ("post", "/1/close"),
    ("get", "/settings"), ("put", "/settings"),
])
def test_the_admin_api_is_admin_only(client, db_session, method, path):
    from app.models.user import User
    from app.services.auth_service import auth_service

    authorization = client.headers.pop("Authorization")
    try:
        assert getattr(client, method)(f"{ADMIN}{path}").status_code == 401
        docente = User(ci="IC-DOCENTE", full_name="Docente", role="docente", is_active=True,
                       password_hash=auth_service.hash_password("testpass123"))
        db_session.add(docente)
        db_session.flush()
        client.headers["Authorization"] = "Bearer " + auth_service.create_access_token(
            {"sub": str(docente.id), "role": "docente"})
        assert getattr(client, method)(f"{ADMIN}{path}").status_code == 403
    finally:
        client.headers["Authorization"] = authorization


def test_a_student_token_never_opens_the_admin_routes(client, world):
    token = _student_token(client, world["failing"])
    for method, path in (("get", ""), ("get", "/settings"), ("get", "/1"), ("post", "/1/close")):
        assert getattr(client, method)(f"{ADMIN}{path}", headers=_as(token)).status_code == 401
    assert client.put(f"{ADMIN}/settings", headers=_as(token), json={}).status_code == 401


def test_the_student_routes_need_a_student_session(client, world):
    for method, path in (("get", ""), ("post", "/1/enroll"), ("post", "/1/cancel")):
        # The staff token set on the client is not a student session.
        assert getattr(client, method)(f"{PORTAL}{path}").status_code == 401
    authorization = client.headers.pop("Authorization")
    try:
        for method, path in (("get", ""), ("post", "/1/enroll"), ("post", "/1/cancel")):
            assert getattr(client, method)(f"{PORTAL}{path}").status_code == 401
    finally:
        client.headers["Authorization"] = authorization


def test_cancelling_after_the_enrollment_dates_is_refused(client, db_session, world, monkeypatch):
    course = _create(client, theory_hours=40, practice_hours=0)
    token = _student_token(client, world["failing"])
    assert client.post(f"{PORTAL}/{course['id']}/enroll", headers=_as(token)).status_code == 200
    monkeypatch.setattr(intensive_courses, "bolivia_today", lambda: date.fromisoformat(course["enrollment_ends_on"]) + timedelta(days=1))

    response = client.post(f"{PORTAL}/{course['id']}/cancel", headers=_as(token))

    assert (response.status_code, response.json()["detail"]) == (409, "La inscripción al curso intensivo no está abierta")
    assert _snapshot(db_session)[1] != []
