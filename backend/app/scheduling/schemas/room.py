from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class RoomTypeCreate(BaseModel):
    code: str = Field(..., example="AULA")
    name: str = Field(..., example="Aula Comun")
    description: str | None = None


class RoomTypeResponse(RoomTypeCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class EquipmentCreate(BaseModel):
    code: str = Field(..., example="PROY")
    name: str = Field(..., example="Proyector")
    description: str | None = None


class EquipmentResponse(EquipmentCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RoomCreate(BaseModel):
    code: str = Field(..., example="A-101")
    name: str = Field(..., example="Aula 101")
    building: str = Field(..., example="Edificio Central")
    floor: str = Field(..., example="1")
    capacity: int = Field(..., ge=1)
    room_type_id: int
    description: str | None = None


class RoomResponse(RoomCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)
