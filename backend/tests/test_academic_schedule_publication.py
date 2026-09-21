from __future__ import annotations

from datetime import date, time

from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricUpload
from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.services.effective_schedule_service import effective_schedule_slots
from app.services.attendance_engine import AttendanceEngine
from app.services.planilla_generator import PlanillaGenerator
from app.services.practice_planilla_generator import PracticePlanillaGenerator
from app.services.monetary_snapshot import build_calculation_snapshot
from app.services.report_generator import ReportGenerator


BASE = "/api/admin/academic-management"


def _post(client, path, payload):
    response = client.post(f"{BASE}{path}", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _seed(client, db_session, *, name="Publication draft"):
    program = _post(client, "/programs", {"code": "PUB", "name": "Publication Program"})
    subject = _post(client, "/subjects", {"code": "PUB-101", "name": "Publication Subject"})
    offering = _post(client, "/offerings", {
        "subject_id": subject["id"], "program_id": program["id"],
        "academic_period": "I/2027", "semester": 1,
        "theory_hours": 10, "practice_hours": 10,
    })
    group = _post(client, "/groups", {
        "program_id": program["id"], "academic_period": "I/2027", "semester": 1,
        "shift": "Morning", "code": "A", "expected_size": 20,
    })
    room = _post(client, "/classrooms", {
        "code": "PUB-A", "name": "Publication Room", "campus": "Central",
        "capacity": 30, "classroom_type": "classroom", "resources": [],
    })
    teacher = Teacher(ci="PUB-T1", full_name="Publication Teacher")
    db_session.add(teacher)
    db_session.flush()
    availability = client.post(f"{BASE}/availability", json={
        "teacher_ci": teacher.ci, "academic_period": "I/2027", "weekday": "monday",
        "start_time": "07:00", "end_time": "12:00",
    })
    assert availability.status_code == 201, availability.text
    draft = _post(client, "/schedule-drafts", {
        "program_id": program["id"], "academic_period": "I/2027", "name": name,
    })
    block = _post(client, f"/schedule-drafts/{draft['id']}/blocks", {
        "offering_id": offering["id"], "group_id": group["id"],
        "classroom_id": room["id"], "activity_type": "theory",
        "weekday": "monday", "start_time": "08:00", "end_time": "09:00",
    })
    return program, subject, offering, group, room, draft, block, teacher


def _assign(client, draft_id, block_id, *, end=None):
    response = client.post(
        f"{BASE}/schedule-drafts/{draft_id}/blocks/{block_id}/assignments",
        json={"teacher_ci": "PUB-T1", "effective_from": "2027-01-01", "effective_to": end},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _preview(client, draft_id, effective="2027-02-01"):
    response = client.post(
        f"{BASE}/schedule-drafts/{draft_id}/publication-preview",
        json={"effective_from": effective},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _publish(client, draft_id, preview):
    return client.post(f"{BASE}/schedule-drafts/{draft_id}/publish", json={
        "effective_from": preview["effective_from"],
        "preview_digest": preview["digest"],
    })


def test_preview_digest_is_deterministic_and_stale_digest_is_rejected(client, db_session):
    _program, _subject, offering, group, room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    first = _preview(client, draft["id"])
    second = _preview(client, draft["id"])
    assert first["digest"] == second["digest"]
    assert first["can_publish"] is True
    extra = _post(client, f"/schedule-drafts/{draft['id']}/blocks", {
        "offering_id": offering["id"], "group_id": group["id"],
        "classroom_id": room["id"], "activity_type": "practice",
        "weekday": "monday", "start_time": "09:00", "end_time": "10:00",
    })
    _assign(client, draft["id"], extra["id"])
    stale = _publish(client, draft["id"], first)
    assert stale.status_code == 409
    assert "nueva vista previa" in stale.json()["detail"]


def test_preview_blocks_bounded_or_noncontiguous_teacher_coverage(client, db_session):
    _program, _subject, _offering, _group, _room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"], end="2027-06-30")
    preview = _preview(client, draft["id"])
    assert preview["can_publish"] is False
    assert {item["category"] for item in preview["blockers"]} == {
        "teacher_coverage_not_open_ended"
    }


def test_preview_revalidates_the_complete_draft(client, db_session):
    _program, _subject, _offering, _group, room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    deactivate = client.post(f"{BASE}/classrooms/{room['id']}/deactivate")
    assert deactivate.status_code == 200, deactivate.text
    preview = _preview(client, draft["id"])
    assert preview["can_publish"] is False
    assert any(item["category"] == "draft_validation" for item in preview["blockers"])


def test_publish_writes_immutable_history_and_clone_is_equivalent(client, db_session):
    program, _subject, _offering, _group, _room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    preview = _preview(client, draft["id"])
    published_response = _publish(client, draft["id"], preview)
    assert published_response.status_code == 201, published_response.text
    publication = published_response.json()
    assert publication["content_digest"] == preview["digest"]
    assert publication["blocks"][0]["subject_name"] == "Publication Subject"
    assert publication["blocks"][0]["assignments"][0]["teacher_name"] == "Publication Teacher"
    assert client.put(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}",
        json={
            "offering_id": publication["blocks"][0]["source_offering_id"],
            "group_id": publication["blocks"][0]["source_group_id"],
            "classroom_id": publication["blocks"][0]["source_classroom_id"],
            "activity_type": "theory", "weekday": "monday",
            "start_time": "08:00", "end_time": "09:00",
        },
    ).status_code == 409
    assert client.post(
        f"{BASE}/schedule-drafts/{draft['id']}/archive"
    ).status_code == 409
    history = client.get(
        f"{BASE}/schedule-publications",
        params={"program_id": program["id"], "academic_period": "I/2027"},
    )
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [publication["id"]]
    clone = client.post(
        f"{BASE}/schedule-publications/{publication['id']}/clone",
        json={"name": "Publication clone"},
    )
    assert clone.status_code == 201, clone.text
    assert clone.json()["status"] == "draft"
    cloned_blocks = client.get(
        f"{BASE}/schedule-drafts/{clone.json()['id']}/blocks"
    ).json()
    assert len(cloned_blocks) == 1
    cloned_assignments = client.get(
        f"{BASE}/schedule-drafts/{clone.json()['id']}/blocks/{cloned_blocks[0]['id']}/assignments"
    ).json()
    assert [(item["teacher_ci"], item["effective_from"], item["effective_to"]) for item in cloned_assignments] == [
        ("PUB-T1", "2027-01-01", None)
    ]
    equivalent = _preview(client, clone.json()["id"])
    assert equivalent["diff"] == {
        "added_blocks": 0, "removed_blocks": 0, "changed_blocks": 0,
        "teacher_replacements": 0, "workload_changes": [],
    }


def test_retroactive_blockers_are_scoped_count_only_and_future_is_unblocked(client, db_session):
    _program, _subject, _offering, _group, _room, draft, block, teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    designation = Designation(
        teacher_ci=teacher.ci, subject="Publication Subject", semester="1", group_code="A",
        academic_period="I/2027", designation_type="regular",
        schedule_json=[{"dia": "monday", "hora_inicio": "08:00", "hora_fin": "09:00", "horas_academicas": 1}],
    )
    db_session.add(designation)
    db_session.flush()
    db_session.add_all([
        AttendanceRecord(
            teacher_ci=teacher.ci, designation_id=designation.id, date=date(2027, 3, 1),
            scheduled_start=time(8), scheduled_end=time(9), status="ATTENDED",
            academic_hours=1, late_minutes=0, month=3, year=2027,
        ),
        PracticeAttendanceLog(
            teacher_ci=teacher.ci, designation_id=designation.id, date=date(2027, 3, 1),
            scheduled_start=time(8), scheduled_end=time(9), status="attended", academic_hours=1,
        ),
        PlanillaOutput(
        month=12, year=2027, total_teachers=1, total_hours=1, total_payment=1,
        status="generated",
        ),
        PracticePlanillaOutput(
            month=11, year=2027, total_teachers=1, total_hours=1, total_payment=1,
            status="generated",
        ),
    ])
    billing = BillingPublication(
        month=10, year=2027, planilla_type="regular", status="published", version=1,
        total_teachers=1, total_payment=1,
    )
    db_session.add(billing)
    db_session.flush()
    db_session.add(BillingPublicationRevision(
        publication_id=billing.id, version=1, calculation_digest="a" * 64,
        billing_digest="b" * 64, calculation_snapshot={}, billing_snapshot={},
    ))
    db_session.flush()
    retroactive = _preview(client, draft["id"], "2026-01-01")
    assert retroactive["can_publish"] is False
    operational = {
        item["category"]: item for item in retroactive["blockers"]
        if item["category"] not in {"teacher_coverage_start"}
    }
    assert set(operational) == {
        "regular_attendance", "practice_attendance", "regular_planilla",
        "practice_planilla", "billing_publication", "billing_revision",
    }
    assert all(set(item) == {"category", "count", "message"} for item in operational.values())
    assert all(item["count"] == 1 for item in operational.values())
    assert "PUB-T1" not in str(retroactive["blockers"])
    future = _preview(client, draft["id"], "2027-02-01")
    assert future["can_publish"] is True


def test_effective_schedule_adapter_prefers_latest_publication_and_suppresses_matching_legacy(
    client, db_session
):
    _program, _subject, _offering, _group, _room, draft, block, teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    preview = _preview(client, draft["id"])
    first_publication = _publish(client, draft["id"], preview)
    assert first_publication.status_code == 201
    clone = client.post(
        f"{BASE}/schedule-publications/{first_publication.json()['id']}/clone",
        json={"name": "Later publication"},
    ).json()
    cloned_block = client.get(f"{BASE}/schedule-drafts/{clone['id']}/blocks").json()[0]
    cloned_assignment = client.get(
        f"{BASE}/schedule-drafts/{clone['id']}/blocks/{cloned_block['id']}/assignments"
    ).json()[0]
    assert client.delete(
        f"{BASE}/schedule-drafts/{clone['id']}/blocks/{cloned_block['id']}/assignments/{cloned_assignment['id']}"
    ).status_code == 204
    db_session.add(Teacher(ci="PUB-T2", full_name="Later Publication Teacher"))
    db_session.flush()
    assert client.post(f"{BASE}/availability", json={
        "teacher_ci": "PUB-T2", "academic_period": "I/2027", "weekday": "monday",
        "start_time": "07:00", "end_time": "12:00",
    }).status_code == 201
    assert client.post(
        f"{BASE}/schedule-drafts/{clone['id']}/blocks/{cloned_block['id']}/assignments",
        json={"teacher_ci": "PUB-T2", "effective_from": "2027-01-01", "effective_to": None},
    ).status_code == 201
    later_preview = _preview(client, clone["id"], "2027-04-01")
    assert _publish(client, clone["id"], later_preview).status_code == 201
    db_session.add_all([
        Designation(
            teacher_ci=teacher.ci, subject="Publication Subject", semester="1", group_code="A",
            academic_period="I/2027", designation_type="regular",
            schedule_json=[{"dia": "monday", "hora_inicio": "08:00", "hora_fin": "09:00", "horas_academicas": 1}],
        ),
        Designation(
            teacher_ci=teacher.ci, subject="Legacy Only", semester="2", group_code="B",
            academic_period="I/2027", designation_type="regular",
            schedule_json=[{"dia": "monday", "hora_inicio": "10:00", "hora_fin": "11:00", "horas_academicas": 1}],
        ),
    ])
    db_session.flush()
    fallback_slots = effective_schedule_slots(db_session, "I/2027", date(2027, 1, 15))
    assert {(item.subject, item.source_type) for item in fallback_slots} == {
        ("Publication Subject", "legacy"), ("Legacy Only", "legacy")
    }
    earlier_slots = effective_schedule_slots(db_session, "I/2027", date(2027, 3, 1))
    assert [(item.subject, item.source_type) for item in earlier_slots] == [
        ("Publication Subject", "published"), ("Legacy Only", "legacy")
    ]
    assert earlier_slots[0].teacher_ci == "PUB-T1"
    later_slots = effective_schedule_slots(db_session, "I/2027", date(2027, 5, 1))
    assert later_slots[0].teacher_ci == "PUB-T2"
    assert later_slots[0].published_assignment_id is not None
    assert later_slots[1].designation_id is not None


def test_attendance_engine_persists_published_and_unrelated_legacy_sources(
    client, db_session, monkeypatch, tmp_path
):
    _program, _subject, _offering, _group, _room, draft, block, teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    preview = _preview(client, draft["id"])
    published = _publish(client, draft["id"], preview)
    assert published.status_code == 201, published.text

    db_session.add_all([
        Designation(
            teacher_ci=teacher.ci, subject="Publication Subject", semester="1", group_code="A",
            academic_period="I/2027", designation_type="regular",
            schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:00", "horas_academicas": 1}],
        ),
        Designation(
            teacher_ci=teacher.ci, subject="Legacy Only", semester="2", group_code="B",
            academic_period="I/2027", designation_type="regular",
            schedule_json=[{"dia": "lunes", "hora_inicio": "10:00", "hora_fin": "11:00", "horas_academicas": 1}],
        ),
        BiometricUpload(
            filename="published-attendance.xlsx", month=3, year=2027,
            total_records=0, total_teachers=0, status="processed",
        ),
    ])
    db_session.flush()
    upload = db_session.query(BiometricUpload).filter_by(filename="published-attendance.xlsx").one()
    monkeypatch.setattr(
        "app.services.attendance_engine.app_settings_service.get_active_academic_period",
        lambda _db: "I/2027",
    )

    result = AttendanceEngine().process_month(
        db_session,
        upload_id=upload.id,
        month=3,
        year=2027,
        start_date=date(2027, 3, 1),
        end_date=date(2027, 3, 1),
    )
    records = db_session.query(AttendanceRecord).order_by(AttendanceRecord.scheduled_start).all()

    assert result.total_slots == 2
    assert result.absent == 2
    assert [(record.source_kind, record.designation_id is not None) for record in records] == [
        ("published", False),
        ("legacy", True),
    ]
    assert records[0].published_schedule_assignment_id == (
        published.json()["blocks"][0]["assignments"][0]["id"]
    )

    attendance_response = client.get("/api/attendance/3/2027")
    assert attendance_response.status_code == 200, attendance_response.text
    attendance_items = attendance_response.json()["items"]
    assert {item["source_kind"] for item in attendance_items} == {"legacy", "published"}
    assert all(item["source_key"] for item in attendance_items)
    published_item = next(item for item in attendance_items if item["source_kind"] == "published")
    assert published_item["designation_id"] is None
    assert published_item["subject"] == "Publication Subject"

    summary_response = client.get("/api/attendance/3/2027/summary")
    assert summary_response.status_code == 200, summary_response.text
    assert {item["source_kind"] for item in summary_response.json()["observations"]} == {
        "legacy", "published"
    }

    audit_response = client.get(
        f"/api/attendance/audit/{teacher.ci}", params={"month": 3, "year": 2027}
    )
    assert audit_response.status_code == 200, audit_response.text
    assert {item["source_kind"] for item in audit_response.json()["attendance_detail"]} == {
        "legacy", "published"
    }
    assert {item["subject"] for item in audit_response.json()["attendance_detail"]} == {
        "Publication Subject", "Legacy Only"
    }
    monkeypatch.setattr("app.services.audit_report_pdf._output_dir", lambda: tmp_path)
    audit_pdf_response = client.get(
        f"/api/attendance/audit/{teacher.ci}/pdf", params={"month": 3, "year": 2027}
    )
    assert audit_pdf_response.status_code == 200, audit_pdf_response.text
    from io import BytesIO
    from pypdf import PdfReader
    audit_pdf_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(audit_pdf_response.content)).pages
    )
    assert "Publication Subject" in audit_pdf_text
    assert "Legacy Only" in audit_pdf_text

    report_response = client.get(
        "/api/reports/preview",
        params={"report_type": "attendance", "month": 3, "year": 2027},
    )
    assert report_response.status_code == 200, report_response.text
    assert {item["source_kind"] for item in report_response.json()["records_sample"]} == {
        "legacy", "published"
    }

    payroll_rows, payroll_details, payroll_warnings = PlanillaGenerator()._build_planilla_data(
        db_session,
        month=3,
        year=2027,
        start_date=date(2027, 3, 1),
        end_date=date(2027, 3, 1),
        discount_mode="full",
    )
    assert len(payroll_rows) == 2
    assert payroll_details == []
    assert payroll_warnings == []
    assert {row.source_kind for row in payroll_rows} == {"legacy", "published"}
    monkeypatch.setattr("app.services.report_generator._output_dir", lambda: tmp_path)
    report = ReportGenerator().generate_attendance_report(
        db_session, month=3, year=2027, teacher_ci=teacher.ci
    )
    report_text = "\n".join(page.extract_text() or "" for page in PdfReader(report.file_path).pages)
    assert "Publication Subject" in report_text
    assert "Legacy Only" in report_text


