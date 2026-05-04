"""ConflictService — detects scheduling conflicts (overlap formula: a.start < b.end AND b.start < a.end)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import time

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.designation import Designation
from app.scheduling.models.academic_period import AcademicPeriod
from app.scheduling.models.availability_slot import AvailabilitySlot
from app.scheduling.models.designation_slot import DesignationSlot
from app.scheduling.models.group import Group
from app.scheduling.models.room import Room
from app.scheduling.models.teacher_availability import TeacherAvailability

logger = logging.getLogger(__name__)


@dataclass
class Conflict:
    type: str  # TEACHER_OVERLAP, ROOM_DOUBLE_BOOKING, GROUP_OVERLAP, ROOM_INACTIVE, OUTSIDE_AVAILABILITY
    severity: str  # HARD or SOFT
    message: str
    conflicting_slot_id: int | None = None
    details: dict = field(default_factory=dict)


class ConflictService:
    """Run all conflict checks for a proposed designation slot."""

    # ─── Public API ───────────────────────────────────────────────────

    def validate_slot(
        self,
        db: Session,
        *,
        period_id: int,
        designation_id: int,
        teacher_ci: str,
        group_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
        room_id: int | None = None,
        exclude_slot_id: int | None = None,
    ) -> list[Conflict]:
        """Run ALL conflict checks. Return list of conflicts (empty = OK)."""
        conflicts: list[Conflict] = []

        conflicts.extend(
            self.check_teacher_overlap(
                db,
                teacher_ci=teacher_ci,
                period_id=period_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                exclude_slot_id=exclude_slot_id,
            )
        )

        if room_id:
            conflicts.extend(
                self.check_room_overlap(
                    db,
                    room_id=room_id,
                    period_id=period_id,
                    day_of_week=day_of_week,
                    start_time=start_time,
                    end_time=end_time,
                    exclude_slot_id=exclude_slot_id,
                )
            )
            conflicts.extend(self.check_room_active(db, room_id=room_id))

        conflicts.extend(
            self.check_group_overlap(
                db,
                group_id=group_id,
                period_id=period_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                exclude_slot_id=exclude_slot_id,
            )
        )

        conflicts.extend(
            self.check_teacher_availability(
                db,
                teacher_ci=teacher_ci,
                period_id=period_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
            )
        )

        return conflicts

    # ─── Individual checks ────────────────────────────────────────────

    def check_teacher_overlap(
        self,
        db: Session,
        *,
        teacher_ci: str,
        period_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> list[Conflict]:
        """Same teacher, same period, same day, overlapping times. HARD conflict."""
        period_code = self._get_period_code(db, period_id)
        if not period_code:
            return []

        query = (
            db.query(DesignationSlot)
            .join(Designation, DesignationSlot.designation_id == Designation.id)
            .filter(
                Designation.teacher_ci == teacher_ci,
                or_(Designation.academic_period_id == period_id, Designation.academic_period == period_code),
                Designation.status != "cancelled",
                DesignationSlot.day_of_week == day_of_week,
                DesignationSlot.start_time < end_time,
                start_time < DesignationSlot.end_time,
            )
        )
        if exclude_slot_id:
            query = query.filter(DesignationSlot.id != exclude_slot_id)

        conflicts: list[Conflict] = []
        for slot in query.all():
            conflicts.append(
                Conflict(
                    type="TEACHER_OVERLAP",
                    severity="HARD",
                    message=(
                        f"Docente {teacher_ci} ya tiene clase "
                        f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')} "
                        f"el mismo día"
                    ),
                    conflicting_slot_id=slot.id,
                    details={
                        "teacher_ci": teacher_ci,
                        "existing_designation_id": slot.designation_id,
                        "existing_start": str(slot.start_time),
                        "existing_end": str(slot.end_time),
                    },
                )
            )
        return conflicts

    def check_room_overlap(
        self,
        db: Session,
        *,
        room_id: int,
        period_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> list[Conflict]:
        """Same room, same period, same day, overlapping times. HARD conflict."""
        period_code = self._get_period_code(db, period_id)
        if not period_code:
            return []

        query = (
            db.query(DesignationSlot)
            .join(Designation, DesignationSlot.designation_id == Designation.id)
            .filter(
                DesignationSlot.room_id == room_id,
                or_(Designation.academic_period_id == period_id, Designation.academic_period == period_code),
                Designation.status != "cancelled",
                DesignationSlot.day_of_week == day_of_week,
                DesignationSlot.start_time < end_time,
                start_time < DesignationSlot.end_time,
            )
        )
        if exclude_slot_id:
            query = query.filter(DesignationSlot.id != exclude_slot_id)

        conflicts: list[Conflict] = []
        for slot in query.all():
            room = db.query(Room).filter(Room.id == room_id).first()
            room_label = room.code if room else str(room_id)
            conflicts.append(
                Conflict(
                    type="ROOM_DOUBLE_BOOKING",
                    severity="HARD",
                    message=(
                        f"Aula {room_label} ya está ocupada "
                        f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')} "
                        f"el mismo día"
                    ),
                    conflicting_slot_id=slot.id,
                    details={
                        "room_id": room_id,
                        "existing_designation_id": slot.designation_id,
                        "existing_start": str(slot.start_time),
                        "existing_end": str(slot.end_time),
                    },
                )
            )
        return conflicts

    def check_room_active(self, db: Session, *, room_id: int) -> list[Conflict]:
        """Room must be active. HARD conflict if inactive."""
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            return [
                Conflict(
                    type="ROOM_INACTIVE",
                    severity="HARD",
                    message=f"Aula con id {room_id} no existe",
                    details={"room_id": room_id},
                )
            ]
        if not room.is_active:
            return [
                Conflict(
                    type="ROOM_INACTIVE",
                    severity="HARD",
                    message=f"Aula {room.code} está inactiva",
                    details={"room_id": room_id, "room_code": room.code},
                )
            ]
        return []

    def check_group_overlap(
        self,
        db: Session,
        *,
        group_id: int,
        period_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
        exclude_slot_id: int | None = None,
    ) -> list[Conflict]:
        """Same group, same period, same day, overlapping times. HARD conflict."""
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            # group_id=0 or group not found in scheduling module — can't validate
            logger.debug(
                "check_group_overlap: group_id=%d not found, skipping group overlap check",
                group_id,
            )
            return []
        period_code = self._get_period_code(db, period_id)
        if not period_code:
            return []

        query = (
            db.query(DesignationSlot)
            .join(Designation, DesignationSlot.designation_id == Designation.id)
            .filter(
                or_(
                    Designation.group_id == group_id,
                    (
                        (Designation.group_id.is_(None))
                        & (Designation.group_code == group.code)
                        & (Designation.semester == group.semester.name)
                        & (Designation.academic_period == period_code)
                    ),
                ),
                or_(Designation.academic_period_id == period_id, Designation.academic_period == period_code),
                Designation.status != "cancelled",
                DesignationSlot.day_of_week == day_of_week,
                DesignationSlot.start_time < end_time,
                start_time < DesignationSlot.end_time,
            )
        )
        if exclude_slot_id:
            query = query.filter(DesignationSlot.id != exclude_slot_id)

        conflicts: list[Conflict] = []
        for slot in query.all():
            conflicts.append(
                Conflict(
                    type="GROUP_OVERLAP",
                    severity="HARD",
                    message=(
                        f"Grupo {group.code} ya tiene clase "
                        f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')} "
                        f"el mismo día"
                    ),
                    conflicting_slot_id=slot.id,
                    details={
                        "group_id": group_id,
                        "group_code": group.code,
                        "existing_designation_id": slot.designation_id,
                        "existing_start": str(slot.start_time),
                        "existing_end": str(slot.end_time),
                    },
                )
            )
        return conflicts

    def check_teacher_availability(
        self,
        db: Session,
        *,
        teacher_ci: str,
        period_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
    ) -> list[Conflict]:
        """Proposed slot must fall within teacher's declared availability. SOFT conflict if outside."""
        availability = (
            db.query(TeacherAvailability)
            .filter(
                TeacherAvailability.teacher_ci == teacher_ci,
                TeacherAvailability.academic_period_id == period_id,
            )
            .first()
        )
        # No availability declared — skip check (no conflict)
        if not availability:
            return []

        # Check if at least one availability slot covers the proposed time
        covering_slot = (
            db.query(AvailabilitySlot)
            .filter(
                AvailabilitySlot.availability_id == availability.id,
                AvailabilitySlot.day_of_week == day_of_week,
                AvailabilitySlot.start_time <= start_time,
                AvailabilitySlot.end_time >= end_time,
            )
            .first()
        )

        if covering_slot:
            return []

        return [
            Conflict(
                type="OUTSIDE_AVAILABILITY",
                severity="SOFT",
                message=(
                    f"Docente {teacher_ci} no tiene disponibilidad declarada para "
                    f"{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')} este día"
                ),
                details={
                    "teacher_ci": teacher_ci,
                    "day_of_week": day_of_week,
                    "proposed_start": str(start_time),
                    "proposed_end": str(end_time),
                },
            )
        ]

    # ─── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _get_period_code(db: Session, period_id: int) -> str | None:
        """Resolve period_id → period.code (e.g. 'I/2026') to join with Designation.academic_period."""
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        return period.code if period else None
