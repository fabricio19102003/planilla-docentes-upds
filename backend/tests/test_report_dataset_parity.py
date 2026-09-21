from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace

from fastapi.encoders import jsonable_encoder

from app.models.academic_management import (
    AcademicProgram,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
)
from app.models.attendance import AttendanceRecord
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.services.monetary_snapshot import build_calculation_snapshot
from app.services.report_generator import ReportGenerator
import app.services.report_generator as report_module


def _snapshot(row, *, month=5, year=2026, excluded_days=None):
    return build_calculation_snapshot(
        rows=[row],
        row_amounts=[Decimal("100.00")],
        month=month,
        year=year,
        start_date=date(year, month, 1),
        end_date=date(year, month, 31),
        discount_mode="attendance",
        payment_overrides={},
        excluded_days=excluded_days or [],
    )


def _financial_row(**overrides):
    values = {
        "designation_id": 1,
        "teacher_ci": "REPORT-REG",
        "teacher_name": "Regular Teacher",
        "has_biometric": True,
        "has_retention": False,
        "subject": "Published Anatomy",
        "group_code": "A",
        "semester": "1",
        "base_monthly_hours": 8,
        "absent_hours": 2,
        "payable_hours": 6,
        "rate_per_hour": Decimal("70.00"),
        "calculated_payment": Decimal("100.00"),
        "retention_amount": Decimal("0.00"),
        "retention_rate": Decimal("0.00"),
        "source_kind": "legacy",
        "source_id": 1,
        "source_key": "legacy:1",
        "publication_id": None,
        "published_block_id": None,
        "published_schedule_assignment_id": None,
        "activity_kind": "theory",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _seed_mixed_report_sources(db_session):
    regular_teacher = Teacher(ci="REPORT-REG", full_name="Regular Teacher")
    practice_teacher = Teacher(ci="REPORT-PRA", full_name="Practice Teacher")
    program = AcademicProgram(code="REPORT", name="Report Program", active=True)
    db_session.add_all([regular_teacher, practice_teacher, program])
    db_session.flush()

    draft = AcademicScheduleDraft(
        program_id=program.id,
        academic_period="I/2026",
        name="Report source",
        normalized_name="report-source",
        status="published",
    )
    db_session.add(draft)
    db_session.flush()
    publication = AcademicSchedulePublication(
        program_id=program.id,
        academic_period="I/2026",
        effective_from=date(2026, 1, 1),
        sequence=1,
        content_digest="a" * 64,
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
        subject_name="Published Anatomy",
        group_code="A",
        semester=1,
        classroom_code="R1",
        classroom_name="Room 1",
        activity_type="theory",
        weekday="monday",
        start_time=time(8),
        end_time=time(9, 30),
    )
    db_session.add(block)
    db_session.flush()
    assignment = AcademicSchedulePublishedAssignment(
        publication_block_id=block.id,
        source_assignment_id=1,
        teacher_ci=regular_teacher.ci,
        teacher_name=regular_teacher.full_name,
        effective_from=date(2026, 1, 1),
    )
    legacy_practice = Designation(
        teacher_ci=practice_teacher.ci,
        subject="Legacy Clinic",
        semester="2",
        group_code="P",
        academic_period="I/2026",
        designation_type="practice",
        schedule_json=[],
        monthly_hours=8,
    )
    db_session.add_all([assignment, legacy_practice])
    db_session.flush()

    db_session.add_all([
        AttendanceRecord(
            teacher_ci=regular_teacher.ci,
            published_schedule_assignment_id=assignment.id,
            date=date(2026, 5, 4),
            scheduled_start=time(8),
            scheduled_end=time(9, 30),
            status="ABSENT",
            academic_hours=2,
            late_minutes=0,
            month=5,
            year=2026,
        ),
        PracticeAttendanceLog(
            teacher_ci=practice_teacher.ci,
            designation_id=legacy_practice.id,
            date=date(2026, 5, 5),
            scheduled_start=time(10),
            scheduled_end=time(11, 30),
            actual_start=time(10),
            actual_end=time(11, 30),
            status="attended",
            academic_hours=2,
        ),
    ])

    regular_row = _financial_row(
        designation_id=None,
        source_kind="published",
        source_id=assignment.id,
        source_key=f"published:{assignment.id}",
        publication_id=publication.id,
        published_block_id=block.id,
        published_schedule_assignment_id=assignment.id,
    )
    practice_row = _financial_row(
        designation_id=legacy_practice.id,
        teacher_ci=practice_teacher.ci,
        teacher_name=practice_teacher.full_name,
        subject=legacy_practice.subject,
        group_code=legacy_practice.group_code,
        semester=legacy_practice.semester,
        source_id=legacy_practice.id,
        source_key=f"legacy:{legacy_practice.id}",
        activity_kind="practice",
    )
    regular_exclusions = [{"date": "2026-05-01", "reason": "Holiday"}]
    practice_exclusions = [{"date": "2026-05-02", "reason": "Closure"}]
    db_session.add_all([
        PlanillaOutput(
            month=5,
            year=2026,
            generated_at=datetime(2026, 5, 31, 12),
            total_teachers=1,
            total_hours=6,
            total_payment=Decimal("100.00"),
            status="approved",
            excluded_days_json=regular_exclusions,
            calculation_snapshot=_snapshot(regular_row, excluded_days=regular_exclusions),
        ),
        PracticePlanillaOutput(
            month=5,
            year=2026,
            generated_at=datetime(2026, 5, 31, 13),
            total_teachers=1,
            total_hours=6,
            total_payment=Decimal("100.00"),
            status="approved",
            excluded_days_json=practice_exclusions,
            calculation_snapshot=_snapshot(practice_row, excluded_days=practice_exclusions),
        ),
    ])
    db_session.commit()


def test_attendance_preview_and_pdf_share_mixed_regular_practice_dataset(
    client, db_session, monkeypatch, tmp_path
):
    _seed_mixed_report_sources(db_session)
    preview = client.get("/api/reports/preview?report_type=attendance&month=5&year=2026")
    assert preview.status_code == 200, preview.text

    generator = ReportGenerator()
    original = generator.build_attendance_dataset
    captured = {}

    def record(*args, **kwargs):
        dataset = original(*args, **kwargs)
        captured.update(dataset.as_preview())
        return dataset

    monkeypatch.setattr(generator, "build_attendance_dataset", record)
    monkeypatch.setattr(report_module, "_output_dir", lambda: tmp_path)
    generator.generate_attendance_report(db_session, month=5, year=2026)

    assert preview.json() == jsonable_encoder(captured)
    assert preview.json()["regular"]["total_records"] == 1
    assert preview.json()["practice"]["total_records"] == 1
    assert {row["source_kind"] for row in preview.json()["records_sample"]} == {"legacy", "published"}

    filtered_preview = client.get(
        "/api/reports/preview?report_type=attendance&month=5&year=2026&teacher_ci=REPORT-REG"
    )
    captured.clear()
    generator.generate_attendance_report(
        db_session,
        month=5,
        year=2026,
        teacher_ci="REPORT-REG",
    )
    assert filtered_preview.json() == jsonable_encoder(captured)
    assert filtered_preview.json()["practice"]["total_records"] == 0

    empty_preview = client.get(
        "/api/reports/preview?report_type=attendance&month=5&year=2026&subject=Missing"
    )
    captured.clear()
    generator.generate_attendance_report(
        db_session,
        month=5,
        year=2026,
        subject="Missing",
    )
    assert empty_preview.json() == jsonable_encoder(captured)
    assert empty_preview.json()["total_records"] == 0


def test_reconciliation_preview_and_pdf_share_sources_exclusions_and_empty_subsets(
    client, db_session, monkeypatch, tmp_path
):
    _seed_mixed_report_sources(db_session)
    preview = client.get("/api/reports/preview?report_type=reconciliation&month=5&year=2026")
    assert preview.status_code == 200, preview.text

    generator = ReportGenerator()
    original = generator.build_reconciliation_dataset
    captured = {}

    def record(*args, **kwargs):
        dataset = original(*args, **kwargs)
        captured.update(dataset.as_preview())
        return dataset

    monkeypatch.setattr(generator, "build_reconciliation_dataset", record)
    monkeypatch.setattr(report_module, "_output_dir", lambda: tmp_path)
    generator.generate_reconciliation_report(db_session, month=5, year=2026)

    assert preview.json() == jsonable_encoder(captured)
    assert preview.json()["regular_exclusion_count"] == 1
    assert preview.json()["practice_exclusion_count"] == 1
    assert {row["source"] for row in preview.json()["discrepancies"]} == {"Regular", "Prácticas"}
