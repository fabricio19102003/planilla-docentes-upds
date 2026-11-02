"""Migration documents of foreign students: the required list, what each student presented and "regularizado" (phase 3 S5)."""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_records import Student
from app.models.migration_documents import MigrationDocumentType, StudentMigrationDocument
from app.models.user import User

MAX_NAME = 120
NAME_REQUIRED = "El nombre del documento es obligatorio"
NAME_TOO_LONG = f"El nombre del documento no puede superar los {MAX_NAME} caracteres"
NAME_TAKEN = "Ya existe un documento con ese nombre"
TYPE_NOT_FOUND = "Tipo de documento migratorio no encontrado"
ALREADY_INACTIVE = "El tipo de documento ya está inactivo"
INACTIVE = "El tipo de documento está inactivo"
STUDENT_NOT_FOUND = "Estudiante no encontrado"
NOT_FOREIGN = "El estudiante no es extranjero"
EXPIRY_REQUIRED = "La fecha de vencimiento es obligatoria para este documento"
NOT_RECORDED = "El estudiante no tiene ese documento registrado"
BLOCKED_PREFIX = "Documentos migratorios pendientes: "


# ── Catalog ──────────────────────────────────────────────────────────────────

def type_payload(doc_type: MigrationDocumentType) -> dict[str, Any]:
    return {
        "id": doc_type.id, "name": doc_type.name, "requires_expiry": doc_type.requires_expiry,
        "active": doc_type.active, "position": doc_type.position,
    }


def _ordered_types(db: Session) -> list[MigrationDocumentType]:
    return db.query(MigrationDocumentType).order_by(MigrationDocumentType.position, MigrationDocumentType.id).all()


def list_types(db: Session) -> list[dict[str, Any]]:
    return [type_payload(t) for t in _ordered_types(db)]


def get_type(db: Session, type_id: int) -> MigrationDocumentType:
    doc_type = db.get(MigrationDocumentType, type_id)
    if doc_type is None:
        raise HTTPException(status_code=404, detail=TYPE_NOT_FOUND)
    return doc_type


def _clean_name(db: Session, name: str, exclude_id: Optional[int] = None) -> str:
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail=NAME_REQUIRED)
    if len(name) > MAX_NAME:
        raise HTTPException(status_code=422, detail=NAME_TOO_LONG)
    taken = db.query(MigrationDocumentType.id).filter(func.lower(MigrationDocumentType.name) == name.lower())
    if exclude_id is not None:
        taken = taken.filter(MigrationDocumentType.id != exclude_id)
    if taken.first() is not None:
        raise HTTPException(status_code=409, detail=NAME_TAKEN)
    return name


