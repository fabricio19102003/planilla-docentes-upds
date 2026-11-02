"""Published schedule in the student portal: main group, recursado/pending groups and intensive courses (academic-phase3 S3)."""
from __future__ import annotations

from datetime import date, time

import pytest

from app.models.academic_management import (
    AcademicGroup, AcademicSchedulePublication, AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock, AcademicScheduleDraft, AcademicSubject,
)
from app.models.academic_records import CurriculumPlan
from app.models.intensive_courses import IntensiveCourse, IntensiveEnrollment
from app.models.student_portal import ReenrollmentRequest
from app.models.teacher import Teacher
from app.services import reenrollment
from tests.test_reenrollment_api import _group, _student_token, _window
from tests.test_reenrollment_eligibility import I_2026, _load
from tests.test_student_accounts import _as

ADMIN = "/api/admin/reenrollment"
PORTAL = "/api/student-portal"
URL = f"{PORTAL}/schedule"
TODAY = date(2027, 2, 10)

NO_REQUEST = "Todavía no enviaste tu solicitud de rematrícula."
NOT_DONE = "Tu horario aparece cuando Registro complete tu rematrícula."
NOT_PUBLISHED = "El horario de I/2027 todavía no fue publicado."


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(reenrollment, "bolivia_today", lambda: TODAY)


@pytest.fixture
def world(client, db_session):
    good = _load(db_session, "SCH-GOOD", [
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
    ])
    other = _load(db_session, "SCH-OTHER", [
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
    ])
    failing = _load(db_session, "SCH-FAIL", [
        ("Inglés Técnico I LIN-0130", "Reprobado", 40, I_2026),
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
    ])
    for code, name in (("T-A", "Docente A"), ("T-B", "Docente B"), ("T-100", "Docente Cien"),
                       ("T-200", "Docente Doscientos")):
        db_session.add(Teacher(ci=code, full_name=name))
    groups = {
        "M-01": _group(db_session, 3, "M-01"),
        "N-01": _group(db_session, 3, "N-01", shift="N"),
        "S1-M-01": _group(db_session, 1, "M-01"),
        "S1-N-01": _group(db_session, 1, "N-01", shift="N"),
        "OLD": _group(db_session, 3, "M-09", period="II/2026"),
    }
    db_session.flush()
    _window(client, starts="2027-01-25", ends="2027-02-20")
    return {"good": good, "other": other, "failing": failing, "groups": groups}


def _program_id(db_session):
    return db_session.query(CurriculumPlan).one().program_id


_sequence = iter(range(1, 10_000))


def _block(group, code, name, weekday="monday", start="08:00", end="09:30", room=("A-1", "Aula 1"),
           activity="theory", teachers=(("T-A", "Docente A", date(2027, 1, 1), None),)):
    return {"group": group, "code": code, "name": name, "weekday": weekday, "start": start, "end": end,
            "room": room, "activity": activity, "teachers": teachers}


def _publish(db_session, blocks, *, period="I/2027", effective_from=TODAY, sequence=1):
    program_id = _program_id(db_session)
    n = next(_sequence)
    draft = AcademicScheduleDraft(program_id=program_id, academic_period=period, name=f"d{n}",
                                  normalized_name=f"d{n}", status="published")
    db_session.add(draft)
    db_session.flush()
    publication = AcademicSchedulePublication(
        program_id=program_id, academic_period=period, effective_from=effective_from, sequence=sequence,
        content_digest="0" * 64, source_draft_id=draft.id,
    )
    db_session.add(publication)
    db_session.flush()
    for spec in blocks:
        group = spec["group"]
        subject = db_session.query(AcademicSubject).filter_by(code=spec["code"]).first()
        row = AcademicSchedulePublishedBlock(
            publication_id=publication.id, source_block_id=next(_sequence), source_offering_id=1,
            source_subject_id=subject.id if subject else 0, source_group_id=group.id,
            source_classroom_id=1, subject_code=spec["code"], subject_name=spec["name"],
            group_code=group.code, semester=group.semester, classroom_code=spec["room"][0],
            classroom_name=spec["room"][1], activity_type=spec["activity"], weekday=spec["weekday"],
            start_time=time.fromisoformat(spec["start"]), end_time=time.fromisoformat(spec["end"]),
        )
        db_session.add(row)
        db_session.flush()
        for ci, full_name, starts, ends in spec["teachers"]:
            db_session.add(AcademicSchedulePublishedAssignment(
                publication_block_id=row.id, source_assignment_id=next(_sequence), teacher_ci=ci,
                teacher_name=full_name, effective_from=starts, effective_to=ends,
            ))
    db_session.flush()
    return publication


