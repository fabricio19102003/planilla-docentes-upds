from __future__ import annotations

from typing import Literal


TeacherType = Literal["EXTERNO", "PERMANENTE", "TITULAR"]
TEACHER_TYPES: tuple[TeacherType, ...] = ("EXTERNO", "PERMANENTE", "TITULAR")


def normalize_teacher_type(value: str | None) -> TeacherType | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("El tipo docente debe ser texto.")
    normalized = value.strip().upper()
    if not normalized:
        return None
    if normalized not in TEACHER_TYPES:
        raise ValueError("El tipo docente debe ser EXTERNO, PERMANENTE o TITULAR.")
    return normalized  # type: ignore[return-value]
