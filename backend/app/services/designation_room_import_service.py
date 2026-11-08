"""Assign each theory designation its classroom from the designation workbook (theory-classrooms S3).

The sheet is the same DOCENTES TEORICOS sheet the schedule loader reads (``open_rooms_sheet``), and a
room number resolves to one classroom through the official catalog (``catalog_room``). A row is matched
to a designation of the active period by (teacher, subject, semester, group); as in the loader, a
designation with no row of its own takes the room that every usable row of its (subject, semester, group)
agrees on. The teacher is the CI column when the sheet has one, otherwise the teacher name (the current
workbook has no CI). Apply only sets ``designations.classroom_id`` of the designations that change;
payroll never reads it.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.academic_management import Classroom
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services.academic_schedule_view_service import _fold, normalized_group
from app.services.app_settings_service import get_active_academic_period
from app.services.classroom_catalog_service import CatalogRoom, catalog_room
from app.services.designation_schedule_loader_service import LoaderInputError, _cell_text, open_rooms_sheet
from app.utils.academic_semester import semester_number

HEADER_ERROR = (
    "La hoja debe tener las columnas MATERIAS, SEMESTRE, AULA y CI (o el nombre del docente antes de MATERIAS)."
)
BLANK_ROOM = "La fila no tiene aula."
NOT_IN_CATALOG = "El aula no está en el catálogo."
NOT_IN_SYSTEM = "El aula del catálogo no existe en el sistema o está inactiva."
CONFLICTING_ROOMS = "La designación aparece con aulas distintas en el Excel (filas {rows}); no se asigna ninguna."


class StalePreview(Exception):
    """The workbook or the designations changed since the preview was generated."""


@dataclass(frozen=True)
class _Row:
    number: int
    teacher: str
    teacher_id: str
    subject: str
    semester: str
    group: str
    aula: str
    room: CatalogRoom | None
    scope: tuple  # (subject, semester number, group): the part of the match shared by co-teachers

    def listed(self, **extra) -> dict:
        return {"row": self.number, "teacher": self.teacher, "subject": self.subject, **extra}


def _name_id(value: object) -> str:
    """Teacher name without accents, case, punctuation or word order."""
    return " ".join(sorted(re.sub(r"[^a-z0-9]+", " ", _fold(value)).split()))


def _aula_text(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return _cell_text(value)


def _read_rows(content: bytes) -> tuple[list[_Row], bool]:
    """Workbook rows and whether the teacher column is the CI (otherwise the teacher name)."""
    sheet = open_rooms_sheet(content)
    header = [_fold(cell) for cell in next(sheet, ())]
    try:
        subject_col, semester_col, room_col = header.index("materias"), header.index("semestre"), header.index("aula")
    except ValueError as exc:
        raise LoaderInputError(HEADER_ERROR) from exc
    if "ci" in header:
        teacher_col, by_ci = header.index("ci"), True
    elif "docente" in header:
        teacher_col, by_ci = header.index("docente"), False
    elif subject_col > 0 and not header[subject_col - 1]:
        teacher_col, by_ci = subject_col - 1, False
    else:
        raise LoaderInputError(HEADER_ERROR)
    group_col = semester_col + 1
    rows = []
    for number, row in enumerate(sheet, start=2):
        if not row or len(row) <= max(subject_col, room_col, teacher_col, group_col) or not row[subject_col]:
            continue
        teacher = _cell_text(row[teacher_col])
        if by_ci and teacher.endswith(".0"):
            teacher = teacher[:-2]
        semester = _cell_text(row[semester_col])
        group = normalized_group(row[group_col])
        subject = _cell_text(row[subject_col])
        rows.append(_Row(
            number=number, teacher=teacher, teacher_id=teacher if by_ci else _name_id(teacher),
            subject=subject, semester=semester, group=group, aula=_aula_text(row[room_col]),
            room=catalog_room(row[room_col]), scope=(_fold(subject), semester_number(semester), group),
        ))
    return rows, by_ci


def _room(item: Classroom | None) -> dict | None:
    return {"id": item.id, "code": item.code, "name": item.name} if item else None


def plan(db: Session, content: bytes) -> dict:
    rows, by_ci = _read_rows(content)
    period = get_active_academic_period(db)
    by_code = {item.code: item for item in db.query(Classroom)}
    by_id = {item.id: item for item in by_code.values()}

    def usable(row: _Row) -> Classroom | None:
        found = by_code.get(row.room.code) if row.room else None
        return found if found is not None and found.active else None

    by_teacher: dict[tuple, list[_Row]] = {}
    by_group: dict[tuple, list[_Row]] = {}
    unknown_rooms: list[dict] = []
    for row in rows:
        by_teacher.setdefault((row.teacher_id, row.scope), []).append(row)
        if usable(row) is None:
            reason = BLANK_ROOM if not row.aula else NOT_IN_CATALOG if row.room is None else NOT_IN_SYSTEM
            unknown_rooms.append(row.listed(group_code=row.group, aula=row.aula, reason=reason))
        else:
            by_group.setdefault(row.scope, []).append(row)
    unusable = {entry["row"] for entry in unknown_rooms}

    designations = (
        db.query(Designation, Teacher.full_name).join(Teacher, Teacher.ci == Designation.teacher_ci)
        .filter(Designation.academic_period == period, Designation.designation_type != "practice")
        .order_by(Designation.id).all()
    )
    matched: list[dict] = []
    without_row: list[dict] = []
    consumed: set[int] = set()
    for item, teacher_name in designations:
        semester = semester_number(item.semester)
        scope = (_fold(item.subject), semester, normalized_group(item.group_code))
        own = by_teacher.get((item.teacher_ci if by_ci else _name_id(teacher_name), scope), []) if semester else []
        if own:
            consumed.update(row.number for row in own)
            usable_own = [row for row in own if row.number not in unusable]
            codes = {usable(row).code for row in usable_own}
            if len(codes) > 1 or (codes and len(usable_own) < len(own)):
                unknown_rooms.append(own[0].listed(
                    group_code=scope[2], aula=" / ".join(dict.fromkeys(row.aula for row in own)),
                    reason=CONFLICTING_ROOMS.format(rows=", ".join(str(row.number) for row in own)),
                ))
                continue
            candidates = usable_own  # empty when every row of the designation names an unusable room
        else:
            candidates = by_group.get(scope, []) if semester else []
            if len({usable(row).code for row in candidates}) != 1:
                without_row.append({
                    "designation_id": item.id, "teacher_name": teacher_name, "subject": item.subject,
                    "group_code": item.group_code,
                })
                continue
            consumed.update(row.number for row in candidates)
        if not candidates:
            continue
        new = usable(candidates[0])
        matched.append({
            "designation_id": item.id, "teacher_ci": item.teacher_ci, "teacher_name": teacher_name,
            "subject": item.subject, "semester": item.semester, "group_code": item.group_code,
            "current_classroom": _room(by_id.get(item.classroom_id)), "new_classroom": _room(new),
            "changed": item.classroom_id != new.id,
        })

    unmatched = [
        row.listed(semester=row.semester, group_code=row.group, aula=row.aula)
        for row in rows if row.number not in consumed and row.number not in unusable
    ]
    unknown_rooms.sort(key=lambda entry: entry["row"])
    result = {
        "academic_period": period, "matched": matched, "unknown_rooms": unknown_rooms,
        "unmatched_rows": unmatched, "designations_without_row": without_row,
        "summary": {
            "matched": len(matched), "changed": sum(1 for entry in matched if entry["changed"]),
            "unknown_rooms": len(unknown_rooms), "unmatched_rows": len(unmatched),
            "designations_without_row": len(without_row),
        },
    }
    result["preview_digest"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def preview(db: Session, content: bytes) -> dict:
    return plan(db, content)


def apply(db: Session, content: bytes, digest: str) -> dict:
    """Set ``classroom_id`` of the designations the preview marked as changed; nothing else is written."""
    result = plan(db, content)
    if result["preview_digest"] != digest:
        raise StalePreview()
    new_room = {
        entry["designation_id"]: entry["new_classroom"]["id"] for entry in result["matched"] if entry["changed"]
    }
    if new_room:
        for item in db.query(Designation).filter(Designation.id.in_(new_room)).with_for_update():
            item.classroom_id = new_room[item.id]
        db.flush()
    return {
        "academic_period": result["academic_period"], "summary": result["summary"],
        "changed_designation_ids": sorted(new_room),
    }
