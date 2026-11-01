from __future__ import annotations

import csv
import hashlib
import io
from datetime import date

import pytest

from app.models.academic_management import AcademicSubject
from app.models.academic_records import (
    AcademicHistoryImport,
    AcademicTerm,
    CurriculumPlan,
    Student,
    StudentSubjectRecord,
)
from app.models.teacher import Teacher
from app.services import academic_history_import as importer

COLUMNS = (
    "EstudianteNombre,EstudianteApellidos,EstudianteNroDocumento,EstudianteTipoDocumento,"
    "EstudianteFechaNacimiento,EstudianteGenero,EstudianteCelular,EstudianteCorreoPersonal,"
    "EstudianteCorreoAcademico,EstudiantePaisNacimiento,EstudianteNacionalidad,InstitucionEducativa,"
    "DireccionDomicilio,DocenteNombre,DocenteApellidos,DocenteNroDocumento,DocenteTipoDocumento,"
    "DocenteFechaNacimiento,DocenteGenero,DocenteCelular,DocenteCorreoPersonal,DocenteCorreoAcademico,"
    "DocentePaisNacimiento,DocenteNacionalidad,DocenteNivelEstudio,DocenteProfesion,DocenteFechaIngreso,"
    "DocenteEstado,DocenteTipoContrato,RegistroMateriaID,EstadoRegistroMateria,Carrera,PlanEstudio,"
    "MateriaNombreSigla,GrupoNombre,GrupoTurno,OfertaPeriodoLiteral,OfertaGestion,OfertaNombre,"
    "RegistroMateriaNota,GrupoAprobados,GrupoReprobados,GrupoPromedioNota,TotalMateriasAprobadas,"
    "TotalMateriasConvalidadas,TotalMateriasReprobadas,TotalMateriasCursadas,EstadoActualInscripcion"
).split(",")

RAIMUNDA = {
    "EstudianteNombre": "Raimunda Jaisa", "EstudianteApellidos": "Paiva Da Silva",
    "EstudianteNroDocumento": "I-11626046", "EstudianteTipoDocumento": "CEDULA DE EXTRANJERIA",
    "EstudianteFechaNacimiento": "25/12/1993 12:00:00 a. m.", "EstudianteGenero": "FEMENINO",
    "EstudianteCelular": "+55681010224", "EstudianteCorreoPersonal": "jaisa@example.com",
    "EstudianteCorreoAcademico": "co.raimunda.paiva.d@upds.net.bo", "EstudiantePaisNacimiento": "Brasil",
    "EstudianteNacionalidad": "Brasileña", "InstitucionEducativa": "GLORIA PEREZ",
    "DireccionDomicilio": "BRASILEIA - COBIJA", "EstadoActualInscripcion": "Antiguo",
}
CARLOS = {
    **RAIMUNDA, "EstudianteNombre": "Carlos", "EstudianteApellidos": "Mamani Quispe",
    "EstudianteNroDocumento": "7485000", "EstudianteTipoDocumento": "CARNET DE IDENTIDAD",
    "EstudianteNacionalidad": "Boliviana", "EstudiantePaisNacimiento": "Bolivia",
    "EstudianteCorreoAcademico": "ND",
}
TEACHER = {
    "DocenteNombre": "Lesly", "DocenteApellidos": "Guerrero Ortega", "DocenteNroDocumento": "7485425",
}


def _row(student, registration_id, subject, status, grade, *, literal="Primer Semestre",
         year="2023", offer="2023/1/1", group="Q", shift="Noche", teacher=TEACHER):
    row = dict.fromkeys(COLUMNS, "")
    row.update(student)
    row.update(teacher)
    row.update({
        "RegistroMateriaID": str(registration_id), "EstadoRegistroMateria": status,
        "Carrera": "Medicina", "PlanEstudio": "Medicina 510-01", "MateriaNombreSigla": subject,
        "GrupoNombre": group, "GrupoTurno": shift, "OfertaPeriodoLiteral": literal,
        "OfertaGestion": year, "OfertaNombre": offer, "RegistroMateriaNota": str(grade),
    })
    return row


def _csv(rows, columns=COLUMNS) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _rows():
    return [
        _row(RAIMUNDA, 5253, "Inglés Técnico I LIN-0130", "Aprobado", 73),
        _row(RAIMUNDA, 5254, "Anatomía Humana I MRF-0100", "Reprobado", 0),
        _row(RAIMUNDA, 9001, "Medicina del Deporte ELE-0690", "Aprobado", 80,
             literal="Invierno", year="2024", offer="INVIERNO 2024"),
        _row(CARLOS, 9100, "Nefrología MED-0650", "Pendiente", 0,
             literal="Segundo Semestre", year="2026", offer="2026/2/1"),
        _row(CARLOS, 9101, "Fisiología I FUN-0310", "Retirado", 0,
             literal="Segundo Semestre", year="2025", offer="2025/ Semestre II", teacher={}),
    ]


