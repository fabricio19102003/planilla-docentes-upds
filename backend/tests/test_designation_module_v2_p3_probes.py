"""Verifier probes for designation-module-v2 P3 (S4, S8, T7b, S7)."""
from __future__ import annotations

import pytest

from app.models.academic_management import (
    AcademicSchedulePublication, AcademicScheduleDraft, AcademicScheduleBlock, AcademicScheduleAssignment,
    Classroom, TeacherAvailability,
)
from app.models.designation import Designation
from app.services.academic_schedule_conflicts_service import analyze
from app.services.academic_schedule_view_service import ViewBlock
from app.services.classroom_catalog_service import CATALOG, room_key
from tests.test_designation_schedule_loader import PERIOD, URL as LOAD_URL, _designation, _post, _workbook, seeded  # noqa: F401

CONFLICTS_URL = "/api/admin/academic-management/schedule-conflicts"


def _b(key, *, teacher="T1", group="M-1", semester=1, subject="Anatomia", activity="theory",
       weekday="lunes", start="08:00", end="09:30", room=None):
    return ViewBlock(key=key, semester=semester, group_code=group, subject_code=None, subject_name=subject,
                     activity_type=activity, weekday=weekday, start_time=start, end_time=end, teacher_ci=teacher,
                     teacher_name=None, classroom_code=room, classroom_name=None, source_type="draft")


def _kinds(blocks, **kw):
    result = analyze(blocks, rooms=kw.get("rooms", []), load_threshold=kw.get("threshold", 40), academic_hour_minutes=45)
    return sorted((c["kind"], c["severity"]) for c in result["clashes"]), result


# S4 / L15: catalog equals the user's verbatim table.
L15 = {"1": (1, 54), "2": (1, 54), "3": (1, 54), "4": (1, 54), "5": (1, 54), "6": (2, 54), "7": (2, 54), "8": (2, 54),
       "9": (2, 54), "10": (2, 54), "A": (1, 20), "B": (1, 20), "11": (2, 35), "12": (2, 50), "13": (2, 50),
       "14": (2, 40), "15": (2, 40), "16": (2, 35), "17": (2, 20), "18": (3, 47), "19": (3, 51), "20": (3, 52),
       "21": (3, 42), "22": (3, 54), "23": (3, 46), "24": (4, 47), "25": (4, 51), "26": (4, 51), "27": (4, 40),
       "28": (4, 45), "29": (4, 45)}


def test_s4_catalog_matches_the_l15_table():
    assert {room.room: (room.floor, room.capacity) for room in CATALOG} == L15
    old = {str(n) for n in range(1, 11)} | {"A", "B"}
    assert all(room.building == ("ANTIGUO" if room.room in old else "NUEVO") for room in CATALOG)
    assert all(room.code == f"COB-{room.building}-P{room.floor}-A{room.room}" for room in CATALOG)


@pytest.mark.parametrize("value,expected", [
    (20, "20"), (20.0, "20"), ("20", "20"), ("Aula 20", "20"), (" aula 20 ", "20"), ("b", "B"), ("Aula B", "B"),
    ("A", "A"), (None, None), ("", None), (30, None), (0, None), (20.5, None), ("Aula", None),
])
def test_s4_room_key_forms(value, expected):
    assert room_key(value) == expected


# S8: 5-minute tolerance for each clash kind.
@pytest.mark.parametrize("kind,left,right", [
    ("teacher", dict(teacher="T1", group="M-1", room="R1"), dict(teacher="T1", group="M-2", subject="X", room="R2")),
    ("group", dict(teacher="T1", group="M-1", room="R1"), dict(teacher="T2", group="M-1", subject="X", room="R2")),
    ("classroom", dict(teacher="T1", group="M-1", room="R1"), dict(teacher="T2", group="M-2", subject="X", room="R1")),
])
@pytest.mark.parametrize("start,clash", [("09:25", False), ("09:24", True), ("09:30", False)])
def test_s8_tolerance_per_kind(kind, left, right, start, clash):
    kinds, _ = _kinds([_b("a", **left, start="08:00", end="09:30"), _b("b", **right, start=start, end="10:30")])
    assert kinds == ([(kind, "conflict")] if clash else [])


def test_s8_split_theory_practice_is_warning_same_activity_is_conflict():
    kinds, _ = _kinds([_b("t", teacher="T1", activity="theory", room="R1"),
                       _b("p", teacher="T2", activity="practice", room="LAB")])
    assert kinds == [("split_group", "warning")]
    kinds, _ = _kinds([_b("t", teacher="T1", room="R1"), _b("u", teacher="T2", room="R2")])
    assert kinds == [("group", "conflict")]


def test_s8_load_threshold_is_configurable():
    blocks = [_b(f"k{i}", weekday=day, group=f"G{i}", start="07:00", end="22:00")  # 900 min = 20 h each
              for i, day in enumerate(("lunes", "martes"))]
    _, result = _kinds(blocks, threshold=40)
    assert result["teacher_loads"][0]["weekly_hours"] == 40.0
    _, low = _kinds(blocks, threshold=39.5)
    assert low["teacher_loads"][0]["over_threshold"] is True
    assert low["summary"]["overloaded_teachers"] == 1


