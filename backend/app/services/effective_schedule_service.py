from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
import unicodedata
from typing import Literal

from sqlalchemy.orm import Session, joinedload

from app.models.academic_management import (
    block_paid_hours,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
)
from app.models.designation import Designation


@dataclass(frozen=True)
class EffectiveScheduleSlot:
    source_type: Literal["legacy", "published"]
    teacher_ci: str
    subject: str
    group_code: str
    semester: str
    activity_type: str
    weekday: str
    start_time: time
    end_time: time
    academic_hours: int
    designation_id: int | None = None
    published_block_id: int | None = None
    published_assignment_id: int | None = None
    publication_id: int | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    monthly_hours: int | None = None
    weekly_hours: int | None = None

    @property
    def source_id(self) -> int:
        source_id = self.designation_id if self.source_type == "legacy" else self.published_assignment_id
        if source_id is None:  # pragma: no cover - constructor invariant
            raise ValueError("Effective schedule source identity is missing")
        return source_id


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    return "".join(character for character in text if not unicodedata.combining(character))


def _legacy_activity(designation: Designation) -> str:
    return "practice" if designation.designation_type == "practice" else "theory"


_WEEKDAY_ALIASES = {
    "monday": "lunes", "lunes": "lunes",
    "tuesday": "martes", "martes": "martes",
    "wednesday": "miercoles", "miercoles": "miercoles",
    "thursday": "jueves", "jueves": "jueves",
    "friday": "viernes", "viernes": "viernes",
    "saturday": "sabado", "sabado": "sabado",
    "sunday": "domingo", "domingo": "domingo",
}


def _canonical_weekday(value: object) -> str:
    normalized = _normalize(value)
    return _WEEKDAY_ALIASES.get(normalized, normalized)


def _scope_key(subject: object, group: object, semester: object, activity: object) -> tuple[str, ...]:
    return tuple(_normalize(item) for item in (subject, group, semester, activity))


def canonical_weekday(value: object) -> str:
    """Expose the Spanish, accent-free weekday name used by effective schedule readers."""
    return _canonical_weekday(value)


def legacy_activity(designation: Designation) -> str:
    """Expose the canonical activity classification used by effective schedule readers."""
    return _legacy_activity(designation)


def schedule_scope_key(
    subject: object,
    group: object,
    semester: object,
    activity: object,
) -> tuple[str, ...]:
    """Expose the normalized authority scope shared by typed workload readers."""
    return _scope_key(subject, group, semester, activity)


@dataclass(frozen=True)
class _PreparedBlock:
    block: AcademicSchedulePublishedBlock
    scope_key: tuple[str, ...]
    weekday: str
    academic_hours: int


@dataclass(frozen=True)
class _PreparedPublication:
    publication: AcademicSchedulePublication
    blocks: tuple[_PreparedBlock, ...]


@dataclass(frozen=True)
class _PreparedDesignation:
    designation: Designation
    activity: str
    scope_key: tuple[str, ...]
    # Slots whose start/end parse; the rest are skipped exactly as the per-day reader did.
    slots: tuple[tuple[dict, time, time, str], ...]


@dataclass(frozen=True)
class LoadedSchedulePeriod:
    """Everything ``effective_schedule_slots`` reads for one academic period, loaded once."""

    academic_period: str
    # Same order as the per-day query: program, newest effective_from, sequence, id.
    publications: tuple[_PreparedPublication, ...]
    designations: tuple[_PreparedDesignation, ...]

    @property
    def designation_rows(self) -> list[Designation]:
        return [item.designation for item in self.designations]


def load_effective_schedule_period(db: Session, academic_period: str) -> LoadedSchedulePeriod:
    """Load every publication (with blocks and assignments) and designation of a period."""
    publications = db.query(AcademicSchedulePublication).options(
        joinedload(AcademicSchedulePublication.blocks)
        .joinedload(AcademicSchedulePublishedBlock.assignments)
    ).filter(
        AcademicSchedulePublication.academic_period == academic_period,
    ).order_by(
        AcademicSchedulePublication.program_id,
        AcademicSchedulePublication.effective_from.desc(),
        AcademicSchedulePublication.sequence.desc(),
        AcademicSchedulePublication.id.desc(),
    ).all()
    prepared_publications = tuple(
        _PreparedPublication(
            publication=publication,
            blocks=tuple(
                _PreparedBlock(
                    block=block,
                    scope_key=_scope_key(
                        block.subject_name, block.group_code, block.semester, block.activity_type
                    ),
                    weekday=_canonical_weekday(block.weekday),
                    academic_hours=block_paid_hours(block.start_time, block.end_time, block.academic_hours),
                )
                for block in publication.blocks
            ),
        )
        for publication in publications
    )
    prepared_designations = []
    for designation in db.query(Designation).filter(
        Designation.academic_period == academic_period,
    ).all():
        activity = _legacy_activity(designation)
        slots = []
        for slot in designation.schedule_json or []:
            try:
                start = time.fromisoformat(str(slot["hora_inicio"]))
                end = time.fromisoformat(str(slot["hora_fin"]))
            except (KeyError, TypeError, ValueError):
                continue
            slots.append((slot, start, end, _canonical_weekday(slot.get("dia", ""))))
        prepared_designations.append(_PreparedDesignation(
            designation=designation,
            activity=activity,
            scope_key=_scope_key(
                designation.subject, designation.group_code, designation.semester, activity
            ),
            slots=tuple(slots),
        ))
    return LoadedSchedulePeriod(
        academic_period=academic_period,
        publications=prepared_publications,
        designations=tuple(prepared_designations),
    )


