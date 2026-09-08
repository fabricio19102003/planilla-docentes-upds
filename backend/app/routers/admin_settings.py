"""
Router: Admin — App Settings

Exposes GET/PUT endpoints for the four business-configurable values that used
to live in ``.env``:

    - ACTIVE_ACADEMIC_PERIOD
    - COMPANY_NAME
    - COMPANY_NIT
    - HOURLY_RATE

Only ``admin`` users can read or modify these values.  Every update is
recorded in the activity log for auditability.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import app_settings_service
from app.services.activity_logger import log_activity
from app.services.whatsapp_delivery_control import current_delivery_status
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-settings"])


class SettingsResponse(BaseModel):
    active_academic_period: str
    company_name: str
    company_nit: str
    hourly_rate: float
    practice_hourly_rate: float
    docente_can_edit_profile: bool
    docente_can_edit_photo: bool
    medicine_schedule_assistant_enabled: bool
    whatsapp_billing_delivery: "WhatsAppBillingDeliveryStatus"

    model_config = ConfigDict(from_attributes=True)


class SettingsUpdateRequest(BaseModel):
    active_academic_period: Optional[str] = Field(default=None, min_length=1, max_length=50)
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    company_nit: Optional[str] = Field(default=None, min_length=1, max_length=50)
    hourly_rate: Optional[float] = Field(default=None, gt=0, le=10000)
    practice_hourly_rate: Optional[float] = Field(default=None, gt=0, le=10000)
    docente_can_edit_profile: Optional[bool] = None
    docente_can_edit_photo: Optional[bool] = None
    medicine_schedule_assistant_enabled: Optional[bool] = None
    whatsapp_billing_requested_enabled: Optional[bool] = None


class WhatsAppBillingDeliveryStatus(BaseModel):
    requested_enabled: bool
    effective_enabled: bool
    can_enable: bool
    blocking_reasons: list[str]
    readiness: dict[str, object]
    worker_heartbeat_at: Optional[datetime] = None


def _current_settings(db: Session) -> SettingsResponse:
    return SettingsResponse(
        active_academic_period=app_settings_service.get_active_academic_period(db),
        company_name=app_settings_service.get_company_name(db),
        company_nit=app_settings_service.get_company_nit(db),
        hourly_rate=app_settings_service.get_hourly_rate(db),
        practice_hourly_rate=app_settings_service.get_practice_hourly_rate(db),
        docente_can_edit_profile=app_settings_service.get_docente_can_edit_profile(db),
        docente_can_edit_photo=app_settings_service.get_docente_can_edit_photo(db),
        medicine_schedule_assistant_enabled=app_settings_service.get_medicine_schedule_assistant_enabled(db),
        whatsapp_billing_delivery=current_delivery_status(db),
    )


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """Return current values of all business settings."""
    return _current_settings(db)


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdateRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """Update any subset of the business settings.  Only non-null fields are applied."""
    try:
        changes: dict[str, object] = {}
        whatsapp_before = current_delivery_status(db)

        if payload.whatsapp_billing_requested_enabled is True and not whatsapp_before["can_enable"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "whatsapp_delivery_unavailable",
                    "blocking_reasons": whatsapp_before["blocking_reasons"],
                },
            )

        if payload.active_academic_period is not None:
            app_settings_service.update_setting(
                db,
                app_settings_service.KEY_ACTIVE_ACADEMIC_PERIOD,
                payload.active_academic_period.strip(),
            )
            changes["active_academic_period"] = payload.active_academic_period.strip()

        if payload.company_name is not None:
            app_settings_service.update_setting(
                db,
                app_settings_service.KEY_COMPANY_NAME,
                payload.company_name.strip(),
            )
            changes["company_name"] = payload.company_name.strip()

        if payload.company_nit is not None:
            app_settings_service.update_setting(
                db,
                app_settings_service.KEY_COMPANY_NIT,
                payload.company_nit.strip(),
            )
            changes["company_nit"] = payload.company_nit.strip()

        if payload.hourly_rate is not None:
            app_settings_service.update_setting(
                db,
                app_settings_service.KEY_HOURLY_RATE,
                str(payload.hourly_rate),
            )
            changes["hourly_rate"] = payload.hourly_rate

        if payload.practice_hourly_rate is not None:
            app_settings_service.update_setting(
                db,
                app_settings_service.KEY_PRACTICE_HOURLY_RATE,
                str(payload.practice_hourly_rate),
            )
            changes["practice_hourly_rate"] = payload.practice_hourly_rate

        if payload.docente_can_edit_profile is not None:
            app_settings_service.set_docente_can_edit_profile(db, payload.docente_can_edit_profile)
            changes["docente_can_edit_profile"] = payload.docente_can_edit_profile

        if payload.docente_can_edit_photo is not None:
            app_settings_service.set_docente_can_edit_photo(db, payload.docente_can_edit_photo)
            changes["docente_can_edit_photo"] = payload.docente_can_edit_photo

        if payload.medicine_schedule_assistant_enabled is not None:
            app_settings_service.set_medicine_schedule_assistant_enabled(
                db, payload.medicine_schedule_assistant_enabled
            )
            changes["medicine_schedule_assistant_enabled"] = payload.medicine_schedule_assistant_enabled

        if payload.whatsapp_billing_requested_enabled is not None:
            app_settings_service.set_billing_whatsapp_delivery_enabled(
                db, payload.whatsapp_billing_requested_enabled
            )
            changes["whatsapp_billing_requested_enabled"] = {
                "old": whatsapp_before["requested_enabled"],
                "new": payload.whatsapp_billing_requested_enabled,
                "effective": payload.whatsapp_billing_requested_enabled and whatsapp_before["can_enable"],
                "blocking_reasons": whatsapp_before["blocking_reasons"],
            }

        if changes:
            log_activity(
                db,
                action="update_settings",
                category="settings",
                description=f"Configuración actualizada: {', '.join(changes.keys())}",
                user=current_user,
                details=changes,
                request=request,
            )

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to update settings: %s", exc)
        raise

    return _current_settings(db)
