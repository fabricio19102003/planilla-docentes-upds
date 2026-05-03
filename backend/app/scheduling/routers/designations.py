"""Router for scheduling-based designation management (E6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.auth import require_admin

from app.scheduling.schemas.designation import (
    DesignationSchedulingCreate,
    DesignationSchedulingUpdate,
    SlotInput,
)
from app.scheduling.services.designation_service import DesignationService, migrate_legacy_designations
from app.scheduling.services.slot_service import SlotService

router = APIRouter(prefix="/api/scheduling", tags=["scheduling-designations"])

desig_svc = DesignationService()
slot_svc = SlotService()


# ─── CRUD ─────────────────────────────────────────────────────────────


@router.post("/designations", status_code=201)
def create_designation(
    data: DesignationSchedulingCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Create a designation with optional slots. Status starts as 'draft'."""
    slots_dicts = [s.model_dump() for s in data.slots] if data.slots else None
    result = desig_svc.create_designation(
        db,
        teacher_ci=data.teacher_ci,
        period_id=data.period_id,
        subject_id=data.subject_id,
        group_id=data.group_id,
        slots=slots_dicts,
        semester_hours=data.semester_hours,
    )
    db.commit()
    return result


@router.get("/designations")
def list_designations(
    period_id: int | None = Query(default=None, description="Filter by period"),
    teacher_ci: str | None = Query(default=None, description="Filter by teacher CI"),
    status: str | None = Query(default=None, description="Filter by status (draft/confirmed/cancelled)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return desig_svc.list_designations(db, period_id=period_id, teacher_ci=teacher_ci, status=status)


@router.get("/designations/{designation_id}")
def get_designation(
    designation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return desig_svc.get_designation(db, designation_id)


@router.put("/designations/{designation_id}")
def update_designation(
    designation_id: int,
    data: DesignationSchedulingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    result = desig_svc.update_designation(db, designation_id, **fields)
    db.commit()
    return result


# ─── Lifecycle ────────────────────────────────────────────────────────


@router.post("/designations/{designation_id}/confirm")
def confirm_designation(
    designation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = desig_svc.confirm_designation(db, designation_id)
    db.commit()
    return result


@router.post("/designations/{designation_id}/cancel")
def cancel_designation(
    designation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = desig_svc.cancel_designation(db, designation_id)
    db.commit()
    return result


# ─── Slot management on designation ──────────────────────────────────


@router.post("/designations/{designation_id}/slots", status_code=201)
def add_slot_to_designation(
    designation_id: int,
    data: SlotInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Add a slot to an existing designation."""
    result = slot_svc.create_slot(
        db,
        designation_id=designation_id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        room_id=data.room_id,
    )
    if not result["blocked"]:
        db.commit()
    return result


@router.delete("/designations/{designation_id}/slots/{slot_id}")
def remove_slot_from_designation(
    designation_id: int,
    slot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Remove a slot from a designation."""
    # Verify slot belongs to this designation
    from app.scheduling.models.designation_slot import DesignationSlot

    slot = db.query(DesignationSlot).filter(
        DesignationSlot.id == slot_id,
        DesignationSlot.designation_id == designation_id,
    ).first()
    if not slot:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Slot {slot_id} no encontrado en designación {designation_id}",
        )
    result = slot_svc.delete_slot(db, slot_id)
    db.commit()
    return result


# ─── Legacy migration ────────────────────────────────────────────────


@router.post("/designations/migrate-legacy")
def migrate_legacy(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Backfill FK columns for existing legacy designations. Admin only."""
    result = migrate_legacy_designations(db)
    db.commit()
    return result
