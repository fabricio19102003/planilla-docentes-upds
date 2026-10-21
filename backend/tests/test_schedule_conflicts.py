from __future__ import annotations

from datetime import date

import pytest

from app.models.academic_management import Classroom
from app.models.app_setting import AppSetting
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services.academic_schedule_conflicts_service import analyze
from app.services.academic_schedule_view_service import ViewBlock

URL = "/api/admin/academic-management/schedule-conflicts"
PERIOD = "I/2026"


def _block(key, *, teacher="T1", group="M-1", semester=1, subject="Anatomia", activity="theory",
           weekday="lunes", start="08:00", end="09:30", room=None):
    return ViewBlock(
        key=key, semester=semester, group_code=group, subject_code=None, subject_name=subject,
        activity_type=activity, weekday=weekday, start_time=start, end_time=end,
        teacher_ci=teacher, teacher_name=f"DOCENTE {teacher}" if teacher else None,
        classroom_code=room, classroom_name=None, source_type="draft",
    )


def _kinds(result):
    return sorted((item["kind"], item["severity"], tuple(sorted(item["keys"]))) for item in result["clashes"])


def test_clashes_over_five_minutes_are_conflicts_and_shorter_overlaps_are_ignored():
    blocks = [
        _block("a", teacher="T1", group="M-1", start="08:00", end="09:30", room="R1"),
        _block("b", teacher="T1", group="M-2", subject="Fisiologia", start="09:20", end="10:50", room="R2"),
        _block("c", teacher="T2", group="M-3", subject="Bioquimica", start="09:25", end="11:00", room="R1"),
        _block("d", teacher="T3", group="M-2", subject="Histologia", start="10:45", end="12:00", room="R3"),
    ]

    result = analyze(blocks, rooms=[], load_threshold=40, academic_hour_minutes=45)

    # a/b: same teacher 10 min; a/c: same room exactly 5 min (tolerated); b/d: same group 5 min (tolerated).
    assert _kinds(result) == [("teacher", "conflict", ("a", "b"))]
    clash = result["clashes"][0]
    assert clash["weekday"] == "lunes"
    assert (clash["start_time"], clash["end_time"], clash["overlap_minutes"]) == ("09:20", "09:30", 10)
    assert [item["key"] for item in clash["blocks"]] == ["a", "b"]
    assert result["summary"]["conflicts"] == 1
    assert result["tolerance_minutes"] == 5


def test_room_and_group_clashes_and_split_group_warning():
    blocks = [
        _block("theory", teacher="T1", subject="Anatomia", activity="theory", start="08:00", end="09:30", room="R1"),
        _block("practice", teacher="T2", subject="Anatomia", activity="practice", start="08:00", end="09:30", room="LAB"),
        _block("other", teacher="T3", subject="Fisiologia", group="T-1", start="08:30", end="10:00", room="R1"),
        _block("same-group", teacher="T4", subject="Bioquimica", start="09:00", end="10:00", room="R9"),
    ]

    result = analyze(blocks, rooms=[], load_threshold=40, academic_hour_minutes=45)

    assert _kinds(result) == [
        ("classroom", "conflict", ("other", "theory")),
        ("group", "conflict", ("practice", "same-group")),
        ("group", "conflict", ("same-group", "theory")),
        ("split_group", "warning", ("practice", "theory")),
    ]
    assert result["summary"] == {
        "conflicts": 3, "warnings": 1, "unassigned": 0, "overloaded_teachers": 0, "blocks": 4,
        "blocks_without_room": 0,
    }


