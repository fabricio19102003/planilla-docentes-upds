"""The institution's schedule is loaded once per period, never once per day.

``payroll_schedule_sources`` used to call ``effective_schedule_slots`` for every day of
the period, re-querying every publication and designation each time. These tests pin
that the load is bounded and that the in-memory resolution is identical to the old
per-day path, whose algorithm is kept below as an independent reference.
"""
from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from sqlalchemy import event
from sqlalchemy.orm import joinedload

from app.models.academic_management import (
    AcademicProgram,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
    block_paid_hours,
)
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services import payroll_schedule_source_service as sources_service
from app.services.designation_window import overlaps_cutoff
from app.services.effective_schedule_service import (
    EffectiveScheduleSlot,
    _canonical_weekday,
    _legacy_activity,
    _scope_key,
    effective_schedule_slots,
)

PERIOD = "I/2026"
PERIOD_START = date(2026, 1, 1)
PERIOD_END = date(2026, 6, 30)


def _publication(db, program, *, effective_from, sequence, blocks):
    draft = AcademicScheduleDraft(
        program_id=program.id,
        academic_period=PERIOD,
        name=f"draft-{program.code}-{effective_from}-{sequence}",
        normalized_name=f"draft-{program.code}-{effective_from}-{sequence}",
        status="published",
    )
    db.add(draft)
    db.flush()
    publication = AcademicSchedulePublication(
        program_id=program.id,
        academic_period=PERIOD,
        effective_from=effective_from,
        sequence=sequence,
        content_digest="a" * 64,
        source_draft_id=draft.id,
    )
    db.add(publication)
    db.flush()
    for index, spec in enumerate(blocks, start=1):
        block = AcademicSchedulePublishedBlock(
            publication_id=publication.id,
            source_block_id=index,
            source_offering_id=index,
            source_subject_id=index,
            source_group_id=index,
            source_classroom_id=index,
            subject_code=f"S{index}",
            subject_name=spec["subject"],
            group_code=spec["group"],
            semester=spec.get("semester", 1),
            classroom_code="A1",
            classroom_name="Aula 1",
            activity_type=spec["activity"],
            weekday=spec["weekday"],
            start_time=spec["start"],
            end_time=spec["end"],
            academic_hours=spec.get("hours"),
        )
        db.add(block)
        db.flush()
        for assignment_index, (teacher_ci, start, end) in enumerate(spec["assignments"], start=1):
            db.add(AcademicSchedulePublishedAssignment(
                publication_block_id=block.id,
                source_assignment_id=assignment_index,
                teacher_ci=teacher_ci,
                teacher_name=teacher_ci,
                effective_from=start,
                effective_to=end,
            ))
    db.flush()
    return publication


def _designation(db, teacher_ci, *, subject, semester, group, kind, slots, start=None, end=None,
                 monthly=None, weekly=None):
    designation = Designation(
        teacher_ci=teacher_ci,
        subject=subject,
        semester=semester,
        group_code=group,
        academic_period=PERIOD,
        designation_type=kind,
        schedule_json=slots,
        semester_hours=80,
        monthly_hours=monthly,
        weekly_hours=weekly,
        contract_start_date=start,
        contract_end_date=end,
    )
    db.add(designation)
    db.flush()
    return designation


def _slot(day, start, end, hours):
    return {"dia": day, "hora_inicio": start, "hora_fin": end, "horas_academicas": hours}


