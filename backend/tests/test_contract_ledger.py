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
        semester_hours=80,
        contract_start_date=date(2026, 2, 2),
        contract_end_date=date(2026, 6, 20),
    )
    practice = Designation(
        teacher_ci=teacher.ci,
        subject="Clínica",
        semester="I",
        group_code="P-1",
        academic_period="I/2026",
        designation_type="practice",
        schedule_json=[],
        semester_hours=96,
        contract_start_date=date(2026, 2, 9),
        contract_end_date=date(2026, 6, 27),
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


def _pdf_text(content: bytes) -> str:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    return " ".join(text.split())


def test_original_contract_uses_the_legal_template_with_separate_rates(
    db_session, contract_sources
):
    teacher, _theory, _practice, _state = contract_sources
    original = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    content = bytes(original.artifact_content)
    text = _pdf_text(content)

    assert original.template_version == "contract-ledger-v3"
    assert "CONTRACT-1 Pando" not in text
    for expected in (
        "CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES",
        "artículo 1297 del Código Civil",
        "PRIMERA: (DE LAS PARTES)",
        "UNIPANDO S.R.L",
        "Por otra, el señor(a) Docente Contrato hábil por ley, con C.I. CONTRACT-1, con domicilio en la "
        "Ciudad de Cobija",
        "SEGUNDA: (OBJETO)",
        "Proyecto Formativo de Aula",
        "Nº Materia Semestre Total Horas",
        "Materias de teoría",
        "1 Anatomía I 80",
        "Materias de práctica",
        "1 Clínica I 96",
        "QUINTA: (OBLIGACIONES DEL CONTRATISTA y PRODUCTOS REQUERIDOS)",
        "OCTAVA: (DURACIÓN, PRECIO, FORMA DE PAGO E IMPUESTOS)",
        "una duración de 4 meses y 25 días computables desde el 02 de febrero de 2026 al "
        "27 de junio de 2026",
        "Bs. 70,00 (Setenta bolivianos 00/100) para las materias de teoría",
        "Bs. 85,00 (Ochenta y cinco bolivianos 00/100) para las materias de práctica",
        "DÉCIMA SÉPTIMA: (CONFORMIDAD)",
        "Cobija, 02 de febrero de 2026.",
        "EL COMITENTE",
        "EL CONTRATISTA",
    ):
        assert expected in text
    for internal in (original.public_id, "contract-ledger", "designación #", "Fuente heredada", "2026-02-02"):
        assert internal not in text
    pages = PdfReader(io.BytesIO(content)).pages
    assert all(
        (float(page.mediabox.width), float(page.mediabox.height)) == (612.0, 936.0)
        for page in pages
    )


def test_single_activity_contract_keeps_the_original_rate_sentence(db_session, contract_sources):
    teacher, _theory, _practice, state = contract_sources
    state["practice"] = []
    original = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    text = _pdf_text(bytes(original.artifact_content))

    assert "el valor de la hora del servicio es de Bs. 70,00 (Setenta bolivianos 00/100). " in text
    assert "1 Anatomía I 80" in text
    assert "Materias de teoría" not in text
    assert "Clínica" not in text
    assert "desde el 02 de febrero de 2026 al 20 de junio de 2026" in text


def test_v1_contract_is_reissued_once_as_full_v2_contract_preserving_history(
    db_session, contract_sources, monkeypatch
):
    teacher, _theory, _practice, _state = contract_sources
    with monkeypatch.context() as legacy:
        legacy.setattr(ledger, "TEMPLATE_VERSION", "contract-ledger-v1")
        original = ledger.issue_contract(
            db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
        )
    original_bytes = bytes(original.artifact_content)

    reissue = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    replay = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )

    assert original.template_version == "contract-ledger-v1"
    assert reissue.id != original.id
    assert reissue.template_version == "contract-ledger-v3"
    assert reissue.document_kind == "amendment"
    assert reissue.amendment_sequence == 1
    assert reissue.root_contract_id == original.id
    assert reissue.predecessor_contract_id == original.id
    assert reissue.effective_date == date(2026, 1, 1)
    assert [(line.activity_kind, line.change_kind, float(line.hours)) for line in reissue.lines] == [
        ("practice", "full", 6.0),
        ("theory", "full", 4.0),
    ]
    text = _pdf_text(bytes(reissue.artifact_content))
    assert "CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES" in text
    assert "DÉCIMA SÉPTIMA: (CONFORMIDAD)" in text
    assert "ADENDA" not in text
    assert "Versión de plantilla" not in text
    assert replay.id == reissue.id
    assert db_session.query(ContractDocument).count() == 2
    db_session.refresh(original)
    assert bytes(original.artifact_content) == original_bytes


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
    text = _pdf_text(first)
    for expected in (
        "ADENDA N.º 2 AL CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES",
        "el señor(a) Docente Prueba con C.I. 123, en adelante el CONTRATISTA",
        "con efecto desde el 16 de marzo de 2026",
        "Anatomía I Cambio 4 → 2",
        "Bs. 70,00 (Setenta bolivianos 00/100)",
        "permanecen vigentes e inalteradas",
        "Cobija, 16 de marzo de 2026.",
        "EL CONTRATISTA",
    ):
        assert expected in text
    for internal in ("fixed-contract-id", "root-contract-id", ledger.TEMPLATE_VERSION, "designación #7"):
        assert internal not in text


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
    text = " ".join(text.split())
    assert "ADENDA N.º 1 AL CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES" in text
    assert "Nombre del docente Docente Contrato Docente Contrato Corregido" in text
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


