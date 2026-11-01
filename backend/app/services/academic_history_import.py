"""Import students and their subject history from legacy academic-system CSV exports.

The legacy system remains the system of record, so every export can be imported
again: students are matched by document number and subject records by the
legacy ``RegistroMateriaID``. ``preview`` never writes; ``apply`` runs the same
analysis and refuses a file whose SHA-256 differs from the previewed one.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.academic_management import AcademicSubject
from app.models.academic_records import (
    AcademicHistoryImport,
    AcademicTerm,
    CurriculumPlan,
    Student,
    StudentSubjectRecord,
)
from app.models.teacher import Teacher
from app.models.teacher_ci_alias import TeacherCiAlias
from app.models.user import User
from app.services import academic_records_service

REQUIRED_COLUMNS = (
    "EstudianteNombre", "EstudianteApellidos", "EstudianteNroDocumento", "EstudianteTipoDocumento",
    "EstudianteFechaNacimiento", "EstudianteGenero", "EstudianteCelular", "EstudianteCorreoPersonal",
    "EstudianteCorreoAcademico", "EstudiantePaisNacimiento", "EstudianteNacionalidad",
    "InstitucionEducativa", "DireccionDomicilio", "DocenteNombre", "DocenteApellidos",
    "DocenteNroDocumento", "RegistroMateriaID", "EstadoRegistroMateria", "PlanEstudio",
    "MateriaNombreSigla", "GrupoNombre", "GrupoTurno", "OfertaPeriodoLiteral", "OfertaGestion",
    "OfertaNombre", "RegistroMateriaNota", "EstadoActualInscripcion",
)
TERM_KINDS = {
    "primer semestre": ("I", "Primer Semestre"),
    "segundo semestre": ("II", "Segundo Semestre"),
    "invierno": ("INV", "Invierno"),
    "verano": ("VER", "Verano"),
}
STATUSES = {"aprobado", "reprobado", "retirado", "pendiente"}
# A 0 on a pending or withdrawn subject is the legacy placeholder, not a grade.
GRADELESS_STATUSES = {"pendiente", "retirado"}
SUBJECT_PATTERN = re.compile(r"^(?P<name>.*\S)\s+(?P<prefix>[A-Z]{3})-(?P<number>\d{4})$")
EMPTY_VALUES = {"", "ND", "N/D"}
NATIONAL = "boliviana"
MAX_REPORTED_ERRORS = 200

STUDENT_FIELDS = (
    "document_type", "first_names", "last_names", "birth_date", "gender", "phone", "personal_email",
    "academic_email", "birth_country", "nationality", "is_foreign", "school", "address",
    "legacy_enrollment_status", "curriculum_plan_id",
)
RECORD_FIELDS = (
    "term_code", "subject_code", "group_code", "shift", "teacher_document", "teacher_name",
    "teacher_ci", "status", "grade",
)


class ImportFormatError(ValueError):
    """The file is not a legacy academic export."""


class ImportConflict(RuntimeError):
    """The file differs from the one that was previewed."""


@dataclass
class _Analysis:
    sha256: str
    rows: int = 0
    error_rows: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    students: dict[str, dict[str, Any]] = field(default_factory=dict)
    records: dict[int, dict[str, Any]] = field(default_factory=dict)
    terms: dict[str, dict[str, Any]] = field(default_factory=dict)
    subjects: dict[str, str] = field(default_factory=dict)
    subject_rows: dict[str, int] = field(default_factory=dict)
    plan_names: set[str] = field(default_factory=set)


def _text(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return None if value.upper() in EMPTY_VALUES else value


def _birth_date(value: Optional[str]) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value.split(" ")[0], "%d/%m/%Y").date()
    except ValueError:
        return None


def _decode(content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportFormatError("El archivo no está en UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    try:
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ImportFormatError("Faltan columnas: " + ", ".join(missing))
        return list(reader)
    except csv.Error as exc:
        # An unbalanced quote swallows the rest of the file, so no row after it can be trusted.
        raise ImportFormatError(f"El CSV está mal formado cerca de la línea {reader.line_num + 1}") from exc


# Model column -> CSV column it comes from, so over-long values are row errors, not failed inserts.
STUDENT_LIMITS = {
    "document_number": "EstudianteNroDocumento", "document_type": "EstudianteTipoDocumento",
    "first_names": "EstudianteNombre", "last_names": "EstudianteApellidos", "gender": "EstudianteGenero",
    "phone": "EstudianteCelular", "personal_email": "EstudianteCorreoPersonal",
    "academic_email": "EstudianteCorreoAcademico", "birth_country": "EstudiantePaisNacimiento",
    "nationality": "EstudianteNacionalidad", "school": "InstitucionEducativa",
    "legacy_enrollment_status": "EstadoActualInscripcion",
}
RECORD_LIMITS = {
    "group_code": "GrupoNombre", "shift": "GrupoTurno", "teacher_document": "DocenteNroDocumento",
    "teacher_name": "DocenteNombre y DocenteApellidos",
}


def _too_long(record: dict[str, Any]) -> Optional[str]:
    checks = (
        (Student, record["student"], STUDENT_LIMITS),
        (StudentSubjectRecord, record, RECORD_LIMITS),
        (AcademicSubject, {"name": record["subject_name"]}, {"name": "MateriaNombreSigla"}),
    )
    for model, values, columns in checks:
        for key, label in columns.items():
            length = model.__table__.c[key].type.length
            if values[key] is not None and len(values[key]) > length:
                return f"{label} supera {length} caracteres"
    return None


def _normalize(row: dict[str, str], plan_ids: dict[str, int]) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Return ``(record, None)`` or ``(None, error message)`` for one CSV row."""
    if None in row:
        return None, "Fila con más columnas que el encabezado"
    cut = next((column for column, value in row.items() if value is None), None)
    if cut is not None:
        return None, f"Fila incompleta: faltan columnas desde {cut}"
    literal = (row["OfertaPeriodoLiteral"] or "").strip()
    kind = TERM_KINDS.get(literal.lower())
    if kind is None:
        return None, f"Período desconocido: {literal}"
    try:
        year = int(row["OfertaGestion"])
    except (TypeError, ValueError):
        return None, f"Gestión inválida: {row['OfertaGestion']}"
    subject = SUBJECT_PATTERN.match((row["MateriaNombreSigla"] or "").strip())
    if subject is None:
        return None, f"Materia sin sigla reconocible: {row['MateriaNombreSigla']}"
    status = (row["EstadoRegistroMateria"] or "").strip().lower()
    if status not in STATUSES:
        return None, f"Estado de materia desconocido: {row['EstadoRegistroMateria']}"
    try:
        grade: Optional[int] = int((row["RegistroMateriaNota"] or "0").strip())
    except ValueError:
        return None, f"Nota inválida: {row['RegistroMateriaNota']}"
    if not 0 <= grade <= 100:
        return None, f"Nota fuera de rango: {grade}"
    if grade == 0 and status in GRADELESS_STATUSES:
        grade = None
    try:
        registration_id = int(row["RegistroMateriaID"])
    except (TypeError, ValueError):
        return None, f"RegistroMateriaID inválido: {row['RegistroMateriaID']}"
    document = _text(row["EstudianteNroDocumento"])
    if document is None:
        return None, "Estudiante sin número de documento"

    teacher_document = _text(row["DocenteNroDocumento"])
    teacher_name = " ".join(filter(None, (_text(row["DocenteNombre"]), _text(row["DocenteApellidos"])))) or None
    nationality = _text(row["EstudianteNacionalidad"])
    plan_name = (row["PlanEstudio"] or "").strip()
    record = {
        "registration_id": registration_id,
        "term_code": f"{kind[0]}/{year}",
        "term": {"year": year, "kind": kind[0], "name": f"{kind[1]} {year}", "legacy_name": row["OfertaNombre"].strip()},
        "subject_code": f"{subject['prefix']} {subject['number']}",
        "subject_name": subject["name"],
        "plan_name": plan_name,
        "student": {
            "document_number": document,
            "document_type": _text(row["EstudianteTipoDocumento"]) or "DESCONOCIDO",
            "first_names": (row["EstudianteNombre"] or "").strip(),
            "last_names": (row["EstudianteApellidos"] or "").strip(),
            "birth_date": _birth_date(row["EstudianteFechaNacimiento"]),
            "gender": _text(row["EstudianteGenero"]),
            "phone": _text(row["EstudianteCelular"]),
            "personal_email": _text(row["EstudianteCorreoPersonal"]),
            "academic_email": _text(row["EstudianteCorreoAcademico"]),
            "birth_country": _text(row["EstudiantePaisNacimiento"]),
            "nationality": nationality,
            "is_foreign": (nationality or "").lower() != NATIONAL,
            "school": _text(row["InstitucionEducativa"]),
            "address": _text(row["DireccionDomicilio"]),
            "legacy_enrollment_status": _text(row["EstadoActualInscripcion"]),
            "curriculum_plan_id": plan_ids.get(plan_name),
        },
        "group_code": _text(row["GrupoNombre"]),
        "shift": _text(row["GrupoTurno"]),
        "teacher_document": teacher_document,
        "teacher_name": teacher_name,
        "status": status,
        "grade": grade,
    }
    error = _too_long(record)
    return (None, error) if error else (record, None)


