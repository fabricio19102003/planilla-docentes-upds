"""Router for designation slots (scheduling) and teacher availability."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.auth import require_admin

from app.scheduling.schemas.availability import (
    AvailabilitySlotInput,
    SetAvailabilityRequest,
    TeacherAvailabilityResponse,
)
from app.scheduling.schemas.slot import (
    ConflictResponse,
    RoomAssignRequest,
    SlotCreate,
    SlotResponse,
    SlotUpdate,
    SlotValidateRequest,
)
from app.scheduling.services.availability_service import AvailabilityService
from app.scheduling.services.slot_service import SlotService

router = APIRouter(prefix="/api/scheduling", tags=["scheduling-slots"])

slot_svc = SlotService()
avail_svc = AvailabilityService()


# ─── Designation Slot endpoints ──────────────────────────────────────


@router.post("/slots", status_code=201)
def create_slot(
    data: SlotCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Create a designation slot. Returns slot + any conflicts.

    If HARD conflicts exist, ``blocked=true`` and slot is NOT created.
    """
    result = slot_svc.create_slot(
        db,
        designation_id=data.designation_id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        room_id=data.room_id,
    )
    if not result["blocked"]:
        db.commit()
    return result


@router.get("/slots")
def list_slots(
    designation_id: int = Query(..., description="Filter by designation"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return slot_svc.list_by_designation(db, designation_id)


@router.put("/slots/{slot_id}")
def update_slot(
    slot_id: int,
    data: SlotUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Update a slot. Re-validates conflicts."""
    fields = data.model_dump(exclude_unset=True)
    result = slot_svc.update_slot(db, slot_id, **fields)
    if not result["blocked"]:
        db.commit()
    return result


@router.delete("/slots/{slot_id}")
def delete_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = slot_svc.delete_slot(db, slot_id)
    db.commit()
    return result


@router.post("/slots/{slot_id}/assign-room")
def assign_room(
    slot_id: int,
    data: RoomAssignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Assign a room to an existing slot, checking room conflicts."""
    result = slot_svc.assign_room(db, slot_id, data.room_id)
    if not result["blocked"]:
        db.commit()
    return result


@router.post("/slots/{slot_id}/unassign-room")
def unassign_room(
    slot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = slot_svc.unassign_room(db, slot_id)
    db.commit()
    return result


@router.post("/slots/validate")
def validate_slot(
    data: SlotValidateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Dry-run validation — returns conflicts without saving."""
    # We reuse create_slot logic but just return conflicts
    from app.models.designation import Designation
    from app.scheduling.services.conflict_service import ConflictService

    designation = db.query(Designation).filter(Designation.id == data.designation_id).first()
    if not designation:
        return {"conflicts": [], "blocked": False, "error": "Designación no encontrada"}

    period_id, group_id = SlotService._resolve_context(db, designation)
    if not period_id:
        return {"conflicts": [], "blocked": False, "error": "Periodo no encontrado"}

    svc = ConflictService()
    conflicts = svc.validate_slot(
        db,
        period_id=period_id,
        designation_id=data.designation_id,
        teacher_ci=designation.teacher_ci,
        group_id=group_id or 0,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        room_id=data.room_id,
    )
    hard = any(c.severity == "HARD" for c in conflicts)
    return {
        "conflicts": [
            {
                "type": c.type,
                "severity": c.severity,
                "message": c.message,
                "conflicting_slot_id": c.conflicting_slot_id,
                "details": c.details,
            }
            for c in conflicts
        ],
        "blocked": hard,
    }


# ─── Teacher Availability endpoints ─────────────────────────────────


@router.post("/availability", status_code=201)
def set_availability(
    data: SetAvailabilityRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Set (create or replace) a teacher's availability for a period."""
    slots_dicts = [s.model_dump() for s in data.slots]
    avail = avail_svc.set_availability(
        db, teacher_ci=data.teacher_ci, period_id=data.period_id, slots=slots_dicts
    )
    db.commit()
    return avail_svc.get_availability(db, teacher_ci=data.teacher_ci, period_id=data.period_id)


@router.get("/availability")
def get_availability(
    teacher_ci: str = Query(..., description="Teacher CI"),
    period_id: int = Query(..., description="Academic period ID"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = avail_svc.get_availability(db, teacher_ci=teacher_ci, period_id=period_id)
    if not result:
        return {"detail": "No availability found", "slots": []}
    return result


@router.delete("/availability")
def clear_availability(
    teacher_ci: str = Query(..., description="Teacher CI"),
    period_id: int = Query(..., description="Academic period ID"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = avail_svc.clear_availability(db, teacher_ci=teacher_ci, period_id=period_id)
    db.commit()
    return result


@router.get("/availability/period/{period_id}")
def list_availability_by_period(
    period_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return avail_svc.list_by_period(db, period_id=period_id)
