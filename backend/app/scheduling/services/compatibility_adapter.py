"""Compatibility Adapter — bridges scheduling slots to legacy schedule_json.

During the transition period, the existing payroll system (planilla_generator,
attendance_engine, etc.) reads schedule_json from the Designation model. This
adapter regenerates schedule_json whenever slots change, so the legacy system
stays in sync with the new scheduling data.

When Phase 4 completes and schedule_json is removed, this adapter is deleted.
"""
from __future__ import annotations
import logging
from sqlalchemy.orm import Session

from app.models.designation import Designation
from app.scheduling.models.designation_slot import DesignationSlot

logger = logging.getLogger(__name__)

WEEKDAY_NAMES: dict[int, str] = {
    0: "lunes", 1: "martes", 2: "miercoles",
    3: "jueves", 4: "viernes", 5: "sabado", 6: "domingo",
}


class CompatibilityAdapter:
    """Generates legacy schedule_json from DesignationSlot records."""

    def slots_to_schedule_json(self, slots: list[DesignationSlot]) -> list[dict]:
        """Convert relational slots to the legacy JSON format that planilla_generator expects.

        Output format (same as designation_loader._parse_horario_string produces):
        [
            {
                "dia": "lunes",
                "hora_inicio": "08:00",
                "hora_fin": "09:30",
                "duracion_minutos": 90,
                "horas_academicas": 2
            },
            ...
        ]

        Slots are ordered by day_of_week then start_time for consistency.
        """
        result = []
        sorted_slots = sorted(slots, key=lambda s: (s.day_of_week, s.start_time))
        for slot in sorted_slots:
            result.append({
                "dia": WEEKDAY_NAMES.get(slot.day_of_week, ""),
                "hora_inicio": slot.start_time.strftime("%H:%M"),
                "hora_fin": slot.end_time.strftime("%H:%M"),
                "duracion_minutos": slot.duration_minutes,
                "horas_academicas": slot.academic_hours,
            })
        return result

    def sync_designation_json(self, db: Session, designation_id: int) -> None:
        """Regenerate and persist schedule_json on the Designation record.

        Also recomputes weekly_hours_calculated and monthly_hours from slots.
        Called automatically after slot add/remove/update.
        """
        designation = db.query(Designation).filter(Designation.id == designation_id).first()
        if not designation:
            logger.error(
                "sync_designation_json: designation %d not found — cannot sync schedule_json. "
                "This likely indicates a data integrity issue (slot references deleted designation).",
                designation_id,
            )
            raise ValueError(f"Designation {designation_id} not found — cannot sync schedule_json")

        slots = (
            db.query(DesignationSlot)
            .filter(DesignationSlot.designation_id == designation_id)
            .order_by(DesignationSlot.day_of_week, DesignationSlot.start_time)
            .all()
        )

        # Regenerate schedule_json
        designation.schedule_json = self.slots_to_schedule_json(slots)

        # Recompute hours
        total_academic_hours = sum(s.academic_hours for s in slots)
        designation.weekly_hours_calculated = total_academic_hours
        designation.monthly_hours = total_academic_hours * 4  # Legacy formula

        db.flush()
        logger.info(
            "Synced designation %d: %d slots -> schedule_json updated, "
            "weekly_hours=%d, monthly_hours=%d",
            designation_id, len(slots), total_academic_hours, total_academic_hours * 4,
        )
