"""Fail-closed operational control for official WhatsApp billing delivery."""
from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.billing_notification import BillingNotificationCapacityWindow
from app.services.app_settings_service import KEY_BILLING_WHATSAPP_DELIVERY_ENABLED


WORKER_HEARTBEAT_MAX_AGE = timedelta(seconds=60)
_REASON_CODES = {
    "configuration_missing", "configuration_unsafe", "provider_unavailable",
    "sender_unavailable", "template_unapproved", "capacity_unavailable",
    "worker_unavailable", "process_gate_disabled", "activation_disabled",
    "global_delivery_enabled",
}


def _provider_readiness() -> dict[str, Any]:
    from app.config import settings
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    configuration = OfficialWhatsAppRuntime.configuration_readiness(settings)
    if not configuration["ready"]:
        return {"ready": False, "reason": "provider_unavailable", "capacity": {"available": False}, "configuration": configuration}
    runtime = OfficialWhatsAppRuntime.from_settings(settings)
    if runtime is None:
        return {"ready": False, "reason": "provider_unavailable", "capacity": {"available": False}, "configuration": {"ready": False, "reason": "configuration_unsafe"}}
    return {**runtime.live_readiness(), "configuration": configuration}


def current_delivery_status(db: Session) -> dict[str, Any]:
    from app.config import settings

    provider_readiness = _provider_readiness()
    provider_configuration = provider_readiness.get("configuration", {"ready": True, "reason": None})
    provider_live = {key: value for key, value in provider_readiness.items() if key != "configuration"}
    return status_from_readiness(
        db, provider_live,
        provider_configuration=provider_configuration,
        official_process_enabled=settings.OFFICIAL_WHATSAPP_ENABLED,
        dispatch_process_enabled=settings.WHATSAPP_DISPATCH_ENABLED,
        activation_api_enabled=settings.BILLING_WHATSAPP_ACTIVATION_API_ENABLED,
        activation_dispatch_enabled=settings.BILLING_WHATSAPP_ACTIVATION_DISPATCH_ENABLED,
        recipient_hmac_key=settings.WHATSAPP_RECIPIENT_HMAC_KEY,
            configured_content_sid=settings.TWILIO_OFFICIAL_CONTENT_SID,
    )


def creation_readiness(db: Session) -> dict[str, Any]:
    """Return creation-only facts without touching provider or worker runtime paths."""
    from app.config import settings

    requested = get_requested_enabled(db)
    configured_content_sid = settings.TWILIO_OFFICIAL_CONTENT_SID
    hmac_ready = (
        isinstance(settings.WHATSAPP_RECIPIENT_HMAC_KEY, str)
        and len(settings.WHATSAPP_RECIPIENT_HMAC_KEY.encode("utf-8")) >= 32
    )
    creation_capable = (
        not requested
        and settings.BILLING_WHATSAPP_ACTIVATION_API_ENABLED is True
        and hmac_ready
        and _configured_content_sid_is_valid(configured_content_sid)
    )
    return {
        "provider_configuration": {"ready": False, "reason": "configuration_unsafe"},
        "provider_live": {"ready": False, "reason": "provider_unavailable", "capacity": {"available": False}},
        "worker": {"ready": False, "reason": "worker_unavailable", "heartbeat_at": None},
        "process_gates": {"official": False, "dispatch": False},
        "global_delivery": {"requested": requested, "effective": False},
        "activation": {
            "api_enabled": settings.BILLING_WHATSAPP_ACTIVATION_API_ENABLED is True,
            "dispatch_enabled": False,
            "creation_capable": creation_capable,
            "dispatch_capable": False,
            "capable": False,
            "blocking_reasons": [] if creation_capable else ["activation_disabled"],
        },
        "approved_content_sid": configured_content_sid,
    }


def _configured_content_sid_is_valid(value: str | None) -> bool:
    return isinstance(value, str) and re.fullmatch(r"HX[0-9A-Fa-f]{32}", value) is not None


def get_requested_enabled(db: Session) -> bool:
    """Read directly so every process observes committed admin changes."""
    row = db.get(AppSetting, KEY_BILLING_WHATSAPP_DELIVERY_ENABLED)
    return bool(row and row.value.strip().lower() == "true")


def mark_worker_heartbeat(db: Session, *, now: datetime | None = None) -> datetime:
    heartbeat = now or datetime.utcnow()
    window = db.get(BillingNotificationCapacityWindow, 1)
    if window is None:
        window = BillingNotificationCapacityWindow(id=1, revision=0)
        db.add(window)
    window.worker_heartbeat_at = heartbeat
    db.flush()
    return heartbeat