@pytest.fixture
def institution(db_session):
    """Publications over several dates/programs plus every kind of legacy fallback."""
    db = db_session
    teachers = [Teacher(ci=f"LOAD-{n}", full_name=f"Docente {n}") for n in range(1, 4)]
    program_a = AcademicProgram(code="PA", name="Programa A", active=True)
    program_b = AcademicProgram(code="PB", name="Programa B", active=True)
    db.add_all([*teachers, program_a, program_b])
    db.flush()
    t1, t2, t3 = (teacher.ci for teacher in teachers)
    feb2, mar16, apr1, may1 = date(2026, 2, 2), date(2026, 3, 16), date(2026, 4, 1), date(2026, 5, 1)

    _publication(db, program_a, effective_from=feb2, sequence=1, blocks=[
        {"subject": "Anatomía", "group": "M-1", "activity": "theory", "weekday": "monday",
         "start": time(8, 0), "end": time(9, 30),
         "assignments": [(t1, feb2, date(2026, 4, 30)), (t2, may1, None)]},
        {"subject": "Anatomía", "group": "M-1", "activity": "theory", "weekday": "wednesday",
         "start": time(8, 0), "end": time(9, 30), "hours": 3, "assignments": [(t1, feb2, None)]},
        {"subject": "Clínica", "group": "P-1", "activity": "practice", "weekday": "friday",
         "start": time(14, 0), "end": time(17, 0), "assignments": [(t3, feb2, None)]},
        {"subject": "Histología", "group": "T-1", "activity": "theory", "weekday": "tuesday",
         "start": time(10, 0), "end": time(11, 30), "assignments": [(t2, date(2026, 3, 1), None)]},
    ])
    _publication(db, program_a, effective_from=mar16, sequence=1, blocks=[
        {"subject": "Anatomía", "group": "M-1", "activity": "theory", "weekday": "monday",
         "start": time(8, 0), "end": time(9, 30), "assignments": [(t1, feb2, None)]},
        {"subject": "Fisiología", "group": "M-2", "activity": "theory", "weekday": "thursday",
         "start": time(9, 0), "end": time(10, 30), "assignments": [(t2, feb2, None)]},
    ])
    _publication(db, program_a, effective_from=mar16, sequence=2, blocks=[
        {"subject": "Anatomía", "group": "M-1", "activity": "theory", "weekday": "monday",
         "start": time(8, 0), "end": time(9, 30), "assignments": [(t2, feb2, None)]},
        {"subject": "Fisiología", "group": "M-2", "activity": "theory", "weekday": "thursday",
         "start": time(9, 0), "end": time(10, 30), "assignments": [(t2, feb2, None)]},
        {"subject": "Clínica", "group": "P-1", "activity": "practice", "weekday": "saturday",
         "start": time(8, 0), "end": time(12, 0), "assignments": [(t3, mar16, date(2026, 6, 13))]},
    ])
    _publication(db, program_b, effective_from=apr1, sequence=1, blocks=[
        {"subject": "Química", "group": "G-1", "activity": "theory", "weekday": "tuesday",
         "start": time(15, 0), "end": time(16, 30), "assignments": [(t3, apr1, None)]},
        {"subject": "Sin docente", "group": "G-2", "activity": "theory", "weekday": "friday",
         "start": time(15, 0), "end": time(16, 30), "assignments": [(t3, date(2026, 8, 1), None)]},
    ])

    # Scope key semester is the published integer ("1"), so these legacy rows are suppressed
    # once their publication is effective and are the fallback before it.
    _designation(db, t1, subject="ANATOMIA", semester="1", group="M-1", kind="regular",
                 slots=[_slot("Lunes", "08:00", "09:30", 2), _slot("Miércoles", "08:00", "09:30", 2)],
                 start=date(2026, 1, 12), end=date(2026, 6, 20), monthly=16, weekly=4)
    _designation(db, t2, subject="Química", semester="1", group="G-1", kind="regular",
                 slots=[_slot("martes", "15:00", "16:30", 2)], start=date(2026, 1, 12),
                 end=date(2026, 6, 20), monthly=8, weekly=2)
    _designation(db, t1, subject="Bioquímica", semester="II", group="N-1", kind="regular",
                 slots=[_slot("monday", "19:00", "20:30", 2), _slot("sabado", "08:00", "10:15", 3)],
                 start=date(2026, 2, 9), end=date(2026, 5, 29), monthly=20, weekly=5)
    _designation(db, t2, subject="Sin fechas", semester="II", group="N-2", kind="regular",
                 slots=[_slot("jueves", "19:00", "20:30", 2)], monthly=8, weekly=2)
    _designation(db, t2, subject="Cero horas", semester="II", group="N-3", kind="regular",
                 slots=[], start=date(2026, 2, 2), end=date(2026, 6, 20), weekly=0)
    _designation(db, t3, subject="Fuera de periodo", semester="II", group="N-4", kind="regular",
                 slots=[_slot("viernes", "19:00", "20:30", 2)], start=date(2025, 8, 1),
                 end=date(2025, 12, 20))
    _designation(db, t3, subject="Franja invalida", semester="II", group="N-5", kind="regular",
                 slots=[{"dia": "lunes", "hora_inicio": "xx"}, {"dia": "martes"},
                        _slot("viernes", "07:00", "08:30", 2)],
                 start=date(2026, 3, 2), end=date(2026, 6, 26), weekly=2)
    _designation(db, t3, subject="Clinica", semester="1", group="P-1", kind="practice",
                 slots=[_slot("lunes", "14:00", "17:00", 4)], start=date(2026, 1, 19),
                 end=date(2026, 6, 26), monthly=16, weekly=4)
    _designation(db, t1, subject="Practica solo legacy", semester="II", group="P-2", kind="practice",
                 slots=[_slot("jueves", "14:00", "17:00", 4)], start=date(2026, 2, 16),
                 end=date(2026, 5, 29), monthly=16, weekly=4)
    _designation(db, t2, subject="Practica sin franjas", semester="II", group="P-3", kind="practice",
                 slots=[], start=date(2026, 2, 16), end=date(2026, 5, 29), weekly=0)
    _designation(db, t1, subject="Practica vencida", semester="II", group="P-4", kind="practice",
                 slots=[_slot("martes", "14:00", "17:00", 4)], start=date(2025, 8, 1),
                 end=date(2025, 12, 20))
    return {"teachers": (t1, t2, t3)}