def _flush_unique(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:  # the same name or document saved twice at once
        db.rollback()
        raise HTTPException(status_code=409, detail=NAME_TAKEN) from exc


def create_type(db: Session, name: str, requires_expiry: bool) -> MigrationDocumentType:
    name = _clean_name(db, name)
    last = db.query(func.max(MigrationDocumentType.position)).scalar()
    doc_type = MigrationDocumentType(name=name, requires_expiry=requires_expiry, active=True,
                                     position=0 if last is None else last + 1)
    db.add(doc_type)
    _flush_unique(db)
    return doc_type


def update_type(db: Session, type_id: int, changes: dict[str, Any]) -> tuple[dict[str, Any], MigrationDocumentType]:
    """Apply the given changes (name, requires_expiry, active, position); returns the payload before them."""
    doc_type = get_type(db, type_id)
    before = type_payload(doc_type)
    if "name" in changes:
        doc_type.name = _clean_name(db, changes["name"], doc_type.id)
    if "requires_expiry" in changes:
        doc_type.requires_expiry = changes["requires_expiry"]
    if "active" in changes:
        doc_type.active = changes["active"]
    if "position" in changes:
        ordered = [t for t in _ordered_types(db) if t.id != doc_type.id]
        ordered.insert(max(0, min(changes["position"], len(ordered))), doc_type)
        for index, item in enumerate(ordered):
            item.position = index
    _flush_unique(db)
    return before, doc_type


def deactivate_type(db: Session, type_id: int) -> tuple[dict[str, Any], MigrationDocumentType]:
    """Types are never deleted: recorded documents keep pointing at them."""
    doc_type = get_type(db, type_id)
    if not doc_type.active:
        raise HTTPException(status_code=409, detail=ALREADY_INACTIVE)
    before = type_payload(doc_type)
    doc_type.active = False
    db.flush()
    return before, doc_type


# ── Regularizado ─────────────────────────────────────────────────────────────

def _document_state(doc_type: MigrationDocumentType, document: Optional[StudentMigrationDocument],
                    today: date) -> dict[str, Any]:
    expires_on = document.expires_on if document is not None and doc_type.requires_expiry else None
    if document is None or (doc_type.requires_expiry and expires_on is None):
        state = "missing"
    elif expires_on is not None and expires_on < today:
        state = "expired"
    else:
        state = "present"
    return {
        "type_id": doc_type.id, "name": doc_type.name, "requires_expiry": doc_type.requires_expiry,
        "state": state, "expires_on": expires_on,
        "notes": document.notes if document is not None else None,
    }


def _build_status(student: Student, active_types: list[MigrationDocumentType],
                  documents: dict[int, StudentMigrationDocument], today: date) -> dict[str, Any]:
    if not student.is_foreign:
        return {"applies": False, "regularizado": True, "missing": [], "expired": [], "documents": []}
    rows = [_document_state(t, documents.get(t.id), today) for t in active_types]
    return {
        "applies": True,
        "regularizado": all(row["state"] == "present" for row in rows),
        "missing": [row["name"] for row in rows if row["state"] == "missing"],
        "expired": [{"name": row["name"], "expires_on": row["expires_on"]} for row in rows if row["state"] == "expired"],
        "documents": rows,
    }


def statuses(db: Session, students: Iterable[Student], today: date) -> dict[int, dict[str, Any]]:
    """Status of several students with one query for the list and one for their documents."""
    students = list(students)
    foreign_ids = [s.id for s in students if s.is_foreign]
    active_types = [t for t in _ordered_types(db) if t.active] if foreign_ids else []
    by_student: dict[int, dict[int, StudentMigrationDocument]] = {}
    if foreign_ids and active_types:
        for document in (
            db.query(StudentMigrationDocument).filter(StudentMigrationDocument.student_id.in_(foreign_ids))
        ):
            by_student.setdefault(document.student_id, {})[document.document_type_id] = document
    return {s.id: _build_status(s, active_types, by_student.get(s.id, {}), today) for s in students}


def status(db: Session, student: Student, today: date) -> dict[str, Any]:
    return statuses(db, [student], today)[student.id]


def pending_labels(result: dict[str, Any]) -> list[str]:
    """The missing and expired documents in list order, as the staff and the block message name them."""
    labels = []
    for row in result["documents"]:
        if row["state"] == "missing":
            labels.append(row["name"])
        elif row["state"] == "expired":
            labels.append(f"{row['name']} (vencido el {row['expires_on']:%d/%m/%Y})")
    return labels


def blocked_detail(result: dict[str, Any]) -> str:
    return BLOCKED_PREFIX + ", ".join(pending_labels(result))


# ── Student documents ────────────────────────────────────────────────────────

def get_student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=STUDENT_NOT_FOUND)
    return student


def _find(db: Session, student_id: int, type_id: int) -> Optional[StudentMigrationDocument]:
    return (
        db.query(StudentMigrationDocument)
        .filter(StudentMigrationDocument.student_id == student_id,
                StudentMigrationDocument.document_type_id == type_id)
        .one_or_none()
    )


def document_payload(document: Optional[StudentMigrationDocument]) -> Optional[dict[str, Any]]:
    if document is None:
        return None
    return {"expires_on": document.expires_on, "notes": document.notes}


def _foreign_student(db: Session, student_id: int) -> Student:
    student = get_student(db, student_id)
    if not student.is_foreign:
        raise HTTPException(status_code=409, detail=NOT_FOREIGN)
    return student


def save_document(db: Session, student_id: int, type_id: int, expires_on: Optional[date], notes: Optional[str],
                  actor: User) -> tuple[Student, Optional[dict[str, Any]], dict[str, Any]]:
    """Record or update a presented document; returns the student, the record before and the one after."""
    doc_type = get_type(db, type_id)
    student = _foreign_student(db, student_id)
    if not doc_type.active:
        raise HTTPException(status_code=409, detail=INACTIVE)
    if doc_type.requires_expiry and expires_on is None:
        raise HTTPException(status_code=422, detail=EXPIRY_REQUIRED)
    document = _find(db, student.id, doc_type.id)
    before = document_payload(document)
    if document is None:
        document = StudentMigrationDocument(student_id=student.id, document_type_id=doc_type.id)
        db.add(document)
    # A document that does not expire has no expiry date to keep.
    document.expires_on = expires_on if doc_type.requires_expiry else None
    document.notes = (notes or "").strip() or None
    document.recorded_by = actor.id
    try:
        db.flush()
    except IntegrityError as exc:  # the same document saved twice at once
        db.rollback()
        raise HTTPException(status_code=409, detail="El documento ya se está registrando; recargá la página") from exc
    return student, before, document_payload(document)


def remove_document(db: Session, student_id: int, type_id: int) -> tuple[Student, dict[str, Any]]:
    student = _foreign_student(db, student_id)
    document = _find(db, student.id, type_id)
    if document is None:
        raise HTTPException(status_code=404, detail=NOT_RECORDED)
    before = document_payload(document)
    db.delete(document)
    db.flush()
    return student, before