def test_s8_free_slots_window_and_minimum():
    _, result = _kinds([_b("a", start="07:20", end="09:30", room="R1")], rooms=["R1", "R2"])
    monday = [(s["start_time"], s["end_time"]) for s in result["free_slots"]["groups"] if s["weekday"] == "lunes"]
    assert monday == [("06:30", "07:20"), ("09:30", "23:05")]  # 50 min before the block is listed
    _, short = _kinds([_b("a", start="07:10", end="09:30")])
    assert [(s["start_time"], s["end_time"]) for s in short["free_slots"]["groups"] if s["weekday"] == "lunes"] == [
        ("09:30", "23:05")]  # 40 min is below the 45-min minimum
    monday_rooms = [(s["classroom_code"], s["start_time"], s["end_time"]) for s in result["free_slots"]["rooms"] if s["weekday"] == "lunes"]
    assert ("R2", "06:30", "23:05") in monday_rooms


def test_s8_route_threshold_validation(client, db_session):
    assert client.get(CONFLICTS_URL, params={"academic_period": PERIOD, "load_threshold": 0}).status_code == 422
    assert client.get(CONFLICTS_URL, params={"academic_period": PERIOD, "load_threshold": 81}).status_code == 422
    ok = client.get(CONFLICTS_URL, params={"academic_period": PERIOD, "load_threshold": 12.5})
    assert ok.status_code == 200 and ok.json()["load_threshold"] == 12.5
    assert client.get(CONFLICTS_URL, params={"academic_period": PERIOD}).json()["load_threshold"] == 40
    assert client.get(CONFLICTS_URL, params={"academic_period": PERIOD, "source": "draft"}).status_code == 422


def _state(db):
    db.expire_all()
    return (
        sorted((d.id, d.teacher_ci, d.subject, str(d.contract_start_date), str(d.contract_end_date), repr(d.schedule_json))
               for d in db.query(Designation)),
        db.query(AcademicScheduleDraft).count(), db.query(AcademicScheduleBlock).count(),
        db.query(AcademicScheduleAssignment).count(), db.query(Classroom).count(), db.query(TeacherAvailability).count(),
        db.query(AcademicSchedulePublication).count(),
    )


def test_t7b_aula_forms_and_designations_untouched(client, seeded):
    _designation(seeded, "LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", [("lunes", "06:30", "08:55", 3)])
    _designation(seeded, "LD-T2", "FISIOLOGÍA I", "SEGUNDO", "T-2", [("martes", "13:40", "15:10", 2)])
    _designation(seeded, "LD-T3", "BIOQUÍMICA", "TERCERO", "N-1", [("jueves", "18:00", "19:30", 2)])
    workbook = _workbook([("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-01", 19.0),
                          ("LD-T2", "FISIOLOGÍA I", "SEGUNDO", "T-02", "Aula 20"),
                          ("LD-T3", "BIOQUÍMICA", "TERCERO", "N-01", "b")])
    before = _state(seeded)
    preview = _post(client, "preview", workbook).json()
    assert preview["can_apply"], preview["blockers"]
    assert sorted(b["classroom_code"] for b in preview["blocks"]) == ["COB-ANTIGUO-P1-AB", "COB-NUEVO-P3-A19", "COB-NUEVO-P3-A20"]
    assert _state(seeded) == before
    stale = _post(client, "apply", _workbook([("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-01", 18),
                                               ("LD-T2", "FISIOLOGÍA I", "SEGUNDO", "T-02", "Aula 20"),
                                               ("LD-T3", "BIOQUÍMICA", "TERCERO", "N-01", "b")]), digest=preview["digest"])
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_preview"
    assert _state(seeded) == before
    applied = _post(client, "apply", workbook, digest=preview["digest"])
    assert applied.status_code == 201
    after = _state(seeded)
    assert after[0] == before[0]  # designations untouched
    assert after[6] == before[6]  # nothing published
    assert seeded.get(AcademicScheduleDraft, applied.json()["draft_id"]).status == "draft"
    again = _post(client, "apply", workbook, digest=preview["digest"])
    assert again.status_code == 409
    assert _state(seeded) == after


def test_t7b_sunday_and_overlong_slots_are_blockers(client, seeded):
    _designation(seeded, "LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", [("domingo", "08:00", "09:30", 2)])
    _designation(seeded, "LD-T2", "FISIOLOGÍA I", "SEGUNDO", "T-2", [("martes", "07:00", "13:05", 8)])
    workbook = _workbook([("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-01", 19),
                          ("LD-T2", "FISIOLOGÍA I", "SEGUNDO", "T-02", 20)])
    before = _state(seeded)
    preview = _post(client, "preview", workbook).json()
    assert sorted(b["code"] for b in preview["blockers"]) == ["invalid_time", "invalid_weekday"]
    assert preview["can_apply"] is False
    refused = _post(client, "apply", workbook, digest=preview["digest"])
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "blocked"
    assert _state(seeded) == before


@pytest.mark.parametrize("hours", ["1.5", 1.5, "x", -2])
def test_t7b_non_whole_academic_hours_are_blockers(client, seeded, hours):
    _designation(seeded, "LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-1", [("lunes", "08:00", "09:30", hours)])
    workbook = _workbook([("LD-T1", "ANATOMÍA HUMANA I", "PRIMERO", "M-01", 19)])
    before = _state(seeded)
    response = _post(client, "preview", workbook)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert [b["code"] for b in preview["blockers"]] == ["invalid_hours"]
    assert preview["blockers"][0]["message"] == (
        "Las horas académicas de cada clase deben ser un número entero positivo."
    )
    assert preview["can_apply"] is False
    assert _state(seeded) == before