def _reason(value: Any, fallback: str) -> str:
    return value if value in _REASON_CODES else fallback


def status_from_readiness(
    db: Session, provider_readiness: dict[str, Any], *, now: datetime | None = None,
    provider_configuration: dict[str, Any] | None = None,
    global_dispatch_enabled: bool | None = None,
    official_process_enabled: bool = True, dispatch_process_enabled: bool = True,
    activation_api_enabled: bool = False, activation_dispatch_enabled: bool = False,
    recipient_hmac_key: str | None = None, configured_content_sid: str | None = None,
) -> dict[str, Any]:
    """Project readiness facts without mutating the persisted delivery request."""
    now = now or datetime.utcnow()
    if global_dispatch_enabled is not None:
        official_process_enabled = global_dispatch_enabled
        dispatch_process_enabled = global_dispatch_enabled
    configuration = {"ready": True, "reason": None} if provider_configuration is None else (provider_configuration if isinstance(provider_configuration, dict) else {"ready": False, "reason": "configuration_unsafe"})
    provider = provider_readiness if isinstance(provider_readiness, dict) else {"ready": False, "reason": "provider_unavailable"}
    configuration_ready = configuration.get("ready") is True
    provider_live_ready = provider.get("ready") is True
    window = db.get(BillingNotificationCapacityWindow, 1)
    heartbeat = window.worker_heartbeat_at if window else None
    heartbeat_age = now - heartbeat if heartbeat else None
    worker_ready = bool(heartbeat_age is not None and timedelta(0) <= heartbeat_age <= WORKER_HEARTBEAT_MAX_AGE)
    process_ready = official_process_enabled is True and dispatch_process_enabled is True
    provider_ready = configuration_ready and provider_live_ready
    requested = get_requested_enabled(db)

    blocking_reasons: list[str] = []
    if not configuration_ready:
        blocking_reasons.append(_reason(configuration.get("reason"), "configuration_unsafe"))
    if not provider_live_ready:
        blocking_reasons.append(_reason(provider.get("reason"), "provider_unavailable"))
    if not worker_ready:
        blocking_reasons.append("worker_unavailable")
    if not process_ready:
        blocking_reasons.append("process_gate_disabled")

    ordinary_effective = requested and process_ready and provider_ready and worker_ready
    activation_reasons = list(blocking_reasons)
    hmac_ready = isinstance(recipient_hmac_key, str) and len(recipient_hmac_key.encode("utf-8")) >= 32
    content_sid_ready = _configured_content_sid_is_valid(configured_content_sid)
    creation_capable = not requested and activation_api_enabled is True and hmac_ready and content_sid_ready
    dispatch_capable = (
        creation_capable and activation_dispatch_enabled is True and process_ready
        and provider_ready and worker_ready
    )
    if not dispatch_capable:
        activation_reasons.append("activation_disabled")
    if requested:
        activation_reasons.append("global_delivery_enabled")
    readiness_reason = "admin_disabled" if not requested else (
        None if not blocking_reasons else blocking_reasons[0]
    )
    provider_live = {
        "ready": provider_live_ready,
        "reason": None if provider_live_ready else _reason(provider.get("reason"), "provider_unavailable"),
        "capacity": provider.get("capacity", {"available": False}),
    }
    worker = {"ready": worker_ready, "reason": None if worker_ready else "worker_unavailable", "heartbeat_at": heartbeat}
    return {
        "provider_configuration": {"ready": configuration_ready, "reason": None if configuration_ready else _reason(configuration.get("reason"), "configuration_unsafe")},
        "provider_live": provider_live,
        "worker": worker,
        "process_gates": {"official": official_process_enabled, "dispatch": dispatch_process_enabled},
        "global_delivery": {"requested": requested, "effective": ordinary_effective},
        "activation": {"api_enabled": activation_api_enabled, "dispatch_enabled": activation_dispatch_enabled, "creation_capable": creation_capable, "dispatch_capable": dispatch_capable, "capable": dispatch_capable, "blocking_reasons": activation_reasons},
        "requested_enabled": requested,
        "effective_enabled": ordinary_effective,
        "can_enable": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "readiness": {"ready": ordinary_effective, "reason": readiness_reason, "capacity": provider_live["capacity"]},
        "worker_heartbeat_at": heartbeat,
    }
