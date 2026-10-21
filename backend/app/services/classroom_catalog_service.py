"""Official Cobija classroom catalog (feature designation-module-v2, L15).

Room numbers are unique across both buildings, so a designation's AULA number
identifies one room. Sync creates missing rooms, corrects capacity, name and
active state of rooms with the same code, and only reports rooms whose number
exists under another code (they may be referenced by published schedules).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.academic_management import Classroom

CAMPUS = "Cobija"
_CODE_RE = re.compile(r"^COB-[A-Z]+-P\d+-A([0-9A-Z]+)$")


@dataclass(frozen=True)
class CatalogRoom:
    building: str
    floor: int
    room: str
    capacity: int

    @property
    def code(self) -> str:
        return f"COB-{self.building}-P{self.floor}-A{self.room}"

    @property
    def name(self) -> str:
        return f"{self.building} / Piso {self.floor} / Aula {self.room}"


CATALOG: tuple[CatalogRoom, ...] = (
    *(CatalogRoom("ANTIGUO", 1, str(room), 54) for room in range(1, 6)),
    *(CatalogRoom("ANTIGUO", 2, str(room), 54) for room in range(6, 11)),
    CatalogRoom("ANTIGUO", 1, "A", 20),
    CatalogRoom("ANTIGUO", 1, "B", 20),
    *(CatalogRoom("NUEVO", 2, str(room), capacity) for room, capacity in (
        (11, 35), (12, 50), (13, 50), (14, 40), (15, 40), (16, 35), (17, 20),
    )),
    *(CatalogRoom("NUEVO", 3, str(room), capacity) for room, capacity in (
        (18, 47), (19, 51), (20, 52), (21, 42), (22, 54), (23, 46),
    )),
    *(CatalogRoom("NUEVO", 4, str(room), capacity) for room, capacity in (
        (24, 47), (25, 51), (26, 51), (27, 40), (28, 45), (29, 45),
    )),
)
BY_ROOM = {item.room: item for item in CATALOG}


def room_key(value: object) -> str | None:
    """Normalize a workbook AULA cell (``20``, ``20.0``, ``" b "``) to a catalog room number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip().upper()
    text = re.sub(r"^(AULA|A)\s*", "", text) if len(text) > 1 else text
    if text.endswith(".0"):
        text = text[:-2]
    return text if text in BY_ROOM else None


def catalog_room(value: object) -> CatalogRoom | None:
    key = room_key(value)
    return BY_ROOM.get(key) if key else None


def _plan(db: Session) -> tuple[dict, list[tuple[CatalogRoom, Classroom | None]]]:
    existing = {room.code: room for room in db.query(Classroom).order_by(Classroom.code).all()}
    create, update, actions = [], [], []
    unchanged = 0
    for item in CATALOG:
        room = existing.get(item.code)
        if room is None:
            create.append({
                "code": item.code, "name": item.name, "building": item.building,
                "floor": item.floor, "room": item.room, "capacity": item.capacity,
            })
            actions.append((item, None))
            continue
        changes = {}
        for field, wanted in (("name", item.name), ("capacity", item.capacity),
                              ("classroom_type", "classroom"), ("active", True)):
            if getattr(room, field) != wanted:
                changes[field] = [getattr(room, field), wanted]
        if changes:
            update.append({"code": item.code, "changes": changes})
            actions.append((item, room))
        else:
            unchanged += 1
    catalog_codes = {item.code for item in CATALOG}
    conflicts = []
    for code, room in existing.items():
        match = _CODE_RE.match(code)
        if room.active and match and code not in catalog_codes and match.group(1) in BY_ROOM:
            conflicts.append({"code": code, "room": match.group(1), "catalog_code": BY_ROOM[match.group(1)].code})
    return {"create": create, "update": update, "unchanged": unchanged, "conflicts": conflicts}, actions


def preview_catalog(db: Session) -> dict:
    return _plan(db)[0]


def apply_catalog(db: Session) -> dict:
    plan, actions = _plan(db)
    for item, room in actions:
        if room is None:
            db.add(Classroom(
                code=item.code, name=item.name, campus=CAMPUS, capacity=item.capacity,
                classroom_type="classroom", resources=[], active=True,
            ))
        else:
            room.name, room.capacity, room.classroom_type, room.active = item.name, item.capacity, "classroom", True
    db.flush()
    return plan
