from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.medicine_schedule import (
    MedicineCorrection, MedicineImportIssue, MedicineMeeting, MedicineOffering,
    MedicineScheduleVersion, MedicineVersionEvent,
)
from app.models.user import User
from app.schemas.medicine_schedule import MedicineWorkbookPreview
from app.services.activity_logger import log_activity


class MedicineVersionError(ValueError):
    pass

class MedicineVersionConflict(MedicineVersionError):
    pass

class MedicineScheduleVersionService:
    def _actor(self, db: Session, actor_id: int) -> User:
        actor = db.get(User, actor_id)
        if actor is None or actor.role != "admin" or not actor.is_active:
            raise MedicineVersionError("Active administrator required")
        return actor
    def _event(self, db: Session, version: MedicineScheduleVersion, event_type: str,
               actor: User, details: dict[str, Any] | None = None) -> None:
        payload = details or {}
        db.add(MedicineVersionEvent(version_id=version.id, event_type=event_type,
                                    actor_id=actor.id, details=payload))
        log_activity(db, event_type, "medicine_schedule", f"Medicine version {event_type}",
                     user=actor, details={"version_id": version.id, **payload})
    def persist_preview(self, db: Session, preview: MedicineWorkbookPreview, academic_period: str,
                        uploader_id: int, source_file_path: str, description: str | None = None
                        ) -> MedicineScheduleVersion:
        actor = self._actor(db, uploader_id)
        version = MedicineScheduleVersion(
            academic_period=academic_period, description=description,
            workbook_sha256=preview.workbook_sha256,
            parser_schema_version=preview.parser_schema_version,
            source_file_path=source_file_path, status="preview", is_active=False,
            uploaded_by=uploader_id,
        )
        db.add(version)
        db.flush()
        for issue in preview.issues:
            db.add(MedicineImportIssue(
                version_id=version.id, severity=issue.severity, code=issue.code,
                message=issue.message, location=issue.location, state="open",
            ))
        for item in preview.offerings:
            offering = MedicineOffering(
                version_id=version.id, category=item.category, semester=item.semester,
                subject_raw=item.subject_raw, subject_key=item.subject_key,
                group_code=item.group_code, shift=item.shift,
                source_sheet=item.source_sheet, source_row=item.source_row,
                raw_payload=item.raw_payload,
            )
            db.add(offering)
            db.flush()
            for item_meeting in item.meetings:
                db.add(MedicineMeeting(
                    offering_id=offering.id, activity=item_meeting.activity,
                    teacher_raw=item_meeting.teacher_raw, teacher_key=item_meeting.teacher_key,
                    day=item_meeting.day, start_time=item_meeting.start_time,
                    end_time=item_meeting.end_time, source_cell=item_meeting.source_cell,
                    raw_payload=item_meeting.raw_payload,
                ))
        self._event(db, version, "upload", actor, {
            "issues": len(preview.issues), "offerings": len(preview.offerings),
            "unsupported_semesters": preview.unsupported_semesters,
        })
        db.flush()
        return version
    def _mutable(self, version: MedicineScheduleVersion | None) -> MedicineScheduleVersion:
        if version is None:
            raise MedicineVersionError("Version not found")
        if version.locked_at is not None:
            raise MedicineVersionError("Activated version content is immutable")
        return version
    def _issue_matches(self, issue: MedicineImportIssue, target: Any,
                       source_sheet: str, field_name: str) -> bool:
        location, payload = issue.location, target.raw_payload
        if not isinstance(location, dict) or not isinstance(payload, dict):
            return False
        cell, lineage = location.get("cell"), payload.get("teacher_cell" if field_name == "teacher_key" else "subject_cell")
        values = source_sheet, location.get("sheet"), cell, lineage
        return all(isinstance(item, str) and item.strip() for item in values) and values[1] == values[0] and cell.strip().upper() == lineage.strip().upper()
    def correct_field(self, db: Session, version_id: int, target_type: str, target_id: int,
                      field_name: str, value: str, actor_id: int,
                      issue_ids: list[int] | None = None) -> MedicineCorrection:
        version = self._mutable(db.get(MedicineScheduleVersion, version_id))
        actor = self._actor(db, actor_id)
        if target_type == "offering" and field_name == "subject_key":
            target = db.query(MedicineOffering).filter_by(id=target_id, version_id=version.id).one_or_none()
            source_sheet = target.source_sheet if target else ""
        elif target_type == "meeting" and field_name == "teacher_key":
            target = (db.query(MedicineMeeting).join(MedicineOffering)
                      .filter(MedicineMeeting.id == target_id,
                              MedicineOffering.version_id == version.id).one_or_none())
            source_sheet = (db.query(MedicineOffering.source_sheet)
                            .filter_by(id=target.offering_id).scalar()) if target else ""
        else:
            raise MedicineVersionError("Unsupported correction target or field")
        if target is None:
            raise MedicineVersionError("Correction target not found in version")
        issues = [db.query(MedicineImportIssue).filter_by(id=issue_id, version_id=version.id).one_or_none()
                  for issue_id in dict.fromkeys(issue_ids or [])]
        if any(issue is None or issue.severity != "error" or issue.state != "open" or
               not self._issue_matches(issue, target, source_sheet, field_name) for issue in issues):
            raise MedicineVersionError("Issue is not causally bound to correction target")
        before = getattr(target, field_name)
        setattr(target, field_name, value)
        correction = MedicineCorrection(
            version_id=version.id, target_type=target_type, target_id=target_id,
            field_name=field_name, before_value={"value": before},
            after_value={"value": value}, actor_id=actor.id,
        )
        db.add(correction)
        for issue in issues:
            issue.state = "resolved"
        self._event(db, version, "correction", actor, {
            "target_type": target_type, "target_id": target_id, "field": field_name,
        })
        db.flush()
        return correction
    def accept_warning(self, db: Session, version_id: int, issue_id: int,
                       actor_id: int) -> MedicineImportIssue:
        version = self._mutable(db.get(MedicineScheduleVersion, version_id))
        actor = self._actor(db, actor_id)
        issue = db.query(MedicineImportIssue).filter_by(id=issue_id, version_id=version.id).one_or_none()
        if issue is None or issue.severity != "warning" or issue.state != "open":
            raise MedicineVersionError("Warning cannot be accepted")
        issue.state, issue.accepted_by, issue.accepted_at = "accepted", actor.id, datetime.now()
        self._event(db, version, "warning_acceptance", actor, {"issue_id": issue.id})
        db.flush()
        return issue
    def _activate(self, db: Session, version: MedicineScheduleVersion, actor: User,
                  event_type: str) -> MedicineScheduleVersion:
        blockers = db.query(MedicineImportIssue).filter(
            MedicineImportIssue.version_id == version.id,
            MedicineImportIssue.state == "open",
        ).count()
        if blockers:
            raise MedicineVersionError(f"Version has {blockers} unresolved issues")
        try:
            with db.begin_nested():
                current = (db.query(MedicineScheduleVersion)
                           .filter(MedicineScheduleVersion.is_active.is_(True)).with_for_update().all())
                for active in current:
                    active.is_active, active.status = False, "inactive"
                db.flush()
                version.is_active, version.status = True, "active"
                version.activated_by, version.locked_at = actor.id, version.locked_at or datetime.now()
                db.flush()
        except IntegrityError as exc:
            db.expire_all()
            raise MedicineVersionConflict("Another Medicine version became active") from exc
        self._event(db, version, event_type, actor)
        db.flush()
        return version
    def activate(self, db: Session, version_id: int, actor_id: int) -> MedicineScheduleVersion:
        version = self._mutable((db.query(MedicineScheduleVersion)
                                 .filter_by(id=version_id).with_for_update().one_or_none()))
        return self._activate(db, version, self._actor(db, actor_id), "activation")
    def restore(self, db: Session, version_id: int, actor_id: int) -> MedicineScheduleVersion:
        version = (db.query(MedicineScheduleVersion)
                   .filter_by(id=version_id).with_for_update().one_or_none())
        if version is None or version.locked_at is None or version.is_active:
            raise MedicineVersionError("Only validated locked history can be restored")
        return self._activate(db, version, self._actor(db, actor_id), "restore")

medicine_schedule_version_service = MedicineScheduleVersionService()
