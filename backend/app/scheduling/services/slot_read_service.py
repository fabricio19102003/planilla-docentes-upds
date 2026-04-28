from __future__ import annotations
from typing import List
from sqlalchemy.orm import Session
from app.scheduling.models import DesignationSlot
from app.scheduling.schemas import ScheduledSlotDTO
from app.models import Designation


class SlotReadService:
    """
    Service for reading scheduled slots for payroll consumption.

    Provides DTOs that abstract away the relational structure,
    maintaining compatibility with existing payroll logic.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_slots_for_period(self, period_id: int) -> List[ScheduledSlotDTO]:
        """
        Get all scheduled slots for a given academic period.

        This replaces the previous logic of querying Designation
        and parsing schedule_json.
        """
        # Join DesignationSlot -> Designation -> AcademicPeriod
        query = (
            self.db.query(DesignationSlot, Designation)
            .join(Designation, DesignationSlot.designation_id == Designation.id)
            .filter(Designation.academic_period_id == period_id)
            .filter(Designation.status.in_(["draft", "confirmed"]))  # Only active designations
        )

        results = []
        for slot, designation in query.all():
            results.append(ScheduledSlotDTO(
                designation_id=designation.id,
                teacher_ci=designation.teacher_ci,
                day_name=slot.dia,
                start_time=slot.hora_inicio,
                end_time=slot.hora_fin,
                academic_hours=slot.horas_academicas,
                subject=designation.subject,
                group_code=designation.group_code,
            ))

        return results

    def get_slot_hours_for_designation(
        self,
        designation_id: int,
        day_of_week: str,
        start_time_str: str
    ) -> int:
        """
        Get academic hours for a specific slot in a designation.

        Used for ABSENT hour recovery in planilla_generator.
        Matches by designation_id, normalized day name, and start time.

        Args:
            designation_id: The designation ID
            day_of_week: Normalized day name (lunes, martes, etc.)
            start_time_str: Start time as HH:MM string

        Returns:
            Academic hours for the slot, or 0 if not found
        """
        from datetime import datetime
        try:
            # Convert HH:MM string to time object for comparison
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
        except ValueError:
            return 0

        slot = (
            self.db.query(DesignationSlot)
            .filter(DesignationSlot.designation_id == designation_id)
            .filter(DesignationSlot.dia == day_of_week)
            .filter(DesignationSlot.hora_inicio == start_time)
            .first()
        )

        return slot.horas_academicas if slot else 0