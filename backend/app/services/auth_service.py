from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return self.pwd_context.verify(plain, hashed)

    # ------------------------------------------------------------------
    # JWT helpers
    # ------------------------------------------------------------------

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta if expires_delta else timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def decode_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate_user(self, db: Session, ci: str, password: str) -> Optional[User]:
        user = db.query(User).filter(User.ci == ci, User.is_active == True).first()  # noqa: E712
        if user is None:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    def get_current_user(self, token: str, db: Session) -> User:
        payload = self.decode_token(token)
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido — falta subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()  # noqa: E712
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no encontrado o inactivo",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def create_user(
        self,
        db: Session,
        ci: str,
        full_name: str,
        password: str,
        role: str,
        teacher_ci: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> User:
        existing = db.query(User).filter(User.ci == ci).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un usuario con CI '{ci}'",
            )

        user = User(
            ci=ci,
            full_name=full_name,
            password_hash=self.hash_password(password),
            role=role,
            teacher_ci=teacher_ci,
            created_by=created_by,
            is_active=True,
        )
        db.add(user)
        db.flush()  # get id without committing
        return user

    def update_user(self, db: Session, user_id: int, **kwargs) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        allowed_fields = {"full_name", "email", "is_active", "role", "teacher_ci"}
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                setattr(user, field, value)

        db.flush()
        return user

    def deactivate_user(self, db: Session, user_id: int) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        user.is_active = False
        db.flush()
        return user

    def reset_password(self, db: Session, user_id: int, new_password: str) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        user.password_hash = self.hash_password(new_password)
        db.flush()
        return user

    def list_users(self, db: Session, role: Optional[str] = None) -> list[User]:
        query = db.query(User)
        if role:
            query = query.filter(User.role == role)
        return query.order_by(User.full_name.asc()).all()

    # ------------------------------------------------------------------
    # Default admin bootstrap
    # ------------------------------------------------------------------

    def create_default_admin(self, db: Session) -> None:
        """Create default admin user if no admin exists."""
        admin_exists = db.query(User).filter(User.role == "admin").first()
        if admin_exists:
            return

        logger.info("No admin user found — creating default admin (CI: admin)")
        admin = User(
            ci="admin",
            full_name="Administrador",
            password_hash=self.hash_password("admin123"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.info("Default admin created successfully")


auth_service = AuthService()
