"""Locked, caller-transaction-owned WhatsApp consent lifecycle mutations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.teacher import Teacher
from app.models.whatsapp_preference import (
    CONSENT_SOURCES,
    WhatsAppConsentRevision,
    WhatsAppPreference,
)


class WhatsAppPreferenceError(ValueError):
    """A bounded domain error safe to return through an API boundary."""


@dataclass(frozen=True)
class PreferenceProjection:
    teacher_ci: str
    consent_revision: int
    is_verified: bool
    eligible: bool
    opted_out: bool
    consent_source: str | None
    consented_at: datetime | None
    recipient_masked: str


class WhatsAppPreferenceService:
    """Mutates preference, protected history, and strict audit in one caller commit.

    This service deliberately neither commits nor rolls back. Callers own the outer
    transaction and must roll it back when a validation, history, or audit flush
    failure is raised.
    """

    def __init__(self, db: Session):
        self.db = db

    def put(
        self,
        teacher_ci: str,
        *,
        phone_e164: str,
        is_verified: bool,
        evidence: str,
        source: str,
        consented_at: datetime,
        actor_id: int | None,
        ip_address: str | None = None,
    ) -> PreferenceProjection:
        phone = self._phone(phone_e164)
        evidence = self._evidence(evidence, "invalid_consent_evidence")
        if source not in CONSENT_SOURCES:
            raise WhatsAppPreferenceError("invalid_consent_source")
        captured_at = self._utc(consented_at, "invalid_consent_time")
        teacher, preference = self._locked(teacher_ci)

        if preference is None:
            preference = WhatsAppPreference(
                teacher_ci=teacher.ci,
                phone_e164=phone,
                is_verified=is_verified,
                consent_evidence=evidence,
                consent_source=source,
                consented_at=captured_at,
                consent_revision=1,
            )
            self.db.add(preference)
            return self._record(preference, "consent", actor_id, ip_address)

        if preference.opted_out_at:
            if evidence == preference.consent_evidence:
                raise WhatsAppPreferenceError("reconsent_requires_new_evidence")
            if preference.consented_at and captured_at <= preference.consented_at:
                raise WhatsAppPreferenceError("invalid_consent_time")
            preference.phone_e164 = phone
            preference.is_verified = is_verified
            preference.consent_evidence = evidence
            preference.consent_source = source
            preference.consented_at = captured_at
            preference.opt_out_evidence = None
            preference.opted_out_at = None
            preference.consent_revision += 1
            return self._record(preference, "reconsent", actor_id, ip_address)

        facts = (phone, is_verified, evidence, source, captured_at)
        current = (
            preference.phone_e164, preference.is_verified, preference.consent_evidence,
            preference.consent_source, preference.consented_at,
        )
        if facts == current:
            return self._project(preference)
        event_type = "verification_change" if facts[0] == current[0] and facts[2:] == current[2:] else "correction"
        preference.phone_e164, preference.is_verified = phone, is_verified
        preference.consent_evidence, preference.consent_source = evidence, source
        preference.consented_at = captured_at
        preference.consent_revision += 1
        return self._record(preference, event_type, actor_id, ip_address)

    def opt_out(
        self,
        teacher_ci: str,
        evidence: str,
        *,
        actor_id: int | None,
        occurred_at: datetime | None = None,
        event_type: str = "opt_out",
        ip_address: str | None = None,
    ) -> PreferenceProjection:
        evidence = self._evidence(evidence, "invalid_opt_out_evidence")
        _, preference = self._locked(teacher_ci)
        if preference is None:
            raise WhatsAppPreferenceError("preference_not_found")
        if preference.opted_out_at and preference.opt_out_evidence == evidence:
            return self._project(preference)
        preference.opt_out_evidence = evidence
        preference.opted_out_at = self._utc(occurred_at or datetime.now(timezone.utc), "invalid_opt_out_time")
        preference.consent_revision += 1
        return self._record(preference, event_type, actor_id, ip_address)

    def _locked(self, teacher_ci: str) -> tuple[Teacher, WhatsAppPreference | None]:
        teacher = self.db.scalar(select(Teacher).where(Teacher.ci == teacher_ci).with_for_update())
        if teacher is None:
            raise WhatsAppPreferenceError("teacher_not_found")
        preference = self.db.scalar(
            select(WhatsAppPreference)
            .where(WhatsAppPreference.teacher_ci == teacher_ci)
            .with_for_update()
        )
        return teacher, preference

    def _record(self, preference: WhatsAppPreference, event_type: str, actor_id: int | None, ip_address: str | None) -> PreferenceProjection:
        self.db.add(WhatsAppConsentRevision(
            teacher_ci=preference.teacher_ci, revision=preference.consent_revision,
            event_type=event_type, phone_e164=preference.phone_e164,
            is_verified=preference.is_verified, consent_evidence=preference.consent_evidence,
            consent_source=preference.consent_source, consented_at=preference.consented_at,
            opt_out_evidence=preference.opt_out_evidence, opted_out_at=preference.opted_out_at,
            actor_user_id=actor_id,
        ))
        self.db.add(ActivityLog(
            user_id=actor_id, action="whatsapp_preference_mutated", category="whatsapp",
            description="WhatsApp preference lifecycle updated",
            details={"teacher_ci": preference.teacher_ci, "event_type": event_type,
                     "consent_revision": preference.consent_revision,
                     "source": preference.consent_source,
                     "recipient_masked": self._mask(preference.phone_e164)},
            ip_address=ip_address,
        ))
        # Unlike the generic logger, audit flush failure is intentionally fatal.
        self.db.flush()
        return self._project(preference)

    @staticmethod
    def _phone(value: str) -> str:
        phone = WhatsAppPreference.canonical_e164(value)
        if not phone or phone != value:
            raise WhatsAppPreferenceError("invalid_canonical_e164")
        return phone

    @staticmethod
    def _evidence(value: str, code: str) -> str:
        value = value.strip() if isinstance(value, str) else ""
        if not 1 <= len(value) <= 500:
            raise WhatsAppPreferenceError(code)
        return value

    @staticmethod
    def _utc(value: datetime, code: str) -> datetime:
        if not isinstance(value, datetime):
            raise WhatsAppPreferenceError(code)
        if value.tzinfo:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    @classmethod
    def _project(cls, preference: WhatsAppPreference) -> PreferenceProjection:
        return PreferenceProjection(
            teacher_ci=preference.teacher_ci, consent_revision=preference.consent_revision,
            is_verified=preference.is_verified, eligible=preference.is_eligible_for_whatsapp,
            opted_out=bool(preference.opted_out_at), consent_source=preference.consent_source,
            consented_at=preference.consented_at, recipient_masked=cls._mask(preference.phone_e164),
        )

    @staticmethod
    def _mask(phone: str) -> str:
        return f"{phone[:4]}••••{phone[-4:]}"
