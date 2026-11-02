"""Staff API for re-enrollment windows and the request inbox."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import academic_records_queries as records_queries
from app.services import reenrollment
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/admin/reenrollment", tags=["reenrollment"])

CATEGORY = "reenrollment"


class WindowDates(BaseModel):
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def _ordered(self):
        if self.ends_on < self.starts_on:
            raise ValueError("La fecha de fin debe ser igual o posterior a la de inicio")
        return self


class WindowCreate(WindowDates):
    term_code: str = Field(..., pattern=r"^(I|II|INV|VER)/[0-9]{4}$")


class Observation(BaseModel):
    reason: Literal["documentos_migracion", "pago_pendiente", "otro"]
    message: str = Field(..., min_length=5, max_length=1000)


def _log(db: Session, request: Request, admin: User, action: str, description: str, details: dict) -> None:
    log_activity(db, action=action, category=CATEGORY, description=description, user=admin,
                 details=details, request=request)


@router.get("/windows")
def list_windows(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return reenrollment.list_windows(db)


@router.post("/windows", status_code=201)
def create_window(payload: WindowCreate, request: Request, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    window = reenrollment.create_window(db, payload.term_code, payload.starts_on, payload.ends_on, admin)
    _log(db, request, admin, "create_reenrollment_window", f"Abrió la rematrícula de {window.term_code}",
         {"window_id": window.id, "starts_on": str(window.starts_on), "ends_on": str(window.ends_on)})
    db.commit()
    return reenrollment.window_payload(window)


@router.put("/windows/{window_id}")
def update_window(window_id: int, payload: WindowDates, request: Request, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    window = reenrollment.get_window(db, window_id)
    window.starts_on, window.ends_on = payload.starts_on, payload.ends_on
    _log(db, request, admin, "update_reenrollment_window", f"Cambió las fechas de la rematrícula de {window.term_code}",
         {"window_id": window.id, "starts_on": str(window.starts_on), "ends_on": str(window.ends_on)})
    db.commit()
    return reenrollment.window_payload(window)


@router.get("/requests")
def list_requests(
    window_id: Optional[int] = None,
    status: Optional[Literal["pendiente", "realizada", "observada"]] = None,
    semester: Optional[int] = Query(None, ge=1, le=20),
    group_id: Optional[int] = None,
    foreign: Optional[bool] = None,
    search: Optional[str] = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return reenrollment.inbox(db, window_id=window_id, status=status, semester=semester, group_id=group_id,
                              foreign=foreign, search=search, page=page, page_size=page_size)


@router.get("/requests/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    found = reenrollment.get_request(db, request_id)
    detail = records_queries.student_detail(db, found.student)
    return {**reenrollment.serialize_request(found), **detail}


def _transition(db: Session, request: Request, admin: User, request_id: int, status: str, action: str,
                description: str, reason: Optional[str] = None, message: Optional[str] = None):
    found = reenrollment.get_request(db, request_id)
    reenrollment.handle(db, found, admin, status, reason, message)
    _log(db, request, admin, action, description, {"request_id": found.id, "student_id": found.student_id,
                                                    "reason": reason})
    db.commit()
    return reenrollment.serialize_request(found)


@router.post("/requests/{request_id}/complete")
def complete_request(request_id: int, request: Request, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    return _transition(db, request, admin, request_id, "realizada", "complete_reenrollment_request",
                       "Marcó una rematrícula como realizada")


@router.post("/requests/{request_id}/observe")
def observe_request(request_id: int, payload: Observation, request: Request, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    return _transition(db, request, admin, request_id, "observada", "observe_reenrollment_request",
                       "Observó una solicitud de rematrícula", payload.reason, payload.message.strip())


@router.post("/requests/{request_id}/reopen")
def reopen_request(request_id: int, request: Request, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    found = reenrollment.get_request(db, request_id)
    if found.status == "pendiente":
        raise HTTPException(status_code=409, detail="La solicitud ya está pendiente")
    return _transition(db, request, admin, request_id, "pendiente", "reopen_reenrollment_request",
                       "Reabrió una solicitud de rematrícula")
