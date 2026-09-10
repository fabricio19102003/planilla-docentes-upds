"""Sanitized admin API contracts for WhatsApp consent preferences."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WhatsAppPreferencePutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_e164: str = Field(min_length=9, max_length=16)
    is_verified: bool
    consent_evidence_reference: str = Field(min_length=1, max_length=500)
    consent_source: Literal["written_record", "verbal_record", "other_documented"]
    consented_at: datetime

    @field_validator("phone_e164")
    @classmethod
    def canonical_phone(cls, value: str) -> str:
        if value != value.strip() or not value.startswith("+"):
            raise ValueError("canonical E.164 required")
        return value

    @field_validator("consent_evidence_reference")
    @classmethod
    def bounded_evidence(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("evidence required")
        return value

    @field_validator("consented_at")
    @classmethod
    def captured_in_the_past(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value > datetime.now(timezone.utc):
            raise ValueError("timezone-aware past timestamp required")
        return value


class WhatsAppPreferenceOptOutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opt_out_evidence_reference: str = Field(min_length=1, max_length=500)

    @field_validator("opt_out_evidence_reference")
    @classmethod
    def bounded_evidence(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("evidence required")
        return value


class WhatsAppPreferenceAdminResponse(BaseModel):
    teacher_ci: str
    exists: bool
    phone_masked: str | None
    is_verified: bool
    eligible: bool
    consent_revision: int
    consent_source: str | None
    consented_at: datetime | None
    opted_out: bool
    opted_out_at: datetime | None
    has_consent_evidence: bool
    has_opt_out_evidence: bool
