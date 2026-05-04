"""Service layer for RoomType, Equipment, Room, and RoomEquipment CRUD."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.scheduling.models.equipment import Equipment
from app.scheduling.models.academic_period import AcademicPeriod
from app.scheduling.models.designation_slot import DesignationSlot
from app.scheduling.models.room import Room
from app.scheduling.models.room_equipment import RoomEquipment
from app.scheduling.models.room_type import RoomType

logger = logging.getLogger(__name__)


class RoomService:
    """Unified service for rooms, room types, equipment, and room-equipment assignments."""

    # ─── RoomType CRUD ────────────────────────────────────────────────

    def create_room_type(
        self,
        db: Session,
        *,
        code: str,
        name: str,
        description: str | None = None,
    ) -> RoomType:
        existing = db.query(RoomType).filter(RoomType.code == code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room type with code '{code}' already exists",
            )
        rt = RoomType(code=code, name=name, description=description)
        db.add(rt)
        db.flush()
        logger.info("Created room type: %s (%s)", code, name)
        return rt

    def list_room_types(self, db: Session) -> list[dict[str, Any]]:
        room_count_sub = (
            db.query(Room.room_type_id, func.count(Room.id).label("cnt"))
            .group_by(Room.room_type_id)
            .subquery()
        )
        results = (
            db.query(RoomType, func.coalesce(room_count_sub.c.cnt, 0).label("room_count"))
            .outerjoin(room_count_sub, RoomType.id == room_count_sub.c.room_type_id)
            .order_by(RoomType.name)
            .all()
        )
        return [
            {
                "id": rt.id,
                "code": rt.code,
                "name": rt.name,
                "description": rt.description,
                "room_count": count,
            }
            for rt, count in results
        ]

    def update_room_type(self, db: Session, room_type_id: int, **fields: Any) -> RoomType:
        rt = db.query(RoomType).filter(RoomType.id == room_type_id).first()
        if not rt:
            raise HTTPException(status_code=404, detail="Room type not found")
        for key, value in fields.items():
            if value is not None:
                setattr(rt, key, value)
        db.flush()
        return rt

    def delete_room_type(self, db: Session, room_type_id: int) -> dict[str, str]:
        """BR-RT-1: Cannot delete if rooms reference it."""
        rt = db.query(RoomType).filter(RoomType.id == room_type_id).first()
        if not rt:
            raise HTTPException(status_code=404, detail="Room type not found")
        room_count = db.query(Room).filter(Room.room_type_id == room_type_id).count()
        if room_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete room type '{rt.code}': {room_count} room(s) still reference it",
            )
        db.delete(rt)
        db.flush()
        logger.info("Deleted room type: %s (id=%d)", rt.code, room_type_id)
        return {"detail": f"Room type '{rt.code}' deleted"}

    # ─── Equipment CRUD ───────────────────────────────────────────────

    def create_equipment(
        self,
        db: Session,
        *,
        code: str,
        name: str,
        description: str | None = None,
    ) -> Equipment:
        existing = db.query(Equipment).filter(Equipment.code == code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Equipment with code '{code}' already exists",
            )
        eq = Equipment(code=code, name=name, description=description)
        db.add(eq)
        db.flush()
        logger.info("Created equipment: %s (%s)", code, name)
        return eq

    def list_equipment(self, db: Session) -> list[Equipment]:
        return db.query(Equipment).order_by(Equipment.name).all()

    def update_equipment(self, db: Session, equipment_id: int, **fields: Any) -> Equipment:
        eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not eq:
            raise HTTPException(status_code=404, detail="Equipment not found")
        for key, value in fields.items():
            if value is not None:
                setattr(eq, key, value)
        db.flush()
        return eq

    def delete_equipment(self, db: Session, equipment_id: int) -> dict[str, str]:
        """BR-EQ-1: Cannot delete if assigned to any room via RoomEquipment."""
        eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not eq:
            raise HTTPException(status_code=404, detail="Equipment not found")
        ref_count = db.query(RoomEquipment).filter(RoomEquipment.equipment_id == equipment_id).count()
        if ref_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete equipment '{eq.code}': assigned to {ref_count} room(s)",
            )
        db.delete(eq)
        db.flush()
        logger.info("Deleted equipment: %s (id=%d)", eq.code, equipment_id)
        return {"detail": f"Equipment '{eq.code}' deleted"}

    # ─── Room CRUD ────────────────────────────────────────────────────

    def create_room(self, db: Session, *, data: Any) -> Room:
        """Create a room with optional equipment assignments."""
        # Validate room_type exists
        rt = db.query(RoomType).filter(RoomType.id == data.room_type_id).first()
        if not rt:
            raise HTTPException(status_code=404, detail="Room type not found")

        # Check unique code
        existing = db.query(Room).filter(Room.code == data.code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Room with code '{data.code}' already exists",
            )

        room = Room(
            code=data.code,
            name=data.name,
            building=data.building,
            floor=data.floor,
            capacity=data.capacity,
            room_type_id=data.room_type_id,
            description=data.description,
        )
        db.add(room)
        db.flush()  # get room.id

        # Attach equipment if provided
        for eq_data in data.equipment:
            eq = db.query(Equipment).filter(Equipment.id == eq_data.equipment_id).first()
            if not eq:
                raise HTTPException(
                    status_code=404,
                    detail=f"Equipment with id {eq_data.equipment_id} not found",
                )
            re_item = RoomEquipment(
                room_id=room.id,
                equipment_id=eq_data.equipment_id,
                quantity=eq_data.quantity,
                notes=eq_data.notes,
            )
            db.add(re_item)

        db.flush()
        logger.info("Created room: %s (%s)", data.code, data.name)
        return room

    def list_rooms(
        self,
        db: Session,
        *,
        building: str | None = None,
        floor: str | None = None,
        room_type_id: int | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        query = (
            db.query(Room)
            .options(joinedload(Room.room_type), joinedload(Room.equipment_items).joinedload(RoomEquipment.equipment))
        )
        if active_only:
            query = query.filter(Room.is_active.is_(True))
        if building:
            query = query.filter(Room.building == building)
        if floor:
            query = query.filter(Room.floor == floor)
        if room_type_id:
            query = query.filter(Room.room_type_id == room_type_id)

        rooms = query.order_by(Room.building, Room.floor, Room.code).all()
        # Deduplicate due to joinedload producing cartesian on multiple collections
        seen: set[int] = set()
        result: list[dict[str, Any]] = []
        for r in rooms:
            if r.id in seen:
                continue
            seen.add(r.id)
            result.append(self._room_to_dict(r))
        return result

    def get_room(self, db: Session, room_id: int) -> dict[str, Any]:
        room = (
            db.query(Room)
            .options(joinedload(Room.room_type), joinedload(Room.equipment_items).joinedload(RoomEquipment.equipment))
            .filter(Room.id == room_id)
            .first()
        )
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        return self._room_to_dict(room)

    def update_room(self, db: Session, room_id: int, **fields: Any) -> Room:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        # Validate room_type_id if being changed
        new_rt_id = fields.get("room_type_id")
        if new_rt_id is not None:
            rt = db.query(RoomType).filter(RoomType.id == new_rt_id).first()
            if not rt:
                raise HTTPException(status_code=404, detail="Room type not found")

        for key, value in fields.items():
            if value is not None:
                setattr(room, key, value)
        db.flush()
        return room

    def deactivate_room(self, db: Session, room_id: int) -> Room:
        """BR-RM-2: Rooms are never hard-deleted, use is_active=False."""
        from app.models.designation import Designation

        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        blocking_slots = (
            db.query(func.count(DesignationSlot.id))
            .join(Designation, DesignationSlot.designation_id == Designation.id)
            .join(
                AcademicPeriod,
                or_(
                    Designation.academic_period_id == AcademicPeriod.id,
                    Designation.academic_period == AcademicPeriod.code,
                ),
            )
            .filter(
                DesignationSlot.room_id == room_id,
                Designation.status != "cancelled",
                AcademicPeriod.status != "closed",
            )
            .scalar()
        )
        if blocking_slots:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate room '{room.code}': {blocking_slots} active schedule slot(s) still reference it",
            )
        room.is_active = False
        db.flush()
        logger.info("Deactivated room: %s (id=%d)", room.code, room_id)
        return room

    # ─── RoomEquipment ────────────────────────────────────────────────

    def add_equipment_to_room(
        self,
        db: Session,
        room_id: int,
        equipment_id: int,
        quantity: int = 1,
        notes: str | None = None,
    ) -> RoomEquipment:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        eq = db.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not eq:
            raise HTTPException(status_code=404, detail="Equipment not found")

        existing = (
            db.query(RoomEquipment)
            .filter(RoomEquipment.room_id == room_id, RoomEquipment.equipment_id == equipment_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Equipment '{eq.code}' already assigned to room '{room.code}'",
            )

        re_item = RoomEquipment(
            room_id=room_id,
            equipment_id=equipment_id,
            quantity=quantity,
            notes=notes,
        )
        db.add(re_item)
        db.flush()
        logger.info("Added equipment %s to room %s (qty=%d)", eq.code, room.code, quantity)
        return re_item

    def remove_equipment_from_room(self, db: Session, room_id: int, equipment_id: int) -> dict[str, str]:
        re_item = (
            db.query(RoomEquipment)
            .filter(RoomEquipment.room_id == room_id, RoomEquipment.equipment_id == equipment_id)
            .first()
        )
        if not re_item:
            raise HTTPException(status_code=404, detail="Equipment assignment not found for this room")
        db.delete(re_item)
        db.flush()
        return {"detail": "Equipment removed from room"}

    def update_room_equipment(
        self, db: Session, room_equipment_id: int, *, quantity: int | None = None, notes: str | None = None
    ) -> RoomEquipment:
        re_item = db.query(RoomEquipment).filter(RoomEquipment.id == room_equipment_id).first()
        if not re_item:
            raise HTTPException(status_code=404, detail="Room equipment assignment not found")
        if quantity is not None:
            re_item.quantity = quantity
        if notes is not None:
            re_item.notes = notes
        db.flush()
        return re_item

    # ─── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _room_to_dict(room: Room) -> dict[str, Any]:
        return {
            "id": room.id,
            "code": room.code,
            "name": room.name,
            "building": room.building,
            "floor": room.floor,
            "capacity": room.capacity,
            "room_type_id": room.room_type_id,
            "room_type_name": room.room_type.name if room.room_type else "",
            "is_active": room.is_active,
            "description": room.description,
            "equipment_items": [
                {
                    "id": ei.id,
                    "equipment_id": ei.equipment_id,
                    "equipment_code": ei.equipment.code if ei.equipment else "",
                    "equipment_name": ei.equipment.name if ei.equipment else "",
                    "quantity": ei.quantity,
                    "notes": ei.notes,
                }
                for ei in room.equipment_items
            ],
        }
