from datetime import date, time

import pytest
from sqlalchemy import text

from app.models.activity_log import ActivityLog
from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord, BiometricUpload
from app.models.billing_notification import BillingMediaToken, BillingNotificationBatch, BillingNotificationJob
from app.models.billing_publication import BillingPublication
from app.models.designation import Designation
from app.models.detail_request import DetailRequest
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.teacher import Teacher
from app.models.user import User
from app.models.whatsapp_preference import WhatsAppConsentRevision, WhatsAppPreference
from app.services.teacher_identity_service import TeacherIdentityConflict, TeacherIdentityService


OLD_CI = "1234567"
NEW_CI = "7654321"


def _seed_all_ci_consumers(db_session):
    teacher = Teacher(ci=OLD_CI, full_name="Original Teacher")
    docente = User(ci=OLD_CI, full_name="Docente", password_hash="x", role="docente", teacher_ci=OLD_CI)
    db_session.add_all([teacher, docente])
    db_session.flush()
    designation = Designation(teacher_ci=OLD_CI, subject="Math", semester="1", group_code="A", schedule_json=[])
    upload = BiometricUpload(filename="source.csv", month=1, year=2026)
    publication = BillingPublication(month=1, year=2026, total_payment=0)
    db_session.add_all([designation, upload, publication])
    db_session.flush()
    biometric = BiometricRecord(upload_id=upload.id, teacher_ci=OLD_CI, date=date(2026, 1, 1))
    db_session.add(biometric)
    db_session.flush()
    batch = BillingNotificationBatch(publication_id=publication.id, publication_version=1, digest="a" * 64, readiness_snapshot={})
    db_session.add(batch)
    db_session.flush()
    job = BillingNotificationJob(batch_id=batch.id, teacher_ci=OLD_CI, channel="whatsapp")
    db_session.add(job)
    db_session.flush()
    db_session.add_all([
        AttendanceRecord(teacher_ci=OLD_CI, designation_id=designation.id, date=date(2026, 1, 1), scheduled_start=time(8), scheduled_end=time(9), status="ATTENDED", month=1, year=2026),
        DetailRequest(teacher_ci=OLD_CI, requested_by=docente.id, month=1, year=2026, request_type="schedule_detail"),
        PracticeAttendanceLog(teacher_ci=OLD_CI, designation_id=designation.id, date=date(2026, 1, 1), scheduled_start=time(8), scheduled_end=time(9)),
        WhatsAppPreference(teacher_ci=OLD_CI, phone_e164="+59170000000", is_verified=True, consent_evidence="record", consent_source="written_record", consented_at=date(2026, 1, 1), consent_revision=1),
        WhatsAppConsentRevision(teacher_ci=OLD_CI, revision=1, event_type="consent", phone_e164="+59170000000", is_verified=True),
        BillingMediaToken(job_id=job.id, batch_id=batch.id, teacher_ci=OLD_CI, token_hash="b" * 64, artifact_hash="c" * 64, artifact_path="artifact.pdf", artifact_size=1, expires_at=date(2027, 1, 1)),
    ])
    db_session.flush()
    return teacher


def test_change_ci_inserts_new_parent_then_repoints_every_current_consumer(db_session):
    _seed_all_ci_consumers(db_session)

    changed = TeacherIdentityService(db_session).change_ci(OLD_CI, NEW_CI)
    db_session.flush()

    assert changed.ci == NEW_CI
    assert db_session.get(Teacher, OLD_CI) is None
    for table in TeacherIdentityService.child_tables:
        assert db_session.execute(text(f"SELECT count(*) FROM {table} WHERE teacher_ci = :ci"), {"ci": NEW_CI}).scalar_one() == 1
    docente = db_session.query(User).filter_by(role="docente").one()
    assert (docente.ci, docente.teacher_ci) == (NEW_CI, NEW_CI)


def test_change_ci_rejects_duplicate_teacher_or_docente_login_ci(db_session):
    _seed_all_ci_consumers(db_session)
    db_session.add(Teacher(ci=NEW_CI, full_name="Taken"))
    db_session.flush()

    with pytest.raises(TeacherIdentityConflict):
        TeacherIdentityService(db_session).change_ci(OLD_CI, NEW_CI)


def test_change_ci_rejects_admin_login_ci_collision(db_session):
    _seed_all_ci_consumers(db_session)
    db_session.add(User(ci=NEW_CI, full_name="Admin", password_hash="x", role="admin"))
    db_session.flush()

    with pytest.raises(TeacherIdentityConflict):
        TeacherIdentityService(db_session).change_ci(OLD_CI, NEW_CI)


def test_change_ci_rejects_null_linked_login_ci_collision(db_session):
    _seed_all_ci_consumers(db_session)
    db_session.add(User(ci=NEW_CI, full_name="Unlinked", password_hash="x", role="docente"))
    db_session.flush()

    with pytest.raises(TeacherIdentityConflict):
        TeacherIdentityService(db_session).change_ci(OLD_CI, NEW_CI)


def test_change_ci_rolls_back_every_repoint_when_a_child_update_fails(db_session, monkeypatch):
    _seed_all_ci_consumers(db_session)
    db_session.commit()
    service = TeacherIdentityService(db_session)
    original = service._repoint_child

    def fail_on_preference(table, old_ci, new_ci):
        if table == "whatsapp_preferences":
            raise RuntimeError("injected child failure")
        return original(table, old_ci, new_ci)

    monkeypatch.setattr(service, "_repoint_child", fail_on_preference)
    with pytest.raises(RuntimeError, match="injected child failure"):
        service.change_ci(OLD_CI, NEW_CI)
    db_session.rollback()

    assert db_session.get(Teacher, OLD_CI) is not None
    assert db_session.get(Teacher, NEW_CI) is None
    assert db_session.get(WhatsAppPreference, OLD_CI) is not None
    assert db_session.query(WhatsAppConsentRevision).filter_by(teacher_ci=OLD_CI).count() == 1


def test_update_route_delegates_ci_change_and_keeps_existing_audit(db_session, client):
    _seed_all_ci_consumers(db_session)

    response = client.put(f"/api/teachers/{OLD_CI}", json={"ci": NEW_CI})

    assert response.status_code == 200
    audit = db_session.query(ActivityLog).filter_by(action="update_teacher").one()
    assert audit.details["old_ci"] == OLD_CI
    assert audit.details["new_ci"] == NEW_CI


def test_change_ci_uses_postgresql_safe_insert_repoint_delete_order(db_session, monkeypatch):
    _seed_all_ci_consumers(db_session)
    operations = []
    service = TeacherIdentityService(db_session)
    original = service._repoint_child

    monkeypatch.setattr(service, "_insert_replacement", lambda teacher, new_ci: operations.append("insert") or Teacher(ci=new_ci, full_name=teacher.full_name))
    monkeypatch.setattr(service, "_repoint_child", lambda table, old_ci, new_ci: operations.append(f"repoint:{table}") or original(table, old_ci, new_ci))
    monkeypatch.setattr(service, "_delete_old_parent", lambda teacher: operations.append("delete"))

    service.change_ci(OLD_CI, NEW_CI)
    assert operations[0] == "insert"
    assert operations[-1] == "delete"
    assert {entry.removeprefix("repoint:") for entry in operations[1:-1]} == set(service.child_tables)