def resolve_effective_schedule_slots(
    loaded: LoadedSchedulePeriod,
    target_date: date,
    include_practice: bool = False,
) -> list[EffectiveScheduleSlot]:
    """Resolve one day from an already loaded period without touching the database.

    Same rules as ``effective_schedule_slots``: the effective publication of each
    program on ``target_date`` wins; legacy designations fill the tuples it does not
    represent.
    """
    effective_by_program: dict[int, _PreparedPublication] = {}
    for prepared in loaded.publications:
        if prepared.publication.effective_from <= target_date:
            effective_by_program.setdefault(prepared.publication.program_id, prepared)

    published: list[EffectiveScheduleSlot] = []
    represented: set[tuple[str, ...]] = set()
    for prepared in effective_by_program.values():
        publication = prepared.publication
        for prepared_block in prepared.blocks:
            block = prepared_block.block
            if block.activity_type == "practice" and not include_practice:
                continue
            assignment = next((
                item for item in block.assignments
                if item.effective_from <= target_date
                and (item.effective_to is None or item.effective_to >= target_date)
            ), None)
            if assignment is None:
                continue
            represented.add(prepared_block.scope_key)
            published.append(EffectiveScheduleSlot(
                source_type="published",
                teacher_ci=assignment.teacher_ci,
                subject=block.subject_name,
                group_code=block.group_code,
                semester=str(block.semester),
                activity_type=block.activity_type,
                weekday=prepared_block.weekday,
                start_time=block.start_time,
                end_time=block.end_time,
                academic_hours=prepared_block.academic_hours,
                published_block_id=block.id,
                published_assignment_id=assignment.id,
                publication_id=publication.id,
                effective_from=max(publication.effective_from, assignment.effective_from),
                effective_to=assignment.effective_to,
            ))

    legacy: list[EffectiveScheduleSlot] = []
    for prepared_designation in loaded.designations:
        designation = prepared_designation.designation
        activity = prepared_designation.activity
        if activity == "practice" and not include_practice:
            continue
        if prepared_designation.scope_key in represented:
            continue
        if designation.contract_start_date and target_date < designation.contract_start_date:
            continue
        if designation.contract_end_date and target_date > designation.contract_end_date:
            continue
        for slot, start, end, weekday in prepared_designation.slots:
            legacy.append(EffectiveScheduleSlot(
                source_type="legacy",
                teacher_ci=designation.teacher_ci,
                subject=designation.subject,
                group_code=designation.group_code,
                semester=designation.semester,
                activity_type=activity,
                weekday=weekday,
                start_time=start,
                end_time=end,
                academic_hours=int(slot.get("horas_academicas", 0)),
                designation_id=designation.id,
                effective_from=designation.contract_start_date,
                effective_to=designation.contract_end_date,
                monthly_hours=designation.monthly_hours,
                weekly_hours=designation.weekly_hours,
            ))
    return sorted(
        [*published, *legacy],
        key=lambda item: (item.weekday, item.start_time, item.teacher_ci, item.source_type),
    )


def effective_schedule_slots(
    db: Session,
    academic_period: str,
    target_date: date,
    include_practice: bool = False,
) -> list[EffectiveScheduleSlot]:
    """Return immutable published slots plus deterministic legacy fallback.

    A publication represents its program/period scope. Because legacy designations
    do not carry a program ID, a legacy designation is suppressed only when its
    normalized subject/group/semester/activity tuple is represented by an effective
    publication. Other legacy tuples remain available as fallback.

    This adapter is intentionally read-only in increment 4. Persisting attendance
    against published rows requires a separate dual-source AttendanceRecord
    migration and is not simulated with synthetic Designation rows.

    Callers resolving many days of one period should call
    ``load_effective_schedule_period`` once and ``resolve_effective_schedule_slots``
    per day instead of this per-day query.
    """
    return resolve_effective_schedule_slots(
        load_effective_schedule_period(db, academic_period), target_date, include_practice
    )
