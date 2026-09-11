"""Strict, sanitized contracts for controlled WhatsApp activation creation."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.whatsapp_preference import WhatsAppPreference


class WhatsAppActivationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teacher_ci: str = Field(min_length=1, max_length=20)
    recipient_e164: str = Field(min_length=9, max_length=16)
    consent_revision: int = Field(ge=1)
    publication_revision_id: int = Field(ge=1)

    @field_validator("teacher_ci")
    @classmethod
    def non_blank_teacher(cls, value: str) -> str:
        if value != value.strip() or not value:
            raise ValueError("teacher CI required")
        return value

    @field_validator("recipient_e164")
    @classmethod
    def canonical_recipient(cls, value: str) -> str:
        if value != value.strip() or WhatsAppPreference.canonical_e164(value) != value:
            raise ValueError("canonical E.164 required")
        return value


ActivationStatus = Literal["queued", "leased", "sending", "accepted", "ambiguous", "sent", "delivered", "read", "failed", "undelivered", "cancelled"]
TerminalReason = Literal["activation_disabled", "activation_readiness_unavailable", "activation_requires_global_delivery_disabled", "activation_recipient_mismatch", "activation_consent_revision_mismatch", "activation_consent_ineligible", "activation_publication_not_current", "activation_publication_corrupt", "activation_teacher_not_in_revision", "activation_template_unapproved", "activation_artifact_unavailable", "activation_provider_failed"]
AuthorizationState = Literal["pending", "authorized", "consumed", "cancelled", "expired", "revoked"]
AuthorizationTerminalReason = Literal["migration_reauthorization_required", "creator_cancelled", "authorization_expired", "pre_provider_rejected", "provider_outcome_ambiguous"]


class WhatsAppActivationRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attestation: Literal["dispatch_reviewed_and_authorized_v1"]


class WhatsAppActivationCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["creator_cancelled"]


class WhatsAppActivationProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    status: ActivationStatus
    terminal_reason: TerminalReason | None
    teacher_ci_at_creation: str
    recipient_masked: str
    consent_revision: int
    publication_revision_id: int
    publication_version: int
    content_template_bound: bool
    pdf_bound: bool
    job_id: int
    job_status: ActivationStatus
    created_at: datetime
    updated_at: datetime
    authorization_state: AuthorizationState
    authorization_expires_at: datetime
    authorized_at: datetime | None
    consumed_at: datetime | None
    revoked_at: datetime | None
    attestation_code: Literal["dispatch_reviewed_and_authorized_v1"] | None
    authorization_terminal_reason: AuthorizationTerminalReason | None
    replayed: bool = False