def _curriculum_codes(db: Session) -> tuple[dict[str, int], dict[str, set[str]]]:
    """Plan ids and subject codes by plan name; the bundled plan counts even before it is loaded."""
    plan_ids: dict[str, int] = {}
    codes: dict[str, set[str]] = {}
    for plan in db.query(CurriculumPlan):
        plan_ids[plan.name] = plan.id
        codes[plan.name] = {slot.subject.code for slot in plan.subjects if slot.subject}
    bundled = json.loads(academic_records_service.DEFAULT_CURRICULUM_PATH.read_text(encoding="utf-8"))
    codes.setdefault(bundled["plan_name"], {
        item["code"] for semester in bundled["semesters"] for item in semester["subjects"] if item["code"]
    })
    return plan_ids, codes


def _teacher_links(db: Session, documents: set[str]) -> dict[str, str]:
    links = {ci: ci for (ci,) in db.query(Teacher.ci).filter(Teacher.ci.in_(documents))} if documents else {}
    for previous, current in db.query(TeacherCiAlias.previous_ci, TeacherCiAlias.teacher_ci):
        if previous in documents and previous not in links:
            links[previous] = current
    return links


def _analyze(db: Session, content: bytes, rows: list[dict[str, str]]) -> _Analysis:
    analysis = _Analysis(sha256=hashlib.sha256(content).hexdigest(), rows=len(rows))
    plan_ids, curriculum = _curriculum_codes(db)
    for line, row in enumerate(rows, start=2):
        record, error = _normalize(row, plan_ids)
        if record is None:
            pass
        elif record["registration_id"] in analysis.records:
            error = f"RegistroMateriaID repetido en el archivo: {record['registration_id']}"
        if error is not None:
            analysis.error_rows += 1
            analysis.errors.append({"level": "error", "row": line, "rows": 1, "message": error})
            continue
        analysis.records[record["registration_id"]] = record
        # The newest row of a student wins; the legacy export repeats the same values.
        analysis.students[record["student"]["document_number"]] = record["student"]
        term = analysis.terms.setdefault(record["term_code"], {**record["term"], "legacy_names": []})
        if record["term"]["legacy_name"] and record["term"]["legacy_name"] not in term["legacy_names"]:
            term["legacy_names"].append(record["term"]["legacy_name"])
        analysis.subjects.setdefault(record["subject_code"], record["subject_name"])
        analysis.plan_names.add(record["plan_name"])
        if record["subject_code"] not in curriculum.get(record["plan_name"], set()):
            analysis.subject_rows[record["subject_code"]] = analysis.subject_rows.get(record["subject_code"], 0) + 1

    links = _teacher_links(db, {r["teacher_document"] for r in analysis.records.values() if r["teacher_document"]})
    for record in analysis.records.values():
        record["teacher_ci"] = links.get(record["teacher_document"])
    return analysis


