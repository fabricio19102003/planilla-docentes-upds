from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth_service import auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Endpoints that are allowed even when must_change_password=True
_ALLOWED_WHEN_MUST_CHANGE = {"/api/auth/change-password", "/api/auth/login"}


def _check_must_change_password(user: User, request: Request) -> None:
    """Block API access if user must change password (except the change-password endpoint)."""
    if not user.must_change_password:
        return
    path = str(request.url.path)
    if any(path.startswith(allowed) or path == allowed for allowed in _ALLOWED_WHEN_MUST_CHANGE):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Debe cambiar su contraseña antes de continuar",
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT and return current user. Raises 401 if invalid or inactive."""
    return auth_service.get_current_user(token=token, db=db)


def require_admin(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Requires admin role. Raises 403 if not admin or if must_change_password is set."""
    current_user = auth_service.get_current_user(token=token, db=db)
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador",
        )
    _check_must_change_password(current_user, request)
    return current_user


def require_docente(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Requires docente role. Raises 403 if not docente or if must_change_password is set."""
    current_user = auth_service.get_current_user(token=token, db=db)
    if current_user.role != "docente":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de docente",
        )
    _check_must_change_password(current_user, request)
    return current_user
