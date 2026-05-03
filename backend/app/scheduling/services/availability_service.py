"""AvailabilityService — manage teacher availability declarations per period."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.scheduling.models.availability_slot import AvailabilitySlot
from app.scheduling.models.teacher_availability import TeacherAvailability
from app.scheduling.schemas.availability import DAY_NAMES

logger = logging.getLogger(__name__)


class AvailabilityService:
    """CRUD for teacher availability per academic period."""

    def set_availability(
        self,
        db: Session,
        *,
        teacher_ci: str,
        period_id: int,
        slots: list[dict[str, Any]],
    ) -> TeacherAvailability:
        """Create or replace a teacher's full availability for a period.

        ``slots`` is a list of dicts with keys: day_of_week, start_time, end_time.
        """
        # Validate times
        for s in slots:
            if s["start_time"] >= s["end_time"]:
                raise HTTPException(
                    status_code=422,
                    detail=f"start_time ({s['start_time']}) debe ser menor que end_time ({s['end_time']})",
                )

        # Upsert: find existing or create
        existing = (
            db.query(TeacherAvailability)
            .filter(
                TeacherAvailability.teacher_ci == teacher_ci,
                TeacherAvailability.academic_period_id == period_id,
            )
            .first()
        )

        if existing:
            # Delete old slots, replace with new
            db.query(AvailabilitySlot).filter(
                AvailabilitySlot.availability_id == existing.id
            ).delete()
            availability = existing
        else:
            availability = TeacherAvailability(
                teacher_ci=teacher_ci,
                academic_period_id=period_id,
            )
            db.add(availability)
            db.flush()  # get id

        # Create new slots
        for s in slots:
            slot = AvailabilitySlot(
                availability_id=availability.id,
                day_of_week=s["day_of_week"],
                start_time=s["start_time"],
                end_time=s["end_time"],
            )
            db.add(slot)

        db.flush()
        logger.info(
            "Set availability for teacher %s period %d: %d slots",
            teacher_ci,
            period_id,
            len(slots),
        )
        return availability

    def get_availability(
        self, db: Session, *, teacher_ci: str, period_id: int
    ) -> dict[str, Any] | None:
        """Return teacher availability with slots for a period, or None."""
        avail = (
            db.query(TeacherAvailability)
            .options(joinedload(TeacherAvailability.slots))
            .filter(
                TeacherAvailability.teacher_ci == teacher_ci,
                TeacherAvailability.academic_period_id == period_id,
            )
            .first()
        )
        if not avail:
            return None
        return self._to_dict(avail)

    def clear_availability(self, db: Session, *, teacher_ci: str, period_id: int) -> dict[str, str]:
        """Delete a teacher's availability for a period."""
        avail = (
            db.query(TeacherAvailability)
            .filter(
                TeacherAvailability.teacher_ci == teacher_ci,
                TeacherAvailability.academic_period_id == period_id,
            )
            .first()
        )
        if not avail:
            raise HTTPException(status_code=404, detail="Disponibilidad no encontrada")
        db.delete(avail)  # cascade deletes slots
        db.flush()
        logger.info("Cleared availability for teacher %s period %d", teacher_ci, period_id)
        return {"detail": f"Disponibilidad eliminada para docente {teacher_ci}"}

    def list_by_period(self, db: Session, *, period_id: int) -> list[dict[str, Any]]:
        """All teacher availabilities for a given period."""
        results = (
            db.query(TeacherAvailability)
            .options(joinedload(TeacherAvailability.slots))
            .filter(TeacherAvailability.academic_period_id == period_id)
            .order_by(TeacherAvailability.teacher_ci)
            .all()
        )
        # Deduplicate due to joinedload
        seen: set[int] = set()
        out: list[dict[str, Any]] = []
        for a in results:
            if a.id in seen:
                continue
            seen.add(a.id)
            out.append(self._to_dict(a))
        return out

    # ─── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _to_dict(avail: TeacherAvailability) -> dict[str, Any]:
        teacher_name = ""
        if avail.teacher:
            first = getattr(avail.teacher, "first_name", "") or ""
            last = getattr(avail.teacher, "last_name", "") or ""
            teacher_name = f"{first} {last}".strip()

        return {
            "id": avail.id,
            "teacher_ci": avail.teacher_ci,
            "teacher_name": teacher_name,
            "academic_period_id": avail.academic_period_id,
            "slots": [
                {
                    "id": s.id,
                    "day_of_week": s.day_of_week,
                    "day_name": DAY_NAMES[s.day_of_week] if 0 <= s.day_of_week <= 6 else "",
                    "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                }
                for s in sorted(avail.slots, key=lambda x: (x.day_of_week, x.start_time))
            ],
        }
