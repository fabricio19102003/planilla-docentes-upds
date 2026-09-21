from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.designation import Designation
from app.services.contract_ledger_service import academic_period_bounds
from app.services.effective_schedule_service import (
    EffectiveScheduleSlot,
    effective_schedule_slots,
    legacy_activity,
    schedule_scope_key,
)


_DISPLAY_WEEKDAYS = {
    "lunes": "Lunes",
    "martes": "Martes",
    "miercoles": "Miércoles",
    "jueves": "Jueves",
    "viernes": "Viernes",
    "sabado": "Sábado",
    "domingo": "Domingo",
}


@dataclass(frozen=True)
class WorkloadSnapshot:
    """Typed read model for one effective legacy or published workload source."""

    source_kind: str
    source_id: int
    teacher_ci: str
    designation_id: int | None
    publication_id: int | None
    published_block_id: int | None
    published_assignment_id: int | None
    activity_kind: str
    subject: str
    group_code: str
    semester: str
    effective_from: date | None
    effective_to: date | None
    source_monthly_hours: int | None
    source_weekly_hours: int | None
    schedule_json: tuple[dict[str, object], ...]

    @property
    def source_key(self) -> str:
        return f"{self.source_kind}:{self.source_id}"

    @property
    def weekly_hours(self) -> int:
        if self.source_weekly_hours is not None:
            return self.source_weekly_hours
        return sum(int(slot.get("horas_academicas", 0) or 0) for slot in self.schedule_json)

    @property
    def monthly_hours(self) -> int | None:
        return self.source_monthly_hours


def active_period_effective_date(academic_period: str, today: date | None = None) -> date:
    """Clamp today to the configured period so stale settings still have deterministic semantics."""
    period_start, period_end = academic_period_bounds(academic_period)
    current = today or date.today()
    return min(max(current, period_start), period_end)


def effective_workloads(
    db: Session,
    *,
    academic_period: str,
    target_date: date,
    teacher_ci: str | None = None,
    activity_kind: str | None = None,
) -> list[WorkloadSnapshot]:
    slots = effective_schedule_slots(
        db,
        academic_period,
        target_date,
        include_practice=True,
    )
    selected = [
        slot
        for slot in slots
        if (teacher_ci is None or slot.teacher_ci == teacher_ci)
        and (activity_kind is None or slot.activity_type == activity_kind)
    ]
    workloads = _group_slots(selected)
    existing_legacy_ids = {
        item.designation_id for item in workloads if item.designation_id is not None
    }
    represented_scopes = {
        schedule_scope_key(item.subject, item.group_code, item.semester, item.activity_kind)
        for item in workloads
        if item.source_kind == "published"
    }
    query = db.query(Designation).filter(Designation.academic_period == academic_period)
    if teacher_ci is not None:
        query = query.filter(Designation.teacher_ci == teacher_ci)
    for designation in query.all():
        activity = legacy_activity(designation)
        if activity_kind is not None and activity != activity_kind:
            continue
        if designation.id in existing_legacy_ids:
            continue
        if schedule_scope_key(
            designation.subject, designation.group_code, designation.semester, activity
        ) in represented_scopes:
            continue
        if designation.contract_start_date and target_date < designation.contract_start_date:
            continue
        if designation.contract_end_date and target_date > designation.contract_end_date:
            continue
        workloads.append(WorkloadSnapshot(
            source_kind="legacy",
            source_id=designation.id,
            teacher_ci=designation.teacher_ci,
            designation_id=designation.id,
            publication_id=None,
            published_block_id=None,
            published_assignment_id=None,
            activity_kind=activity,
            subject=designation.subject,
            group_code=designation.group_code,
            semester=str(designation.semester),
            effective_from=designation.contract_start_date,
            effective_to=designation.contract_end_date,
            source_monthly_hours=designation.monthly_hours,
            source_weekly_hours=designation.weekly_hours,
            schedule_json=(),
        ))
    return _sort_workloads(workloads)


def _group_slots(slots: Iterable[EffectiveScheduleSlot]) -> list[WorkloadSnapshot]:
    grouped: dict[tuple[object, ...], list[EffectiveScheduleSlot]] = {}
    for slot in slots:
        key = (
            slot.source_type,
            slot.source_id,
            slot.teacher_ci,
            slot.subject,
            slot.group_code,
            slot.semester,
            slot.activity_type,
            slot.effective_from,
            slot.effective_to,
        )
        grouped.setdefault(key, []).append(slot)

    workloads: list[WorkloadSnapshot] = []
    for key, source_slots in grouped.items():
        first = source_slots[0]
        schedule = tuple(sorted((
            {
                "dia": _DISPLAY_WEEKDAYS.get(slot.weekday, slot.weekday),
                "hora_inicio": slot.start_time.strftime("%H:%M"),
                "hora_fin": slot.end_time.strftime("%H:%M"),
                "horas_academicas": slot.academic_hours,
            }
            for slot in source_slots
        ), key=lambda item: (str(item["dia"]), str(item["hora_inicio"]), str(item["hora_fin"]))))
        workloads.append(WorkloadSnapshot(
            source_kind=first.source_type,
            source_id=first.source_id,
            teacher_ci=first.teacher_ci,
            designation_id=first.designation_id,
            publication_id=first.publication_id,
            published_block_id=first.published_block_id,
            published_assignment_id=first.published_assignment_id,
            activity_kind=first.activity_type,
            subject=first.subject,
            group_code=first.group_code,
            semester=str(first.semester),
            effective_from=first.effective_from,
            effective_to=first.effective_to,
            source_monthly_hours=first.monthly_hours,
            source_weekly_hours=first.weekly_hours,
            schedule_json=schedule,
        ))
    return _sort_workloads(workloads)


def _sort_workloads(workloads: Iterable[WorkloadSnapshot]) -> list[WorkloadSnapshot]:
    return sorted(
        workloads,
        key=lambda item: (
            item.subject.casefold(), item.group_code.casefold(), item.activity_kind, item.source_key,
        ),
    )