def _issue(db_session, teacher, **kwargs):
    return ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando", **kwargs
    )


def test_default_contract_states_the_built_in_comitente_text(db_session, contract_sources):
    teacher, _theory, _practice, _state = contract_sources
    text = _pdf_text(bytes(_issue(db_session, teacher).artifact_content))

    assert (
        "representada legalmente en este acto por el señor Luis Michel Bravo Alencar con CI. N.º "
        "1750986 Pando Boliviano"
    ) in text
    assert (
        "según consta en el Testimonio N. º1818/2024, de fecha 4 de septiembre de 2024, otorgado "
        "ante la Notaría de Fe Pública N.º 10, a cargo del Notario Jaime David Canedo Encinas"
    ) in text
    assert "Cobija, 02 de febrero de 2026." in text


def test_custom_terms_render_persist_and_reissue_full_contract(db_session, contract_sources):
    teacher, _theory, _practice, _state = contract_sources
    custom = _issue(
        db_session,
        teacher,
        terms={"start": date(2026, 3, 1), "end": date(2026, 5, 31), "signature": date(2026, 2, 25)},
    )
    custom_bytes = bytes(custom.artifact_content)
    text = _pdf_text(custom_bytes)

    assert custom.document_kind == "original"
    assert (
        "una duración de 2 meses y 30 días computables desde el 01 de marzo de 2026 al "
        "31 de mayo de 2026"
    ) in text
    assert "Cobija, 25 de febrero de 2026." in text
    assert custom.full_snapshot["contract_terms"] == {
        "start": "2026-03-01", "end": "2026-05-31", "signature": "2026-02-25",
    }

    inherited = _issue(db_session, teacher)
    assert inherited.id == custom.id

    cleared = _issue(db_session, teacher, terms={})
    cleared_text = _pdf_text(bytes(cleared.artifact_content))
    assert cleared.id != custom.id
    assert cleared.document_kind == "amendment"
    assert cleared.amendment_sequence == 1
    assert [line.change_kind for line in cleared.lines] == ["full", "full"]
    assert "CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES" in cleared_text
    assert "ADENDA" not in cleared_text
    assert "desde el 02 de febrero de 2026 al 27 de junio de 2026" in cleared_text
    assert "contract_terms" not in cleared.full_snapshot
    db_session.refresh(custom)
    assert bytes(custom.artifact_content) == custom_bytes
    assert db_session.query(ContractDocument).count() == 2


def test_explicit_empty_terms_keep_the_default_contract(db_session, contract_sources):
    teacher, _theory, _practice, _state = contract_sources
    original = _issue(db_session, teacher)
    again = _issue(db_session, teacher, terms={})

    assert again.id == original.id
    assert "contract_terms" not in original.full_snapshot
    assert "comitente" not in original.full_snapshot
    assert db_session.query(ContractDocument).count() == 1


