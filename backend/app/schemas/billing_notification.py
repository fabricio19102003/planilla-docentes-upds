from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class WhatsAppPreferenceResponse(BaseModel):
    teacher_ci: str
    phone_e164: str
    is_verified: bool
    consent_revision: int


class BillingNotificationBatchResponse(BaseModel):
    id: int
    publication_id: int
    publication_version: int
    digest: str
    status: str
    created_at: datetime


class BillingNotificationJobResponse(BaseModel):
    id: int
    batch_id: int
    teacher_ci: str
    channel: str
    status: str
    provider_sid: Optional[str]
    lease_expires_at: Optional[datetime]


class WhatsAppEventResponse(BaseModel):
    id: int
    job_id: Optional[int]
    provider_sid: Optional[str]
    event_type: str
    facts: dict[str, Any]
    occurred_at: datetime


class BillingMediaTokenResponse(BaseModel):
    id: int
    batch_id: int
    teacher_ci: str
    expires_at: datetime
    revoked_at: Optional[datetime]