def _counts(result):
    return {key: result["counts"][key] for key in (
        "rows", "valid_rows", "error_rows", "students_new", "students_updated", "students_unchanged",
        "records_new", "records_updated", "records_unchanged", "terms_new",
    )}


def test_preview_reports_what_would_change_without_writing(db_session):
    content = _csv(_rows())

    result = importer.preview(db_session, content, "gestion-2023.csv")

    assert result["file_sha256"] == hashlib.sha256(content).hexdigest()
    assert _counts(result) == {
        "rows": 5, "valid_rows": 5, "error_rows": 0, "students_new": 2, "students_updated": 0,
        "students_unchanged": 0, "records_new": 5, "records_updated": 0, "records_unchanged": 0,
        "terms_new": 4,
    }
    assert result["terms"] == ["I/2023", "INV/2024", "II/2025", "II/2026"]
    assert result["issues"] == [{
        "level": "warning", "row": None, "rows": 1,
        "message": "Materia fuera de malla: ELE 0690 (Medicina del Deporte)",
    }]
    assert db_session.query(Student).count() == 0
    assert db_session.query(StudentSubjectRecord).count() == 0
    assert db_session.query(AcademicTerm).count() == 0
    assert db_session.query(CurriculumPlan).count() == 0


def test_apply_imports_students_terms_and_history(db_session):
    db_session.add(Teacher(ci="7485425", full_name="Lesly Guerrero Ortega"))
    db_session.flush()
    content = _csv(_rows())

    result = importer.apply(db_session, content, "gestion-2023.csv", hashlib.sha256(content).hexdigest(), None)

    assert result["counts"]["records_new"] == 5
    receipt = db_session.get(AcademicHistoryImport, result["import_id"])
    assert receipt.file_name == "gestion-2023.csv"
    assert receipt.file_sha256 == hashlib.sha256(content).hexdigest()
    assert receipt.terms == ["I/2023", "INV/2024", "II/2025", "II/2026"]

    raimunda = db_session.query(Student).filter_by(document_number="I-11626046").one()
    assert (raimunda.first_names, raimunda.last_names) == ("Raimunda Jaisa", "Paiva Da Silva")
    assert raimunda.birth_date == date(1993, 12, 25)
    assert raimunda.is_foreign is True
    assert raimunda.legacy_enrollment_status == "Antiguo"
    assert raimunda.curriculum_plan_id == db_session.query(CurriculumPlan).one().id
    carlos = db_session.query(Student).filter_by(document_number="7485000").one()
    assert carlos.is_foreign is False
    assert carlos.academic_email is None

    winter = db_session.query(AcademicTerm).filter_by(code="INV/2024").one()
    assert (winter.year, winter.kind, winter.is_intensive) == (2024, "INV", True)
    assert winter.legacy_names == ["INVIERNO 2024"]
    assert db_session.query(AcademicTerm).filter_by(code="II/2025").one().legacy_names == ["2025/ Semestre II"]

    records = {r.legacy_registration_id: r for r in db_session.query(StudentSubjectRecord)}
    english = records[5253]
    assert (english.subject.code, english.term.code, english.status, english.grade) == (
        "LIN 0130", "I/2023", "aprobado", 73,
    )
    assert (english.group_code, english.shift, english.teacher_ci) == ("Q", "Noche", "7485425")
    assert english.teacher_name == "Lesly Guerrero Ortega"
    assert records[5254].grade == 0 and records[5254].status == "reprobado"
    assert records[9100].grade is None and records[9100].status == "pendiente"
    assert records[9101].grade is None and records[9101].teacher_document is None
    assert records[9001].subject.code == "ELE 0690"
    assert db_session.query(Teacher).count() == 1


