"""Transactional teacher CI changes that preserve current foreign-key consumers."""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, aliased

from app.models.biometric import BiometricRecord
from app.models.contract import ContractDocument
from app.models.contract_ci_correction import ContractCiCorrection
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.teacher import Teacher
from app.models.teacher_ci_alias import TeacherCiAlias
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
        "teacher_availability",
        "academic_schedule_assignments",
        "teacher_ci_aliases",
        "chat_conversations",
        # Issued contracts are immutable; _grant_contract_correction lets this single
        # teacher_ci UPDATE through the trigger and records it.
        "contract_documents",
    )
    guarded_tables: tuple[str, ...] = ()

    def __init__(self, db: Session):
        self.db = db

    def change_ci(self, old_ci: str, new_ci: str, corrected_by: int | None = None) -> Teacher:
        teacher = self.db.scalar(select(Teacher).where(Teacher.ci == old_ci).with_for_update())
        if teacher is None:
            raise LookupError("teacher not found")
        if self.db.scalar(select(Teacher.ci).where(Teacher.ci == new_ci).with_for_update()) is not None:
            raise TeacherIdentityConflict(f"Ya existe un docente con CI {new_ci}")
        existing_user = self.db.scalar(select(User).where(User.ci == new_ci).with_for_update())
        if existing_user is not None and (
            existing_user.role != "docente" or existing_user.teacher_ci != old_ci
        ):
            raise TeacherIdentityConflict(
                f"El CI {new_ci} ya está en uso por el usuario {existing_user.full_name}"
            )
        self._check_portal_logins(old_ci, new_ci)
        self._check_biometric_collisions(old_ci, new_ci)

        replacement = self._insert_replacement(teacher, new_ci)
        self._grant_contract_correction(old_ci, new_ci, corrected_by)
        for table in self.child_tables:
            self._repoint_child(table, old_ci, new_ci)
        self._repoint_docente_login(old_ci, new_ci)
        self.db.add(TeacherCiAlias(previous_ci=old_ci, teacher_ci=new_ci))
        self._delete_old_parent(teacher)
        return replacement

    def _grant_contract_correction(self, old_ci: str, new_ci: str, corrected_by: int | None) -> None:
        contracts = self.db.scalar(
            select(func.count()).select_from(ContractDocument).where(ContractDocument.teacher_ci == old_ci)
        )
        if not contracts:
            return
        txid = None
        if self.db.get_bind().dialect.name == "postgresql":
            txid = self.db.scalar(text("SELECT txid_current()"))
        self.db.add(ContractCiCorrection(
            old_ci=old_ci, new_ci=new_ci, contract_count=contracts, corrected_by=corrected_by, txid=txid,
        ))
        self.db.flush()

    def _check_portal_logins(self, old_ci: str, new_ci: str) -> None:
        """Reject renames the database cannot apply without a 500."""
        logins = self.db.scalars(
            select(User.ci)
            .where(User.role == "docente")
            .where((User.teacher_ci == old_ci) | (User.ci == old_ci))
            .with_for_update()
        ).all()
        if len(logins) > 1:
            raise TeacherIdentityConflict(
                f"No se puede cambiar el CI: el docente tiene {len(logins)} usuarios del portal "
                "vinculados; dejá uno solo"
            )
        # practice_attendance_logs.registered_by references users.ci without ON UPDATE.
        for login in logins:
            if login == new_ci:
                continue  # this login keeps its CI, so its references stay valid
            registered = self.db.scalar(
                select(func.count()).select_from(PracticeAttendanceLog).where(
                    PracticeAttendanceLog.registered_by == login
                )
            )
            if registered:
                raise TeacherIdentityConflict(
                    f"No se puede cambiar el CI: el usuario {login} figura como quien registró "
                    "asistencias de prácticas"
                )

    def _check_biometric_collisions(self, old_ci: str, new_ci: str) -> None:
        # biometric_records has no FK to teachers, so marks may already exist under new_ci.
        other = aliased(BiometricRecord)
        collisions = self.db.scalar(
            select(func.count())
            .select_from(BiometricRecord)
            .join(
                other,
                (other.upload_id == BiometricRecord.upload_id)
                & (other.date == BiometricRecord.date)
                & (other.entry_time == BiometricRecord.entry_time),
            )
            .where(BiometricRecord.teacher_ci == old_ci, other.teacher_ci == new_ci)
        )
        if collisions:
            raise TeacherIdentityConflict(
                f"No se puede cambiar el CI: el biométrico ya tiene {collisions} marca(s) con el "
                f"CI {new_ci} en la misma fecha y hora que las del CI {old_ci}"
            )

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
        # Runs after users.teacher_ci was repointed: follow the link, not only a login equal to old_ci.
        self.db.execute(
            text(
                "UPDATE users SET ci = :new_ci "
                "WHERE role = 'docente' AND (ci = :old_ci OR teacher_ci = :new_ci)"
            ),
            {"new_ci": new_ci, "old_ci": old_ci},
        )

    def _delete_old_parent(self, teacher: Teacher) -> None:
        self.db.delete(teacher)
        self.db.flush()