@pytest.mark.parametrize(
    ("terms", "message"),
    [
        (
            {"start": date(2026, 5, 1), "end": date(2026, 4, 30)},
            "La fecha de inicio del contrato no puede ser posterior a la fecha de fin.",
        ),
        (
            {"start": date(2025, 12, 31)},
            "Las fechas del contrato deben estar dentro del período I/2026 "
            "(01 de enero de 2026 al 30 de junio de 2026).",
        ),
        (
            {"end": date(2026, 7, 1)},
            "Las fechas del contrato deben estar dentro del período I/2026 "
            "(01 de enero de 2026 al 30 de junio de 2026).",
        ),
        (
            {"start": date(2026, 6, 28)},
            "La fecha de inicio del contrato no puede ser posterior a la fecha de fin.",
        ),
    ],
)
def test_invalid_terms_are_refused_without_issuing(db_session, contract_sources, terms, message):
    teacher, _theory, _practice, _state = contract_sources
    with pytest.raises(ledger.ContractIssuanceError) as excinfo:
        _issue(db_session, teacher, terms=terms)

    assert str(excinfo.value) == message
    assert db_session.query(ContractDocument).count() == 0


def test_comitente_settings_render_and_reissue_full_contract(db_session, contract_sources):
    from app.services import app_settings_service as settings

    teacher, _theory, _practice, _state = contract_sources
    original = _issue(db_session, teacher)
    for key, value in (
        (settings.KEY_CONTRACT_REPRESENTATIVE_NAME, "Ana María Suárez Vaca"),
        (settings.KEY_CONTRACT_REPRESENTATIVE_CI, "4455667 Beni"),
        (settings.KEY_CONTRACT_POWER_NUMBER, "2020/2026"),
        (settings.KEY_CONTRACT_POWER_DATE, "2026-01-15"),
        (settings.KEY_CONTRACT_NOTARY_OFFICE, "3"),
        (settings.KEY_CONTRACT_NOTARY_NAME, "Carla Rivero Paz"),
        (settings.KEY_CONTRACT_CITY, "Riberalta"),
    ):
        settings.update_setting(db_session, key, value)
    db_session.flush()

    reissue = _issue(db_session, teacher)
    text = _pdf_text(bytes(reissue.artifact_content))

    assert reissue.id != original.id
    assert reissue.document_kind == "amendment"
    assert [line.change_kind for line in reissue.lines] == ["full", "full"]
    assert (
        "representada legalmente en este acto por el señor Ana María Suárez Vaca con CI. N.º "
        "4455667 Beni Boliviano"
    ) in text
    assert (
        "según consta en el Testimonio N. º2020/2026, de fecha 15 de enero de 2026, otorgado "
        "ante la Notaría de Fe Pública N.º 3, a cargo del Notario Carla Rivero Paz"
    ) in text
    assert "Riberalta, 02 de febrero de 2026." in text
    assert "Luis Michel Bravo Alencar" not in text
    assert _issue(db_session, teacher).id == reissue.id


def test_issue_route_accepts_terms_and_reports_them(client, db_session, contract_sources):
    teacher, _theory, _practice, _state = contract_sources
    before = client.get(f"/api/contracts/terms/{teacher.ci}?academic_period=I/2026")
    issue = client.post(
        f"/api/contracts/issue/{teacher.ci}",
        json={
            "department": "Pando",
            "academic_period": "I/2026",
            "contract_start_date": "2026-03-01",
            "contract_end_date": "2026-05-31",
            "signature_date": "2026-02-25",
        },
    )
    after = client.get(f"/api/contracts/terms/{teacher.ci}?academic_period=I/2026")

    assert before.status_code == 200
    assert before.json() == {
        "academic_period": "I/2026",
        "period_start": "2026-01-01",
        "period_end": "2026-06-30",
        "default_start": "2026-02-02",
        "default_end": "2026-06-27",
        "contract_start_date": None,
        "contract_end_date": None,
        "signature_date": None,
    }
    assert issue.status_code == 200
    assert after.json()["contract_start_date"] == "2026-03-01"
    assert after.json()["contract_end_date"] == "2026-05-31"
    assert after.json()["signature_date"] == "2026-02-25"

    cleared = client.post(
        f"/api/contracts/issue/{teacher.ci}",
        json={"department": "Pando", "academic_period": "I/2026", "clear_custom_terms": True},
    )
    assert cleared.status_code == 200
    assert cleared.json()["public_id"] != issue.json()["public_id"]
    assert client.get(
        f"/api/contracts/terms/{teacher.ci}?academic_period=I/2026"
    ).json()["contract_start_date"] is None


