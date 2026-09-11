"""Persistence primitives for the official WhatsApp billing outbox."""

import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


WHATSAPP_DISPATCH_AUTHORIZATION_STATES = (
    "pending", "authorized", "consumed", "cancelled", "expired", "revoked",
)
WHATSAPP_DISPATCH_AUTHORIZATION_REASONS = (
    "migration_reauthorization_required", "creator_cancelled", "authorization_expired",
    "pre_provider_rejected", "provider_outcome_ambiguous",
)
WHATSAPP_DISPATCH_AUTHORIZATION_ATTESTATION = "dispatch_reviewed_and_authorized_v1"
WHATSAPP_DISPATCH_AUTHORIZATION_CHECKS = {
    "ck_whatsapp_dispatch_authorization_state": "state IN ({})".format(
        ", ".join(repr(state) for state in WHATSAPP_DISPATCH_AUTHORIZATION_STATES)
    ),
    "ck_whatsapp_dispatch_authorization_expiry": "expires_at > created_at",
    "ck_whatsapp_dispatch_authorization_attestation": "attestation_code IS NULL OR attestation_code = '{}'".format(
        WHATSAPP_DISPATCH_AUTHORIZATION_ATTESTATION
    ),
    "ck_whatsapp_dispatch_authorization_reason": "terminal_reason IS NULL OR terminal_reason IN ({})".format(
        ", ".join(repr(reason) for reason in WHATSAPP_DISPATCH_AUTHORIZATION_REASONS)
    ),
    "ck_whatsapp_dispatch_authorization_release": "(released_at IS NULL) = (attestation_code IS NULL AND release_actor_user_id IS NULL AND release_key_hash IS NULL AND release_request_digest IS NULL)",
    "ck_whatsapp_dispatch_authorization_consumed": "consumed_at IS NULL OR released_at IS NOT NULL",
    "ck_whatsapp_dispatch_authorization_cancel": "(cancelled_at IS NULL) = (cancel_key_hash IS NULL AND cancel_request_digest IS NULL)",
    "ck_whatsapp_dispatch_authorization_pending_lifecycle": "state != 'pending' OR (released_at IS NULL AND consumed_at IS NULL AND cancelled_at IS NULL AND revoked_at IS NULL)",
    "ck_whatsapp_dispatch_authorization_authorized_lifecycle": "state != 'authorized' OR (released_at IS NOT NULL AND consumed_at IS NULL AND cancelled_at IS NULL AND revoked_at IS NULL)",
    "ck_whatsapp_dispatch_authorization_consumed_lifecycle": "state != 'consumed' OR (released_at IS NOT NULL AND consumed_at IS NOT NULL AND cancelled_at IS NULL)",
    "ck_whatsapp_dispatch_authorization_cancelled_lifecycle": "state != 'cancelled' OR (cancelled_at IS NOT NULL AND revoked_at IS NOT NULL)",
    "ck_whatsapp_dispatch_authorization_revoked_lifecycle": "state NOT IN ('expired', 'revoked') OR revoked_at IS NOT NULL",
}


