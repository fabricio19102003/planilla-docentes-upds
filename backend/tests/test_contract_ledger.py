from __future__ import annotations

from datetime import date, time
from hashlib import sha256
import io

import pytest
from pypdf import PdfReader

from app.models.contract import ContractDocument
from app.models.academic_management import (
    AcademicProgram,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
)
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services import contract_ledger_service as ledger
from app.services.contract_pdf import render_contract_document_pdf
from app.services.payroll_schedule_source_service import PayrollScheduleSource


def _source(
    designation: Designation,
    *,
    activity: str,
    hours: int,
    effective_from: date = date(2026, 1, 1),
    effective_to: date = date(2026, 6, 30),
) -> PayrollScheduleSource:
    return PayrollScheduleSource(
        source_kind="legacy",
        source_id=designation.id,
        teacher_ci=designation.teacher_ci,
        subject=designation.subject,
        group_code=designation.group_code,
        semester=designation.semester,
        activity_kind=activity,
        effective_from=effective_from,
        effective_to=effective_to,
        designation_id=designation.id,
        weekly_hours=hours,
        schedule=[{
            "dia": "lunes" if activity == "theory" else "martes",
            "hora_inicio": "08:00",
            "hora_fin": "09:30",
            "horas_academicas": hours,
        }],
    )


@pytest.fixture
def contract_sources(db_session, monkeypatch):
    teacher = Teacher(ci="CONTRACT-1", full_name="Docente Contrato")
    db_session.add(teacher)
    db_session.flush()
    theory = Designation(
        teacher_ci=teacher.ci,
        subject="Anatomía",
        semester="I",
        group_code="M-1",
        academic_period="I/2026",
        designation_type="regular",
        schedule_json=[],
    )
    practice = Designation(
        teacher_ci=teacher.ci,
        subject="Clínica",
        semester="I",
        group_code="P-1",
        academic_period="I/2026",
        designation_type="practice",
        schedule_json=[],
    )
    db_session.add_all([theory, practice])
    db_session.flush()
    state = {
        "theory": [_source(theory, activity="theory", hours=4)],
        "practice": [_source(practice, activity="practice", hours=6)],
    }

    def sources(_db, *, activity_kind, **_kwargs):
        return state[activity_kind]

    monkeypatch.setattr(ledger, "payroll_schedule_sources", sources)
    monkeypatch.setattr(ledger.app_settings_service, "get_hourly_rate", lambda _db: 70.0)
    monkeypatch.setattr(ledger.app_settings_service, "get_practice_hourly_rate", lambda _db: 85.0)
    return teacher, theory, practice, state


def test_mixed_original_has_separate_theory_and_practice_rates_and_is_idempotent(
    db_session, contract_sources
):
    teacher, _theory, _practice, _state = contract_sources
    original = ledger.issue_contract(
        db_session,
        teacher_ci=teacher.ci,
        academic_period="I/2026",
        department="Pando",
    )
    first_bytes = bytes(original.artifact_content)
    replay = ledger.issue_contract(
        db_session,
        teacher_ci=teacher.ci,
        academic_period="I/2026",
        department="Pando",
    )

    assert replay.id == original.id
    assert replay.document_kind == "original"
    assert [(line.activity_kind, float(line.hourly_rate), float(line.hours)) for line in replay.lines] == [
        ("practice", 85.0, 6.0),
        ("theory", 70.0, 4.0),
    ]
    assert bytes(replay.artifact_content) == first_bytes
    assert replay.artifact_sha256 == sha256(first_bytes).hexdigest()
    assert db_session.query(ContractDocument).count() == 1


def test_changed_load_appends_amendment_and_preserves_original_bytes(
    db_session, contract_sources
):
    teacher, theory, _practice, state = contract_sources
    original = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    original_bytes = bytes(original.artifact_content)
    state["theory"] = [
        _source(
            theory,
            activity="theory",
            hours=2,
            effective_from=date(2026, 3, 16),
        )
    ]
    amendment = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    replay = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )

    assert amendment.document_kind == "amendment"
    assert amendment.amendment_sequence == 1
    assert amendment.root_contract_id == original.id
    assert amendment.predecessor_contract_id == original.id
    assert amendment.effective_date == date(2026, 3, 16)
    changed = next(line for line in amendment.lines if line.activity_kind == "theory")
    assert changed.change_kind == "changed"
    assert float(changed.previous_hours) == 4.0
    assert float(changed.hours) == 2.0
    assert replay.id == amendment.id
    db_session.refresh(original)
    assert bytes(original.artifact_content) == original_bytes