def _submit(client, student, main_group, items=()):
    token = _student_token(client, student)
    response = client.post(f"{PORTAL}/reenrollment/request", headers=_as(token), json={
        "main_group_id": main_group.id,
        "items": [{"subject_code": code, "group_id": group.id} for code, group in items],
    })
    assert response.status_code == 200, response.text
    return token, response.json()


def _complete(client, request_id):
    response = client.post(f"{ADMIN}/requests/{request_id}/complete")
    assert response.status_code == 200, response.text


def _view(client, token):
    response = client.get(URL, headers=_as(token))
    assert response.status_code == 200, response.text
    return response.json()


def _shape(entries):
    return [(e["source"], e["subject_code"], e["group_code"], e["weekday"], e["start_time"]) for e in entries]


def _regular_codes(request):
    return [item["code"] for item in request["snapshot"]["regular"] if item["code"]]


# ── Status messages ──────────────────────────────────────────────────────────

def test_without_a_request_the_status_says_so(client, world):
    token = _student_token(client, world["good"])

    body = _view(client, token)

    assert body["entries"] == []
    assert body["status"] == {"code": "no_request", "message": NO_REQUEST}


def test_without_any_window_the_status_still_says_there_is_no_request(client, db_session, world):
    from app.models.student_portal import ReenrollmentWindow

    db_session.query(ReenrollmentWindow).delete()
    db_session.flush()
    token = _student_token(client, world["good"])

    assert _view(client, token)["status"] == {"code": "no_request", "message": NO_REQUEST}


def test_a_pending_or_observed_request_shows_no_schedule_yet(client, db_session, world):
    groups = world["groups"]
    _publish(db_session, [_block(groups["M-01"], "FUN 0300", "Bioquímica III")])
    token, request = _submit(client, world["good"], groups["M-01"])

    pending = _view(client, token)
    assert pending["entries"] == []
    assert pending["status"] == {"code": "not_done", "message": NOT_DONE}

    observed = client.post(f"{ADMIN}/requests/{request['id']}/observe",
                           json={"reason": "otro", "message": "Falta un papel"})
    assert observed.status_code == 200, observed.text
    again = _view(client, token)
    assert again["entries"] == []
    assert again["status"] == {"code": "not_done", "message": NOT_DONE}


def test_a_done_request_without_a_publication_says_the_term_is_not_published(client, db_session, world):
    groups = world["groups"]
    token, request = _submit(client, world["good"], groups["M-01"])
    _complete(client, request["id"])
    # Another term's publication does not count.
    _publish(db_session, [_block(groups["OLD"], "FUN 0300", "Bioquímica III")], period="II/2026",
             effective_from=date(2026, 8, 1))

    body = _view(client, token)

    assert body["entries"] == []
    assert body["status"] == {"code": "not_published", "message": NOT_PUBLISHED}


# ── Main group and request items ─────────────────────────────────────────────