def test_reimport_updates_changed_records_and_never_duplicates(db_session):
    first = _csv(_rows())
    importer.apply(db_session, first, "a.csv", hashlib.sha256(first).hexdigest(), None)
    rows = _rows()
    rows[3] = _row(CARLOS, 9100, "Nefrología MED-0650", "Aprobado", 81,
                   literal="Segundo Semestre", year="2026", offer="2026/2/1")
    for row in rows[3:]:
        row["EstudianteCelular"] = "+59170000000"
    second = _csv(rows)

    result = importer.apply(db_session, second, "b.csv", hashlib.sha256(second).hexdigest(), None)

    assert _counts(result) == {
        "rows": 5, "valid_rows": 5, "error_rows": 0, "students_new": 0, "students_updated": 1,
        "students_unchanged": 1, "records_new": 0, "records_updated": 1, "records_unchanged": 4,
        "terms_new": 0,
    }
    record = db_session.query(StudentSubjectRecord).filter_by(legacy_registration_id=9100).one()
    assert (record.status, record.grade) == ("aprobado", 81)
    assert db_session.query(Student).filter_by(document_number="7485000").one().phone == "+59170000000"
    assert db_session.query(StudentSubjectRecord).count() == 5
    assert db_session.query(Student).count() == 2
    assert db_session.query(AcademicHistoryImport).count() == 2


def test_apply_refuses_a_file_that_changed_after_preview(db_session):
    content = _csv(_rows())

    with pytest.raises(importer.ImportConflict, match="El archivo cambió después de la vista previa"):
        importer.apply(db_session, content, "a.csv", "0" * 64, None)

    assert db_session.query(Student).count() == 0
    assert db_session.query(AcademicHistoryImport).count() == 0


def test_invalid_rows_are_skipped_and_reported_by_row_number(db_session):
    rows = _rows()[:1] + [
        _row(CARLOS, 7001, "Nefrología MED-0650", "Aprobado", 70, literal="Trimestre"),
        _row(CARLOS, 7002, "Materia sin sigla", "Aprobado", 70),
        _row(CARLOS, 7003, "Nefrología MED-0650", "Aprobado", 140),
        _row(CARLOS, 7004, "Nefrología MED-0650", "Convalidado", 70),
        _row(CARLOS, 5253, "Nefrología MED-0650", "Aprobado", 70),
    ]
    content = _csv(rows)

    result = importer.apply(db_session, content, "a.csv", hashlib.sha256(content).hexdigest(), None)

    assert result["counts"]["valid_rows"] == 1
    assert result["counts"]["error_rows"] == 5
    errors = [(issue["row"], issue["message"]) for issue in result["issues"] if issue["level"] == "error"]
    assert errors == [
        (3, "Período desconocido: Trimestre"),
        (4, "Materia sin sigla reconocible: Materia sin sigla"),
        (5, "Nota fuera de rango: 140"),
        (6, "Estado de materia desconocido: Convalidado"),
        (7, "RegistroMateriaID repetido en el archivo: 5253"),
    ]
    assert [r.legacy_registration_id for r in db_session.query(StudentSubjectRecord)] == [5253]
    assert db_session.query(Student).filter_by(document_number="7485000").count() == 0


def test_a_file_without_the_legacy_columns_is_rejected(db_session):
    content = _csv([{"EstudianteNombre": "X"}], columns=["EstudianteNombre", "Otra"])

    with pytest.raises(importer.ImportFormatError, match="Faltan columnas: EstudianteApellidos"):
        importer.preview(db_session, content, "a.csv")


def test_the_import_reuses_catalog_subjects_and_never_renames_them(db_session):
    db_session.add(AcademicSubject(code="LIN 0130", name="English I", active=True))
    db_session.flush()
    content = _csv(_rows()[:1])

    importer.apply(db_session, content, "a.csv", hashlib.sha256(content).hexdigest(), None)

    subjects = db_session.query(AcademicSubject).filter_by(code="LIN 0130").all()
    assert [subject.name for subject in subjects] == ["English I"]


def test_a_teacher_ci_change_moves_the_history_link_and_reimports_keep_it(db_session):
    from app.services.teacher_identity_service import TeacherIdentityService

    db_session.add(Teacher(ci="7485425", full_name="Lesly Guerrero Ortega"))
    db_session.flush()
    content = _csv(_rows()[:1])
    importer.apply(db_session, content, "a.csv", hashlib.sha256(content).hexdigest(), None)

    TeacherIdentityService(db_session).change_ci("7485425", "7485425-1A")
    db_session.flush()
    db_session.expire_all()

    record = db_session.query(StudentSubjectRecord).filter_by(legacy_registration_id=5253).one()
    assert (record.teacher_ci, record.teacher_document) == ("7485425-1A", "7485425")
    result = importer.apply(db_session, content, "a.csv", hashlib.sha256(content).hexdigest(), None)
    assert result["counts"]["records_unchanged"] == 1
    assert db_session.query(StudentSubjectRecord).one().teacher_ci == "7485425-1A"
