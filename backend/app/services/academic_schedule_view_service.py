"""Read model: weekly schedule blocks by semester and group.

``current`` is the schedule payroll uses (``effective_schedule_slots``: legacy theory
designations plus the latest practice publication). ``draft`` is a schedule draft with the
teacher assigned on the reference date. Nothing here writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import re
import unicodedata
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.academic_management import (
    AcademicScheduleDraft,
    AcademicSchedulePublishedBlock,
    AcademicSubject,
)
from app.models.teacher import Teacher
from app.services import academic_management_service as academic
from app.services.effective_schedule_service import canonical_weekday, effective_schedule_slots
from app.utils.academic_semester import semester_number
from app.utils.helpers import normalize_group_code

Source = Literal["current", "draft"]
WEEKDAYS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")


@dataclass(frozen=True)
class ViewBlock:
    key: str
    semester: int | None
    group_code: str
    subject_code: str | None
    subject_name: str
    activity_type: str
    weekday: str
    start_time: str
    end_time: str
    teacher_ci: str
    teacher_name: str | None
    classroom_code: str | None
    classroom_name: str | None
    source_type: str


def normalized_group(value: object) -> str:
    text = str(value or "").strip()
    return str(normalize_group_code(text) or "").strip().upper()


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip()


def _group_sort(code: str) -> tuple:
    match = re.fullmatch(r"([A-Z]+)-(\d+)", code)
    return (match.group(1), int(match.group(2)), code) if match else (code, 0, code)


def _block_sort(block: ViewBlock) -> tuple:
    weekday = WEEKDAYS.index(block.weekday) if block.weekday in WEEKDAYS else len(WEEKDAYS)
    return (
        block.semester is None, block.semester or 0, _group_sort(block.group_code),
        weekday, block.start_time, block.subject_name,
    )


def _subject_codes(db: Session) -> dict[str, str | None]:
    codes: dict[str, str | None] = {}
    for subject in db.query(AcademicSubject).all():
        key = _fold(subject.name)
        codes[key] = None if key in codes else subject.code
    return codes


def _teacher_names(db: Session, cis: set[str]) -> dict[str, str]:
    if not cis:
        return {}
    return {ci: name for ci, name in db.query(Teacher.ci, Teacher.full_name).filter(Teacher.ci.in_(cis))}


def _current_blocks(db: Session, academic_period: str, reference: date) -> list[ViewBlock]:
    slots = effective_schedule_slots(db, academic_period, reference, include_practice=True)
    published_ids = {slot.published_block_id for slot in slots if slot.published_block_id}
    published = {
        block.id: block
        for block in db.query(AcademicSchedulePublishedBlock).filter(
            AcademicSchedulePublishedBlock.id.in_(published_ids)
        )
    } if published_ids else {}
    codes = _subject_codes(db)
    names = _teacher_names(db, {slot.teacher_ci for slot in slots})
    blocks = []
    for slot in slots:
        start, end = slot.start_time.strftime("%H:%M"), slot.end_time.strftime("%H:%M")
        source = published.get(slot.published_block_id) if slot.published_block_id else None
        identity = slot.published_assignment_id if source else slot.designation_id
        blocks.append(ViewBlock(
            key=f"{slot.source_type}:{identity}:{slot.weekday}:{start}",
            semester=semester_number(slot.semester),
            group_code=normalized_group(slot.group_code),
            subject_code=source.subject_code if source else codes.get(_fold(slot.subject)),
            subject_name=slot.subject,
            activity_type=slot.activity_type,
            weekday=slot.weekday,
            start_time=start,
            end_time=end,
            teacher_ci=slot.teacher_ci,
            teacher_name=names.get(slot.teacher_ci),
            classroom_code=source.classroom_code if source else None,
            classroom_name=source.classroom_name if source else None,
            source_type=slot.source_type,
        ))
    return blocks


def _draft_blocks(db: Session, draft_id: int, reference: date) -> list[ViewBlock]:
    if db.get(AcademicScheduleDraft, draft_id) is None:
        raise HTTPException(404, detail="No se encontró el borrador de horario solicitado.")
    rows = academic._schedule_block_query(db).filter_by(draft_id=draft_id).all()
    current = {}
    for block in rows:
        active = [
            item for item in block.assignments
            if item.effective_from <= reference and (item.effective_to is None or reference <= item.effective_to)
        ]
        current[block.id] = active[0].teacher_ci if len(active) == 1 else ""
    names = _teacher_names(db, {ci for ci in current.values() if ci})
    blocks = []
    for block in rows:
        start, end = block.start_time.strftime("%H:%M"), block.end_time.strftime("%H:%M")
        teacher_ci = current[block.id]
        blocks.append(ViewBlock(
            key=f"draft:{block.id}",
            semester=semester_number(block.group.semester),
            group_code=normalized_group(block.group.code),
            subject_code=block.offering.subject.code,
            subject_name=block.offering.subject.name,
            activity_type=block.activity_type,
            weekday=canonical_weekday(block.weekday),
            start_time=start,
            end_time=end,
            teacher_ci=teacher_ci,
            teacher_name=names.get(teacher_ci),
            classroom_code=block.classroom.code,
            classroom_name=block.classroom.name,
            source_type="draft",
        ))
    return blocks


def schedule_view(
    db: Session,
    *,
    academic_period: str,
    source: Source,
    reference: date,
    draft_id: int | None = None,
    semester: int | None = None,
    group: str | None = None,
) -> dict:
    if source == "draft":
        if draft_id is None:
            raise HTTPException(422, detail="Seleccione el borrador que desea consultar.")
        blocks = _draft_blocks(db, draft_id, reference)
    else:
        blocks = _current_blocks(db, academic_period, reference)

    groups: dict[int | None, set[str]] = {}
    for block in blocks:
        groups.setdefault(block.semester, set()).add(block.group_code)
    semesters = [
        {"semester": key, "groups": sorted(values, key=_group_sort)}
        for key, values in sorted(groups.items(), key=lambda item: (item[0] is None, item[0] or 0))
    ]
    wanted_group = normalized_group(group) if group else None
    selected = [
        block for block in blocks
        if (semester is None or block.semester == semester)
        and (wanted_group is None or block.group_code == wanted_group)
    ]
    return {
        "academic_period": academic_period,
        "source": source,
        "reference_date": reference,
        "draft_id": draft_id if source == "draft" else None,
        "semesters": semesters,
        "blocks": [asdict(block) for block in sorted(selected, key=_block_sort)],
    }