def test_a_done_request_shows_the_main_group_filtered_to_the_regular_subjects(client, db_session, world):
    groups = world["groups"]
    token, request = _submit(client, world["good"], groups["M-01"])
    regular = _regular_codes(request)
    assert "FUN 0300" in regular and "FUN 0200" not in regular
    _publish(db_session, [
        _block(groups["M-01"], "FUN 0300", "Bioquímica III", weekday="tuesday", start="10:00", end="11:30",
               room=("L-2", "Laboratorio 2"), activity="practice"),
        _block(groups["M-01"], "CIR 0300", "Cirugía III", weekday="monday", start="08:00", end="09:30"),
        # Same group, but a subject of another semester: not part of this student's regular load.
        _block(groups["M-01"], "FUN 0200", "Bioquímica II", weekday="monday", start="14:00", end="15:30"),
        # Another group of the same semester.
        _block(groups["N-01"], "FUN 0300", "Bioquímica III", weekday="monday", start="19:00", end="20:30"),
    ])
    _complete(client, request["id"])

    body = _view(client, token)

    assert body["status"] == {"code": "ok", "message": None}
    assert _shape(body["entries"]) == [
        ("grupo", "CIR 0300", "M-01", "monday", "08:00"),
        ("grupo", "FUN 0300", "M-01", "tuesday", "10:00"),
    ]
    assert body["entries"][1] == {
        "source": "grupo", "subject_code": "FUN 0300", "subject_name": "Bioquímica III", "group_code": "M-01",
        "weekday": "tuesday", "start_time": "10:00", "end_time": "11:30",
        "classroom": {"code": "L-2", "name": "Laboratorio 2"}, "activity_type": "practice",
        "teacher_name": "Docente A", "term_code": "I/2027", "effective_from": "2027-02-10",
        "is_upcoming": False,
    }


def test_a_recursado_item_shows_the_block_of_its_own_group_and_subject_only(client, db_session, world):
    groups = world["groups"]
    token, request = _submit(client, world["failing"], groups["N-01"], [("LIN 0130", groups["S1-M-01"])])
    _publish(db_session, [
        _block(groups["S1-M-01"], "LIN 0130", "Inglés Técnico I", weekday="friday", start="08:00", end="09:30"),
        # Same subject in another group and another subject in the chosen group.
        _block(groups["S1-N-01"], "LIN 0130", "Inglés Técnico I", weekday="friday", start="19:00", end="20:30"),
        _block(groups["S1-M-01"], "MRF 0100", "Anatomía I", weekday="monday", start="08:00", end="09:30"),
        _block(groups["N-01"], "LIN 0330", "Inglés Técnico III", weekday="monday", start="19:00", end="20:30"),
    ])
    _complete(client, request["id"])

    body = _view(client, token)

    assert _shape(body["entries"]) == [
        ("grupo", "LIN 0330", "N-01", "monday", "19:00"),
        ("recursado", "LIN 0130", "M-01", "friday", "08:00"),
    ]


def test_a_pending_item_is_labelled_pendiente(client, db_session, world):
    groups = world["groups"]
    retired = _load(db_session, "SCH-RETIRED", [
        ("Anatomía Humana I MRF-0100", "Aprobado", 80, I_2026),
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 70, I_2026),
        ("Caso Básico Clínico Integrador II CBC-0200", "Retirado", 0, I_2026),
    ])
    group = _group(db_session, 2, "M-01")
    token, request = _submit(client, retired, groups["M-01"], [("CBC 0200", group)])
    _publish(db_session, [_block(group, "CBC 0200", "Caso Básico II", weekday="wednesday")])
    _complete(client, request["id"])

    assert _shape(_view(client, token)["entries"]) == [("pendiente", "CBC 0200", "M-01", "wednesday", "08:00")]


