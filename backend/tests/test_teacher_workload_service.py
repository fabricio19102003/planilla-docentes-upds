from datetime import date, time

from app.models.academic_management import (
    AcademicProgram,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
)
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services.teacher_workload_service import active_period_effective_date, effective_workloads


def test_effective_workloads_prefer_published_scope_and_keep_typed_legacy_fallback(db_session):
    teacher = Teacher(ci="WORKLOAD-1", full_name="Workload Teacher")
    program = AcademicProgram(code="MED-WORKLOAD", name="Medicine", active=True)
    db_session.add_all([teacher, program])
    db_session.flush()

    matching_legacy = Designation(
        id=1,
        teacher_ci=teacher.ci,
        subject="Anatomy",
        semester="1",
        group_code="M-1",
        academic_period="I/2026",
        designation_type="regular",
        schedule_json=[{
            "dia": "lunes",
            "hora_inicio": "07:00",
            "hora_fin": "08:30",
            "horas_academicas": 2,
        }],
        weekly_hours=2,
        monthly_hours=8,
    )
    fallback = Designation(
        teacher_ci=teacher.ci,
        subject="Physiology",
        semester="2",
        group_code="T-2",
        academic_period="I/2026",
        designation_type="regular",
        schedule_json=[{
            "dia": "martes",
            "hora_inicio": "10:00",
            "hora_fin": "11:30",
            "horas_academicas": 2,
        }],
        weekly_hours=2,
        monthly_hours=8,
    )
    db_session.add_all([matching_legacy, fallback])
    db_session.flush()

    draft = AcademicScheduleDraft(
        program_id=program.id,
        academic_period="I/2026",
        name="Published schedule",
        normalized_name="published-schedule",
        status="published",
    )
    db_session.add(draft)
    db_session.flush()
    publication = AcademicSchedulePublication(
        program_id=program.id,
        academic_period="I/2026",
        effective_from=date(2026, 3, 1),
        sequence=1,
        content_digest="b" * 64,
        source_draft_id=draft.id,
    )
    db_session.add(publication)
    db_session.flush()
    block = AcademicSchedulePublishedBlock(
        publication_id=publication.id,
        source_block_id=1,
        source_offering_id=1,
        source_subject_id=1,
        source_group_id=1,
        source_classroom_id=1,
        subject_code="ANAT",
        subject_name="Anatomy",
        group_code="M-1",
        semester=1,
        classroom_code="A-1",
        classroom_name="Room A-1",
        activity_type="theory",
        weekday="monday",
        start_time=time(8, 0),
        end_time=time(9, 30),
    )
    db_session.add(block)
    db_session.flush()
    assignment = AcademicSchedulePublishedAssignment(
        id=1,
        publication_block_id=block.id,
        source_assignment_id=1,
        teacher_ci=teacher.ci,
        teacher_name=teacher.full_name,
        effective_from=date(2026, 2, 1),
        effective_to=date(2026, 6, 30),
    )
    db_session.add(assignment)
    db_session.flush()

    workloads = effective_workloads(
        db_session,
        academic_period="I/2026",
        target_date=date(2026, 4, 1),
        teacher_ci=teacher.ci,
        activity_kind="theory",
    )

    assert [item.source_key for item in workloads] == [
        f"published:{assignment.id}",
        f"legacy:{fallback.id}",
    ]
    published = workloads[0]
    assert published.designation_id is None
    assert published.publication_id == publication.id
    assert published.effective_from == date(2026, 3, 1)
    assert published.schedule_json[0]["hora_inicio"] == "08:00"
    assert workloads[1].monthly_hours == 8


def test_active_period_effective_date_clamps_to_period_boundaries():
    assert active_period_effective_date("I/2026", date(2025, 12, 1)) == date(2026, 1, 1)
    assert active_period_effective_date("I/2026", date(2026, 9, 1)) == date(2026, 6, 30)


def test_effective_workloads_keep_unscheduled_legacy_fallback(db_session):
    teacher = Teacher(ci="WORKLOAD-EMPTY", full_name="Unscheduled Teacher")
    designation = Designation(
        teacher_ci=teacher.ci,
        subject="Research",
        semester="1",
        group_code="R-1",
        academic_period="I/2026",
        designation_type="regular",
        schedule_json=[],
        weekly_hours=0,
        monthly_hours=0,
    )
    db_session.add_all([teacher, designation])
    db_session.flush()

    workloads = effective_workloads(
        db_session,
        academic_period="I/2026",
        target_date=date(2026, 4, 1),
        teacher_ci=teacher.ci,
    )

    assert len(workloads) == 1
    assert workloads[0].source_key == f"legacy:{designation.id}"
    assert workloads[0].schedule_json == ()
