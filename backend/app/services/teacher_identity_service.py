"""Transactional teacher CI changes that preserve current foreign-key consumers."""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.teacher import Teacher
from app.models.user import User


class TeacherIdentityConflict(ValueError):
    """Raised when a CI change would collide with a current identity."""


class TeacherIdentityService:
    """Move a teacher CI without relying on deferred foreign-key constraints.

    The caller owns the transaction and is responsible for the audit and commit.
    """

    child_tables = (
        "designations",
        "attendance_records",
        "biometric_records",
        "detail_requests",
        "users",
        "practice_attendance_logs",
        "whatsapp_preferences",
        "whatsapp_consent_revisions",
        "billing_notification_jobs",
        "billing_media_tokens",
    )

    def __init__(self, db: Session):
        self.db = db

    def change_ci(self, old_ci: str, new_ci: str) -> Teacher:
        teacher = self.db.scalar(select(Teacher).where(Teacher.ci == old_ci).with_for_update())
        if teacher is None:
            raise LookupError("teacher not found")
        if self.db.scalar(select(Teacher.ci).where(Teacher.ci == new_ci).with_for_update()) is not None:
            raise TeacherIdentityConflict("teacher CI already exists")
        existing_user = self.db.scalar(select(User).where(User.ci == new_ci).with_for_update())
        if existing_user is not None and (
            existing_user.role != "docente" or existing_user.teacher_ci != old_ci
        ):
            raise TeacherIdentityConflict("user login CI already exists")

        replacement = self._insert_replacement(teacher, new_ci)
        for table in self.child_tables:
            self._repoint_child(table, old_ci, new_ci)
        self._repoint_docente_login(old_ci, new_ci)
        self._delete_old_parent(teacher)
        return replacement

    def _insert_replacement(self, teacher: Teacher, new_ci: str) -> Teacher:
        values = {
            attribute.key: getattr(teacher, attribute.key)
            for attribute in Teacher.__mapper__.column_attrs
            if attribute.key != "ci"
        }
        replacement = Teacher(ci=new_ci, **values)
        self.db.add(replacement)
        self.db.flush()
        return replacement

    def _repoint_child(self, table: str, old_ci: str, new_ci: str) -> None:
        self.db.execute(
            text(f"UPDATE {table} SET teacher_ci = :new_ci WHERE teacher_ci = :old_ci"),
            {"new_ci": new_ci, "old_ci": old_ci},
        )

    def _repoint_docente_login(self, old_ci: str, new_ci: str) -> None:
        self.db.execute(
            text("UPDATE users SET ci = :new_ci WHERE ci = :old_ci AND role = 'docente'"),
            {"new_ci": new_ci, "old_ci": old_ci},
        )

    def _delete_old_parent(self, teacher: Teacher) -> None:
        self.db.delete(teacher)
        self.db.flush()
