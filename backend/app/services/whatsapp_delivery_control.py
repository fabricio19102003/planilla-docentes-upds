"""Fail-closed operational control for official WhatsApp billing delivery."""
from __future__ import annotations

from datetime import datetime, timedelta
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
    )


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
    recipient_hmac_key: str | None = None,
) -> dict[str, Any]:
    """Project readiness facts without mutating the persisted delivery request."""
    now = now or datetime.utcnow()
    if global_dispatch_enabled is not None:
        official_process_enabled = global_dispatch_enabled
        dispatch_process_enabled = global_dispatch_enabled
    configuration = provider_configuration or {"ready": True, "reason": None}
    configuration_ready = configuration.get("ready") is True
    provider_live_ready = provider_readiness.get("ready") is True
    window = db.get(BillingNotificationCapacityWindow, 1)
    heartbeat = window.worker_heartbeat_at if window else None
    heartbeat_age = now - heartbeat if heartbeat else None
    worker_ready = bool(heartbeat_age is not None and timedelta(0) <= heartbeat_age <= WORKER_HEARTBEAT_MAX_AGE)
    process_ready = official_process_enabled and dispatch_process_enabled
    provider_ready = configuration_ready and provider_live_ready
    requested = get_requested_enabled(db)

    blocking_reasons: list[str] = []
    if not configuration_ready:
        blocking_reasons.append(_reason(configuration.get("reason"), "configuration_unsafe"))
    if not provider_live_ready:
        blocking_reasons.append(_reason(provider_readiness.get("reason"), "provider_unavailable"))
    if not worker_ready:
        blocking_reasons.append("worker_unavailable")
    if not process_ready:
        blocking_reasons.append("process_gate_disabled")

    ordinary_effective = requested and process_ready and provider_ready and worker_ready
    activation_reasons = list(blocking_reasons)
    activation_gates_ready = activation_api_enabled and activation_dispatch_enabled
    hmac_ready = bool(recipient_hmac_key and len(recipient_hmac_key.encode("utf-8")) >= 32)
    if not activation_gates_ready or not hmac_ready:
        activation_reasons.append("activation_disabled")
    if requested:
        activation_reasons.append("global_delivery_enabled")
    activation_capable = (
        not requested and activation_gates_ready and process_ready and hmac_ready
        and provider_ready and worker_ready
    )
    readiness_reason = "admin_disabled" if not requested else (
        None if not blocking_reasons else blocking_reasons[0]
    )
    provider_live = {
        "ready": provider_live_ready,
        "reason": None if provider_live_ready else _reason(provider_readiness.get("reason"), "provider_unavailable"),
        "capacity": provider_readiness.get("capacity", {"available": False}),
    }
    worker = {"ready": worker_ready, "reason": None if worker_ready else "worker_unavailable", "heartbeat_at": heartbeat}
    return {
        "provider_configuration": {"ready": configuration_ready, "reason": None if configuration_ready else _reason(configuration.get("reason"), "configuration_unsafe")},
        "provider_live": provider_live,
        "worker": worker,
        "process_gates": {"official": official_process_enabled, "dispatch": dispatch_process_enabled},
        "global_delivery": {"requested": requested, "effective": ordinary_effective},
        "activation": {"api_enabled": activation_api_enabled, "dispatch_enabled": activation_dispatch_enabled, "capable": activation_capable, "blocking_reasons": activation_reasons},
        "requested_enabled": requested,
        "effective_enabled": ordinary_effective,
        "can_enable": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "readiness": {"ready": ordinary_effective, "reason": readiness_reason, "capacity": provider_live["capacity"]},
        "worker_heartbeat_at": heartbeat,
    }
