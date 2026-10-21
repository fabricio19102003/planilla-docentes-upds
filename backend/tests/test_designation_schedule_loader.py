from __future__ import annotations

import io
from datetime import date, time

import openpyxl
import pytest

from app.models.academic_management import (
    AcademicGroup,
    AcademicProgram,
    AcademicScheduleAssignment,
    AcademicScheduleBlock,
    AcademicScheduleDraft,
    AcademicSubject,
    Classroom,
    SubjectOffering,
    TeacherAvailability,
)
from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.designation import Designation
from app.models.teacher import Teacher

URL = "/api/admin/academic-management/designation-load"
PERIOD = "II/2026"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def seeded(db_session):
    existing = db_session.get(AppSetting, "ACTIVE_ACADEMIC_PERIOD")
    if existing is None:
        db_session.add(AppSetting(key="ACTIVE_ACADEMIC_PERIOD", value=PERIOD, description="test"))
    else:
        existing.value = PERIOD
    program = AcademicProgram(code="MED-LOAD", name="Medicina carga", active=True)
    db_session.add(program)
    for ci in ("LD-T1", "LD-T2", "LD-T3"):
        db_session.add(Teacher(ci=ci, full_name=f"DOCENTE {ci}"))
    db_session.flush()
    # Anatomía already exists in the catalog with its offering and group; Fisiología does not.
    subject = AcademicSubject(code="MED-101", name="Anatomía Humana I", active=True)
    db_session.add(subject)
    db_session.flush()
    db_session.add(SubjectOffering(subject_id=subject.id, program_id=program.id, academic_period=PERIOD,
                                   semester=1, theory_hours=140, practice_hours=0, active=True))
    db_session.add(AcademicGroup(program_id=program.id, academic_period=PERIOD, semester=1, shift="M",
                                 code="M-1", expected_size=None, active=True))
    db_session.flush()
    db_session.info["program_id"] = program.id
    return db_session


def _designation(db, ci, subject, semester, group, slots, *, start=None, end=None, kind="regular", hours=2):
    item = Designation(
        teacher_ci=ci, subject=subject, semester=semester, group_code=group, academic_period=PERIOD,
        designation_type=kind, weekly_hours=hours, monthly_hours=hours * 4, semester_hours=hours * 20,
        schedule_raw="x", contract_start_date=start, contract_end_date=end,
        schedule_json=[{"dia": day, "hora_inicio": a, "hora_fin": b, "horas_academicas": h} for day, a, b, h in slots],
    )
    db.add(item)
    db.flush()
    return item


