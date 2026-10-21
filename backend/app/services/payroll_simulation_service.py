"""Payroll base per teacher (hours and Bs before attendance discounts) and what-if simulations.

Simulations write the hypothetical change inside a savepoint, read the real payroll
schedule source, and always roll the savepoint back, so nothing is persisted.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.teacher import Teacher
from app.services import app_settings_service
from app.services import academic_schedule_publication_service as publication_service
from app.services.payroll_schedule_source_service import payroll_schedule_sources

ACTIVITIES = ("theory", "practice")
HoursKey = tuple[str, str]  # (teacher_ci, activity)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def hours_by_teacher(
    db: Session,
    academic_period: str,
    period_start: date,
    period_end: date,
    activities: Iterable[str] = ACTIVITIES,
    teachers: set[str] | None = None,
) -> dict[HoursKey, int]:
    totals: dict[HoursKey, int] = defaultdict(int)
    for activity in sorted(set(activities)):
        for source in payroll_schedule_sources(
            db, academic_period=academic_period, period_start=period_start,
            period_end=period_end, activity_kind=activity,
        ):
            if teachers is None or source.teacher_ci in teachers:
                totals[(source.teacher_ci, activity)] += int(source.monthly_hours or 0)
    return dict(totals)


def teacher_impacts(
    db: Session, before: dict[HoursKey, int], after: dict[HoursKey, int], keys: Iterable[HoursKey]
) -> list[dict]:
    rates = {
        "theory": app_settings_service.get_hourly_rate(db),
        "practice": app_settings_service.get_practice_hourly_rate(db),
    }
    keys = sorted(set(keys))
    names = {
        teacher.ci: teacher.full_name
        for teacher in db.query(Teacher).filter(Teacher.ci.in_({ci for ci, _ in keys})).all()
    } if keys else {}
    impacts = []
    for ci, activity in keys:
        hours_before, hours_after = before.get((ci, activity), 0), after.get((ci, activity), 0)
        impacts.append({
            "teacher_ci": ci,
            "teacher_name": names.get(ci, ci),
            "activity": activity,
            "hours_before": hours_before,
            "hours_after": hours_after,
            "amount_before": round(hours_before * rates[activity], 2),
            "amount_after": round(hours_after * rates[activity], 2),
        })
    return impacts


def simulate_publication(db: Session, draft_id: int, effective_from: date, month: int, year: int) -> dict:
    """Bs per teacher for a month if the draft were published from ``effective_from``."""
    draft = publication_service._draft_graph(db, draft_id, lock=False)
    start, end = month_bounds(year, month)
    before = hours_by_teacher(db, draft.academic_period, start, end)
    savepoint = db.begin_nested()
    try:
        sequence = publication_service._next_sequence(db, draft, effective_from)
        publication_service._materialize_publication(db, draft, effective_from, sequence, "simulation", None)
        after = hours_by_teacher(db, draft.academic_period, start, end)
    finally:
        savepoint.rollback()
    changed = [key for key in set(before) | set(after) if before.get(key, 0) != after.get(key, 0)]
    teachers = teacher_impacts(db, before, after, changed)
    return {
        "draft_id": draft_id,
        "effective_from": effective_from,
        "month": month,
        "year": year,
        "teachers": teachers,
        "total_before": round(sum(item["amount_before"] for item in teachers), 2),
        "total_after": round(sum(item["amount_after"] for item in teachers), 2),
    }
