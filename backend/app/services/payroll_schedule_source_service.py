from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta
from types import SimpleNamespace
from typing import Literal

from sqlalchemy.orm import Session

from app.models.designation import Designation
from app.services.effective_schedule_service import EffectiveScheduleSlot, effective_schedule_slots


@dataclass(frozen=True)
class PayableScheduleSlot:
    date: date
    scheduled_start: time
    scheduled_end: time
    academic_hours: int


@dataclass
class PayrollScheduleSource:
    """Immutable, typed schedule evidence used by attendance and payroll."""

    source_kind: Literal["legacy", "published"]
    source_id: int
    teacher_ci: str
    subject: str
    group_code: str
    semester: str
    activity_kind: Literal["theory", "practice"]
    effective_from: date
    effective_to: date
    designation_id: int | None = None
    publication_id: int | None = None
    published_block_id: int | None = None
    published_assignment_id: int | None = None
    monthly_hours: int | None = None
    weekly_hours: int | None = None
    schedule: list[dict[str, object]] = field(default_factory=list)
    payable_slots: list[PayableScheduleSlot] = field(default_factory=list)

    @property
    def source_key(self) -> str:
        return f"{self.source_kind}:{self.source_id}"

    @property
    def rate_class(self) -> Literal["regular", "practice"]:
        return "practice" if self.activity_kind == "practice" else "regular"

    def designation_adapter(self) -> SimpleNamespace:
        """Expose the narrow legacy shape consumed by the established row calculator."""
        return SimpleNamespace(
            id=self.source_id,
            teacher_ci=self.teacher_ci,
            subject=self.subject,
            group_code=self.group_code,
            semester=self.semester,
            designation_type="practice" if self.activity_kind == "practice" else "regular",
            schedule_json=self.schedule,
            monthly_hours=self.monthly_hours,
            weekly_hours=self.weekly_hours,
            contract_start_date=self.effective_from,
            contract_end_date=self.effective_to,
        )


def _slot_schedule(slot: EffectiveScheduleSlot) -> dict[str, object]:
    return {
        "dia": slot.weekday,
        "hora_inicio": slot.start_time.strftime("%H:%M"),
        "hora_fin": slot.end_time.strftime("%H:%M"),
        "horas_academicas": slot.academic_hours,
    }


def payroll_schedule_sources(
    db: Session,
    *,
    academic_period: str,
    period_start: date,
    period_end: date,
    activity_kind: Literal["theory", "practice"],
) -> list[PayrollScheduleSource]:
    """Resolve published schedules per date with deterministic legacy fallback."""
    groups: dict[str, PayrollScheduleSource] = {}
    active_dates: dict[str, list[date]] = {}
    legacy_by_id = {
        item.id: item
        for item in db.query(Designation).filter(Designation.academic_period == academic_period).all()
    }
    current = period_start
    while current <= period_end:
        for slot in effective_schedule_slots(db, academic_period, current, include_practice=True):
            if slot.activity_type != activity_kind:
                continue
            key = f"{slot.source_type}:{slot.source_id}"
            source = groups.get(key)
            if source is None:
                legacy = legacy_by_id.get(slot.designation_id) if slot.designation_id is not None else None
                source = PayrollScheduleSource(
                    source_kind=slot.source_type,
                    source_id=slot.source_id,
                    teacher_ci=slot.teacher_ci,
                    subject=slot.subject,
                    group_code=slot.group_code,
                    semester=slot.semester,
                    activity_kind=activity_kind,
                    effective_from=current,
                    effective_to=current,
                    designation_id=slot.designation_id,
                    publication_id=slot.publication_id,
                    published_block_id=slot.published_block_id,
                    published_assignment_id=slot.published_assignment_id,
                    monthly_hours=int(legacy.monthly_hours or 0) if legacy else None,
                    weekly_hours=int(legacy.weekly_hours or 0) if legacy and legacy.weekly_hours is not None else None,
                )
                groups[key] = source
                active_dates[key] = []
            active_dates[key].append(current)
            schedule_item = _slot_schedule(slot)
            if schedule_item not in source.schedule:
                source.schedule.append(schedule_item)
            if slot.weekday == {
                0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
                4: "viernes", 5: "sabado", 6: "domingo",
            }[current.weekday()]:
                payable = PayableScheduleSlot(
                    date=current,
                    scheduled_start=slot.start_time,
                    scheduled_end=slot.end_time,
                    academic_hours=slot.academic_hours,
                )
                if payable not in source.payable_slots:
                    source.payable_slots.append(payable)
        current += timedelta(days=1)

    for key, source in groups.items():
        source.effective_from = min(active_dates[key])
        source.effective_to = max(active_dates[key])
        source.schedule.sort(key=lambda item: (str(item["dia"]), str(item["hora_inicio"])))
        source.payable_slots.sort(key=lambda item: (item.date, item.scheduled_start))
        # Published and partially selected legacy sources are paid by actual slots.
        if source.source_kind == "published" or source.effective_from > period_start or source.effective_to < period_end:
            source.monthly_hours = sum(item.academic_hours for item in source.payable_slots)

    published_scopes = {
        (item.subject.casefold().strip(), item.group_code.casefold().strip(), str(item.semester).casefold().strip())
        for item in groups.values()
        if item.source_kind == "published"
    }
    for designation in legacy_by_id.values():
        legacy_activity = "practice" if designation.designation_type == "practice" else "theory"
        key = f"legacy:{designation.id}"
        scope = (
            designation.subject.casefold().strip(),
            designation.group_code.casefold().strip(),
            str(designation.semester).casefold().strip(),
        )
        if legacy_activity != activity_kind or key in groups or scope in published_scopes:
            continue
        # Preserve the historical zero-pay row for an unmatched legacy contract
        # that does not intersect the requested period.
        groups[key] = PayrollScheduleSource(
            source_kind="legacy",
            source_id=designation.id,
            teacher_ci=designation.teacher_ci,
            subject=designation.subject,
            group_code=designation.group_code,
            semester=str(designation.semester),
            activity_kind=activity_kind,
            effective_from=period_start,
            effective_to=period_end,
            designation_id=designation.id,
            monthly_hours=0,
            weekly_hours=int(designation.weekly_hours or 0) if designation.weekly_hours is not None else None,
            schedule=[],
        )
    return sorted(
        groups.values(),
        key=lambda item: (item.teacher_ci, item.activity_kind, item.subject, item.group_code, item.source_key),
    )
