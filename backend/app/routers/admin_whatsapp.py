"""Admin-only, provider-free controlled WhatsApp activation API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.billing_notification import BillingWhatsAppActivationTest
from app.models.user import User
from app.schemas.whatsapp_activation import (
    WhatsAppActivationCancel, WhatsAppActivationCreate, WhatsAppActivationProjection,
    WhatsAppActivationRelease,
)
from app.services.whatsapp_activation_service import WhatsAppActivationError, WhatsAppActivationService
from app.services.whatsapp_delivery_control import creation_readiness, current_delivery_status
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/admin/whatsapp", tags=["admin-whatsapp"])
ReadinessReason = Literal[
    "configuration_missing", "configuration_unsafe", "provider_unavailable",
    "sender_unavailable", "template_unapproved", "capacity_unavailable",
    "worker_unavailable", "process_gate_disabled", "activation_disabled",
    "global_delivery_enabled",
]


class ReadinessCapacity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    moving_recipient_limit: int | None = Field(default=None, ge=0, le=10_000_000)
    media_mps: float | None = Field(default=None, ge=0, le=1_000_000)
    window_seconds: int | None = Field(default=None, ge=0, le=604_800)


class ProviderConfigurationReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    reason: ReadinessReason | None


class ProviderLiveReadiness(ProviderConfigurationReadiness):
    capacity: ReadinessCapacity


class WorkerReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: bool
    reason: ReadinessReason | None
    heartbeat_at: datetime | None


class ProcessGatesReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    official: bool
    dispatch: bool


class GlobalDeliveryReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested: bool
    effective: bool


class ActivationReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_enabled: bool
    dispatch_enabled: bool
    creation_capable: bool
    dispatch_capable: bool
    capable: bool
    blocking_reasons: list[ReadinessReason]


class WhatsAppActivationReadiness(BaseModel):
    """Strict public projection; deliberately excludes provider identifiers."""

    model_config = ConfigDict(extra="forbid")

    provider_configuration: ProviderConfigurationReadiness
    provider_live: ProviderLiveReadiness
    worker: WorkerReadiness
    process_gates: ProcessGatesReadiness
    global_delivery: GlobalDeliveryReadiness
    activation: ActivationReadiness


def _readiness(db: Session) -> tuple[dict[str, Any], WhatsAppActivationReadiness]:
    facts = current_delivery_status(db)
    public = WhatsAppActivationReadiness.model_validate({
        key: facts.get(key) for key in WhatsAppActivationReadiness.model_fields
    })
    # The configured SID is not public. A ready live projection means the runtime
    # inspected this exact configured Content SID in the same readiness request.
    private = dict(facts)
    private["approved_content_sid"] = settings.TWILIO_OFFICIAL_CONTENT_SID
    return private, public


def _error(code: str, *, http_status: int = status.HTTP_409_CONFLICT) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code})


def _valid_idempotency_key(value: str | None) -> bool:
    return isinstance(value, str) and 16 <= len(value) <= 128 and all(33 <= ord(char) <= 126 for char in value)


def _service(db: Session) -> WhatsAppActivationService:
    key = settings.WHATSAPP_RECIPIENT_HMAC_KEY
    if not isinstance(key, str):
        raise WhatsAppActivationError("activation_disabled")
    return WhatsAppActivationService(db, recipient_hmac_key=key)


@router.get("/readiness", response_model=WhatsAppActivationReadiness)
def readiness(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> WhatsAppActivationReadiness:
    """Inspect named readiness facts without changing persisted settings."""
    _, public = _readiness(db)
    return public


@router.post("/activation-tests", response_model=WhatsAppActivationProjection, status_code=status.HTTP_201_CREATED)
async def create_activation(
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WhatsAppActivationProjection:
    if (
        not isinstance(idempotency_key, str)
        or not 16 <= len(idempotency_key) <= 128
        or not idempotency_key.isascii()
        or not idempotency_key.isprintable()
    ):
        raise _error("invalid_idempotency_key", http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        payload = WhatsAppActivationCreate.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        raise _error("invalid_activation_request", http_status=status.HTTP_422_UNPROCESSABLE_ENTITY) from None
    try:
        result = _service(db).create(
            actor_user_id=actor.id,
            request=payload,
            idempotency_key=idempotency_key,
            readiness=lambda: creation_readiness(db),
            configured_content_sid=settings.TWILIO_OFFICIAL_CONTENT_SID,
            approved_content_sid=settings.TWILIO_OFFICIAL_CONTENT_SID,
            ip_address=request.client.host if request.client else None,
        )
        if result.replayed:
            db.rollback()
            response.status_code = status.HTTP_200_OK
            return result
        db.commit()
        return result
    except WhatsAppActivationError as exc:
        db.rollback()
        raise _error(str(exc)) from exc
    except Exception:
        db.rollback()
        raise _error("activation_artifact_unavailable")


@router.post("/activation-tests/{activation_id}/release", response_model=WhatsAppActivationProjection)
async def release_activation(
    activation_id: int, request: Request, response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> WhatsAppActivationProjection:
    if not _valid_idempotency_key(idempotency_key):
        raise _error("invalid_idempotency_key", http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        payload = WhatsAppActivationRelease.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        raise _error("invalid_release_request", http_status=status.HTTP_422_UNPROCESSABLE_ENTITY) from None
    try:
        # Readiness is intentionally lazy: exact replay does not depend on it.
        result = _service(db).release(actor_user_id=actor.id, activation_id=activation_id, request=payload, idempotency_key=idempotency_key, readiness=lambda: _readiness(db)[0], ip_address=request.client.host if request.client else None)
        if result.replayed:
            db.rollback()
        else:
            db.commit()
        return result
    except WhatsAppActivationError as exc:
        db.rollback()
        raise _error(str(exc)) from exc


@router.post("/activation-tests/{activation_id}/cancel", response_model=WhatsAppActivationProjection)
async def cancel_activation(
    activation_id: int, request: Request, response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> WhatsAppActivationProjection:
    if not _valid_idempotency_key(idempotency_key):
        raise _error("invalid_idempotency_key", http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    try:
        payload = WhatsAppActivationCancel.model_validate(await request.json())
    except (ValidationError, ValueError, TypeError):
        raise _error("invalid_cancel_request", http_status=status.HTTP_422_UNPROCESSABLE_ENTITY) from None
    try:
        result = _service(db).cancel(actor_user_id=actor.id, activation_id=activation_id, request=payload, idempotency_key=idempotency_key, ip_address=request.client.host if request.client else None)
        if result.replayed:
            db.rollback()
        else:
            db.commit()
        return result
    except WhatsAppActivationError as exc:
        db.rollback()
        raise _error(
            str(exc),
            http_status=status.HTTP_403_FORBIDDEN if str(exc) == "activation_cancel_forbidden" else status.HTTP_409_CONFLICT,
        ) from exc


@router.get("/activation-tests/{activation_id}", response_model=WhatsAppActivationProjection)
def activation_status(
    activation_id: int,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> WhatsAppActivationProjection:
    activation = db.scalar(select(BillingWhatsAppActivationTest).where(
        BillingWhatsAppActivationTest.id == activation_id,
        BillingWhatsAppActivationTest.actor_user_id == actor.id,
    ))
    if activation is None:
        raise _error("activation_not_found", http_status=status.HTTP_404_NOT_FOUND)
    try:
        return WhatsAppActivationService.project(db, activation)
    except WhatsAppActivationError as exc:
        raise _error(str(exc)) from exc
