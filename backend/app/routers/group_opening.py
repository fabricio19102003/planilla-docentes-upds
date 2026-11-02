"""Staff API for group opening suggestions and the default group size."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import app_settings_service, group_opening, reenrollment
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/admin/group-opening", tags=["group-opening"])

CATEGORY = "group_opening"


class GroupSizePayload(BaseModel):
    group_size: StrictInt = Field(..., ge=1, le=200)


@router.get("")
def get_group_opening(window_id: Optional[int] = None, db: Session = Depends(get_db),
                      _admin: User = Depends(require_admin)):
    window = reenrollment.get_window(db, window_id) if window_id is not None else reenrollment.current_window(db)
    return group_opening.compute(db, window) if window else group_opening.empty(db)


@router.put("/settings")
def update_group_size(payload: GroupSizePayload, request: Request, db: Session = Depends(get_db),
                      admin: User = Depends(require_admin)):
    before = app_settings_service.get_default_group_size(db)
    app_settings_service.update_setting(db, app_settings_service.KEY_DEFAULT_GROUP_SIZE, str(payload.group_size))
    log_activity(db, action="update_group_opening_size", category=CATEGORY,
                 description=f"Cambió el tamaño de grupo por defecto de {before} a {payload.group_size}",
                 user=admin, details={"before": before, "after": payload.group_size}, request=request)
    db.commit()
    return {"group_size": payload.group_size}