# ----- independent reference: the previous per-day algorithm, kept verbatim -----

def _reference_slots(db, academic_period, target_date, include_practice=False):
    candidates = db.query(AcademicSchedulePublication).options(
        joinedload(AcademicSchedulePublication.blocks)
        .joinedload(AcademicSchedulePublishedBlock.assignments)
    ).filter(
        AcademicSchedulePublication.academic_period == academic_period,
        AcademicSchedulePublication.effective_from <= target_date,
    ).order_by(
        AcademicSchedulePublication.program_id,
        AcademicSchedulePublication.effective_from.desc(),
        AcademicSchedulePublication.sequence.desc(),
        AcademicSchedulePublication.id.desc(),
    ).all()
    effective_by_program = {}
    for publication in candidates:
        effective_by_program.setdefault(publication.program_id, publication)
    published, represented = [], set()
    for publication in effective_by_program.values():
        for block in publication.blocks:
            if block.activity_type == "practice" and not include_practice:
                continue
            assignment = next((
                item for item in block.assignments
                if item.effective_from <= target_date
                and (item.effective_to is None or item.effective_to >= target_date)
            ), None)
            if assignment is None:
                continue
            represented.add(_scope_key(
                block.subject_name, block.group_code, block.semester, block.activity_type
            ))
            published.append(EffectiveScheduleSlot(
                source_type="published",
                teacher_ci=assignment.teacher_ci,
                subject=block.subject_name,
                group_code=block.group_code,
                semester=str(block.semester),
                activity_type=block.activity_type,
                weekday=_canonical_weekday(block.weekday),
                start_time=block.start_time,
                end_time=block.end_time,
                academic_hours=block_paid_hours(block.start_time, block.end_time, block.academic_hours),
                published_block_id=block.id,
                published_assignment_id=assignment.id,
                publication_id=publication.id,
                effective_from=max(publication.effective_from, assignment.effective_from),
                effective_to=assignment.effective_to,
            ))
    legacy = []
    for designation in db.query(Designation).filter(Designation.academic_period == academic_period).all():
        activity = _legacy_activity(designation)
        if activity == "practice" and not include_practice:
            continue
        if _scope_key(designation.subject, designation.group_code, designation.semester, activity) in represented:
            continue
        if designation.contract_start_date and target_date < designation.contract_start_date:
            continue
        if designation.contract_end_date and target_date > designation.contract_end_date:
            continue
        for slot in designation.schedule_json or []:
            try:
                start = time.fromisoformat(str(slot["hora_inicio"]))
                end = time.fromisoformat(str(slot["hora_fin"]))
            except (KeyError, TypeError, ValueError):
                continue
            legacy.append(EffectiveScheduleSlot(
                source_type="legacy",
                teacher_ci=designation.teacher_ci,
                subject=designation.subject,
                group_code=designation.group_code,
                semester=designation.semester,
                activity_type=activity,
                weekday=_canonical_weekday(slot.get("dia", "")),
                start_time=start,
                end_time=end,
                academic_hours=int(slot.get("horas_academicas", 0)),
                designation_id=designation.id,
                effective_from=designation.contract_start_date,
                effective_to=designation.contract_end_date,
                monthly_hours=designation.monthly_hours,
                weekly_hours=designation.weekly_hours,
            ))
    return sorted(
        [*published, *legacy],
        key=lambda item: (item.weekday, item.start_time, item.teacher_ci, item.source_type),
    )


