"""Staff API for the migration documents foreign students must present."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import migration_documents as service
from app.services import reenrollment
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/admin/migration-documents", tags=["migration-documents"])

CATEGORY = "migration_documents"
MAX_LOGGED_NOTES = 200
MAX_NOTES = 1000


class TypeCreate(BaseModel):
    # The name is checked by the service so its messages are in Spanish.
    name: str
    requires_expiry: bool = False


class TypeUpdate(BaseModel):
    name: Optional[str] = None
    requires_expiry: Optional[bool] = None
    active: Optional[bool] = None
    position: Optional[int] = Field(None, ge=0)


class DocumentPayload(BaseModel):
    expires_on: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=MAX_NOTES)


def _log(db: Session, request: Request, admin: User, action: str, description: str, details: dict) -> None:
    log_activity(db, action=action, category=CATEGORY, description=description, user=admin,
                 details=details, request=request)


def _logged(document: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if document is None:
        return None
    return {"expires_on": document["expires_on"].isoformat() if document["expires_on"] else None,
            "notes": (document["notes"] or "")[:MAX_LOGGED_NOTES] or None}


def student_status(db: Session, student) -> dict[str, Any]:
    return {"student_id": student.id, **service.status(db, student, reenrollment.bolivia_today())}


@router.get("/types")
def list_types(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return service.list_types(db)


@router.post("/types", status_code=201)
def create_type(payload: TypeCreate, request: Request, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    doc_type = service.create_type(db, payload.name, payload.requires_expiry)
    after = service.type_payload(doc_type)
    _log(db, request, admin, "create_migration_document_type", f"Agregó el documento migratorio {doc_type.name}",
         {"type_id": doc_type.id, "before": None, "after": after})
    db.commit()
    return after


@router.put("/types/{type_id}")
def update_type(type_id: int, payload: TypeUpdate, request: Request, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    changes = {key: value for key, value in payload.model_dump().items() if value is not None}
    before, doc_type = service.update_type(db, type_id, changes)
    after = service.type_payload(doc_type)
    _log(db, request, admin, "update_migration_document_type", f"Cambió el documento migratorio {doc_type.name}",
         {"type_id": doc_type.id, "before": before, "after": after})
    db.commit()
    return after


@router.post("/types/{type_id}/deactivate")
def deactivate_type(type_id: int, request: Request, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    before, doc_type = service.deactivate_type(db, type_id)
    after = service.type_payload(doc_type)
    _log(db, request, admin, "deactivate_migration_document_type",
         f"Desactivó el documento migratorio {doc_type.name}", {"type_id": doc_type.id, "before": before, "after": after})
    db.commit()
    return after


@router.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return student_status(db, service.get_student(db, student_id))


@router.put("/students/{student_id}/documents/{type_id}")
def save_document(student_id: int, type_id: int, payload: DocumentPayload, request: Request,
                  db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    student, before, after = service.save_document(db, student_id, type_id, payload.expires_on, payload.notes, admin)
    _log(db, request, admin, "save_migration_document",
         f"Registró un documento migratorio del estudiante {student.document_number}",
         {"student_id": student.id, "document_type_id": type_id, "before": _logged(before), "after": _logged(after)})
    db.commit()
    return student_status(db, student)


@router.delete("/students/{student_id}/documents/{type_id}")
def remove_document(student_id: int, type_id: int, request: Request, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    student, before = service.remove_document(db, student_id, type_id)
    _log(db, request, admin, "remove_migration_document",
         f"Quitó un documento migratorio del estudiante {student.document_number}",
         {"student_id": student.id, "document_type_id": type_id, "before": _logged(before), "after": None})
    db.commit()
    return student_status(db, student)
