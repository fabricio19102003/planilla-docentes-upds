"""Fail-closed operational control for official WhatsApp billing delivery."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.billing_notification import BillingNotificationCapacityWindow
from app.services.app_settings_service import KEY_BILLING_WHATSAPP_DELIVERY_ENABLED


WORKER_HEARTBEAT_MAX_AGE = timedelta(seconds=60)


def _provider_readiness() -> dict[str, Any]:
    from app.config import settings
    from app.workers.official_whatsapp_runner import OfficialWhatsAppRuntime

    if not settings.OFFICIAL_WHATSAPP_ENABLED:
        return {"ready": False, "reason": "official_whatsapp_disabled", "capacity": {"available": False}}
    if not settings.WHATSAPP_DISPATCH_ENABLED:
        return {"ready": False, "reason": "whatsapp_dispatch_disabled", "capacity": {"available": False}}
    runtime = OfficialWhatsAppRuntime.from_settings(settings)
    if runtime is None:
        return {"ready": False, "reason": "official_configuration_unavailable", "capacity": {"available": False}}
    return runtime.live_readiness()


def current_delivery_status(db: Session) -> dict[str, Any]:
    return status_from_readiness(db, _provider_readiness())


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


def status_from_readiness(
    db: Session,
    provider_readiness: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.utcnow()
    window = db.get(BillingNotificationCapacityWindow, 1)
    heartbeat = window.worker_heartbeat_at if window else None
    worker_ready = bool(heartbeat and now - heartbeat <= WORKER_HEARTBEAT_MAX_AGE)
    provider_ready = provider_readiness.get("ready") is True
    blocking_reasons: list[str] = []
    if not provider_ready:
        blocking_reasons.append(str(provider_readiness.get("reason") or "official_readiness_unavailable"))
    if not worker_ready:
        blocking_reasons.append("worker_unavailable")
    requested = get_requested_enabled(db)
    can_enable = not blocking_reasons
    effective = requested and can_enable
    readiness = {
        **provider_readiness,
        "ready": effective,
        "reason": None if effective else ("admin_disabled" if can_enable else blocking_reasons[0]),
    }
    return {
        "requested_enabled": requested,
        "effective_enabled": effective,
        "can_enable": can_enable,
        "blocking_reasons": blocking_reasons,
        "readiness": readiness,
        "worker_heartbeat_at": heartbeat,
    }