def test_published_theory_and_practice_use_distinct_sources_rates_and_snapshots(
    client, db_session, monkeypatch
):
    _program, _subject, offering, group, room, draft, theory, teacher = _seed(client, db_session)
    practice = _post(client, f"/schedule-drafts/{draft['id']}/blocks", {
        "offering_id": offering["id"], "group_id": group["id"],
        "classroom_id": room["id"], "activity_type": "practice",
        "weekday": "monday", "start_time": "09:00", "end_time": "10:00",
    })
    _assign(client, draft["id"], theory["id"])
    _assign(client, draft["id"], practice["id"])
    preview = _preview(client, draft["id"], effective="2027-03-01")
    published = _publish(client, draft["id"], preview)
    assert published.status_code == 201, published.text
    monkeypatch.setattr(
        "app.services.app_settings_service.get_active_academic_period", lambda _db: "I/2027"
    )

    generated = client.post("/api/practice-attendance/generate", json={
        "month": 3, "year": 2027, "start_date": "2027-03-01", "end_date": "2027-03-01",
    })
    assert generated.status_code == 200, generated.text
    assert generated.json()["created"] == 1
    listed = client.get("/api/practice-attendance/3/2027", params={
        "start_date": "2027-03-01", "end_date": "2027-03-01",
    })
    assert listed.status_code == 200, listed.text
    practice_entry = listed.json()[0]
    assert practice_entry["designation_id"] is None
    assert practice_entry["source_kind"] == "published"
    assert practice_entry["source_key"].startswith("published:")
    assert client.put(
        f"/api/practice-attendance/{practice_entry['id']}", json={"status": "attended"}
    ).status_code == 200

    regular_rows = PlanillaGenerator()._build_planilla_data(
        db_session, 3, 2027, start_date=date(2027, 3, 1), end_date=date(2027, 3, 1),
        discount_mode="full",
    )[0]
    practice_rows = PracticePlanillaGenerator()._build_planilla_data(
        db_session, 3, 2027, start_date=date(2027, 3, 1), end_date=date(2027, 3, 1),
        discount_mode="attendance",
    )[0]
    assert [(row.activity_kind, row.rate_per_hour, row.payable_hours) for row in regular_rows] == [
        ("theory", 70.0, 1)
    ]
    assert [(row.activity_kind, row.rate_per_hour, row.payable_hours) for row in practice_rows] == [
        ("practice", 50.0, 1)
    ]
    combined_total = sum(row.final_payment for row in [*regular_rows, *practice_rows])
    assert combined_total == 120.0

    snapshot = build_calculation_snapshot(
        rows=[*regular_rows, *practice_rows],
        row_amounts=[row.final_payment for row in [*regular_rows, *practice_rows]],
        month=3, year=2027, start_date=date(2027, 3, 1), end_date=date(2027, 3, 1),
        discount_mode="attendance", payment_overrides={}, excluded_days=[],
    )
    assert {item["activity_kind"] for item in snapshot["designations"]} == {"theory", "practice"}
    assert all(item["source_kind"] == "published" for item in snapshot["designations"])
    assert all(item["published_schedule_assignment_id"] for item in snapshot["designations"])