def test_empty_and_incoherent_periods_are_refused(db_session, contract_sources):
    teacher, _theory, _practice, state = contract_sources
    state["theory"] = []
    state["practice"] = []
    with pytest.raises(ledger.ContractIssuanceError, match="no tiene carga efectiva"):
        ledger.build_contract_snapshot(
            db_session,
            teacher_ci=teacher.ci,
            academic_period="I/2026",
            department="Pando",
        )
    with pytest.raises(ledger.ContractIssuanceError, match="no permite determinar fechas"):
        ledger.build_contract_snapshot(
            db_session,
            teacher_ci=teacher.ci,
            academic_period="GESTION-2026",
            department="Pando",
        )


def test_snapshot_pdf_is_deterministic_and_labels_amendment():
    payload = {
        "public_id": "fixed-contract-id",
        "document_kind": "amendment",
        "amendment_sequence": 2,
        "root_public_id": "root-contract-id",
        "effective_date": "2026-03-16",
        "issued_at": "2026-03-16T12:00:00",
        "teacher": {"ci": "123", "full_name": "Docente Prueba"},
        "academic_period": {"identity": "I/2026", "start": "2026-01-01", "end": "2026-06-30"},
        "department": "Pando",
        "template_version": ledger.TEMPLATE_VERSION,
        "metadata_changes": [],
        "lines": [{
            "activity_kind": "theory",
            "rate_class": "regular",
            "hourly_rate": "70.00",
            "hours": "2.00",
            "hour_basis": "weekly",
            "subject_label": "Anatomía",
            "group_label": "M-1",
            "semester_label": "I",
            "schedule_label": "lunes 08:00-09:30 (2h)",
            "effective_from": "2026-03-16",
            "effective_to": "2026-06-30",
            "source_kind": "legacy",
            "source_id": 7,
            "designation_id": 7,
            "publication_id": None,
            "publication_sequence": None,
            "publication_program_id": None,
            "authority_effective_from": "2026-03-16",
            "published_block_id": None,
            "published_assignment_id": None,
            "change_kind": "changed",
            "previous_hours": "4.00",
            "previous_hourly_rate": "70.00",
        }],
    }
    first = render_contract_document_pdf(payload)
    second = render_contract_document_pdf(payload)
    assert first == second
    assert b"%PDF" in first[:8]
    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(first)).pages)
    assert "Docente Prueba" in text
    assert "CI 123 Pando" in text
    assert ledger.TEMPLATE_VERSION in text
    assert "designación #7" in text


def test_non_contractual_profile_change_is_idempotent_and_legal_name_change_is_metadata_amendment(
    db_session, contract_sources
):
    teacher, _theory, _practice, _state = contract_sources
    original = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    original_hash = original.artifact_sha256

    teacher.email = "new-address@example.test"
    db_session.flush()
    replay = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    assert replay.id == original.id

    teacher.full_name = "Docente Contrato Corregido"
    db_session.flush()
    amendment = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    assert amendment.document_kind == "amendment"
    assert amendment.amendment_sequence == 1
    assert amendment.lines == []
    assert amendment.teacher_snapshot == {
        "ci": teacher.ci,
        "full_name": "Docente Contrato Corregido",
    }
    text = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(io.BytesIO(bytes(amendment.artifact_content))).pages
    )
    assert "Cambios de identificación contractual" in text
    assert "Docente Contrato Corregido" in text
    db_session.refresh(original)
    assert original.artifact_sha256 == original_hash


def test_removed_load_uses_new_authoritative_publication_date():
    old = {
        "activity_kind": "theory",
        "rate_class": "regular",
        "hourly_rate": "70.00",
        "hours": "4.00",
        "hour_basis": "weekly",
        "subject_label": "Anatomía",
        "group_label": "M-1",
        "semester_label": "I",
        "schedule_label": "lunes 08:00-09:30 (4h)",
        "effective_from": "2026-01-01",
        "effective_to": "2026-06-30",
        "source_kind": "published",
        "source_id": 11,
        "designation_id": None,
        "publication_id": 1,
        "publication_sequence": 1,
        "publication_program_id": 9,
        "authority_effective_from": "2026-01-01",
        "published_block_id": 21,
        "published_assignment_id": 11,
    }
    previous = {
        "teacher": {"ci": "123", "full_name": "Docente"},
        "academic_period": {"identity": "I/2026", "start": "2026-01-01", "end": "2026-06-30"},
        "department": "Pando",
        "template_version": ledger.TEMPLATE_VERSION,
        "lines": [old],
        "authority_transitions": [{
            "publication_id": 1, "program_id": 9, "sequence": 1,
            "effective_from": "2026-01-01",
        }],
    }
    current = ledger.ContractSnapshot(
        teacher={"ci": "123", "full_name": "Docente"},
        academic_period={"identity": "I/2026", "start": "2026-01-01", "end": "2026-06-30"},
        department="Pando",
        template_version=ledger.TEMPLATE_VERSION,
        lines=(),
        authority_transitions=({
            "publication_id": 1, "program_id": 9, "sequence": 1,
            "effective_from": "2026-01-01",
        }, {
            "publication_id": 2, "program_id": 9, "sequence": 2,
            "effective_from": "2026-04-06",
        }),
    )
    delta, effective_date, metadata = ledger._delta_lines(
        previous, current, issuance_date=date(2026, 4, 7)
    )
    assert effective_date == date(2026, 4, 6)
    assert delta[0]["change_kind"] == "removed"
    assert metadata == []


