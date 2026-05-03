"""SlotService — CRUD for DesignationSlot with conflict validation."""

from __future__ import annotations

import logging
import math
from datetime import time
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.designation import Designation
from app.scheduling.models.designation_slot import DesignationSlot
from app.scheduling.models.group import Group
from app.scheduling.models.room import Room
from app.scheduling.schemas.slot import DAY_NAMES
from app.scheduling.services.conflict_service import ConflictService

logger = logging.getLogger(__name__)

conflict_svc = ConflictService()


class SlotService:
    """CRUD for designation slots with automatic conflict detection."""

    # ─── Create ───────────────────────────────────────────────────────

    def create_slot(
        self,
        db: Session,
        *,
        designation_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
        room_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a slot, validating conflicts first. Returns dict with slot + conflicts."""
        if start_time >= end_time:
            raise HTTPException(
                status_code=422,
                detail=f"start_time ({start_time}) debe ser menor que end_time ({end_time})",
            )

        # Load designation to get teacher_ci, group_code, period
        designation = db.query(Designation).filter(Designation.id == designation_id).first()
        if not designation:
            raise HTTPException(status_code=404, detail="Designación no encontrada")

        # Resolve group_id from group_code + period
        period_id, group_id = self._resolve_context(db, designation)

        if not period_id:
            raise HTTPException(
                status_code=422,
                detail=f"Periodo académico '{designation.academic_period}' no encontrado en scheduling",
            )

        # Run conflict validation
        conflicts = conflict_svc.validate_slot(
            db,
            period_id=period_id,
            designation_id=designation_id,
            teacher_ci=designation.teacher_ci,
            group_id=group_id or 0,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            room_id=room_id,
        )

        # Block on HARD conflicts
        hard_conflicts = [c for c in conflicts if c.severity == "HARD"]
        if hard_conflicts:
            return {
                "slot": None,
                "conflicts": [self._conflict_to_dict(c) for c in conflicts],
                "blocked": True,
            }

        # Compute duration and academic hours
        duration_minutes = self._compute_duration(start_time, end_time)
        academic_hours = max(1, round(duration_minutes / 45))

        slot = DesignationSlot(
            designation_id=designation_id,
            room_id=room_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            academic_hours=academic_hours,
        )
        db.add(slot)
        db.flush()

        logger.info("Created slot %d for designation %d", slot.id, designation_id)

        soft_conflicts = [c for c in conflicts if c.severity == "SOFT"]
        return {
            "slot": self._slot_to_dict(db, slot),
            "conflicts": [self._conflict_to_dict(c) for c in soft_conflicts],
            "blocked": False,
        }

    # ─── Update ───────────────────────────────────────────────────────

    def update_slot(self, db: Session, slot_id: int, **fields: Any) -> dict[str, Any]:
        """Update a slot, re-validating conflicts."""
        slot = db.query(DesignationSlot).filter(DesignationSlot.id == slot_id).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot no encontrado")

        # Apply fields
        new_day = fields.get("day_of_week", slot.day_of_week)
        new_start = fields.get("start_time", slot.start_time)
        new_end = fields.get("end_time", slot.end_time)
        new_room = fields.get("room_id", slot.room_id)

        if new_start >= new_end:
            raise HTTPException(
                status_code=422,
                detail=f"start_time ({new_start}) debe ser menor que end_time ({new_end})",
            )

        designation = db.query(Designation).filter(Designation.id == slot.designation_id).first()
        if not designation:
            raise HTTPException(status_code=404, detail="Designación no encontrada")

        period_id, group_id = self._resolve_context(db, designation)

        conflicts = conflict_svc.validate_slot(
            db,
            period_id=period_id or 0,
            designation_id=slot.designation_id,
            teacher_ci=designation.teacher_ci,
            group_id=group_id or 0,
            day_of_week=new_day,
            start_time=new_start,
            end_time=new_end,
            room_id=new_room,
            exclude_slot_id=slot_id,
        )

        hard_conflicts = [c for c in conflicts if c.severity == "HARD"]
        if hard_conflicts:
            return {
                "slot": None,
                "conflicts": [self._conflict_to_dict(c) for c in conflicts],
                "blocked": True,
            }

        # Apply updates
        slot.day_of_week = new_day
        slot.start_time = new_start
        slot.end_time = new_end
        slot.room_id = new_room
        slot.duration_minutes = self._compute_duration(new_start, new_end)
        slot.academic_hours = max(1, round(slot.duration_minutes / 45))

        db.flush()
        logger.info("Updated slot %d", slot_id)

        soft_conflicts = [c for c in conflicts if c.severity == "SOFT"]
        return {
            "slot": self._slot_to_dict(db, slot),
            "conflicts": [self._conflict_to_dict(c) for c in soft_conflicts],
            "blocked": False,
        }

    # ─── Delete ───────────────────────────────────────────────────────

    def delete_slot(self, db: Session, slot_id: int) -> dict[str, str]:
        slot = db.query(DesignationSlot).filter(DesignationSlot.id == slot_id).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot no encontrado")
        db.delete(slot)
        db.flush()
        logger.info("Deleted slot %d", slot_id)
        return {"detail": f"Slot {slot_id} eliminado"}

    # ─── List ─────────────────────────────────────────────────────────

    def list_by_designation(self, db: Session, designation_id: int) -> list[dict[str, Any]]:
        slots = (
            db.query(DesignationSlot)
            .filter(DesignationSlot.designation_id == designation_id)
            .order_by(DesignationSlot.day_of_week, DesignationSlot.start_time)
            .all()
        )
        return [self._slot_to_dict(db, s) for s in slots]

    # ─── Room assignment ──────────────────────────────────────────────

    def assign_room(self, db: Session, slot_id: int, room_id: int) -> dict[str, Any]:
        """Assign a room to a slot, checking room conflicts + active status."""
        slot = db.query(DesignationSlot).filter(DesignationSlot.id == slot_id).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot no encontrado")

        designation = db.query(Designation).filter(Designation.id == slot.designation_id).first()
        if not designation:
            raise HTTPException(status_code=404, detail="Designación no encontrada")

        period_id, _ = self._resolve_context(db, designation)

        # Check room-specific conflicts only
        conflicts: list = []
        conflicts.extend(
            conflict_svc.check_room_overlap(
                db,
                room_id=room_id,
                period_id=period_id or 0,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                exclude_slot_id=slot_id,
            )
        )
        conflicts.extend(conflict_svc.check_room_active(db, room_id=room_id))

        hard = [c for c in conflicts if c.severity == "HARD"]
        if hard:
            return {
                "slot": None,
                "conflicts": [self._conflict_to_dict(c) for c in conflicts],
                "blocked": True,
            }

        slot.room_id = room_id
        db.flush()
        logger.info("Assigned room %d to slot %d", room_id, slot_id)
        return {
            "slot": self._slot_to_dict(db, slot),
            "conflicts": [self._conflict_to_dict(c) for c in conflicts],
            "blocked": False,
        }

    def unassign_room(self, db: Session, slot_id: int) -> dict[str, Any]:
        slot = db.query(DesignationSlot).filter(DesignationSlot.id == slot_id).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot no encontrado")
        slot.room_id = None
        db.flush()
        logger.info("Unassigned room from slot %d", slot_id)
        return {"slot": self._slot_to_dict(db, slot), "conflicts": [], "blocked": False}

    # ─── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _compute_duration(start: time, end: time) -> int:
        start_min = start.hour * 60 + start.minute
        end_min = end.hour * 60 + end.minute
        return end_min - start_min

    @staticmethod
    def _slot_to_dict(db: Session, slot: DesignationSlot) -> dict[str, Any]:
        room_code = ""
        if slot.room_id:
            room = db.query(Room).filter(Room.id == slot.room_id).first()
            room_code = room.code if room else ""

        return {
            "id": slot.id,
            "designation_id": slot.designation_id,
            "room_id": slot.room_id,
            "room_code": room_code,
            "day_of_week": slot.day_of_week,
            "day_name": DAY_NAMES[slot.day_of_week] if 0 <= slot.day_of_week <= 6 else "",
            "start_time": slot.start_time.strftime("%H:%M") if slot.start_time else "",
            "end_time": slot.end_time.strftime("%H:%M") if slot.end_time else "",
            "duration_minutes": slot.duration_minutes,
            "academic_hours": slot.academic_hours,
        }

    @staticmethod
    def _conflict_to_dict(conflict: Any) -> dict[str, Any]:
        return {
            "type": conflict.type,
            "severity": conflict.severity,
            "message": conflict.message,
            "conflicting_slot_id": conflict.conflicting_slot_id,
            "details": conflict.details,
        }

    @staticmethod
    def _resolve_context(db: Session, designation: Designation) -> tuple[int | None, int | None]:
        """Resolve period_id and group_id from Designation string fields."""
        from app.scheduling.models.academic_period import AcademicPeriod

        period = (
            db.query(AcademicPeriod)
            .filter(AcademicPeriod.code == designation.academic_period)
            .first()
        )
        period_id = period.id if period else None

        group_id = None
        if period_id:
            group = (
                db.query(Group)
                .filter(
                    Group.code == designation.group_code,
                    Group.academic_period_id == period_id,
                )
                .first()
            )
            group_id = group.id if group else None

        return period_id, group_id