def test_issue_route_rejects_invalid_terms_with_a_clear_message(client, db_session, contract_sources):
    teacher, _theory, _practice, _state = contract_sources
    response = client.post(
        f"/api/contracts/issue/{teacher.ci}",
        json={
            "department": "Pando",
            "academic_period": "I/2026",
            "contract_start_date": "2026-05-01",
            "contract_end_date": "2026-04-30",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "La fecha de inicio del contrato no puede ser posterior a la fecha de fin."
    )
    assert db_session.query(ContractDocument).count() == 0


def test_batch_route_ignores_custom_dates(client, db_session, contract_sources):
    teacher, _theory, _practice, _state = contract_sources
    response = client.post(
        "/api/contracts/generate-batch",
        json={
            "department": "Pando",
            "academic_period": "I/2026",
            "teacher_cis": [teacher.ci],
            "contract_start_date": "2026-03-01",
            "contract_end_date": "2026-05-31",
        },
    )

    assert response.status_code == 200
    document = db_session.query(ContractDocument).one()
    assert "contract_terms" not in document.full_snapshot
    assert "desde el 02 de febrero de 2026 al 27 de junio de 2026" in _pdf_text(
        bytes(document.artifact_content)
    )


def _designation(db_session, teacher, *, group, start, end, semester_hours):
    designation = Designation(
        teacher_ci=teacher.ci,
        subject="Histología I",
        semester="I",
        group_code=group,
        academic_period="I/2026",
        designation_type="regular",
        schedule_json=[],
        semester_hours=semester_hours,
        contract_start_date=start,
        contract_end_date=end,
    )
    db_session.add(designation)
    db_session.flush()
    return designation


def test_renamed_group_does_not_add_the_closed_group_hours(db_session, contract_sources):
    teacher, _theory, _practice, state = contract_sources
    closed = _designation(
        db_session, teacher, group="EXTRA",
        start=date(2026, 2, 2), end=date(2026, 3, 15), semester_hours=None,
    )
    renamed = _designation(
        db_session, teacher, group="T-2",
        start=date(2026, 3, 16), end=date(2026, 6, 20), semester_hours=100,
    )
    state["theory"] = [
        _source(closed, activity="theory", hours=5,
                effective_from=date(2026, 2, 2), effective_to=date(2026, 3, 15)),
        _source(renamed, activity="theory", hours=5,
                effective_from=date(2026, 3, 16), effective_to=date(2026, 6, 20)),
    ]
    state["practice"] = []

    document = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )
    text = _pdf_text(bytes(document.artifact_content))

    assert "1 Histología I I 100" in text
    assert "Histología I I 105" not in text
    assert "desde el 02 de febrero de 2026 al 20 de junio de 2026" in text
    assert [line["term_hours"] for line in document.full_snapshot["lines"]] == ["0.00", "100.00"]


def test_parallel_group_without_official_hours_keeps_its_hours(db_session, contract_sources):
    teacher, _theory, _practice, state = contract_sources
    parallel = _designation(
        db_session, teacher, group="EXTRA",
        start=date(2026, 2, 2), end=date(2026, 3, 15), semester_hours=None,
    )
    official = _designation(
        db_session, teacher, group="T-1",
        start=date(2026, 2, 2), end=date(2026, 6, 20), semester_hours=100,
    )
    state["theory"] = [
        _source(parallel, activity="theory", hours=5,
                effective_from=date(2026, 2, 2), effective_to=date(2026, 3, 15)),
        _source(official, activity="theory", hours=5,
                effective_from=date(2026, 2, 2), effective_to=date(2026, 6, 20)),
    ]
    state["practice"] = []

    document = ledger.issue_contract(
        db_session, teacher_ci=teacher.ci, academic_period="I/2026", department="Pando"
    )

    assert "1 Histología I I 105" in _pdf_text(bytes(document.artifact_content))
