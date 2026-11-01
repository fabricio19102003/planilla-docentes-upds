"""Semester to take, regular/recursado/pending subjects, scholarship and amounts (S3, S6)."""
from __future__ import annotations

import hashlib
import itertools

from app.models.academic_records import Student
from app.services import academic_history_import as importer
from app.services import reenrollment_eligibility as eligibility
from tests.test_academic_history_import import _csv, _row

I_2025 = {"literal": "Primer Semestre", "year": "2025", "offer": "2025/ Semestre I"}
II_2025 = {"literal": "Segundo Semestre", "year": "2025", "offer": "2025/ Semestre II"}
I_2026 = {"literal": "Primer Semestre", "year": "2026", "offer": "2026/1/1"}
II_2026 = {"literal": "Segundo Semestre", "year": "2026", "offer": "2026/2/1"}
INV_2026 = {"literal": "Invierno", "year": "2026", "offer": "INVIERNO 2026"}
_REGISTRATION_IDS = itertools.count(50_000)


def _student(document):
    return {
        "EstudianteNroDocumento": document, "EstudianteTipoDocumento": "CI", "EstudianteNombre": "Est",
        "EstudianteApellidos": document, "EstudianteNacionalidad": "Boliviana",
    }


def _load(db_session, document, rows):
    student = _student(document)
    built = [_row(student, next(_REGISTRATION_IDS), subject, status, grade, **term)
             for subject, status, grade, term in rows]
    content = _csv(built)
    importer.apply(db_session, content, f"{document}.csv", hashlib.sha256(content).hexdigest(), None)
    return db_session.query(Student).filter_by(document_number=document).one()


def _codes(items):
    return [item["code"] for item in items]