def test_unassigned_blocks_teacher_load_and_free_slots():
    blocks = [
        _block("a", teacher="T1", weekday="lunes", start="08:00", end="09:30", room="R1"),
        _block("b", teacher="T1", weekday="martes", start="08:00", end="09:30", room="R1"),
        _block("c", teacher="T1", weekday="miercoles", start="19:00", end="20:30", room=None),
        _block("d", teacher="", weekday="lunes", start="10:00", end="11:00", room="R2"),
    ]

    result = analyze(blocks, rooms=["R1", "R2"], load_threshold=5, academic_hour_minutes=45)

    assert [item["key"] for item in result["unassigned"]] == ["d"]
    assert result["teacher_loads"] == [
        {"teacher_ci": "T1", "teacher_name": "DOCENTE T1", "weekly_minutes": 270, "weekly_hours": 6.0,
         "blocks": 3, "over_threshold": True},
    ]
    assert result["summary"]["overloaded_teachers"] == 1
    assert result["summary"]["blocks_without_room"] == 1
    monday = [item for item in result["free_slots"]["groups"] if item["weekday"] == "lunes"]
    # The 30-minute gap 09:30–10:00 is shorter than 45 minutes and is not listed.
    assert monday == [
        {"semester": 1, "group_code": "M-1", "weekday": "lunes", "start_time": "06:30", "end_time": "08:00", "minutes": 90},
        {"semester": 1, "group_code": "M-1", "weekday": "lunes", "start_time": "11:00", "end_time": "23:05", "minutes": 725},
    ]
    saturday = [item for item in result["free_slots"]["groups"] if item["weekday"] == "sabado"]
    assert saturday == [{"semester": 1, "group_code": "M-1", "weekday": "sabado",
                         "start_time": "06:30", "end_time": "23:05", "minutes": 995}]
    r2_monday = [item for item in result["free_slots"]["rooms"]
                 if item["classroom_code"] == "R2" and item["weekday"] == "lunes"]
    assert [(item["start_time"], item["end_time"]) for item in r2_monday] == [("06:30", "10:00"), ("11:00", "23:05")]


@pytest.fixture
def seeded(db_session):
    for key, value in (("ACTIVE_ACADEMIC_PERIOD", PERIOD), ("ACADEMIC_HOUR_MINUTES", "45")):
        existing = db_session.get(AppSetting, key)
        if existing is None:
            db_session.add(AppSetting(key=key, value=value, description="test"))
        else:
            existing.value = value
    for ci in ("CF-T1", "CF-T2"):
        db_session.add(Teacher(ci=ci, full_name=f"DOCENTE {ci}"))
    db_session.add(Classroom(code="COB-NUEVO-P2-A11", name="NUEVO / Piso 2 / Aula 11", campus="Cobija",
                             capacity=35, classroom_type="classroom", resources=[], active=True))
    for ci, subject, group, start, end in (
        ("CF-T1", "Anatomia", "M-1", "08:00", "09:30"),
        ("CF-T1", "Fisiologia", "M-2", "09:00", "10:30"),
        ("CF-T2", "Bioquimica", "T-1", "15:00", "16:30"),
    ):
        db_session.add(Designation(
            teacher_ci=ci, subject=subject, semester="1", group_code=group, academic_period=PERIOD,
            designation_type="regular", weekly_hours=2, monthly_hours=8, schedule_raw="x",
            schedule_json=[{"dia": "lunes", "hora_inicio": start, "hora_fin": end, "horas_academicas": 2}],
        ))
    db_session.flush()
    return db_session


def test_endpoint_reports_current_schedule_conflicts(client, seeded):
    response = client.get(URL, params={"academic_period": PERIOD, "date": "2026-05-18", "load_threshold": 3})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source"] == "current" and data["reference_date"] == "2026-05-18"
    assert data["load_threshold"] == 3
    assert [(item["kind"], item["teacher_ci"], item["overlap_minutes"]) for item in data["clashes"]] == [
        ("teacher", "CF-T1", 30),
    ]
    assert [(item["teacher_ci"], item["over_threshold"]) for item in data["teacher_loads"]] == [
        ("CF-T1", True), ("CF-T2", False),
    ]
    # Legacy theory has no room: the report says so instead of claiming free rooms.
    assert data["summary"]["blocks_without_room"] == 3
    assert {item["classroom_code"] for item in data["free_slots"]["rooms"]} == {"COB-NUEVO-P2-A11"}


def test_endpoint_validates_source_and_threshold(client, seeded):
    assert client.get(URL, params={"academic_period": PERIOD, "source": "draft"}).status_code == 422
    assert client.get(URL, params={"academic_period": PERIOD, "load_threshold": 0}).status_code == 422
    missing = client.get(URL, params={"academic_period": PERIOD, "source": "draft", "draft_id": 999999})
    assert missing.status_code == 404
    default = client.get(URL, params={"academic_period": PERIOD, "date": date(2026, 5, 18).isoformat()})
    assert default.json()["load_threshold"] == 40
