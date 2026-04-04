from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import PasswordReset, UserCreate, UserResponse, UserUpdate
from app.services.auth_service import auth_service
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    role: str | None = Query(default=None, description="Filtrar por rol: 'admin' o 'docente'"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    """List all users (admin only). Optionally filter by role."""
    users = auth_service.list_users(db=db, role=role)
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Create a new user (admin only)."""
    if payload.role == "docente" and not payload.teacher_ci:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Se requiere teacher_ci para usuarios con rol 'docente'",
        )

    try:
        user = auth_service.create_user(
            db=db,
            ci=payload.ci,
            full_name=payload.full_name,
            password=payload.password,
            role=payload.role,
            teacher_ci=payload.teacher_ci,
            created_by=current_user.id,
        )
        log_activity(
            db,
            "create_user",
            "users",
            f"Usuario creado: {payload.full_name} (CI: {payload.ci}, rol: {payload.role})",
            user=current_user,
            details={"created_ci": payload.ci, "created_name": payload.full_name, "role": payload.role},
            request=request,
        )
        db.commit()
        db.refresh(user)
        return UserResponse.model_validate(user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to create user: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo crear el usuario",
        ) from exc


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Get user detail by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update user data (admin only)."""
    try:
        update_data = payload.model_dump(exclude_none=True)
        user = auth_service.update_user(db=db, user_id=user_id, **update_data)
        log_activity(
            db,
            "update_user",
            "users",
            f"Usuario actualizado: {user.full_name} (ID: {user_id})",
            user=current_user,
            details={"target_user_id": user_id, "updated_fields": list(update_data.keys())},
            request=request,
        )
        db.commit()
        db.refresh(user)
        return UserResponse.model_validate(user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to update user %d: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo actualizar el usuario",
        ) from exc


@router.delete("/{user_id}", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Soft-delete a user by deactivating them (admin only)."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No podés desactivar tu propio usuario",
        )

    try:
        user = auth_service.deactivate_user(db=db, user_id=user_id)
        log_activity(
            db,
            "deactivate_user",
            "users",
            f"Usuario desactivado: {user.full_name} (ID: {user_id})",
            user=current_user,
            details={"target_user_id": user_id, "target_name": user.full_name},
            request=request,
        )
        db.commit()
        db.refresh(user)
        return UserResponse.model_validate(user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to deactivate user %d: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo desactivar el usuario",
        ) from exc


@router.post("/{user_id}/reset-password", response_model=UserResponse)
def reset_user_password(
    user_id: int,
    payload: PasswordReset,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Reset a user's password (admin only)."""
    try:
        user = auth_service.reset_password(db=db, user_id=user_id, new_password=payload.new_password)
        log_activity(
            db,
            "reset_password",
            "users",
            f"Contraseña reseteada para: {user.full_name} (ID: {user_id})",
            user=current_user,
            details={"target_user_id": user_id, "target_name": user.full_name},
            request=request,
        )
        db.commit()
        db.refresh(user)
        return UserResponse.model_validate(user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to reset password for user %d: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo resetear la contraseña",
        ) from exc