def test_midmonth_replacement_splits_payroll_by_actual_published_slots(
    client, db_session, monkeypatch
):
    _program, _subject, _offering, _group, _room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    replacement = Teacher(ci="PUB-T2", full_name="Replacement Teacher")
    db_session.add(replacement)
    db_session.flush()
    availability = client.post(f"{BASE}/availability", json={
        "teacher_ci": replacement.ci, "academic_period": "I/2027", "weekday": "monday",
        "start_time": "07:00", "end_time": "12:00",
    })
    assert availability.status_code == 201, availability.text
    replaced = client.post(
        f"{BASE}/schedule-drafts/{draft['id']}/blocks/{block['id']}/assignments/replace",
        json={"teacher_ci": replacement.ci, "effective_from": "2027-03-15", "effective_to": None},
    )
    assert replaced.status_code == 201, replaced.text
    preview = _preview(client, draft["id"], effective="2027-02-01")
    assert _publish(client, draft["id"], preview).status_code == 201
    monkeypatch.setattr(
        "app.services.app_settings_service.get_active_academic_period", lambda _db: "I/2027"
    )

    rows = PlanillaGenerator()._build_planilla_data(
        db_session, month=3, year=2027, discount_mode="full"
    )[0]
    assert [(row.teacher_ci, row.base_monthly_hours, row.payable_hours) for row in rows] == [
        ("PUB-T1", 2, 2),
        ("PUB-T2", 3, 3),
    ]
    assert sum(row.final_payment for row in rows) == 5 * 70.0

def test_publication_preview_discloses_operational_boundary(client, db_session):
    _program, _subject, _offering, _group, _room, draft, block, _teacher = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    preview = _preview(client, draft["id"])
    assert any("asistencia regular" in warning for warning in preview["warnings"])
    assert any("práctica" in warning for warning in preview["warnings"])
