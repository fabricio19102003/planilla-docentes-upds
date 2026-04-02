from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth_service import auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT and return current user. Raises 401 if invalid or inactive."""
    return auth_service.get_current_user(token=token, db=db)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Requires admin role. Raises 403 if not admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador",
        )
    return current_user


def require_docente(current_user: User = Depends(get_current_user)) -> User:
    """Requires docente role. Raises 403 if not docente."""
    if current_user.role != "docente":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de docente",
        )
    return current_user
