"""Router for rooms, room types, equipment, and room-equipment assignments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.auth import require_admin

from app.scheduling.schemas.room import (
    EquipmentCreate,
    EquipmentResponse,
    EquipmentUpdate,
    RoomCreate,
    RoomEquipmentCreate,
    RoomEquipmentResponse,
    RoomResponse,
    RoomTypeCreate,
    RoomTypeResponse,
    RoomTypeUpdate,
    RoomUpdate,
)
from app.scheduling.services.room_service import RoomService

router = APIRouter(prefix="/api/scheduling", tags=["scheduling-rooms"])

room_svc = RoomService()


# ─── RoomType endpoints ──────────────────────────────────────────────

@router.post("/room-types", response_model=RoomTypeResponse, status_code=201)
def create_room_type(
    data: RoomTypeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    rt = room_svc.create_room_type(db, code=data.code, name=data.name, description=data.description)
    db.commit()
    return RoomTypeResponse(
        id=rt.id, code=rt.code, name=rt.name, description=rt.description, room_count=0
    )


@router.get("/room-types", response_model=list[RoomTypeResponse])
def list_room_types(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return room_svc.list_room_types(db)


@router.put("/room-types/{room_type_id}", response_model=RoomTypeResponse)
def update_room_type(
    room_type_id: int,
    data: RoomTypeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    room_svc.update_room_type(db, room_type_id, **fields)
    db.commit()
    # Re-fetch with room_count
    all_types = room_svc.list_room_types(db)
    return next((t for t in all_types if t["id"] == room_type_id), all_types[-1])


@router.delete("/room-types/{room_type_id}")
def delete_room_type(
    room_type_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = room_svc.delete_room_type(db, room_type_id)
    db.commit()
    return result


# ─── Equipment endpoints ─────────────────────────────────────────────

@router.post("/equipment", response_model=EquipmentResponse, status_code=201)
def create_equipment(
    data: EquipmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    eq = room_svc.create_equipment(db, code=data.code, name=data.name, description=data.description)
    db.commit()
    return EquipmentResponse(id=eq.id, code=eq.code, name=eq.name, description=eq.description)


@router.get("/equipment", response_model=list[EquipmentResponse])
def list_equipment(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return room_svc.list_equipment(db)


@router.put("/equipment/{equipment_id}", response_model=EquipmentResponse)
def update_equipment(
    equipment_id: int,
    data: EquipmentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    eq = room_svc.update_equipment(db, equipment_id, **fields)
    db.commit()
    return EquipmentResponse(id=eq.id, code=eq.code, name=eq.name, description=eq.description)


@router.delete("/equipment/{equipment_id}")
def delete_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = room_svc.delete_equipment(db, equipment_id)
    db.commit()
    return result


# ─── Room endpoints ──────────────────────────────────────────────────

@router.post("/rooms", response_model=RoomResponse, status_code=201)
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    room = room_svc.create_room(db, data=data)
    db.commit()
    return room_svc.get_room(db, room.id)


@router.get("/rooms", response_model=list[RoomResponse])
def list_rooms(
    building: str | None = Query(default=None, description="Filter by building"),
    floor: str | None = Query(default=None, description="Filter by floor"),
    room_type_id: int | None = Query(default=None, description="Filter by room type"),
    active_only: bool = Query(default=True, description="Only active rooms"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return room_svc.list_rooms(
        db, building=building, floor=floor, room_type_id=room_type_id, active_only=active_only
    )


@router.get("/rooms/{room_id}", response_model=RoomResponse)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return room_svc.get_room(db, room_id)


@router.put("/rooms/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: int,
    data: RoomUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    room_svc.update_room(db, room_id, **fields)
    db.commit()
    return room_svc.get_room(db, room_id)


@router.delete("/rooms/{room_id}", response_model=RoomResponse)
def deactivate_room(
    room_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """BR-RM-2: Soft delete — deactivate instead of hard delete."""
    room_svc.deactivate_room(db, room_id)
    db.commit()
    return room_svc.get_room(db, room_id)


# ─── Room Equipment endpoints ────────────────────────────────────────

@router.post("/rooms/{room_id}/equipment", response_model=RoomEquipmentResponse, status_code=201)
def add_equipment_to_room(
    room_id: int,
    data: RoomEquipmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    re_item = room_svc.add_equipment_to_room(
        db, room_id, data.equipment_id, quantity=data.quantity, notes=data.notes
    )
    db.commit()
    # Reload to get equipment details
    eq = re_item.equipment
    return RoomEquipmentResponse(
        id=re_item.id,
        equipment_id=re_item.equipment_id,
        equipment_code=eq.code if eq else "",
        equipment_name=eq.name if eq else "",
        quantity=re_item.quantity,
        notes=re_item.notes,
    )


@router.delete("/rooms/{room_id}/equipment/{equipment_id}")
def remove_equipment_from_room(
    room_id: int,
    equipment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = room_svc.remove_equipment_from_room(db, room_id, equipment_id)
    db.commit()
    return result