def test_removed_load_without_authoritative_transition_is_refused(db_session, contract_sources):
    teacher, _theory, _practice, state = contract_sources
    ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    state["theory"] = []
    state["practice"] = []
    with pytest.raises(ledger.ContractIssuanceError, match="fecha efectiva autoritativa"):
        ledger.issue_contract(
            db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
        )


def test_service_rejects_mixed_published_provenance(db_session, monkeypatch):
    teacher = Teacher(ci="PUBLISHED-1", full_name="Published Teacher")
    program = AcademicProgram(code="MED-LEDGER", name="Medicine", active=True)
    db_session.add_all([teacher, program])
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
        effective_from=date(2026, 2, 2),
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
        subject_name="Anatomy",
        group_code="M-1",
        semester=1,
        classroom_code="A1",
        classroom_name="Room A1",
        activity_type="theory",
        weekday="monday",
        start_time=time(8, 0),
        end_time=time(9, 30),
    )
    db_session.add(block)
    db_session.flush()
    assignment = AcademicSchedulePublishedAssignment(
        publication_block_id=block.id,
        source_assignment_id=1,
        teacher_ci=teacher.ci,
        teacher_name=teacher.full_name,
        effective_from=date(2026, 2, 2),
        effective_to=date(2026, 6, 30),
    )
    db_session.add(assignment)
    db_session.flush()
    source = PayrollScheduleSource(
        source_kind="published",
        source_id=assignment.id,
        teacher_ci=teacher.ci,
        subject="Anatomy",
        group_code="M-1",
        semester="I",
        activity_kind="theory",
        effective_from=date(2026, 2, 2),
        effective_to=date(2026, 6, 30),
        publication_id=publication.id,
        published_block_id=block.id + 999,
        published_assignment_id=assignment.id,
        schedule=[{
            "dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30",
            "horas_academicas": 2,
        }],
    )
    monkeypatch.setattr(
        ledger,
        "payroll_schedule_sources",
        lambda _db, *, activity_kind, **_kwargs: [source] if activity_kind == "theory" else [],
    )
    monkeypatch.setattr(ledger.app_settings_service, "get_hourly_rate", lambda _db: 70.0)
    monkeypatch.setattr(ledger.app_settings_service, "get_practice_hourly_rate", lambda _db: 85.0)
    with pytest.raises(ledger.ContractIssuanceError, match="procedencia publicada coherente"):
        ledger.build_contract_snapshot(
            db_session,
            teacher_ci=teacher.ci,
            academic_period="I/2026",
            department="Pando",
        )


def test_contract_history_get_download_and_compatibility_route(
    client, db_session, contract_sources
):
    teacher, _theory, _practice, _state = contract_sources
    issue = client.post(
        f"/api/contracts/issue/{teacher.ci}",
        json={"department": "Pando", "academic_period": "I/2026"},
    )
    assert issue.status_code == 200
    public_id = issue.json()["public_id"]
    history = client.get(f"/api/contracts/history?teacher_ci={teacher.ci}")
    detail = client.get(f"/api/contracts/documents/{public_id}")
    download = client.get(f"/api/contracts/documents/{public_id}/download")
    compatibility = client.post(
        f"/api/contracts/generate/{teacher.ci}",
        json={"department": "Pando", "academic_period": "I/2026"},
    )
    assert history.status_code == detail.status_code == download.status_code == compatibility.status_code == 200
    assert [item["public_id"] for item in history.json()] == [public_id]
    assert detail.json()["version"] == 1
    assert download.content == compatibility.content
    assert download.headers["etag"] == f'"{issue.json()["artifact_sha256"]}"'


def test_mutable_contract_date_route_is_retired(client, contract_sources):
    _teacher, theory, _practice, _state = contract_sources
    response = client.put(
        f"/api/teachers/designations/{theory.id}/contract-dates",
        json={"contract_start_date": "2026-01-01", "contract_end_date": "2026-06-30"},
    )
    assert response.status_code == 410
