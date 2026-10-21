"""Conflicts and gaps of a weekly schedule (feature designation-module-v2, S8).

Works on the normalized ``ViewBlock`` rows of the schedule view, so the same report
covers the current schedule (legacy theory + published practice) and any draft.
Overlaps of up to ``TOLERANCE_MINUTES`` are classroom/teacher handovers, not clashes.
Theory and practice of the same subject and group at the same time are split groups:
reported as warnings. Nothing here writes.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from itertools import combinations

from sqlalchemy.orm import Session

from app.models.academic_management import Classroom
from app.services.academic_schedule_view_service import ViewBlock, schedule_blocks
from app.services.app_settings_service import get_academic_hour_minutes

TOLERANCE_MINUTES = 5
DAY_START = "06:30"
DAY_END = "23:05"
MIN_FREE_MINUTES = 45
CLASS_DAYS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado")


def _minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def _summary(block: ViewBlock) -> dict:
    return {
        "key": block.key, "semester": block.semester, "group_code": block.group_code,
        "subject_name": block.subject_name, "activity_type": block.activity_type,
        "start_time": block.start_time, "end_time": block.end_time,
        "teacher_ci": block.teacher_ci or None, "teacher_name": block.teacher_name,
        "classroom_code": block.classroom_code,
    }


def _clash_kinds(left: ViewBlock, right: ViewBlock) -> list[tuple[str, str]]:
    kinds = []
    if left.teacher_ci and left.teacher_ci == right.teacher_ci:
        kinds.append(("teacher", "conflict"))
    if left.semester == right.semester and left.group_code == right.group_code:
        split = left.subject_name == right.subject_name and left.activity_type != right.activity_type
        kinds.append(("split_group", "warning") if split else ("group", "conflict"))
    if left.classroom_code and left.classroom_code == right.classroom_code:
        kinds.append(("classroom", "conflict"))
    return kinds


def _clashes(blocks: list[ViewBlock]) -> list[dict]:
    by_day: dict[str, list[ViewBlock]] = defaultdict(list)
    for block in blocks:
        by_day[block.weekday].append(block)
    clashes = []
    for weekday, items in by_day.items():
        items.sort(key=lambda item: (item.start_time, item.key))
        for left, right in combinations(items, 2):
            start = max(_minutes(left.start_time), _minutes(right.start_time))
            end = min(_minutes(left.end_time), _minutes(right.end_time))
            if end - start <= TOLERANCE_MINUTES:
                continue
            for kind, severity in _clash_kinds(left, right):
                clashes.append({
                    "kind": kind, "severity": severity, "weekday": weekday,
                    "start_time": _clock(start), "end_time": _clock(end), "overlap_minutes": end - start,
                    "teacher_ci": left.teacher_ci if kind == "teacher" else None,
                    "group_code": left.group_code if kind in ("group", "split_group") else None,
                    "semester": left.semester if kind in ("group", "split_group") else None,
                    "classroom_code": left.classroom_code if kind == "classroom" else None,
                    "keys": [left.key, right.key],
                    "blocks": [_summary(left), _summary(right)],
                })
    day_order = {day: index for index, day in enumerate(CLASS_DAYS + ("domingo",))}
    clashes.sort(key=lambda item: (
        item["severity"] != "conflict", day_order.get(item["weekday"], 9), item["start_time"], item["kind"], item["keys"],
    ))
    return clashes


def _gaps(busy: list[tuple[int, int]]) -> list[tuple[int, int]]:
    cursor, day_end, gaps = _minutes(DAY_START), _minutes(DAY_END), []
    for start, end in sorted(busy):
        if start - cursor >= MIN_FREE_MINUTES:
            gaps.append((cursor, min(start, day_end)))
        cursor = max(cursor, end)
    if day_end - cursor >= MIN_FREE_MINUTES:
        gaps.append((cursor, day_end))
    return gaps


def _free_slots(keyed: dict[tuple, dict[str, list[tuple[int, int]]]], label) -> list[dict]:
    result = []
    for key in keyed:
        for weekday in CLASS_DAYS:
            for start, end in _gaps(keyed[key].get(weekday, [])):
                result.append({**label(key), "weekday": weekday, "start_time": _clock(start),
                               "end_time": _clock(end), "minutes": end - start})
    return result


def analyze(blocks: list[ViewBlock], *, rooms: list[str], load_threshold: float,
            academic_hour_minutes: int) -> dict:
    clashes = _clashes(blocks)
    unassigned = [_summary(block) for block in blocks if not block.teacher_ci]

    loads: dict[str, dict] = {}
    for block in blocks:
        if not block.teacher_ci:
            continue
        item = loads.setdefault(block.teacher_ci, {
            "teacher_ci": block.teacher_ci, "teacher_name": block.teacher_name, "weekly_minutes": 0, "blocks": 0,
        })
        item["weekly_minutes"] += _minutes(block.end_time) - _minutes(block.start_time)
        item["blocks"] += 1
    teacher_loads = []
    for item in loads.values():
        hours = round(item["weekly_minutes"] / academic_hour_minutes, 1)
        teacher_loads.append({**item, "weekly_hours": hours, "over_threshold": hours > load_threshold})
    teacher_loads.sort(key=lambda item: (-item["weekly_minutes"], item["teacher_ci"]))
    teacher_loads = [{key: item[key] for key in (
        "teacher_ci", "teacher_name", "weekly_minutes", "weekly_hours", "blocks", "over_threshold",
    )} for item in teacher_loads]

    group_busy: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    room_busy: dict[tuple, dict[str, list]] = {(code,): defaultdict(list) for code in sorted(rooms)}
    for block in blocks:
        span = (_minutes(block.start_time), _minutes(block.end_time))
        group_busy[(block.semester, block.group_code)][block.weekday].append(span)
        if (block.classroom_code,) in room_busy:
            room_busy[(block.classroom_code,)][block.weekday].append(span)
    ordered_groups = dict(sorted(group_busy.items(), key=lambda item: (item[0][0] is None, item[0][0] or 0, item[0][1])))

    return {
        "tolerance_minutes": TOLERANCE_MINUTES,
        "day_window": {"start_time": DAY_START, "end_time": DAY_END, "min_free_minutes": MIN_FREE_MINUTES},
        "load_threshold": load_threshold,
        "summary": {
            "conflicts": sum(item["severity"] == "conflict" for item in clashes),
            "warnings": sum(item["severity"] == "warning" for item in clashes),
            "unassigned": len(unassigned),
            "overloaded_teachers": sum(item["over_threshold"] for item in teacher_loads),
            "blocks": len(blocks),
            "blocks_without_room": sum(not block.classroom_code for block in blocks),
        },
        "clashes": clashes,
        "unassigned": unassigned,
        "teacher_loads": teacher_loads,
        "free_slots": {
            "groups": _free_slots(ordered_groups, lambda key: {"semester": key[0], "group_code": key[1]}),
            "rooms": _free_slots(room_busy, lambda key: {"classroom_code": key[0]}),
        },
    }


def schedule_conflicts(db: Session, *, academic_period: str, source: str, reference: date,
                       draft_id: int | None, load_threshold: float) -> dict:
    blocks = schedule_blocks(db, academic_period=academic_period, source=source,
                             reference=reference, draft_id=draft_id)
    rooms = [code for (code,) in db.query(Classroom.code).filter(
        Classroom.active.is_(True), Classroom.classroom_type.in_(("classroom", "laboratory")),
    )]
    report = analyze(blocks, rooms=rooms, load_threshold=load_threshold,
                     academic_hour_minutes=get_academic_hour_minutes(db))
    return {
        "academic_period": academic_period, "source": source, "reference_date": reference,
        "draft_id": draft_id if source == "draft" else None, **report,
    }

