from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session
from fastapi import Request

from app.models.activity_log import ActivityLog
from app.models.user import User

logger = logging.getLogger(__name__)


def log_activity(
    db: Session,
    action: str,
    category: str,
    description: str,
    user: User | None = None,
    details: dict[str, Any] | None = None,
    status: str = "success",
    request: Request | None = None,
) -> ActivityLog:
    """Log an activity to the database."""
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None

    entry = ActivityLog(
        user_id=user.id if user else None,
        user_ci=user.ci if user else None,
        user_name=user.full_name if user else None,
        user_role=user.role if user else None,
        action=action,
        category=category,
        description=description,
        details=details,
        status=status,
        ip_address=ip_address,
    )
    db.add(entry)
    # Don't flush — let the caller's transaction handle it
    # If we're in a request that commits, the log entry goes with it
    try:
        db.flush()
    except Exception:
        logger.warning("Could not flush activity log entry: %s", action)

    return entry
