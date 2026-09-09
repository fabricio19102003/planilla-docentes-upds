from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models.whatsapp_preference import WhatsAppConsentRevision, WhatsAppPreference


def test_consent_revision_is_registered_with_the_model_package():
    from app.models import WhatsAppConsentRevision as registered_revision

    assert registered_revision is WhatsAppConsentRevision


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
