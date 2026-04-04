from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/activity", tags=["activity-log"])


# ------------------------------------------------------------------
# Response schemas
# ------------------------------------------------------------------


class ActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    user_ci: Optional[str]
    user_name: Optional[str]
    user_role: Optional[str]
    action: str
    category: str
    description: str
    details: Optional[dict] = None
    status: str
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedActivityLogResponse(BaseModel):
    items: list[ActivityLogResponse]
    total: int
    page: int
    per_page: int


class ActiveUserStat(BaseModel):
    user_name: str
    user_ci: str
    count: int


class CategoryStat(BaseModel):
    category: str
    count: int


class ActivityStatsResponse(BaseModel):
    total_logs: int
    logs_today: int
    most_active_users: list[ActiveUserStat]
    actions_by_category: list[CategoryStat]
    recent_logins: list[ActivityLogResponse]


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("/logs", response_model=PaginatedActivityLogResponse)
def list_activity_logs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    user_ci: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedActivityLogResponse:
    """List activity logs with optional filters (admin only)."""
    try:
        query = db.query(ActivityLog)

        if user_ci:
            query = query.filter(ActivityLog.user_ci.ilike(f"%{user_ci}%"))
        if category:
            query = query.filter(ActivityLog.category == category)
        if action:
            query = query.filter(ActivityLog.action == action)
        if start_date:
            query = query.filter(ActivityLog.created_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query = query.filter(ActivityLog.created_at <= datetime.combine(end_date, datetime.max.time()))

        total = query.count()
        items = (
            query.order_by(ActivityLog.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return PaginatedActivityLogResponse(
            items=[ActivityLogResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            per_page=per_page,
        )
    except Exception as exc:
        logger.exception("Failed to list activity logs: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo obtener el registro de actividad") from exc


@router.get("/stats", response_model=ActivityStatsResponse)
def activity_stats(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ActivityStatsResponse:
    """Activity statistics summary (admin only)."""
    try:
        total_logs = db.query(func.count(ActivityLog.id)).scalar() or 0

        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        logs_today = (
            db.query(func.count(ActivityLog.id))
            .filter(ActivityLog.created_at >= today_start, ActivityLog.created_at <= today_end)
            .scalar()
            or 0
        )

        # Top 5 most active users
        active_users_rows = (
            db.query(
                ActivityLog.user_name,
                ActivityLog.user_ci,
                func.count(ActivityLog.id).label("count"),
            )
            .filter(ActivityLog.user_ci.isnot(None))
            .group_by(ActivityLog.user_name, ActivityLog.user_ci)
            .order_by(func.count(ActivityLog.id).desc())
            .limit(5)
            .all()
        )
        most_active_users = [
            ActiveUserStat(
                user_name=str(row[0] or ""),
                user_ci=str(row[1] or ""),
                count=row[2],  # type: ignore[arg-type]
            )
            for row in active_users_rows
        ]

        # Actions by category
        category_rows = (
            db.query(
                ActivityLog.category,
                func.count(ActivityLog.id).label("cnt"),
            )
            .group_by(ActivityLog.category)
            .order_by(func.count(ActivityLog.id).desc())
            .all()
        )
        actions_by_category = [
            CategoryStat(category=str(row[0]), count=row[1])  # type: ignore[arg-type]
            for row in category_rows
        ]

        # Last 10 logins
        recent_login_rows = (
            db.query(ActivityLog)
            .filter(ActivityLog.action == "login")
            .order_by(ActivityLog.created_at.desc())
            .limit(10)
            .all()
        )
        recent_logins = [ActivityLogResponse.model_validate(row) for row in recent_login_rows]

        return ActivityStatsResponse(
            total_logs=total_logs,
            logs_today=logs_today,
            most_active_users=most_active_users,
            actions_by_category=actions_by_category,
            recent_logins=recent_logins,
        )
    except Exception as exc:
        logger.exception("Failed to get activity stats: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo obtener las estadísticas de actividad") from exc
