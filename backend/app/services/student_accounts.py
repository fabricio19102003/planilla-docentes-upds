"""Student portal accounts: temporary passwords issued by staff, student login and sessions."""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models.academic_records import Student
from app.models.student_portal import StudentAccount
from app.models.user import User
from app.services.auth_service import auth_service

SCOPE = "student"
MAX_BULK = 100
LOGIN_FAILED = "Documento o contraseña incorrectos"
ACCOUNT_DISABLED = "Tu cuenta está deshabilitada. Acercate a Registro para habilitarla."
# Unambiguous characters: staff read these passwords out loud or print them.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
# Temporary passwords are random (about 64 bits), so a lower bcrypt cost keeps bulk issuing fast
# without making them guessable; the password the student chooses uses the normal cost.
_temporary_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=8)
_DUMMY_HASH = auth_service.hash_password(secrets.token_urlsafe(16))


def _invalid_session() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )


def generate_temporary_password() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(11))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def account_summary(account: Optional[StudentAccount]) -> Optional[dict[str, Any]]:
    if account is None:
        return None
    return {
        "is_active": account.is_active,
        "must_change_password": account.must_change_password,
        "temporary_issued_at": account.temporary_issued_at,
        "last_login": account.last_login,
    }


def get_account(db: Session, student: Student) -> Optional[StudentAccount]:
    return db.query(StudentAccount).filter(StudentAccount.student_id == student.id).one_or_none()


def issue_temporary_password(db: Session, student: Student, actor: User) -> dict[str, Any]:
    """Create or reset the account with a new temporary password; open sessions end."""
    password = generate_temporary_password()
    account = get_account(db, student)
    if account is None:
        account = StudentAccount(student_id=student.id, token_version=0)
        db.add(account)
    else:
        account.token_version += 1
    account.password_hash = _temporary_context.hash(password)
    account.must_change_password = True
    account.is_active = True
    account.temporary_issued_at = datetime.utcnow()
    account.temporary_issued_by = actor.id
    db.flush()
    return {
        "student_id": student.id,
        "document_number": student.document_number,
        "full_name": student.full_name,
        "temporary_password": password,
    }


def set_active(db: Session, student: Student, active: bool) -> StudentAccount:
    account = get_account(db, student)
    if account is None:
        raise HTTPException(status_code=404, detail="El estudiante todavía no tiene cuenta")
    if account.is_active != active:
        account.is_active = active
        account.token_version += 1
    db.flush()
    return account


def _token(account: StudentAccount) -> str:
    return auth_service.create_access_token({"sub": str(account.id), "scope": SCOPE, "ver": account.token_version})


def login(db: Session, document_number: str, password: str) -> dict[str, Any]:
    student = db.query(Student).filter(Student.document_number == document_number.strip()).one_or_none()
    account = get_account(db, student) if student else None
    # Verify against a dummy hash too, so an unknown document is not faster to reject.
    valid = auth_service.verify_password(password, account.password_hash if account else _DUMMY_HASH)
    if account is None or not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=LOGIN_FAILED)
    if not account.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ACCOUNT_DISABLED)
    account.last_login = datetime.utcnow()
    db.flush()
    return {"access_token": _token(account), "token_type": "bearer",
            "must_change_password": account.must_change_password}


def account_from_token(db: Session, token: str) -> StudentAccount:
    payload = auth_service.decode_token(token)
    subject = str(payload.get("sub") or "")
    if payload.get("scope") != SCOPE or not subject.isdigit():
        raise _invalid_session()
    account = db.get(StudentAccount, int(subject))
    if account is None or not account.is_active or payload.get("ver") != account.token_version:
        raise _invalid_session()
    return account


def change_password(db: Session, account: StudentAccount, current: str, new: str) -> dict[str, Any]:
    if not auth_service.verify_password(current, account.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    if auth_service.verify_password(new, account.password_hash):
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente de la actual")
    account.password_hash = auth_service.hash_password(new)
    account.must_change_password = False
    account.token_version += 1
    db.flush()
    return {"access_token": _token(account), "token_type": "bearer", "must_change_password": False}
