from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, PasswordChange, UserResponse
from app.services.auth_service import auth_service
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Authenticate user and return JWT token."""
    user = auth_service.authenticate_user(db=db, ci=payload.ci, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CI o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)

    token = auth_service.create_access_token(data={"sub": str(user.id), "role": user.role})

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        must_change_password=user.must_change_password,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get current authenticated user info."""
    return UserResponse.model_validate(current_user)


@router.put("/change-password", response_model=UserResponse)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Change own password (requires current password for verification)."""
    if not auth_service.verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta",
        )

    updated = auth_service.reset_password(db=db, user_id=current_user.id, new_password=payload.new_password)
    updated.must_change_password = False  # Clear forced change flag
    db.commit()
    db.refresh(updated)

    return UserResponse.model_validate(updated)