def test_a_student_never_sees_the_blocks_of_another_students_group(client, db_session, world):
    groups = world["groups"]
    mine, my_request = _submit(client, world["good"], groups["M-01"])
    theirs, their_request = _submit(client, world["other"], groups["N-01"])
    _publish(db_session, [
        _block(groups["M-01"], "FUN 0300", "Bioquímica III", start="08:00", end="09:30"),
        _block(groups["N-01"], "FUN 0300", "Bioquímica III", start="19:00", end="20:30"),
    ])
    _complete(client, my_request["id"])

    assert _shape(_view(client, mine)["entries"]) == [("grupo", "FUN 0300", "M-01", "monday", "08:00")]
    # The other student's request is still pending: nothing, whatever the groups hold.
    other = _view(client, theirs)
    assert (other["entries"], other["status"]["code"]) == ([], "not_done")
    _complete(client, their_request["id"])
    assert _shape(_view(client, theirs)["entries"]) == [("grupo", "FUN 0300", "N-01", "monday", "19:00")]
    assert _shape(_view(client, mine)["entries"]) == [("grupo", "FUN 0300", "M-01", "monday", "08:00")]


# ── Publication selection ────────────────────────────────────────────────────

def test_the_publication_in_force_today_wins_over_older_and_future_ones(client, db_session, world):
    groups = world["groups"]
    token, request = _submit(client, world["good"], groups["M-01"])
    _complete(client, request["id"])
    _publish(db_session, [_block(groups["M-01"], "FUN 0300", "Bioquímica III", start="07:00", end="08:00")],
             effective_from=date(2027, 1, 1), sequence=1)
    _publish(db_session, [_block(groups["M-01"], "FUN 0300", "Bioquímica III", start="09:00", end="10:00")],
             effective_from=date(2027, 2, 1), sequence=1)
    _publish(db_session, [_block(groups["M-01"], "FUN 0300", "Bioquímica III", start="10:00", end="11:00")],
             effective_from=date(2027, 2, 1), sequence=2)
    _publish(db_session, [_block(groups["M-01"], "FUN 0300", "Bioquímica III", start="11:00", end="12:00")],
             effective_from=date(2027, 3, 1), sequence=1)

    body = _view(client, token)

    assert [(e["start_time"], e["effective_from"], e["is_upcoming"]) for e in body["entries"]] == [
        ("10:00", "2027-02-01", False),
    ]
    assert body["status"]["code"] == "ok"


def test_only_a_future_publication_is_shown_with_its_date_and_its_teachers_on_that_date(client, db_session, world):
    groups = world["groups"]
    token, request = _submit(client, world["good"], groups["M-01"])
    _complete(client, request["id"])
    _publish(db_session, [_block(groups["M-01"], "FUN 0300", "Bioquímica III", teachers=(
        ("T-A", "Docente A", date(2027, 1, 1), date(2027, 3, 14)),
        ("T-B", "Docente B", date(2027, 3, 15), None),
    ))], effective_from=date(2027, 3, 1), sequence=1)
    # The earliest upcoming one wins, and among the same date the highest sequence.
    _publish(db_session, [_block(groups["M-01"], "FUN 0300", "Bioquímica III", start="15:00", end="16:00",
                                 teachers=(("T-B", "Docente B", date(2027, 1, 1), None),))],
             effective_from=date(2027, 4, 1), sequence=1)

    body = _view(client, token)

    assert [(e["start_time"], e["teacher_name"], e["effective_from"], e["is_upcoming"])
            for e in body["entries"]] == [("08:00", "Docente A", "2027-03-01", True)]
    assert body["effective_from"] == "2027-03-01"
    assert body["status"] == {"code": "ok", "message": None}