def _workbook(rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "DOCENTES TEORICOS"
    sheet.append(["N°", None, "MATERIAS", "SEMESTRE", "M-04", "AULA", "HORARIO", "CARGA HORARIA",
                  "MES", "SEMANA", "REAL", "CI", "FECHA INICIO", "FECHA FIN", "OBSERVACION"])
    for index, (ci, subject, semester, group, room) in enumerate(rows, start=1):
        sheet.append([index, f"DOCENTE {ci}", subject, semester, group, room, "", 40, 8, 2, 38, ci, None, None, None])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _post(client, action, workbook, **form):
    data = {"academic_period": PERIOD, "effective_from": "2026-11-02", **form}
    return client.post(f"{URL}/{action}", data=data, files={"workbook": ("designacion.xlsx", workbook, XLSX)})


def _counts(db):
    db.expire_all()
    return {
        "drafts": db.query(AcademicScheduleDraft).count(),
        "blocks": db.query(AcademicScheduleBlock).count(),
        "subjects": db.query(AcademicSubject).count(),
        "groups": db.query(AcademicGroup).count(),
        "classrooms": db.query(Classroom).count(),
        "availability": db.query(TeacherAvailability).count(),
    }


def _standard(db):
    anatomy = _designation(db, "LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-1",
                           [("lunes", "06:30", "08:55", 3), ("miercoles", "08:00", "09:30", 2)])
    physiology = _designation(db, "LD-T2", "FISIOLOGÍA I", "SEGUNDO", "T-2", [("martes", "13:40", "15:10", 2)])
    workbook = _workbook([
        ("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-01", 19),
        ("LD-T2", "FISIOLOGÍA I", "SEGUNDO", "T-02", "a"),
    ])
    return anatomy, physiology, workbook


def test_preview_plans_the_draft_and_writes_nothing(client, seeded):
    anatomy, physiology, workbook = _standard(seeded)
    before = _counts(seeded)

    response = _post(client, "preview", workbook)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["can_apply"] is True, data["blockers"]
    assert data["blockers"] == []
    assert data["warnings"] == []
    assert data["program_id"] == seeded.info["program_id"]
    assert data["draft_name"] == "Designación vigente II/2026 desde 2026-11-02"
    assert data["counts"] == {"designations": 2, "blocks": 3, "assignments": 3}
    assert data["create"] == {
        "subjects": ["FISIOLOGÍA I"],
        "offerings": 1,
        "groups": ["2 T-2"],
        "classrooms": ["COB-ANTIGUO-P1-AA", "COB-NUEVO-P3-A19"],
        "availability": 3,
    }
    assert [(item["designation_id"], item["weekday"], item["start_time"], item["end_time"],
             item["classroom_code"], item["academic_hours"], item["teacher_ci"], item["effective_from"])
            for item in data["blocks"]] == [
        (anatomy.id, "lunes", "06:30", "08:55", "COB-NUEVO-P3-A19", 3, "LD-T1", "2026-11-02"),
        (physiology.id, "martes", "13:40", "15:10", "COB-ANTIGUO-P1-AA", 2, "LD-T2", "2026-11-02"),
        (anatomy.id, "miercoles", "08:00", "09:30", "COB-NUEVO-P3-A19", 2, "LD-T1", "2026-11-02"),
    ]
    assert data["conflicts"]["summary"]["conflicts"] == 0
    assert len(data["digest"]) == 64
    assert _counts(seeded) == before


def test_apply_creates_the_draft_catalog_and_availability(client, seeded):
    anatomy, _physiology, workbook = _standard(seeded)
    digest = _post(client, "preview", workbook).json()["digest"]

    response = _post(client, "apply", workbook, digest=digest)

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["blocks"] == 3 and result["assignments"] == 3
    draft = seeded.get(AcademicScheduleDraft, result["draft_id"])
    assert draft.status == "draft" and draft.name == "Designación vigente II/2026 desde 2026-11-02"
    blocks = seeded.query(AcademicScheduleBlock).filter_by(draft_id=draft.id).order_by(AcademicScheduleBlock.weekday).all()
    monday = next(item for item in blocks if item.weekday == "monday")
    assert (monday.start_time, monday.end_time, monday.academic_hours, monday.activity_type) == (
        time(6, 30), time(8, 55), 3, "theory")
    assert monday.classroom.code == "COB-NUEVO-P3-A19" and monday.offering.subject.code == "MED-101"
    assert [(a.teacher_ci, a.effective_from, a.effective_to) for a in monday.assignments] == [
        ("LD-T1", date(2026, 11, 2), None)]
    physiology = seeded.query(AcademicSubject).filter_by(name="FISIOLOGÍA I").one()
    offering = seeded.query(SubjectOffering).filter_by(subject_id=physiology.id).one()
    assert (offering.semester, offering.theory_hours, offering.practice_hours) == (2, 40, 0)
    assert seeded.query(AcademicGroup).filter_by(semester=2, code="T-2").one().shift == "T"
    windows = sorted((a.teacher_ci, a.weekday, a.start_time, a.end_time)
                     for a in seeded.query(TeacherAvailability).filter_by(academic_period=PERIOD))
    assert windows == [
        ("LD-T1", "monday", time(6, 30), time(23, 5)),
        ("LD-T1", "wednesday", time(6, 30), time(23, 5)),
        ("LD-T2", "tuesday", time(6, 30), time(23, 5)),
    ]
    assert seeded.query(Classroom).filter_by(code="COB-ANTIGUO-P1-AA").one().capacity == 20
    log = seeded.query(ActivityLog).filter_by(action="designation_schedule_load").one()
    assert log.details["draft_id"] == draft.id and log.details["designations"] == [anatomy.id, _physiology.id]

    conflicts = client.get("/api/admin/academic-management/schedule-conflicts", params={
        "academic_period": PERIOD, "source": "draft", "draft_id": draft.id, "date": "2026-11-02"})
    assert conflicts.status_code == 200 and conflicts.json()["summary"]["blocks"] == 3

    # The same name cannot be loaded twice while that draft is active.
    again = _post(client, "preview", workbook).json()
    assert again["can_apply"] is False
    assert [item["code"] for item in again["blockers"]] == ["draft_exists"]


def test_teacher_handover_becomes_successive_assignments_of_one_block(client, seeded):
    slots = [("jueves", "10:00", "11:30", 2)]
    _designation(seeded, "LD-T1", "ANATOMÍA HUMANA I", "1", "M-1", slots, end=date(2026, 11, 15))
    _designation(seeded, "LD-T3", "ANATOMÍA HUMANA I", "1", "M-1", slots, start=date(2026, 11, 16))
    workbook = _workbook([("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", 3)])

    data = _post(client, "preview", workbook).json()

    assert data["blockers"] == []
    assert data["counts"] == {"designations": 2, "blocks": 1, "assignments": 2}
    result = _post(client, "apply", workbook, digest=data["digest"]).json()
    block = seeded.query(AcademicScheduleBlock).filter_by(draft_id=result["draft_id"]).one()
    assert block.classroom.code == "COB-ANTIGUO-P1-A3"
    assert sorted((a.teacher_ci, a.effective_from, a.effective_to) for a in block.assignments) == [
        ("LD-T1", date(2026, 11, 2), date(2026, 11, 15)),
        ("LD-T3", date(2026, 11, 16), None),
    ]


def test_blockers_are_listed_per_row_and_apply_writes_nothing(client, seeded):
    missing_room = _designation(seeded, "LD-T1", "ANATOMÍA HUMANA I", "1", "M-1", [("lunes", "08:00", "09:30", 2)])
    co_teacher = _designation(seeded, "LD-T2", "ANATOMÍA HUMANA I", "1", "M-1", [("lunes", "08:00", "09:30", 2)])
    odd_time = _designation(seeded, "LD-T3", "BIOQUÍMICA", "1", "M-1", [("viernes", "07:12", "08:00", 1)])
    workbook = _workbook([
        ("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", None),
        ("LD-T2", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", 99),
        ("LD-T3", "BIOQUÍMICA", "PRIMERO", "M-1", 4),
    ])
    before = _counts(seeded)

    data = _post(client, "preview", workbook).json()

    assert data["can_apply"] is False
    assert sorted((item["code"], item["designation_id"]) for item in data["blockers"]) == sorted([
        ("missing_classroom", missing_room.id),
        ("missing_classroom", co_teacher.id),
        ("invalid_time", odd_time.id),
    ])
    blocker = next(item for item in data["blockers"] if item["designation_id"] == odd_time.id)
    assert blocker["teacher_ci"] == "LD-T3" and blocker["subject"] == "BIOQUÍMICA" and blocker["message"]

    refused = _post(client, "apply", workbook, digest=data["digest"])
    assert refused.status_code == 409
    assert {item["code"] for item in refused.json()["detail"]["blockers"]} == {"missing_classroom", "invalid_time"}
    assert _counts(seeded) == before


def test_two_teachers_in_the_same_block_and_dates_is_a_blocker(client, seeded):
    first = _designation(seeded, "LD-T1", "ANATOMÍA HUMANA I", "1", "M-1", [("lunes", "08:00", "09:30", 2)])
    second = _designation(seeded, "LD-T2", "ANATOMÍA HUMANA I", "1", "M-1", [("lunes", "08:00", "09:30", 2)])
    workbook = _workbook([("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", 5),
                          ("LD-T2", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", 5)])

    data = _post(client, "preview", workbook).json()

    assert [(item["code"], item["designation_id"]) for item in data["blockers"]] == [("duplicate_assignment", second.id)]
    assert first.id != second.id


def test_stale_digest_is_refused(client, seeded):
    _anatomy, _physiology, workbook = _standard(seeded)
    digest = _post(client, "preview", workbook).json()["digest"]
    _designation(seeded, "LD-T3", "BIOQUÍMICA", "1", "M-1", [("viernes", "10:00", "11:30", 2)])
    before = _counts(seeded)

    response = _post(client, "apply", workbook, digest=digest)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_preview"
    assert _counts(seeded) == before


def test_ended_practice_and_other_period_designations_are_not_loaded(client, seeded):
    kept = _designation(seeded, "LD-T1", "ANATOMÍA HUMANA I", "1", "M-1", [("lunes", "08:00", "09:30", 2)])
    _designation(seeded, "LD-T2", "ANATOMÍA HUMANA I", "1", "M-1", [("martes", "08:00", "09:30", 2)],
                 end=date(2026, 11, 1))
    _designation(seeded, "LD-T3", "ANATOMÍA HUMANA I PRACTICA", "1", "M-1", [("jueves", "08:00", "09:30", 2)],
                 kind="practice")
    other = _designation(seeded, "LD-T3", "BIOQUÍMICA", "1", "M-1", [("viernes", "08:00", "09:30", 2)])
    other.academic_period = "I/2026"
    seeded.flush()
    workbook = _workbook([("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", 6)])

    data = _post(client, "preview", workbook).json()

    assert [item["designation_id"] for item in data["blocks"]] == [kept.id]
    assert data["blockers"] == []


def test_subject_outside_its_curriculum_semester_is_a_warning(client, seeded):
    misplaced = _designation(seeded, "LD-T2", "ANATOMÍA HUMANA I", "SEGUNDO", "M-1", [("lunes", "08:00", "09:30", 2)])
    workbook = _workbook([("LD-T2", "ANATOMÍA HUMANA I", "SEGUNDO", "M-1", 7)])

    data = _post(client, "preview", workbook).json()

    assert data["can_apply"] is True
    assert data["create"]["offerings"] == 1
    assert data["warnings"] == [{
        "code": "subject_other_semester", "designation_id": misplaced.id, "teacher_ci": "LD-T2",
        "subject": "ANATOMÍA HUMANA I", "semester": "SEGUNDO", "group_code": "M-1",
        "message": "La materia MED-101 está en la malla del semestre 1, pero la designación dice semestre 2: se creará una oferta en el semestre 2.",
    }]


def test_request_validation(client, seeded):
    _anatomy, _physiology, workbook = _standard(seeded)
    assert _post(client, "preview", workbook, academic_period="").status_code == 422
    bad_type = client.post(f"{URL}/preview", data={"academic_period": PERIOD, "effective_from": "2026-11-02"},
                           files={"workbook": ("designacion.csv", b"a,b", "text/csv")})
    assert bad_type.status_code == 415
    assert _post(client, "apply", workbook).status_code == 422  # digest is required
    wrong_sheet = openpyxl.Workbook()
    buffer = io.BytesIO()
    wrong_sheet.save(buffer)
    missing = _post(client, "preview", buffer.getvalue())
    assert missing.status_code == 400
    assert "DOCENTES TEORICOS" in missing.json()["detail"]
