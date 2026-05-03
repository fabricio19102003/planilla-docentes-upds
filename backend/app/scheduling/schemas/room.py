"""Schemas for RoomType, Equipment, Room, and RoomEquipment CRUD operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ─── RoomType ─────────────────────────────────────────────────────────

class RoomTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class RoomTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class RoomTypeResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    room_count: int = 0
    model_config = ConfigDict(from_attributes=True)


# ─── Equipment ────────────────────────────────────────────────────────

class EquipmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class EquipmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class EquipmentResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ─── RoomEquipment ────────────────────────────────────────────────────

class RoomEquipmentCreate(BaseModel):
    equipment_id: int
    quantity: int = Field(default=1, ge=1)
    notes: str | None = None


class RoomEquipmentResponse(BaseModel):
    id: int
    equipment_id: int
    equipment_code: str = ""
    equipment_name: str = ""
    quantity: int
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ─── Room ─────────────────────────────────────────────────────────────

class RoomCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    building: str = Field(min_length=1, max_length=100)
    floor: str = Field(min_length=1, max_length=20)
    capacity: int = Field(ge=1)
    room_type_id: int
    description: str | None = None
    equipment: list[RoomEquipmentCreate] = []


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    building: str | None = None
    floor: str | None = None
    capacity: int | None = Field(default=None, ge=1)
    room_type_id: int | None = None
    description: str | None = None
    is_active: bool | None = None


class RoomResponse(BaseModel):
    id: int
    code: str
    name: str
    building: str
    floor: str
    capacity: int
    room_type_id: int
    room_type_name: str = ""
    is_active: bool
    description: str | None = None
    equipment_items: list[RoomEquipmentResponse] = []
    model_config = ConfigDict(from_attributes=True)