def _issues(analysis: _Analysis) -> list[dict[str, Any]]:
    warnings = [
        {
            "level": "warning", "row": None, "rows": count,
            "message": f"Materia fuera de malla: {code} ({analysis.subjects[code]})",
        }
        for code, count in sorted(analysis.subject_rows.items())
    ]
    return analysis.errors[:MAX_REPORTED_ERRORS] + warnings


def _existing(db: Session, analysis: _Analysis):
    students = {}
    documents = list(analysis.students)
    for start in range(0, len(documents), 500):
        chunk = documents[start:start + 500]
        students.update({s.document_number: s for s in db.query(Student).filter(Student.document_number.in_(chunk))})
    records = {}
    ids = list(analysis.records)
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        records.update({
            r.legacy_registration_id: r
            for r in db.query(StudentSubjectRecord).filter(StudentSubjectRecord.legacy_registration_id.in_(chunk))
        })
    terms = {t.code: t for t in db.query(AcademicTerm).filter(AcademicTerm.code.in_(list(analysis.terms)))}
    subjects = {
        s.code: s for s in db.query(AcademicSubject).filter(AcademicSubject.code.in_(list(analysis.subjects)))
    }
    return students, records, terms, subjects


def _record_values(record: StudentSubjectRecord) -> dict[str, Any]:
    return {
        "term_code": record.term.code, "subject_code": record.subject.code,
        **{name: getattr(record, name) for name in RECORD_FIELDS[2:]},
    }