class BillingNotificationBatch(Base):
    __tablename__ = "billing_notification_batches"
    __table_args__ = (UniqueConstraint("digest", name="uq_billing_notification_batch_digest"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publication_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("billing_publications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    publication_version: Mapped[int] = mapped_column(Integer, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    readiness_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())


class BillingNotificationJob(Base):
    __tablename__ = "billing_notification_jobs"
    __table_args__ = (
        UniqueConstraint("batch_id", "teacher_ci", "channel", name="uq_billing_notification_job_intent"),
        CheckConstraint(
            "intent_type IN ('ordinary', 'activation_test')",
            name="ck_billing_notification_job_intent_type",
        ),
        Index("ix_billing_notification_job_claim", "intent_type", "status", "lease_expires_at"),
        Index("ix_billing_notification_job_due", "status", "next_attempt_at"),
        Index("ix_billing_notification_job_provider_sid", "provider_sid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("billing_notification_batches.id", ondelete="CASCADE"), nullable=False
    )
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    intent_type: Mapped[str] = mapped_column(
        String(24), nullable=False, default="ordinary", server_default="ordinary"
    )
    content_sid: Mapped[Optional[str]] = mapped_column(String(34), nullable=True)
    media_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    lease_owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_sid: Mapped[Optional[str]] = mapped_column(String(34), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    @staticmethod
    def is_provider_sid(value: object) -> bool:
        return isinstance(value, str) and re.fullmatch(r"(?:SM|MM)[0-9A-Fa-f]{32}", value) is not None


class BillingWhatsAppActivationTest(Base):
    """Immutable creation binding; only lifecycle status may evolve in later slices."""

    __tablename__ = "billing_whatsapp_activation_tests"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "idempotency_key_hash", name="uq_whatsapp_activation_actor_key"),
        UniqueConstraint("batch_id", name="uq_whatsapp_activation_batch"),
        UniqueConstraint("job_id", name="uq_whatsapp_activation_job"),
        UniqueConstraint("media_token_id", name="uq_whatsapp_activation_media_token"),
        CheckConstraint("consent_revision > 0", name="ck_whatsapp_activation_consent_revision_positive"),
        CheckConstraint("artifact_size > 0", name="ck_whatsapp_activation_artifact_size_positive"),
        CheckConstraint(
            "status IN ('queued', 'leased', 'sending', 'accepted', 'ambiguous', 'sent', 'delivered', 'read', 'failed', 'undelivered', 'cancelled')",
            name="ck_whatsapp_activation_status",
        ),
        Index("ix_whatsapp_activation_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    actor_ci: Mapped[str] = mapped_column(String(20), nullable=False)
    idempotency_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    teacher_ci_at_creation: Mapped[str] = mapped_column(String(20), nullable=False)
    recipient_hmac: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_masked: Mapped[str] = mapped_column(String(20), nullable=False)
    consent_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    publication_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_publications.id", ondelete="RESTRICT"), nullable=False)
    publication_revision_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_publication_revisions.id", ondelete="RESTRICT"), nullable=False)
    publication_version: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sid: Mapped[str] = mapped_column(String(34), nullable=False)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_notification_batches.id", ondelete="RESTRICT"), nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_notification_jobs.id", ondelete="RESTRICT"), nullable=False)
    media_token_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_media_tokens.id", ondelete="RESTRICT"), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    terminal_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class BillingWhatsAppDispatchAuthorization(Base):
    """One-shot, fail-closed authority for an activation-test dispatch."""

    __tablename__ = "billing_whatsapp_dispatch_authorizations"
    __table_args__ = (
        UniqueConstraint("activation_id", name="uq_whatsapp_dispatch_authorization_activation"),
        UniqueConstraint("job_id", name="uq_whatsapp_dispatch_authorization_job"),
        *(CheckConstraint(expression, name=name) for name, expression in WHATSAPP_DISPATCH_AUTHORIZATION_CHECKS.items()),
        Index("ix_whatsapp_dispatch_authorization_claim", "state", "expires_at", "job_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activation_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_whatsapp_activation_tests.id", ondelete="RESTRICT"), nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("billing_notification_jobs.id", ondelete="RESTRICT"), nullable=False)
    creator_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attestation_code: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    release_actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    release_key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    release_request_digest: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancel_key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cancel_request_digest: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    terminal_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class WhatsAppEvent(Base):
    __tablename__ = "whatsapp_events"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_whatsapp_event_dedupe_key"),
        Index("ix_whatsapp_event_provider_sid", "provider_sid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("billing_notification_jobs.id", ondelete="SET NULL"), nullable=True
    )
    provider_sid: Mapped[Optional[str]] = mapped_column(String(34), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    @staticmethod
    def is_provider_sid(value: object) -> bool:
        return BillingNotificationJob.is_provider_sid(value)


class BillingMediaToken(Base):
    __tablename__ = "billing_media_tokens"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_billing_media_token_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("billing_notification_jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("billing_notification_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_size: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())


class BillingNotificationCapacityWindow(Base):
    """Singleton row used to serialize moving-recipient reservations."""

    __tablename__ = "billing_notification_capacity_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_dispatch_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    worker_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class BillingNotificationCapacityReservation(Base):
    """A durable recipient slot in the provider's moving capacity window."""

    __tablename__ = "billing_notification_capacity_reservations"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_billing_notification_capacity_job"),
        Index("ix_billing_notification_capacity_reserved_at", "reserved_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient_key: Mapped[str] = mapped_column(String(64), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