def _reference_sources(db, *, academic_period, period_start, period_end, activity_kind,
                       explicit_cutoff=False):
    P = sources_service.PayrollScheduleSource
    groups, active_dates = {}, {}
    legacy_by_id = {
        item.id: item
        for item in db.query(Designation).filter(Designation.academic_period == academic_period).all()
    }
    current = period_start
    while current <= period_end:
        for slot in _reference_slots(db, academic_period, current, include_practice=True):
            if slot.activity_type != activity_kind:
                continue
            key = f"{slot.source_type}:{slot.source_id}"
            source = groups.get(key)
            if source is None:
                legacy = legacy_by_id.get(slot.designation_id) if slot.designation_id is not None else None
                source = P(
                    source_kind=slot.source_type, source_id=slot.source_id, teacher_ci=slot.teacher_ci,
                    subject=slot.subject, group_code=slot.group_code, semester=slot.semester,
                    activity_kind=activity_kind, effective_from=current, effective_to=current,
                    designation_id=slot.designation_id, publication_id=slot.publication_id,
                    published_block_id=slot.published_block_id,
                    published_assignment_id=slot.published_assignment_id,
                    monthly_hours=int(legacy.monthly_hours or 0) if legacy else None,
                    weekly_hours=int(legacy.weekly_hours or 0) if legacy and legacy.weekly_hours is not None else None,
                )
                groups[key] = source
                active_dates[key] = []
            active_dates[key].append(current)
            item = sources_service._slot_schedule(slot)
            if item not in source.schedule:
                source.schedule.append(item)
            if slot.weekday == ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado",
                                "domingo")[current.weekday()]:
                payable = sources_service.PayableScheduleSlot(
                    date=current, scheduled_start=slot.start_time, scheduled_end=slot.end_time,
                    academic_hours=slot.academic_hours,
                )
                if payable not in source.payable_slots:
                    source.payable_slots.append(payable)
        current += timedelta(days=1)
    for key, source in groups.items():
        source.effective_from = min(active_dates[key])
        source.effective_to = max(active_dates[key])
        source.schedule.sort(key=lambda item: (str(item["dia"]), str(item["hora_inicio"])))
        source.payable_slots.sort(key=lambda item: (item.date, item.scheduled_start))
        if source.source_kind == "published" or source.effective_from > period_start or source.effective_to < period_end:
            source.monthly_hours = sum(item.academic_hours for item in source.payable_slots)
    published_scopes = {
        (i.subject.casefold().strip(), i.group_code.casefold().strip(), str(i.semester).casefold().strip())
        for i in groups.values() if i.source_kind == "published"
    }
    for designation in legacy_by_id.values():
        legacy_activity = "practice" if designation.designation_type == "practice" else "theory"
        key = f"legacy:{designation.id}"
        scope = (designation.subject.casefold().strip(), designation.group_code.casefold().strip(),
                 str(designation.semester).casefold().strip())
        if legacy_activity != activity_kind or key in groups or scope in published_scopes:
            continue
        if explicit_cutoff and not overlaps_cutoff(
            designation.contract_start_date, designation.contract_end_date, period_start, period_end,
        ):
            continue
        groups[key] = P(
            source_kind="legacy", source_id=designation.id, teacher_ci=designation.teacher_ci,
            subject=designation.subject, group_code=designation.group_code,
            semester=str(designation.semester), activity_kind=activity_kind,
            effective_from=period_start, effective_to=period_end, designation_id=designation.id,
            monthly_hours=0,
            weekly_hours=int(designation.weekly_hours or 0) if designation.weekly_hours is not None else None,
            schedule=[],
        )
    return sorted(
        groups.values(),
        key=lambda item: (item.teacher_ci, item.activity_kind, item.subject, item.group_code, item.source_key),
    )


