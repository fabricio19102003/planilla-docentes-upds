"""Unit tests for the October 2026 practice-planilla operator (deploy/operators).

The operator is a one-off production script, so it is loaded by path. These tests use a
minimal synthetic fixture (two practice blocks, one teacher CI change, one override); the
end-to-end run is rehearsed on a restored production copy.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.models.academic_management import (
    AcademicGroup,
    AcademicProgram,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
    AcademicScheduleDraft,
    AcademicSubject,
    Classroom,
    SubjectOffering,
)
from app.models.billing_publication import BillingPublication
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher

OPERATOR_PATH = Path(__file__).resolve().parents[2] / "deploy" / "operators" / "practicas_octubre_2026.py"
HEAD = "c5e7a9b1d3f4"


def _load_operator():
    spec = importlib.util.spec_from_file_location("practicas_octubre_2026", OPERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def op():
    return _load_operator()


# ── Pure helpers ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("minutes,expected", [
    (0, 1), (10, 1), (22, 1), (23, 1),   # never below one hour
    (45, 1), (67, 1), (68, 2),           # 1.5 academic hours rounds half up
    (90, 2), (130, 3), (135, 3), (190, 4), (185, 4),
])
def test_academic_hours_round_half_up_from_minutes(op, minutes, expected):
    assert op.academic_hours_for(minutes) == expected


def test_academic_hours_use_the_configured_length(op):
    assert op.academic_hours_for(60, length=60) == 1
    assert op.academic_hours_for(90, length=60) == 2  # 1.5 rounds up


def test_override_key_uses_the_published_assignment_id(op):
    assert op.override_key("123", 77) == "123:published:77"


def _published(block_id, offering, group, weekday, start, end):
    return SimpleNamespace(
        id=block_id, source_offering_id=offering, source_group_id=group,
        weekday=weekday, start_time=start, end_time=end,
    )


def _draft_block(block_id, offering, group, weekday, start, end):
    return SimpleNamespace(
        id=block_id, offering_id=offering, group_id=group,
        weekday=weekday, start_time=start, end_time=end,
    )


def test_blocks_map_by_offering_group_weekday_start_end(op):
    sources = [
        _published(81, 1, 1, "thursday", time(15, 20), time(17, 30)),
        _published(85, 1, 2, "thursday", time(15, 20), time(17, 30)),
    ]
    drafts = [
        _draft_block(501, 1, 2, "thursday", time(15, 20), time(17, 30)),
        _draft_block(500, 1, 1, "thursday", time(15, 20), time(17, 30)),
    ]
    mapped = op.map_blocks(sources, drafts)
    assert {key: block.id for key, block in mapped.items()} == {81: 500, 85: 501}


def test_block_mapping_fails_when_a_source_has_no_draft_block(op):
    sources = [_published(81, 1, 1, "thursday", time(15, 20), time(17, 30))]
    drafts = [_draft_block(500, 1, 1, "thursday", time(15, 20), time(17, 45))]
    with pytest.raises(op.OperatorError, match="81"):
        op.map_blocks(sources, drafts)


def test_block_mapping_fails_when_two_draft_blocks_share_the_key(op):
    sources = [_published(81, 1, 1, "thursday", time(15, 20), time(17, 30))]
    drafts = [
        _draft_block(500, 1, 1, "thursday", time(15, 20), time(17, 30)),
        _draft_block(501, 1, 1, "thursday", time(15, 20), time(17, 30)),
    ]
    with pytest.raises(op.OperatorError, match="81"):
        op.map_blocks(sources, drafts)


# ── Comparison against the reviewed workbook ──────────────────────────────────

def _expected(rows):
    return {
        "teachers": len({r["ci"] for r in rows}),
        "rows": len(rows),
        "gross": f'{sum(r["gross"] for r in rows):.2f}',
        "retention": f'{sum(r["retention"] for r in rows):.2f}',
        "net": f'{sum(r["net"] for r in rows):.2f}',
        "rows_detail": rows,
    }


def _row(ci, hours, gross, retention, net, overridden=False):
    return {
        "teacher_ci": ci, "hours": hours, "gross": Decimal(gross),
        "retention": Decimal(retention), "net": Decimal(net), "overridden": overridden,
    }


WORKBOOK = [
    {"ci": "NEW1", "hours": 4, "gross": 200, "retention": 26, "net": 174},
    {"ci": "T2", "hours": 8, "gross": 400, "retention": 0, "net": 400},
]


def test_comparison_matches_rows_per_teacher_after_the_ci_change(op):
    actual = [_row("NEW1", 4, "200", "26", "174"), _row("T2", 8, "400", "0", "400")]
    result = op.compare_rows(actual, _expected(WORKBOOK), {"OLD1": "NEW1"})
    assert result.ok, result.mismatches
    assert result.mismatches == []
    assert result.totals == {
        "rows": 2, "teachers": 2,
        "gross": Decimal("600.00"), "retention": Decimal("26.00"), "net": Decimal("574.00"),
    }


def test_comparison_maps_the_workbook_ci_through_the_ci_change(op):
    workbook = [dict(WORKBOOK[0], ci="OLD1"), WORKBOOK[1]]
    actual = [_row("NEW1", 4, "200", "26", "174"), _row("T2", 8, "400", "0", "400")]
    assert op.compare_rows(actual, _expected(workbook), {"OLD1": "NEW1"}).ok


def test_comparison_reports_a_changed_hours_value_without_hiding_it(op):
    actual = [_row("NEW1", 5, "250", "32.50", "217.50"), _row("T2", 8, "400", "0", "400")]
    result = op.compare_rows(actual, _expected(WORKBOOK), {})
    assert not result.ok
    assert any("hours" in line or "4" in line for line in result.mismatches)
    assert any("gross" in line for line in result.mismatches)  # totals differ too
    assert result.totals["gross"] == Decimal("650.00")


def test_comparison_fails_on_a_missing_row_and_on_the_row_count(op):
    result = op.compare_rows([_row("NEW1", 4, "200", "26", "174")], _expected(WORKBOOK), {})
    assert not result.ok
    assert any("rows" in line for line in result.mismatches)


def test_overridden_rows_match_on_amount_and_report_hours_separately(op):
    workbook = [WORKBOOK[0], dict(WORKBOOK[1], hours=8)]
    # The block rule pays 9 hours; the override keeps the reviewed Bs 400.
    actual = [_row("NEW1", 4, "200", "26", "174"), _row("T2", 9, "450", "0", "400", overridden=True)]
    result = op.compare_rows(actual, _expected(workbook), {})
    assert result.ok, result.mismatches
    assert result.overridden == [{
        "teacher_ci": "T2", "hours_actual": 9, "hours_expected": 8,
        "amount_actual": Decimal("400"), "amount_expected": Decimal("400"),
    }]
    assert result.totals["gross"] == Decimal("600.00")  # an overridden row counts what it pays


def test_overridden_row_with_a_different_amount_is_a_mismatch(op):
    actual = [_row("NEW1", 4, "200", "26", "174"), _row("T2", 8, "400", "0", "350", overridden=True)]
    result = op.compare_rows(actual, _expected(WORKBOOK), {})
    assert not result.ok


# ── Preconditions (fail closed, write nothing) ────────────────────────────────

@pytest.fixture
def world(db_session):
    db = db_session
    db.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
    db.execute(text("DELETE FROM alembic_version"))
    db.execute(text("INSERT INTO alembic_version (version_num) VALUES (:head)"), {"head": HEAD})
    program = AcademicProgram(code="MED", name="Medicina")
    subject = AcademicSubject(code="ANA2", name="Anatomía Humana II")
    db.add_all([program, subject])
    db.flush()
    offering = SubjectOffering(
        subject_id=subject.id, program_id=program.id, academic_period="II/2026", semester=2, practice_hours=4,
    )
    group = AcademicGroup(
        program_id=program.id, academic_period="II/2026", semester=2, shift="T", code="T-02",
    )
    classroom = Classroom(code="H1", name="Hospital", campus="C", classroom_type="other")
    draft = AcademicScheduleDraft(
        program_id=program.id, academic_period="II/2026", name="Historic", normalized_name="historic",
        status="published",
    )
    db.add_all([offering, group, classroom, draft, Teacher(ci="OLD1", full_name="Teacher One"),
                Teacher(ci="T2", full_name="Teacher Two")])
    db.flush()
    publication = AcademicSchedulePublication(
        program_id=program.id, academic_period="II/2026", effective_from=date(2026, 9, 2),
        sequence=1, content_digest="0" * 64, source_draft_id=draft.id,
    )
    db.add(publication)
    db.flush()
    blocks = []
    for index, (teacher, start, end) in enumerate((("OLD1", time(8, 0), time(9, 30)), ("T2", time(15, 20), time(17, 30)))):
        block = AcademicSchedulePublishedBlock(
            publication_id=publication.id, source_block_id=900 + index, source_offering_id=offering.id,
            source_subject_id=subject.id, source_group_id=group.id, source_classroom_id=classroom.id,
            subject_code="ANA2", subject_name="Anatomy II", group_code="T-02", semester=2,
            classroom_code="H1", classroom_name="Hospital", activity_type="practice",
            weekday="thursday", start_time=start, end_time=end,
        )
        db.add(block)
        db.flush()
        db.add(AcademicSchedulePublishedAssignment(
            publication_block_id=block.id, source_assignment_id=800 + index, teacher_ci=teacher,
            teacher_name=teacher, effective_from=date(2026, 9, 2),
        ))
        blocks.append(block)
    planilla = PracticePlanillaOutput(
        month=10, year=2026, total_teachers=2, total_hours=12, total_payment=Decimal("500"),
        discount_mode="full", start_date=date(2026, 9, 21), end_date=date(2026, 10, 20),
        status="generated",
    )
    db.add(planilla)
    db.flush()
    envelope = {
        "source_publication_id": publication.id,
        "program_id": program.id,
        "academic_period": "II/2026",
        "new_publication_effective_from": "2026-09-21",
        "clone_draft_name": "Prácticas corregidas",
        "teacher_updates": [{"ci": "OLD1", "new_ci": "NEW1", "invoice_retention": "RETENCION"}],
        "block_hours": [
            {"source_published_block_id": blocks[0].id, "teacher_ci": "OLD1", "subject_catalog": "Anatomía Humana II",
             "group": "T-02", "weekday": "thursday", "start": "08:00", "end": "09:30", "minutes": 90,
             "academic_hours": 2},
            {"source_published_block_id": blocks[1].id, "teacher_ci": "T2", "subject_catalog": "Anatomía Humana II",
             "group": "T-02", "weekday": "thursday", "start": "15:20", "end": "17:30", "minutes": 130,
             "academic_hours": 3},
        ],
        "amount_overrides": [
            {"source_published_block_id": blocks[1].id, "teacher_ci": "T2", "amount": "400.00", "reason": "reviewed"},
        ],
        "planilla": {
            "month": 10, "year": 2026, "start_date": "2026-09-21", "end_date": "2026-10-20",
            "copy_params_from_practice_planilla_id": planilla.id,
        },
        "expected": _expected(WORKBOOK),
    }
    return SimpleNamespace(
        db=db, envelope=envelope, publication=publication, blocks=blocks, planilla=planilla,
        program=program,
    )


def _state(db):
    tables = ("teachers", "academic_schedule_drafts", "academic_schedule_publications",
              "practice_planilla_outputs", "activity_logs", "billing_publications",
              "academic_schedule_assignments")
    return {name: db.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() for name in tables}


def test_preconditions_accept_the_untouched_world(op, world):
    facts = op.check_preconditions(world.db, world.envelope, alembic_head=HEAD)
    assert facts.ci_changes_done is False
    assert facts.planilla.id == world.planilla.id
    assert facts.publication.id == world.publication.id
    assert [block.id for block in facts.published_blocks] == [b.id for b in world.blocks]


def _break_alembic(world):
    world.db.execute(text("UPDATE alembic_version SET version_num = 'other'"))


def _break_block_set(world):
    world.envelope["block_hours"].pop()


def _break_teacher_ci(world):
    world.envelope["block_hours"][0]["teacher_ci"] = "SOMEONE"


def _break_planilla_approved(world):
    world.planilla.status = "approved"


def _break_planilla_missing(world):
    world.planilla.month = 11


def _break_billing_publication(world):
    world.db.add(BillingPublication(
        month=10, year=2026, planilla_type="practice", status="published", total_teachers=1, total_payment=1.0,
    ))


def _break_new_ci_exists_with_old(world):
    world.db.add(Teacher(ci="NEW1", full_name="Teacher New"))


def _break_old_ci_missing(world):
    world.db.execute(text("UPDATE teachers SET ci = 'ELSE' WHERE ci = 'OLD1'"))


def _break_attendance_in_window(world):
    world.db.add(PracticeAttendanceLog(
        teacher_ci="T2", published_schedule_assignment_id=world.db.execute(
            text("SELECT id FROM academic_schedule_published_assignments LIMIT 1")
        ).scalar(),
        date=date(2026, 10, 1), scheduled_start=time(8, 0), scheduled_end=time(9, 30),
        academic_hours=2, status="attended",
    ))


@pytest.mark.parametrize("breaker,fragment", [
    (_break_alembic, "alembic"),
    (_break_block_set, "bloques"),
    (_break_teacher_ci, "docente"),
    (_break_planilla_approved, "planilla"),
    (_break_planilla_missing, "planilla"),
    (_break_billing_publication, "facturación"),
    (_break_new_ci_exists_with_old, "CI"),
    (_break_old_ci_missing, "CI"),
    (_break_attendance_in_window, "asistencia"),
])
def test_preconditions_fail_closed_and_write_nothing(op, world, breaker, fragment):
    breaker(world)
    world.db.flush()
    before = _state(world.db)
    with pytest.raises(op.PreconditionError) as raised:
        op.check_preconditions(world.db, world.envelope, alembic_head=HEAD)
    assert any(fragment in failure for failure in raised.value.failures), raised.value.failures
    assert _state(world.db) == before
    assert not world.db.new and not world.db.dirty


def test_preconditions_report_every_failure_at_once(op, world):
    _break_alembic(world)
    _break_planilla_approved(world)
    world.db.flush()
    with pytest.raises(op.PreconditionError) as raised:
        op.check_preconditions(world.db, world.envelope, alembic_head=HEAD)
    assert len(raised.value.failures) >= 2


def test_preconditions_recognise_an_already_changed_ci(op, world):
    world.db.execute(text("UPDATE teachers SET ci = 'NEW1' WHERE ci = 'OLD1'"))
    world.db.flush()
    facts = op.check_preconditions(world.db, world.envelope, alembic_head=HEAD)
    assert facts.ci_changes_done is True
    assert facts.ci_alias == {"OLD1": "NEW1"}