def _diff(db: Session, analysis: _Analysis) -> dict[str, Any]:
    students, records, terms, subjects = _existing(db, analysis)
    changed_students = {
        document for document, values in analysis.students.items()
        if document in students and any(getattr(students[document], f) != values[f] for f in STUDENT_FIELDS)
    }
    changed_records = set()
    for registration_id, values in analysis.records.items():
        current = records.get(registration_id)
        if current is None:
            continue
        if current.student.document_number != values["student"]["document_number"] or any(
            _record_values(current)[name] != values[name] for name in RECORD_FIELDS
        ):
            changed_records.add(registration_id)
    counts = {
        "rows": analysis.rows,
        "valid_rows": analysis.rows - analysis.error_rows,
        "error_rows": analysis.error_rows,
        "students_new": len(set(analysis.students) - set(students)),
        "students_updated": len(changed_students),
        "students_unchanged": len(set(analysis.students) & set(students)) - len(changed_students),
        "records_new": len(set(analysis.records) - set(records)),
        "records_updated": len(changed_records),
        "records_unchanged": len(set(analysis.records) & set(records)) - len(changed_records),
        "terms_new": len(set(analysis.terms) - set(terms)),
        "subjects_new": len(set(analysis.subjects) - set(subjects)),
        "teachers_linked": sum(1 for r in analysis.records.values() if r["teacher_ci"]),
        "warnings": len(analysis.subject_rows),
    }
    return {
        "counts": counts, "students": students, "records": records, "terms": terms, "subjects": subjects,
        "changed_students": changed_students, "changed_records": changed_records,
    }


def preview(db: Session, content: bytes, file_name: str) -> dict[str, Any]:
    analysis = _analyze(db, content, _decode(content))
    diff = _diff(db, analysis)
    return {
        "file_name": file_name,
        "file_sha256": analysis.sha256,
        "counts": diff["counts"],
        "terms": sorted(analysis.terms, key=_term_sort_key),
        "issues": _issues(analysis),
    }


def _term_sort_key(code: str) -> tuple[int, int]:
    kind, year = code.split("/")
    return int(year), ("VER", "I", "INV", "II").index(kind)


def apply(
    db: Session, content: bytes, file_name: str, expected_sha256: str, actor: Optional[User]
) -> dict[str, Any]:
    """Apply one legacy export. Flushes, never commits; the caller owns the transaction."""
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ImportConflict("El archivo cambió después de la vista previa")
    rows = _decode(content)
    # Students are linked to their plan, so the bundled curriculum must exist first.
    academic_records_service.load_default_curriculum(db)
    analysis = _analyze(db, content, rows)
    diff = _diff(db, analysis)
    result = {
        "file_name": file_name,
        "file_sha256": analysis.sha256,
        "counts": diff["counts"],
        "terms": sorted(analysis.terms, key=_term_sort_key),
        "issues": _issues(analysis),
    }
    receipt = AcademicHistoryImport(
        file_name=file_name, file_sha256=analysis.sha256, actor_id=actor.id if actor else None,
        counts=result["counts"], terms=result["terms"], issues=result["issues"],
    )
    db.add(receipt)
    db.flush()

    terms = diff["terms"]
    for code, values in analysis.terms.items():
        term = terms.get(code)
        if term is None:
            term = AcademicTerm(
                code=code, year=values["year"], kind=values["kind"], name=values["name"],
                is_intensive=values["kind"] in ("INV", "VER"), legacy_names=list(values["legacy_names"]),
            )
            db.add(term)
            terms[code] = term
        else:
            merged = list(term.legacy_names) + [n for n in values["legacy_names"] if n not in term.legacy_names]
            if merged != list(term.legacy_names):
                term.legacy_names = merged
    subjects = diff["subjects"]
    for code, name in analysis.subjects.items():
        if code not in subjects:
            subjects[code] = academic_records_service.get_or_create_subject(db, code, name)[0]

    students = diff["students"]
    for document, values in analysis.students.items():
        student = students.get(document)
        if student is None:
            student = Student(document_number=document)
            db.add(student)
            students[document] = student
        if student.id is None or document in diff["changed_students"]:
            for name in STUDENT_FIELDS:
                setattr(student, name, values[name])
            student.last_import_id = receipt.id
    db.flush()

    records = diff["records"]
    for registration_id, values in analysis.records.items():
        record = records.get(registration_id)
        if record is not None and registration_id not in diff["changed_records"]:
            continue
        if record is None:
            record = StudentSubjectRecord(legacy_registration_id=registration_id)
            db.add(record)
        record.student_id = students[values["student"]["document_number"]].id
        record.term_id = terms[values["term_code"]].id
        record.subject_id = subjects[values["subject_code"]].id
        for name in RECORD_FIELDS[2:]:
            setattr(record, name, values[name])
        record.last_import_id = receipt.id
    db.flush()
    result["import_id"] = receipt.id
    return result

