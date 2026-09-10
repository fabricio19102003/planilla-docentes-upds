from datetime import datetime

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models.activity_log import ActivityLog
from app.models.teacher import Teacher
from app.models.user import User
from app.models.whatsapp_preference import WhatsAppConsentRevision, WhatsAppPreference
from app.services.whatsapp_preference_service import WhatsAppPreferenceService


@pytest.fixture
def preference_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Teacher(ci="teacher-1", full_name="Teacher"),
            User(ci="admin-1", full_name="Admin", password_hash="x", role="admin"),
        ])
        session.commit()
        yield session


def consent_facts(**overrides):
    facts = {
        "phone_e164": "+59170000000", "is_verified": True,
        "evidence": "signed-record", "source": "written_record",
        "consented_at": datetime(2026, 9, 10, 12, tzinfo=__import__("datetime").timezone.utc),
    }
    facts.update(overrides)
    return facts


def test_lifecycle_creates_sanitized_initial_consent(preference_session):
    service = WhatsAppPreferenceService(preference_session)
    preference = service.put("teacher-1", actor_id=1, **consent_facts())
    preference_session.commit()

    assert preference.consent_revision == 1
    assert preference.consented_at.tzinfo is None
    assert "+59170000000" not in str(preference)
    assert "signed-record" not in str(preference)
    assert preference_session.query(WhatsAppConsentRevision).count() == 1
    audit = preference_session.query(ActivityLog).one()
    assert audit.details["recipient_masked"] == "+591••••0000"
    assert "+59170000000" not in str(audit.details)
    assert "signed-record" not in str(audit.details)


def test_lifecycle_rejects_noncanonical_recipient_and_sanitizes_error(preference_session):
    with pytest.raises(ValueError, match="invalid_canonical_e164") as error:
        WhatsAppPreferenceService(preference_session).put(
            "teacher-1", actor_id=1, **consent_facts(phone_e164=" 59170000000 ")
        )
    assert "59170000000" not in str(error.value)


def test_lifecycle_correction_verification_and_noop_cardinality(preference_session):
    service = WhatsAppPreferenceService(preference_session)
    service.put("teacher-1", actor_id=1, **consent_facts())
    same = service.put("teacher-1", actor_id=1, **consent_facts())
    changed = service.put("teacher-1", actor_id=1, **consent_facts(is_verified=False))
    preference_session.commit()

    assert same.consent_revision == 1
    assert changed.consent_revision == 2
    assert [row.event_type for row in preference_session.query(WhatsAppConsentRevision).all()] == ["consent", "verification_change"]
    assert preference_session.query(ActivityLog).count() == 2


def test_lifecycle_opt_out_and_reconsent_require_new_evidence_and_time(preference_session):
    service = WhatsAppPreferenceService(preference_session)
    service.put("teacher-1", actor_id=1, **consent_facts())
    service.opt_out("teacher-1", "withdrawn", actor_id=1, occurred_at=datetime(2026, 9, 11))
    repeated_noop = service.opt_out("teacher-1", "withdrawn", actor_id=1, occurred_at=datetime(2026, 9, 11))
    with pytest.raises(ValueError, match="reconsent_requires_new_evidence"):
        service.put("teacher-1", actor_id=1, **consent_facts())
    with pytest.raises(ValueError, match="invalid_consent_time"):
        service.put("teacher-1", actor_id=1, **consent_facts(evidence="new-record", consented_at=datetime(2026, 9, 10, 12, tzinfo=__import__("datetime").timezone.utc)))
    restored = service.put("teacher-1", actor_id=1, **consent_facts(evidence="new-record", consented_at=datetime(2026, 9, 12, tzinfo=__import__("datetime").timezone.utc)))
    repeated = service.opt_out("teacher-1", "withdrawn", actor_id=1, occurred_at=datetime(2026, 9, 13))
    preference_session.commit()

    assert repeated_noop.consent_revision == 2
    assert restored.consent_revision == 3
    assert repeated.consent_revision == 4
    assert preference_session.query(WhatsAppConsentRevision).count() == 4


def test_lifecycle_flush_failure_leaves_transaction_for_caller_rollback(preference_session, monkeypatch):
    service = WhatsAppPreferenceService(preference_session)
    original_flush = preference_session.flush
    monkeypatch.setattr(preference_session, "flush", lambda: (_ for _ in ()).throw(RuntimeError("flush failed")))

    with pytest.raises(RuntimeError, match="flush failed"):
        service.put("teacher-1", actor_id=1, **consent_facts())
    preference_session.rollback()
    monkeypatch.setattr(preference_session, "flush", original_flush)
    assert preference_session.query(WhatsAppPreference).count() == 0


def test_consent_revision_is_registered_with_the_model_package():
    from app.models import WhatsAppConsentRevision as registered_revision

    assert registered_revision is WhatsAppConsentRevision
    assert "ck_whatsapp_preference_revision_nonnegative" in {
        constraint.name for constraint in WhatsAppPreference.__table__.constraints
    }


def test_legacy_preference_without_consent_metadata_is_ineligible():
    preference = WhatsAppPreference(
        teacher_ci="legacy-teacher",
        phone_e164="+59170000000",
        is_verified=True,
        consent_evidence="legacy-record",
        consent_revision=1,
    )

    assert preference.is_eligible_for_whatsapp is False


def test_preference_with_complete_consent_metadata_is_eligible():
    preference = WhatsAppPreference(
        teacher_ci="consented-teacher",
        phone_e164="+59170000000",
        is_verified=True,
        consent_evidence="signed-record",
        consent_source="written_record",
        consented_at=datetime(2026, 9, 10, 12, 0, 0),
        consent_revision=1,
    )

    assert preference.is_eligible_for_whatsapp is True


def test_consent_revision_requires_a_positive_unique_teacher_revision():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[WhatsAppConsentRevision.__table__])

    with Session(engine) as session:
        session.add_all(
            [
                WhatsAppConsentRevision(
                    teacher_ci="teacher-1",
                    revision=1,
                    event_type="consent",
                    phone_e164="+59170000000",
                    is_verified=True,
                ),
                WhatsAppConsentRevision(
                    teacher_ci="teacher-1",
                    revision=1,
                    event_type="correction",
                    phone_e164="+59170000000",
                    is_verified=True,
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_consent_revision_rejects_zero_revision_numbers():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[WhatsAppConsentRevision.__table__])

    with Session(engine) as session:
        session.add(
            WhatsAppConsentRevision(
                teacher_ci="teacher-1",
                revision=0,
                event_type="consent",
                phone_e164="+59170000000",
                is_verified=True,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()



def test_consent_history_rejects_instance_and_bulk_orm_mutation():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[WhatsAppConsentRevision.__table__])
    with Session(engine) as session:
        revision = WhatsAppConsentRevision(
            teacher_ci="teacher-1", revision=1, event_type="consent",
            phone_e164="+59170000000", is_verified=True,
        )
        session.add(revision)
        session.commit()
        revision.event_type = "correction"
        with pytest.raises(TypeError, match="append-only"):
            session.commit()
        session.rollback()
        with pytest.raises(TypeError, match="append-only"):
            session.execute(update(WhatsAppConsentRevision).values(event_type="correction"))