def test_the_teacher_is_the_assignment_effective_today(client, db_session, world, monkeypatch):
    groups = world["groups"]
    token, request = _submit(client, world["good"], groups["M-01"])
    _complete(client, request["id"])
    _publish(db_session, [
        _block(groups["M-01"], "FUN 0300", "Bioquímica III", start="08:00", end="09:00", teachers=(
            ("T-A", "Docente A", date(2027, 1, 1), date(2027, 2, 9)),
            ("T-B", "Docente B", date(2027, 2, 10), None),
        )),
        _block(groups["M-01"], "CIR 0300", "Cirugía III", start="09:00", end="10:00", teachers=(
            ("T-A", "Docente A", date(2027, 1, 1), date(2027, 2, 9)),
        )),
        _block(groups["M-01"], "INF 0310", "Informática III", start="10:00", end="11:00", teachers=()),
    ], effective_from=date(2027, 1, 1))

    teachers = {e["subject_code"]: e["teacher_name"] for e in _view(client, token)["entries"]}
    assert teachers == {"FUN 0300": "Docente B", "CIR 0300": None, "INF 0310": None}

    monkeypatch.setattr(reenrollment, "bolivia_today", lambda: date(2027, 2, 9))
    teachers = {e["subject_code"]: e["teacher_name"] for e in _view(client, token)["entries"]}
    assert teachers == {"FUN 0300": "Docente A", "CIR 0300": "Docente A", "INF 0310": None}


# ── Intensive courses ────────────────────────────────────────────────────────

def _course(db_session, student, *, code="LIN 0130", term="VER/2027", teacher="T-100", enroll=True):
    subject = db_session.query(AcademicSubject).filter_by(code=code).one()
    course = IntensiveCourse(
        term_code=term, subject_id=subject.id, teacher_ci=teacher, capacity=5,
        enrollment_starts_on=date(2027, 1, 1), enrollment_ends_on=date(2027, 1, 20),
        theory_hours=40, practice_hours=0,
    )
    db_session.add(course)
    db_session.flush()
    if enroll:
        db_session.add(IntensiveEnrollment(course_id=course.id, student_id=student.id))
        db_session.flush()
    return course


def test_an_enrolled_intensive_course_shows_the_blocks_of_its_teachers_group(client, db_session, world):
    groups = world["groups"]
    token = _student_token(client, world["failing"])
    _course(db_session, world["failing"])
    ver_a = _group(db_session, 1, "V-A", period="VER/2027")
    ver_b = _group(db_session, 1, "V-B", period="VER/2027")
    ver_c = _group(db_session, 1, "V-C", period="VER/2027")
    _publish(db_session, [
        _block(ver_a, "LIN 0130", "Inglés Técnico I", weekday="monday", start="08:00", end="10:00",
               teachers=(("T-100", "Docente Cien", date(2027, 1, 1), None),)),
        _block(ver_a, "LIN 0130", "Inglés Técnico I", weekday="wednesday", start="08:00", end="10:00",
               teachers=(("T-100", "Docente Cien", date(2027, 1, 1), None),)),
        _block(ver_b, "LIN 0130", "Inglés Técnico I", weekday="tuesday", start="08:00", end="10:00",
               teachers=(("T-200", "Docente Doscientos", date(2027, 1, 1), None),)),
        _block(ver_c, "LIN 0130", "Inglés Técnico I", weekday="thursday", start="08:00", end="10:00",
               teachers=(("T-100", "Docente Cien", date(2027, 3, 1), None),)),
        _block(ver_a, "MRF 0100", "Anatomía I", weekday="friday", start="08:00", end="10:00"),
    ], period="VER/2027", effective_from=date(2027, 1, 15))

    body = _view(client, token)

    assert _shape(body["entries"]) == [
        ("intensivo", "LIN 0130", "V-A", "monday", "08:00"),
        ("intensivo", "LIN 0130", "V-A", "wednesday", "08:00"),
    ]
    assert {(e["teacher_name"], e["term_code"]) for e in body["entries"]} == {("Docente Cien", "VER/2027")}
    assert body["unscheduled"] == []
    # The request side is independent of the intensive course.
    assert body["status"]["code"] == "no_request"


