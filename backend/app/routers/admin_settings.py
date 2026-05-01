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
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import app_settings_service
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-settings"])


class SettingsResponse(BaseModel):
    active_academic_period: str
    company_name: str
    company_nit: str
    hourly_rate: float
    practice_hourly_rate: float

    model_config = ConfigDict(from_attributes=True)


class SettingsUpdateRequest(BaseModel):
    active_academic_period: Optional[str] = Field(default=None, min_length=1, max_length=50)
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    company_nit: Optional[str] = Field(default=None, min_length=1, max_length=50)
    hourly_rate: Optional[float] = Field(default=None, gt=0, le=10000)
    practice_hourly_rate: Optional[float] = Field(default=None, gt=0, le=10000)


def _current_settings(db: Session) -> SettingsResponse:
    return SettingsResponse(
        active_academic_period=app_settings_service.get_active_academic_period(db),
        company_name=app_settings_service.get_company_name(db),
        company_nit=app_settings_service.get_company_nit(db),
        hourly_rate=app_settings_service.get_hourly_rate(db),
        practice_hourly_rate=app_settings_service.get_practice_hourly_rate(db),
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
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to update settings: %s", exc)
        raise

    # Invalidate cache AFTER commit succeeds — outside try/except so a failure
    # here doesn't trigger a pointless rollback on an already-committed tx.
    app_settings_service.invalidate_cache()
    return _current_settings(db)
