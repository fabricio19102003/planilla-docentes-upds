"""Service layer for Shift operations."""

from __future__ import annotations

import logging
from datetime import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.scheduling.models.shift import Shift

logger = logging.getLogger(__name__)

# Default shifts for UPDS
_DEFAULT_SHIFTS = [
    {"code": "M", "name": "Mañana", "start_time": time(6, 30), "end_time": time(12, 30), "display_order": 1},
    {"code": "T", "name": "Tarde", "start_time": time(12, 30), "end_time": time(18, 30), "display_order": 2},
    {"code": "N", "name": "Noche", "start_time": time(18, 30), "end_time": time(22, 0), "display_order": 3},
]


class ShiftService:
    """Shift operations — mostly read-only since shifts are pre-seeded."""

    def list_all(self, db: Session) -> list[dict[str, Any]]:
        """List all shifts ordered by display_order."""
        shifts = db.query(Shift).order_by(Shift.display_order).all()
        return [
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "start_time": s.start_time.strftime("%H:%M"),
                "end_time": s.end_time.strftime("%H:%M"),
                "display_order": s.display_order,
            }
            for s in shifts
        ]

    def get(self, db: Session, shift_id: int) -> Shift:
        """Get a single shift by ID."""
        shift = db.query(Shift).filter(Shift.id == shift_id).first()
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")
        return shift

    def update(self, db: Session, shift_id: int, **fields: Any) -> Shift:
        """Update shift fields (name, times, order)."""
        shift = self.get(db, shift_id)
        for key, value in fields.items():
            if value is not None:
                setattr(shift, key, value)
        db.flush()
        return shift

    def seed_defaults(self, db: Session) -> None:
        """Seed default shifts (M, T, N) if they don't exist. Idempotent."""
        existing_codes = {row[0] for row in db.query(Shift.code).all()}
        added = 0
        for shift_data in _DEFAULT_SHIFTS:
            if shift_data["code"] not in existing_codes:
                db.add(Shift(**shift_data))
                added += 1
        if added:
            db.commit()
            logger.info("Seeded %d default shifts", added)
