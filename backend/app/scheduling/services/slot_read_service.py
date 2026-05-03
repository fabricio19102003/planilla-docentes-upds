"""SlotReadService — public read-only interface for payroll consumption.

Payroll code should import ScheduledSlotDTO from here instead of directly
accessing scheduling models. This provides a stable contract that survives
internal scheduling refactors.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import time
from typing import Optional
from sqlalchemy.orm import Session

from app.models.designation import Designation
from app.scheduling.models.designation_slot import DesignationSlot
from app.scheduling.models.academic_period import AcademicPeriod
from app.scheduling.models.room import Room

logger = logging.getLogger(__name__)

WEEKDAY_NAMES: dict[int, str] = {
    0: "lunes", 1: "martes", 2: "miercoles",
    3: "jueves", 4: "viernes", 5: "sabado", 6: "domingo",
}


@dataclass
class ScheduledSlotDTO:
    """Flat, immutable DTO for payroll consumption."""
    designation_id: int
    teacher_ci: str
    academic_period_code: str
    subject: str
    group_code: str
    semester: str
    day_of_week: int
    day_name: str
    start_time: time
    end_time: time
    duration_minutes: int
    academic_hours: int
    room_code: Optional[str]


class SlotReadService:
    """Public read API for payroll/attendance systems to consume scheduling data."""

    def _slot_to_dto(self, slot: DesignationSlot, designation: Designation) -> ScheduledSlotDTO:
        room_code = None
        if slot.room and hasattr(slot.room, 'code'):
            room_code = slot.room.code
        return ScheduledSlotDTO(
            designation_id=designation.id,
            teacher_ci=designation.teacher_ci,
            academic_period_code=designation.academic_period or "",
            subject=designation.subject or "",
            group_code=designation.group_code or "",
            semester=designation.semester or "",
            day_of_week=slot.day_of_week,
            day_name=WEEKDAY_NAMES.get(slot.day_of_week, ""),
            start_time=slot.start_time,
            end_time=slot.end_time,
            duration_minutes=slot.duration_minutes,
            academic_hours=slot.academic_hours,
            room_code=room_code,
        )

    def get_slots_for_period(self, db: Session, period_id: int) -> list[ScheduledSlotDTO]:
        """All slots for all confirmed/active designations in this period."""
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if not period:
            return []

        results = (
            db.query(DesignationSlot, Designation)
            .join(Designation, DesignationSlot.designation_id == Designation.id)
            .filter(Designation.academic_period == period.code)
            .order_by(Designation.teacher_ci, DesignationSlot.day_of_week, DesignationSlot.start_time)
            .all()
        )
        return [self._slot_to_dto(slot, desig) for slot, desig in results]

    def get_slots_for_teacher(self, db: Session, teacher_ci: str, period_id: int) -> list[ScheduledSlotDTO]:
        """All slots for one teacher in one period."""
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if not period:
            return []

        results = (
            db.query(DesignationSlot, Designation)
            .join(Designation, DesignationSlot.designation_id == Designation.id)
            .filter(Designation.teacher_ci == teacher_ci, Designation.academic_period == period.code)
            .order_by(DesignationSlot.day_of_week, DesignationSlot.start_time)
            .all()
        )
        return [self._slot_to_dto(slot, desig) for slot, desig in results]

    def get_slots_for_teacher_on_day(
        self, db: Session, teacher_ci: str, period_id: int, day_of_week: int
    ) -> list[ScheduledSlotDTO]:
        """Slots for one teacher on a specific weekday."""
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if not period:
            return []

        results = (
            db.query(DesignationSlot, Designation)
            .join(Designation, DesignationSlot.designation_id == Designation.id)
            .filter(
                Designation.teacher_ci == teacher_ci,
                Designation.academic_period == period.code,
                DesignationSlot.day_of_week == day_of_week,
            )
            .order_by(DesignationSlot.start_time)
            .all()
        )
        return [self._slot_to_dto(slot, desig) for slot, desig in results]

    def get_slot_hours_for_designation(
        self, db: Session, designation_id: int, day_of_week: int, start_time: time
    ) -> int:
        """Get academic_hours for a specific slot. Used by planilla_generator for ABSENT hour recovery."""
        slot = (
            db.query(DesignationSlot)
            .filter(
                DesignationSlot.designation_id == designation_id,
                DesignationSlot.day_of_week == day_of_week,
                DesignationSlot.start_time == start_time,
            )
            .first()
        )
        if slot:
            return slot.academic_hours
        return 0