def test_a_single_matching_group_is_kept_whoever_teaches_it(client, db_session, world):
    token = _student_token(client, world["failing"])
    _course(db_session, world["failing"])
    ver_a = _group(db_session, 1, "V-A", period="VER/2027")
    _publish(db_session, [_block(ver_a, "LIN 0130", "Inglés Técnico I", teachers=(
        ("T-200", "Docente Doscientos", date(2027, 1, 1), None),))], period="VER/2027",
        effective_from=date(2027, 1, 15))

    assert _shape(_view(client, token)["entries"]) == [("intensivo", "LIN 0130", "V-A", "monday", "08:00")]


def test_several_groups_none_of_the_courses_teacher_leave_the_course_without_schedule(client, db_session, world):
    token = _student_token(client, world["failing"])
    _course(db_session, world["failing"])
    ver_a = _group(db_session, 1, "V-A", period="VER/2027")
    ver_b = _group(db_session, 1, "V-B", period="VER/2027")
    _publish(db_session, [
        _block(ver_a, "LIN 0130", "Inglés Técnico I", teachers=(("T-200", "Docente Doscientos", date(2027, 1, 1), None),)),
        _block(ver_b, "LIN 0130", "Inglés Técnico I", teachers=(("T-A", "Docente A", date(2027, 1, 1), None),)),
    ], period="VER/2027", effective_from=date(2027, 1, 15))

    body = _view(client, token)

    assert body["entries"] == []
    assert body["unscheduled"] == [{"source": "intensivo", "subject_code": "LIN 0130",
                                    "subject_name": "Inglés Técnico I", "term_code": "VER/2027"}]


def test_an_intensive_course_without_a_publication_is_returned_with_an_empty_schedule(client, db_session, world):
    token = _student_token(client, world["failing"])
    _course(db_session, world["failing"])

    body = _view(client, token)

    assert body["entries"] == []
    assert [(c["subject_code"], c["term_code"]) for c in body["unscheduled"]] == [("LIN 0130", "VER/2027")]


def test_a_student_only_sees_the_intensive_courses_they_are_enrolled_in(client, db_session, world):
    mine = _student_token(client, world["failing"])
    theirs = _student_token(client, world["other"])
    _course(db_session, world["failing"])
    ver_a = _group(db_session, 1, "V-A", period="VER/2027")
    _publish(db_session, [_block(ver_a, "LIN 0130", "Inglés Técnico I")], period="VER/2027",
             effective_from=date(2027, 1, 15))

    assert len(_view(client, mine)["entries"]) == 1
    other = _view(client, theirs)
    assert (other["entries"], other["unscheduled"]) == ([], [])


def test_requests_and_intensive_courses_are_combined_in_week_order(client, db_session, world):
    groups = world["groups"]
    token, request = _submit(client, world["failing"], groups["N-01"], [("LIN 0130", groups["S1-M-01"])])
    _complete(client, request["id"])
    _course(db_session, world["failing"], enroll=True)
    ver_a = _group(db_session, 1, "V-A", period="VER/2027")
    _publish(db_session, [_block(groups["S1-M-01"], "LIN 0130", "Inglés Técnico I", weekday="tuesday")],
             effective_from=date(2027, 2, 1))
    _publish(db_session, [_block(ver_a, "LIN 0130", "Inglés Técnico I", weekday="monday")], period="VER/2027",
             effective_from=date(2027, 1, 15))

    body = _view(client, token)

    assert [(e["source"], e["weekday"]) for e in body["entries"]] == [
        ("intensivo", "monday"), ("recursado", "tuesday"),
    ]
    assert db_session.query(ReenrollmentRequest).count() == 1


# ── Access ───────────────────────────────────────────────────────────────────

def test_the_schedule_needs_a_student_session(client, world):
    staff = client.get(URL)  # the client carries an admin token
    assert staff.status_code == 401
    client.headers.pop("Authorization")
    assert client.get(URL).status_code == 401
    forged = client.get(URL, headers=_as("not-a-token"))
    assert forged.status_code == 401
