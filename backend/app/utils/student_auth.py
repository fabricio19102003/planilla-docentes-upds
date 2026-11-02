"""Dependencies for student portal routes; staff tokens never pass them."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.student_portal import StudentAccount
from app.services import student_accounts

student_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/student-portal/auth/login")

_ALLOWED_WHEN_MUST_CHANGE = {"/api/student-portal/me", "/api/student-portal/auth/change-password"}


def require_student_session(token: str = Depends(student_oauth2), db: Session = Depends(get_db)) -> StudentAccount:
    """Any valid student session, including one that still has to change its temporary password."""
    return student_accounts.account_from_token(db, token)


def require_student(
    request: Request, account: StudentAccount = Depends(require_student_session)
) -> StudentAccount:
    if account.must_change_password and request.url.path not in _ALLOWED_WHEN_MUST_CHANGE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Debe cambiar su contraseña antes de continuar")
    return account
