"""How many groups to open per semester and shift, from the re-enrollment requests of a window (academic phase 3, S4)."""
from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.models.academic_management import AcademicGroup
from app.models.student_portal import ReenrollmentRequest, ReenrollmentRequestItem, ReenrollmentWindow
from app.services import app_settings_service
from app.services.reenrollment import HOLDING_STATUSES, window_payload

SHIFT_ORDER = {"M": 0, "T": 1, "N": 2}


def _difference(suggested: int, existing: int) -> tuple[int, str, str]:
    difference = suggested - existing
    if difference > 0:
        return difference, "faltan", "Falta 1 grupo" if difference == 1 else f"Faltan {difference} grupos"
    if difference < 0:
        return difference, "sobran", "Sobra 1 grupo" if difference == -1 else f"Sobran {-difference} grupos"
    return 0, "correcto", "Correcto"


def _sort_key(key: tuple[int, str]) -> tuple[int, int, str]:
    semester, shift = key
    return semester, SHIFT_ORDER.get(shift, len(SHIFT_ORDER)), shift


def compute(db: Session, window: ReenrollmentWindow) -> dict[str, Any]:
    size = app_settings_service.get_default_group_size(db)
    main = aliased(AcademicGroup)

    requests: dict[tuple[int, str], int] = {
        (semester, shift): count
        for semester, shift, count in db.query(main.semester, main.shift, func.count(ReenrollmentRequest.id))
        .join(main, main.id == ReenrollmentRequest.main_group_id)
        .filter(ReenrollmentRequest.window_id == window.id, ReenrollmentRequest.status.in_(HOLDING_STATUSES))
        .group_by(main.semester, main.shift)
    }

    # Retakers choose groups through items. They only inform: a student whose main group is already in the
    # same semester and shift is a request there, not a retaker.
    retakers: dict[tuple[int, str], set[int]] = {}
    for request_id, semester, shift, main_semester, main_shift in (
        db.query(ReenrollmentRequest.id, AcademicGroup.semester, AcademicGroup.shift, main.semester, main.shift)
        .join(ReenrollmentRequestItem, ReenrollmentRequestItem.request_id == ReenrollmentRequest.id)
        .join(AcademicGroup, AcademicGroup.id == ReenrollmentRequestItem.group_id)
        .join(main, main.id == ReenrollmentRequest.main_group_id)
        .filter(ReenrollmentRequest.window_id == window.id, ReenrollmentRequest.status.in_(HOLDING_STATUSES))
    ):
        if (semester, shift) != (main_semester, main_shift):
            retakers.setdefault((semester, shift), set()).add(request_id)

    existing: dict[tuple[int, str], dict[str, int]] = {}
    for group in db.query(AcademicGroup).filter(
        AcademicGroup.academic_period == window.term_code, AcademicGroup.active.is_(True)
    ):
        entry = existing.setdefault((group.semester, group.shift), {"groups": 0, "capacity": 0, "no_capacity": 0})
        entry["groups"] += 1
        if group.expected_size is None:
            entry["no_capacity"] += 1
        else:
            entry["capacity"] += group.expected_size

    rows = []
    for key in sorted({*requests, *retakers, *existing}, key=_sort_key):
        semester, shift = key
        count = requests.get(key, 0)
        suggested = ceil(count / size)
        groups = existing.get(key, {"groups": 0, "capacity": 0, "no_capacity": 0})
        difference, status, label = _difference(suggested, groups["groups"])
        rows.append({
            "semester": semester, "shift": shift, "requests": count, "retakers": len(retakers.get(key, ())),
            "suggested_groups": suggested, "existing_groups": groups["groups"],
            "existing_capacity": groups["capacity"], "groups_without_capacity": groups["no_capacity"],
            "difference": difference, "status": status, "label": label,
        })

    totals = {
        field: sum(row[field] for row in rows)
        for field in ("requests", "retakers", "suggested_groups", "existing_groups", "existing_capacity",
                      "groups_without_capacity")
    }
    totals["missing_groups"] = sum(row["difference"] for row in rows if row["difference"] > 0)
    totals["leftover_groups"] = -sum(row["difference"] for row in rows if row["difference"] < 0)
    return {"window": window_payload(window), "group_size": size, "rows": rows, "totals": totals}


def empty(db: Session) -> dict[str, Any]:
    totals = dict.fromkeys(
        ("requests", "retakers", "suggested_groups", "existing_groups", "existing_capacity",
         "groups_without_capacity", "missing_groups", "leftover_groups"), 0)
    return {"window": None, "group_size": app_settings_service.get_default_group_size(db), "rows": [],
            "totals": totals}