def test_a_student_who_never_failed_takes_the_next_semester_with_fundador(db_session):
    student = _load(db_session, "GOOD-1", [
        ("Anatomía Humana I MRF-0100", "Aprobado", 80, II_2025),
        ("Salud Pública Comunidad I SPC-0100", "Aprobado", 75, II_2025),
        ("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026),
        ("Bioquímica y Biología Molecular II FUN-0200", "Aprobado", 70, I_2026),
        ("Caso Básico Clínico Integrador II CBC-0200", "Retirado", 0, I_2026),
    ])

    result = eligibility.evaluate(db_session, student)

    assert (result["last_term"], result["graded_term"]) == ("I/2026", "I/2026")
    assert (result["primary_semester"], result["target_semester"]) == (2, 3)
    assert _codes(result["regular"]) == [
        "FUN 0300", "FUN 0310", "CIR 0300", "SCP 0300", "INF 0310", "CBC 0300", "LIN 0330",
    ]
    assert result["recursado"] == []
    # Retirado only, never failed: offered again without the recursado fee. SPC 0100 counts as SCP 0100.
    assert [(p["code"], p["semester"]) for p in result["pending"]] == [("CBC 0200", 2)]
    assert result["scholarship"] == {
        "category": "fundador", "label": "Beca Fundador", "average": 72.5, "never_failed": True,
        "cuota": 850, "cuotas": 5, "total": 4250,
    }
    assert result["recursado_fee"] == {"per_subject": 1200, "subjects": 0, "charged_subjects": 0, "total": 0}


def test_failed_subjects_are_recursado_charged_for_three_at_most(db_session):
    student = _load(db_session, "FAIL-1", [
        ("Inglés Técnico I LIN-0130", "Reprobado", 40, I_2026),
        ("Embriología Humana I MRF-0110", "Reprobado", 20, I_2026),
        ("Histología I MRF-0120", "Reprobado", 10, I_2026),
        ("Anatomía Humana II MRF-0200", "Reprobado", 30, I_2026),
        ("Bioquímica II FUN-0200", "Aprobado", 65, I_2026),
        ("Introducción II PSI-0200", "Aprobado", 63, I_2026),
        ("Caso Básico II CBC-0200", "Aprobado", 70, I_2026),
    ])

    result = eligibility.evaluate(db_session, student)

    assert (result["primary_semester"], result["target_semester"]) == (2, 3)
    assert [(r["code"], r["semester"]) for r in result["recursado"]] == [
        ("MRF 0110", 1), ("MRF 0120", 1), ("LIN 0130", 1), ("MRF 0200", 2),
    ]
    assert result["recursado_fee"] == {"per_subject": 1200, "subjects": 4, "charged_subjects": 3, "total": 3600}
    assert result["scholarship"]["category"] == "sin_beca"
    assert result["scholarship"]["never_failed"] is False
    assert (result["scholarship"]["cuota"], result["scholarship"]["total"]) == (1600, 8000)


def test_a_failed_subject_approved_later_is_not_recursado_but_still_loses_the_scholarship(db_session):
    student = _load(db_session, "LATE-1", [
        ("Anatomía Humana I MRF-0100", "Reprobado", 30, II_2025),
        ("Anatomía Humana I MRF-0100", "Aprobado", 90, I_2026),
        ("Anatomía Humana II MRF-0200", "Aprobado", 90, I_2026),
    ])

    result = eligibility.evaluate(db_session, student)

    assert result["recursado"] == []
    assert result["scholarship"]["category"] == "sin_beca"


def test_desafio_needs_an_average_above_61(db_session):
    desafio = _load(db_session, "DES-1", [("Anatomía II MRF-0200", "Aprobado", 62, I_2026)])
    none = _load(db_session, "DES-2", [("Anatomía II MRF-0200", "Aprobado", 61, I_2026)])
    fundador_edge = _load(db_session, "DES-3", [("Anatomía II MRF-0200", "Aprobado", 64, I_2026)])

    assert eligibility.evaluate(db_session, desafio)["scholarship"]["category"] == "desafio"
    assert eligibility.evaluate(db_session, desafio)["scholarship"]["cuota"] == 1300
    assert eligibility.evaluate(db_session, none)["scholarship"]["category"] == "sin_beca"
    assert eligibility.evaluate(db_session, fundador_edge)["scholarship"]["category"] == "desafio"


def test_ties_go_to_the_higher_semester_and_intensive_terms_are_ignored(db_session):
    student = _load(db_session, "TIE-1", [
        ("Farmacología I FUN-0300", "Aprobado", 70, I_2026),
        ("Fisiología I FUN-0310", "Aprobado", 70, I_2026),
        ("Farmacología II FUN-0400", "Aprobado", 70, I_2026),
        ("Fisiología II FUN-0410", "Aprobado", 70, I_2026),
        ("Epidemiología SCP-0500", "Aprobado", 90, INV_2026),
    ])

    result = eligibility.evaluate(db_session, student)

    assert (result["last_term"], result["primary_semester"], result["target_semester"]) == ("I/2026", 4, 5)
    assert result["scholarship"]["average"] == 70


def test_an_ungraded_current_term_sets_the_semester_and_the_last_graded_term_the_average(db_session):
    student = _load(db_session, "CUR-1", [
        ("Anatomía Humana II MRF-0200", "Aprobado", 66, I_2026),
        ("Farmacología I FUN-0300", "Pendiente", 0, II_2026),
        ("Fisiología I FUN-0310", "Pendiente", 0, II_2026),
    ])

    result = eligibility.evaluate(db_session, student)

    assert (result["last_term"], result["graded_term"]) == ("II/2026", "I/2026")
    assert (result["primary_semester"], result["target_semester"]) == (3, 4)
    assert (result["scholarship"]["category"], result["scholarship"]["average"]) == ("fundador", 66)
    # Subjects still in progress are neither recursado nor pending.
    assert "FUN 0300" not in _codes(result["recursado"] + result["pending"])


def test_the_last_semester_is_the_cap_and_a_student_without_history_gets_no_target(db_session):
    student = _load(db_session, "LAST-1", [("Medicina Familiar SCP-1000", "Pendiente", 0, II_2026)])
    empty = Student(document_number="EMPTY-1", document_type="CI", first_names="A", last_names="B", is_foreign=False)
    db_session.add(empty)
    db_session.flush()

    assert eligibility.evaluate(db_session, student)["target_semester"] == 10
    result = eligibility.evaluate(db_session, empty)
    assert (result["primary_semester"], result["target_semester"], result["regular"]) == (None, None, [])
    assert result["scholarship"]["average"] is None
