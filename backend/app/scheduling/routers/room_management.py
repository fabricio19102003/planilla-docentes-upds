from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.scheduling.models.room_type import RoomType
from app.scheduling.models.equipment import Equipment
from app.scheduling.models.room import Room
from app.scheduling.schemas.room import (
    RoomTypeCreate,
    RoomTypeResponse,
    EquipmentCreate,
    EquipmentResponse,
    RoomCreate,
    RoomResponse,
)
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/scheduling/rooms", tags=["scheduling"])


@router.get("/types", response_model=list[RoomTypeResponse])
def list_room_types(db: Session = Depends(get_db)):
    return db.query(RoomType).order_by(RoomType.code).all()


@router.post("/types", response_model=RoomTypeResponse, status_code=status.HTTP_201_CREATED)
def create_room_type(
    payload: RoomTypeCreate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
) -> RoomTypeResponse:
    existing = db.query(RoomType).filter(RoomType.code == payload.code.strip().upper()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room type code already exists")

    room_type = RoomType(
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        description=payload.description,
    )
    db.add(room_type)
    db.commit()
    db.refresh(room_type)
    return room_type


@router.get("/equipment", response_model=list[EquipmentResponse])
def list_equipment(db: Session = Depends(get_db)):
    return db.query(Equipment).order_by(Equipment.code).all()


@router.post("/equipment", response_model=EquipmentResponse, status_code=status.HTTP_201_CREATED)
def create_equipment(
    payload: EquipmentCreate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
) -> EquipmentResponse:
    existing = db.query(Equipment).filter(Equipment.code == payload.code.strip().upper()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Equipment code already exists")

    equipment = Equipment(
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        description=payload.description,
    )
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return equipment


@router.get("/", response_model=list[RoomResponse])
def list_rooms(db: Session = Depends(get_db)):
    return db.query(Room).order_by(Room.code).all()


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: RoomCreate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
) -> RoomResponse:
    room_type = db.query(RoomType).filter(RoomType.id == payload.room_type_id).first()
    if room_type is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room type")

    existing = db.query(Room).filter(Room.code == payload.code.strip().upper()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room code already exists")

    room = Room(
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        building=payload.building.strip(),
        floor=payload.floor.strip(),
        capacity=payload.capacity,
        room_type_id=payload.room_type_id,
        description=payload.description,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room
