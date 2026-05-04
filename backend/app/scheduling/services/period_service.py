"""Service layer for AcademicPeriod CRUD operations."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.scheduling.models.academic_period import AcademicPeriod

logger = logging.getLogger(__name__)


class PeriodService:
    """AcademicPeriod CRUD operations."""

    def create_period(
        self,
        db: Session,
        *,
        code: str,
        name: str,
        year: int,
        semester_number: int,
        start_date: date,
        end_date: date,
    ) -> AcademicPeriod:
        """Create a new academic period.

        Business rules:
        - BR-AP-5: start_date must be before end_date
        - BR-AP-6: code must match I/YYYY or II/YYYY format
        - Unique code constraint
        """
        # BR-AP-6: validate code format
        if not re.match(r"^(I|II)/\d{4}$", code):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Code must match format I/YYYY or II/YYYY",
            )

        # BR-AP-5: validate date range
        if end_date <= start_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_date must be after start_date",
            )

        # Unique code
        existing = db.query(AcademicPeriod).filter(AcademicPeriod.code == code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Academic period with code '{code}' already exists",
            )

        period = AcademicPeriod(
            code=code,
            name=name.strip(),
            year=year,
            semester_number=semester_number,
            start_date=start_date,
            end_date=end_date,
            status="planning",
            is_active=False,
        )
        db.add(period)
        db.flush()
        logger.info("Created academic period: %s", period.code)
        return period

    def activate_period(self, db: Session, period_id: int) -> AcademicPeriod:
        """Activate a period, deactivating any currently active one.

        Business rules:
        - BR-AP-1: Only one period can be active at a time
        - Sets status to 'active' if it was 'planning'
        """
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Academic period not found")

        if period.status == "closed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot activate a closed period",
            )

        # Deactivate current active period — use FOR UPDATE to prevent race condition
        # where two concurrent activate calls could both succeed (BR-AP-1)
        current_active = (
            db.query(AcademicPeriod)
            .filter(AcademicPeriod.is_active.is_(True), AcademicPeriod.id != period_id)
            .with_for_update()
            .first()
        )
        if current_active:
            current_active.is_active = False
            logger.info("Deactivated period: %s", current_active.code)

        period.is_active = True
        if period.status == "planning":
            period.status = "active"

        db.flush()
        logger.info("Activated period: %s", period.code)
        return period

    def get_active_period(self, db: Session) -> AcademicPeriod | None:
        """Return the single active period, or None."""
        return db.query(AcademicPeriod).filter(AcademicPeriod.is_active.is_(True)).first()

    def list_periods(
        self,
        db: Session,
        *,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all periods, ordered by year DESC, semester_number DESC."""
        query = db.query(AcademicPeriod)
        if status_filter:
            query = query.filter(AcademicPeriod.status == status_filter)
        query = query.order_by(AcademicPeriod.year.desc(), AcademicPeriod.semester_number.desc())
        periods = query.all()

        results = []
        for p in periods:
            group_count = len(p.groups) if p.groups else 0
            results.append({
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "year": p.year,
                "semester_number": p.semester_number,
                "start_date": p.start_date,
                "end_date": p.end_date,
                "is_active": p.is_active,
                "status": p.status,
                "group_count": group_count,
            })
        return results

    def get_period(self, db: Session, period_id: int) -> dict[str, Any]:
        """Get a single period by ID."""
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Academic period not found")

        group_count = len(period.groups) if period.groups else 0
        return {
            "id": period.id,
            "code": period.code,
            "name": period.name,
            "year": period.year,
            "semester_number": period.semester_number,
            "start_date": period.start_date,
            "end_date": period.end_date,
            "is_active": period.is_active,
            "status": period.status,
            "group_count": group_count,
        }

    def update_period(self, db: Session, period_id: int, **fields: Any) -> AcademicPeriod:
        """Update a period. Cannot update if status is 'closed' (BR-AP-3)."""
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Academic period not found")

        if period.status == "closed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot update a closed period",
            )

        # Validate date consistency if both dates are being set
        new_start = fields.get("start_date", period.start_date)
        new_end = fields.get("end_date", period.end_date)
        if new_start and new_end and new_end <= new_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_date must be after start_date",
            )

        for key, value in fields.items():
            if value is not None:
                setattr(period, key, value)
        db.flush()
        return period

    def close_period(self, db: Session, period_id: int) -> AcademicPeriod:
        """Close a period. BR-AP-4: validates no draft designations exist."""
        from app.models.designation import Designation
        from sqlalchemy import or_

        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Academic period not found")

        if period.status == "closed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Period is already closed",
            )

        draft_count = (
            db.query(Designation)
            .filter(
                or_(Designation.academic_period_id == period_id, Designation.academic_period == period.code),
                Designation.status == "draft",
            )
            .count()
        )
        if draft_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot close period '{period.code}': {draft_count} draft designation(s) remain",
            )

        period.status = "closed"
        period.is_active = False
        db.flush()
        logger.info("Closed period: %s", period.code)
        return period