def _days(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _count_statements(db, action):
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        result = action()
    finally:
        event.remove(bind, "before_cursor_execute", record)
    return result, statements


# ----- tests -----

def test_fixture_exercises_published_and_legacy_paths(db_session, institution):
    slots = [
        slot
        for day in _days(PERIOD_START, PERIOD_END)
        for slot in _reference_slots(db_session, PERIOD, day, include_practice=True)
    ]
    assert {slot.source_type for slot in slots} == {"legacy", "published"}
    assert {slot.activity_type for slot in slots} == {"theory", "practice"}
    assert len({slot.publication_id for slot in slots if slot.publication_id}) >= 3


def test_per_day_resolution_over_loaded_period_equals_the_per_day_query_for_every_day(
    db_session, institution
):
    from app.services.effective_schedule_service import (
        load_effective_schedule_period,
        resolve_effective_schedule_slots,
    )

    loaded = load_effective_schedule_period(db_session, PERIOD)
    # Cover days before the period and after it too: publications/contracts open and close.
    for day in _days(date(2025, 12, 20), date(2026, 7, 10)):
        for include_practice in (False, True):
            expected = _reference_slots(db_session, PERIOD, day, include_practice)
            assert effective_schedule_slots(db_session, PERIOD, day, include_practice) == expected
            assert resolve_effective_schedule_slots(loaded, day, include_practice) == expected


@pytest.mark.parametrize("activity_kind", ["theory", "practice"])
@pytest.mark.parametrize("explicit_cutoff", [False, True])
@pytest.mark.parametrize(
    "start,end",
    [
        (PERIOD_START, PERIOD_END),
        (date(2026, 3, 1), date(2026, 3, 31)),
        (date(2026, 4, 20), date(2026, 5, 10)),
        (date(2026, 7, 1), date(2026, 7, 31)),
    ],
)
def test_payroll_schedule_sources_equal_the_reference_per_day_loop(
    db_session, institution, activity_kind, explicit_cutoff, start, end
):
    kwargs = dict(
        academic_period=PERIOD, period_start=start, period_end=end,
        activity_kind=activity_kind, explicit_cutoff=explicit_cutoff,
    )
    expected = _reference_sources(db_session, **kwargs)
    actual = sources_service.payroll_schedule_sources(db_session, **kwargs)

    assert actual == expected
    assert [item.source_key for item in actual] == [item.source_key for item in expected]
    if start == PERIOD_START and not explicit_cutoff:
        assert expected, "the fixture must yield sources for the whole period"


def test_payroll_schedule_sources_issue_a_bounded_number_of_statements(db_session, institution):
    kwargs = dict(
        academic_period=PERIOD, period_start=PERIOD_START, period_end=PERIOD_END,
        activity_kind="theory",
    )
    _, statements = _count_statements(
        db_session, lambda: sources_service.payroll_schedule_sources(db_session, **kwargs)
    )
    assert len(statements) <= 4, f"{len(statements)} statements: {statements}"


def test_individual_terms_route_does_not_query_the_schedule_once_per_day(
    client, db_session, institution
):
    teacher_ci = institution["teachers"][0]

    response, statements = _count_statements(
        db_session, lambda: client.get(f"/api/contracts/terms/{teacher_ci}?academic_period={PERIOD}")
    )

    assert response.status_code == 200, response.text
    assert response.json()["default_start"] is not None
    days = (PERIOD_END - PERIOD_START).days + 1
    assert days > 180
    period_loads = [sql for sql in statements if "ORDER BY academic_schedule_publications.program_id" in sql]
    # One period load (publications + designations) per activity kind, independent of days.
    assert len(period_loads) <= 2, f"{len(period_loads)} period loads"
    assert len(statements) <= 40, f"{len(statements)} statements in total"


def test_issue_route_does_not_query_the_schedule_once_per_day(client, db_session, institution):
    ci = institution["teachers"][0]

    response, statements = _count_statements(db_session, lambda: client.post(
        f"/api/contracts/issue/{ci}", json={"department": "Pando", "academic_period": PERIOD}))

    assert response.status_code == 200, response.text
    loads = [s for s in statements if "ORDER BY academic_schedule_publications.program_id" in s]
    assert len(loads) <= 2


def test_invalid_legacy_hours_still_raise_only_on_active_days(db_session, institution):
    _designation(db_session, institution["teachers"][0], subject="Mala", semester="II", group="Z-9",
                 kind="regular", slots=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:00",
                                         "horas_academicas": None}],
                 start=date(2026, 3, 2), end=date(2026, 3, 6))

    assert effective_schedule_slots(db_session, PERIOD, date(2026, 3, 1)) == _reference_slots(
        db_session, PERIOD, date(2026, 3, 1))
    for resolve in (_reference_slots, effective_schedule_slots):
        with pytest.raises(TypeError):
            resolve(db_session, PERIOD, date(2026, 3, 2))
