"""Student portal API: login, password change, own profile and academic history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.student_portal import StudentAccount
from app.schemas.auth import PasswordChange
from app.services import academic_records_queries as records_queries
from app.services import reenrollment, student_accounts
from app.services.activity_logger import log_activity
from app.utils.student_auth import require_student, require_student_session

router = APIRouter(prefix="/api/student-portal", tags=["student-portal"])

CATEGORY = "student_portal"


class StudentLoginRequest(BaseModel):
    document_number: str = Field(..., min_length=1, max_length=30)
    password: str = Field(..., min_length=1, max_length=128)


@router.post("/auth/login")
def login(payload: StudentLoginRequest, request: Request, db: Session = Depends(get_db)):
    result = student_accounts.login(db, payload.document_number, payload.password)
    account = student_accounts.account_from_token(db, result["access_token"])
    log_activity(
        db, action="student_login", category=CATEGORY, description="Ingreso al portal de estudiante",
        details={"student_id": account.student_id}, request=request,
    )
    db.commit()
    return result


@router.put("/auth/change-password")
def change_password(
    payload: PasswordChange, request: Request, db: Session = Depends(get_db),
    account: StudentAccount = Depends(require_student_session),
):
    result = student_accounts.change_password(db, account, payload.current_password, payload.new_password)
    log_activity(
        db, action="student_change_password", category=CATEGORY, description="Cambio de contraseña del estudiante",
        details={"student_id": account.student_id}, request=request,
    )
    db.commit()
    return result


@router.get("/me")
def me(db: Session = Depends(get_db), account: StudentAccount = Depends(require_student_session)):
    profile = records_queries.student_detail(db, account.student)["student"]
    return {**profile, "must_change_password": account.must_change_password}


@router.get("/history")
def history(db: Session = Depends(get_db), account: StudentAccount = Depends(require_student)):
    return {"history": records_queries.student_detail(db, account.student)["history"]}


class RequestItem(BaseModel):
    subject_code: str = Field(..., min_length=1, max_length=30)
    group_id: int


class ReenrollmentSubmission(BaseModel):
    main_group_id: int
    items: list[RequestItem] = Field(default_factory=list, max_length=30)


@router.get("/reenrollment")
def reenrollment_view(db: Session = Depends(get_db), account: StudentAccount = Depends(require_student)):
    return reenrollment.student_view(db, account)


@router.post("/reenrollment/request")
def submit_reenrollment(
    payload: ReenrollmentSubmission, request: Request, db: Session = Depends(get_db),
    account: StudentAccount = Depends(require_student),
):
    submitted = reenrollment.submit(db, account, payload.main_group_id, [i.model_dump() for i in payload.items])
    log_activity(
        db, action="submit_reenrollment_request", category="reenrollment",
        description=f"Envió su solicitud de rematrícula para {submitted.window.term_code}",
        details={"request_id": submitted.id, "student_id": account.student_id}, request=request,
    )
    db.commit()
    return reenrollment.serialize_request(submitted)
