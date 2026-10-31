"""Single-designation management for admins ("Designaciones" page).

Designations feed attendance, payroll and contracts, so every write is guarded:
months already paid (approved planilla or published billing) cannot change, dates
fixed by an issued contract stay fixed, and only designations nobody has used yet
can be deleted. Everything else is "finalized" by shortening its end date, which
already cuts attendance and payroll per day.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.billing_publication import BillingPublication
from app.models.contract import ContractLine
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.schemas.designation_admin import (
    DesignationActions,
    DesignationActionState,
    DesignationAdminItem,
    DesignationAdminList,
    DesignationAdminMutation,
    DesignationWriteRequest,
)
from app.schemas.designation_change import DesignationChangeBlocker, DesignationChangeRegeneration
from app.services import app_settings_service
from app.services.contract_ledger_service import ContractIssuanceError, academic_period_bounds
from app.services.designation_change_service import PRACTICE_PRESENT, REGULAR_PRESENT
from app.services.designation_import_service import PERIOD_RE, _canonical_schedule
from app.services.designation_loader import DesignationLoader
from app.services.payroll_simulation_service import month_bounds
from app.utils.helpers import normalize_group_code

KIND_LABEL = {"regular": "teoría", "practice": "práctica"}
CONTRACT_DATES_LOCKED = (
    "Las fechas quedaron fijadas en el contrato emitido. Para cambiarlas, emití una adenda desde Contratos."
)
CONTRACT_FINALIZE_WARNING = "El contrato emitido no cambia; si corresponde, emití una adenda desde Contratos."
PAID_MESSAGE = "No se puede guardar porque ya se pagó con estos datos."
DUPLICATE_MESSAGE = "Ya existe una designación de esa materia, semestre y grupo para este docente en el período."
DATE_ORDER_ERROR = "La fecha de fin no puede ser anterior a la fecha de inicio."
TRACKED_FIELDS = (
    "teacher_ci", "subject", "semester", "group_code", "designation_type", "schedule_json", "monthly_hours",
    "semester_hours", "weekly_hours", "weekly_hours_calculated", "schedule_raw", "contract_start_date",
    "contract_end_date",
)
DATE_FIELDS = {"contract_start_date", "contract_end_date"}


class DesignationNotFound(Exception):
    pass


class DesignationInvalid(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class DesignationBlocked(Exception):
    def __init__(self, message: str, blockers: list[DesignationChangeBlocker]):
        super().__init__(message)
        self.message = message
        self.blockers = blockers


def _blocker(code: str, message: str, dates: list[date] | None = None) -> DesignationChangeBlocker:
    return DesignationChangeBlocker(code=code, message=message, dates=dates or [])


def _kind(value: str | None) -> str:
    return "practice" if value == "practice" else "regular"


def _window(period: str, start: date | None, end: date | None) -> tuple[date, date]:
    try:
        period_start, period_end = academic_period_bounds(period)
    except ContractIssuanceError:
        period_start, period_end = date.min, date.max
    return start or period_start, end or period_end


@dataclass
class _PayrollIndex:
    """Payroll months loaded once so a whole list can be checked without N+1 queries."""

    outputs: dict[str, list[Any]] = field(default_factory=dict)
    publications: dict[str, list[BillingPublication]] = field(default_factory=dict)

    @classmethod
    def load(cls, db: Session) -> "_PayrollIndex":
        index = cls()
        for kind, model in (("regular", PlanillaOutput), ("practice", PracticePlanillaOutput)):
            index.outputs[kind] = db.query(model).order_by(model.year, model.month).all()
            index.publications[kind] = (
                db.query(BillingPublication)
                .filter(BillingPublication.planilla_type == kind, BillingPublication.status == "published")
                .order_by(BillingPublication.year, BillingPublication.month)
                .all()
            )
        return index

    def check(
        self, kind: str, start: date, end: date
    ) -> tuple[list[DesignationChangeBlocker], list[DesignationChangeRegeneration]]:
        blockers: list[DesignationChangeBlocker] = []
        regenerate: list[DesignationChangeRegeneration] = []
        if end < start:
            return blockers, regenerate
        label = KIND_LABEL[kind]
        for output in self.outputs.get(kind, []):
            month_start, month_end = month_bounds(output.year, output.month)
            if (output.end_date or month_end) < start or (output.start_date or month_start) > end:
                continue
            if output.status == "approved":
                blockers.append(_blocker(
                    "payroll_approved", f"La planilla de {label} {output.month}/{output.year} ya está aprobada.",
                ))
            else:
                regenerate.append(DesignationChangeRegeneration(
                    planilla=kind, month=output.month, year=output.year, status=output.status,
                ))
        for publication in self.publications.get(kind, []):
            month_start, month_end = month_bounds(publication.year, publication.month)
            if month_end < start or month_start > end:
                continue
            blockers.append(_blocker(
                "billing_published",
                f"La facturación de {label} {publication.month}/{publication.year} ya está publicada.",
            ))
        return blockers, regenerate

    def override_ids(self) -> set[int]:
        """Designation ids that a stored payment override points at (keys `ci:id` or `ci:legacy:id`)."""
        ids: set[int] = set()
        for outputs in self.outputs.values():
            for output in outputs:
                for key in (output.payment_overrides_json or {}):
                    parts = str(key).split(":")
                    if len(parts) == 3 and parts[1] == "legacy" and parts[2].isdigit():
                        ids.add(int(parts[2]))
                    elif len(parts) == 2 and parts[1].isdigit():
                        ids.add(int(parts[1]))
        return ids


@dataclass
class _Usage:
    contracts: set[int]
    attendance: dict[int, int]
    overrides: set[int]
    payroll: _PayrollIndex


def _usage(db: Session, ids: list[int]) -> _Usage:
    payroll = _PayrollIndex.load(db)
    if not ids:
        return _Usage(set(), {}, set(), payroll)
    contracts = {
        row[0]
        for row in db.query(ContractLine.designation_id).filter(ContractLine.designation_id.in_(ids)).distinct()
    }
    attendance: dict[int, int] = {}
    for model in (AttendanceRecord, PracticeAttendanceLog):
        rows = (
            db.query(model.designation_id, func.count(model.id))
            .filter(model.designation_id.in_(ids))
            .group_by(model.designation_id)
        )
        for designation_id, count in rows:
            attendance[designation_id] = attendance.get(designation_id, 0) + count
    return _Usage(contracts, attendance, payroll.override_ids(), payroll)


def _status(item: Designation) -> str:
    return "finalized" if item.contract_end_date is not None and item.contract_end_date < date.today() else "active"


def _lock(usage: _Usage, item: Designation) -> tuple[list[DesignationChangeBlocker], list[DesignationChangeRegeneration]]:
    start, end = _window(item.academic_period, item.contract_start_date, item.contract_end_date)
    return usage.payroll.check(_kind(item.designation_type), start, end)


def _delete_blockers(usage: _Usage, item: Designation) -> list[DesignationChangeBlocker]:
    blockers: list[DesignationChangeBlocker] = []
    if usage.attendance.get(item.id):
        blockers.append(_blocker("has_attendance", "Tiene asistencia registrada; usá Finalizar."))
    if item.id in usage.contracts:
        blockers.append(_blocker("has_contract", "Ya tiene un contrato emitido; usá Finalizar."))
    if item.id in usage.overrides:
        blockers.append(_blocker(
            "payment_override", "Una planilla tiene un monto manual para esta designación; usá Finalizar.",
        ))
    blockers.extend(_lock(usage, item)[0])
    return blockers


def _state(reason: str | None) -> DesignationActionState:
    return DesignationActionState(allowed=reason is None, reason=reason)


def _item(usage: _Usage, item: Designation, teacher_name: str) -> DesignationAdminItem:
    lock_blockers = _lock(usage, item)[0]
    lock_reason = lock_blockers[0].message if lock_blockers else None
    has_contract = item.id in usage.contracts
    status = _status(item)
    delete_blockers = _delete_blockers(usage, item)
    actions = DesignationActions(
        edit=_state(lock_reason),
        edit_dates=_state(lock_reason or (CONTRACT_DATES_LOCKED if has_contract else None)),
        finalize=_state("La designación ya está finalizada." if status == "finalized" else None),
        delete=_state(delete_blockers[0].message if delete_blockers else None),
    )
    return DesignationAdminItem.model_validate({
        **{name: getattr(item, name) for name in (
            "id", "teacher_ci", "subject", "semester", "group_code", "academic_period", "designation_type",
            "schedule_json", "semester_hours", "monthly_hours", "weekly_hours", "weekly_hours_calculated",
            "schedule_raw", "contract_start_date", "contract_end_date", "created_at",
        )},
        "teacher_name": teacher_name,
        "status": status,
        "has_contract": has_contract,
        "attendance_count": usage.attendance.get(item.id, 0),
        "actions": actions,
    })


def _period_key(period: str) -> tuple[int, int]:
    match = re.fullmatch(r"(I{1,2})/(\d{4})", period)
    return (int(match.group(2)), len(match.group(1))) if match else (0, 0)


def list_designations(
    db: Session,
    *,
    academic_period: str | None = None,
    teacher_ci: str | None = None,
    q: str | None = None,
    semester: str | None = None,
    designation_type: str | None = None,
    status: str = "all",
) -> DesignationAdminList:
    period = academic_period or app_settings_service.get_active_academic_period(db)
    query = (
        db.query(Designation, Teacher.full_name)
        .join(Teacher, Teacher.ci == Designation.teacher_ci)
        .filter(Designation.academic_period == period)
    )
    if teacher_ci:
        query = query.filter(Designation.teacher_ci == teacher_ci)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(Designation.subject.ilike(pattern), Teacher.full_name.ilike(pattern)))
    if semester:
        query = query.filter(func.upper(Designation.semester) == semester.strip().upper())
    if designation_type == "practice":
        query = query.filter(Designation.designation_type == "practice")
    elif designation_type == "regular":
        query = query.filter(Designation.designation_type != "practice")
    rows = query.order_by(Teacher.full_name, Designation.subject, Designation.group_code, Designation.id).all()
    usage = _usage(db, [item.id for item, _name in rows])
    items = [_item(usage, item, name) for item, name in rows]
    if status in ("active", "finalized"):
        items = [item for item in items if item.status == status]
    periods = {row[0] for row in db.query(Designation.academic_period).distinct()} | {period}
    return DesignationAdminList(
        academic_period=period,
        periods=sorted(periods, key=_period_key, reverse=True),
        items=items,
    )


def _plain_schedule_errors(errors: list[str]) -> list[str]:
    # The import validator speaks in file rows ("Fila 0, horario 1: ..."); a form has no rows.
    plain = []
    bad_time_slots = set()
    for message in errors:
        text = re.sub(r"^Fila 0(, |: )", "", message)
        text = text[:1].upper() + text[1:]
        slot = re.match(r"Horario (\d+):", text)
        if slot and "HH:MM" in text:
            bad_time_slots.add(slot.group(1))
        plain.append(text)
    return [
        text for text in plain
        if not (re.match(r"Horario (\d+):", text) and "mayores a cero" in text
                and re.match(r"Horario (\d+):", text).group(1) in bad_time_slots)
    ]


def _schedule_raw(slots: list[dict[str, Any]]) -> str:
    return "\n".join(f"{slot['dia'].capitalize()}: {slot['hora_inicio']}-{slot['hora_fin']}" for slot in slots)


def _clean(value: str) -> str:
    return " ".join(value.split()).upper()


def _normalized_fields(payload: DesignationWriteRequest) -> dict[str, Any]:
    errors: list[str] = []
    subject = _clean(payload.subject)
    semester = _clean(payload.semester)
    group = _clean(payload.group_code)
    if not subject:
        errors.append("Falta la materia.")
    if not semester:
        errors.append("Falta el semestre.")
    if not group:
        errors.append("Falta el grupo.")
    schedule_errors: list[str] = []
    slots = _canonical_schedule([slot.model_dump(exclude_none=True) for slot in payload.schedule], 0, schedule_errors)
    errors.extend(_plain_schedule_errors(schedule_errors))
    if payload.contract_start_date and payload.contract_end_date and payload.contract_end_date < payload.contract_start_date:
        errors.append(DATE_ORDER_ERROR)
    if errors:
        raise DesignationInvalid(errors)
    weekly = sum(slot["horas_academicas"] for slot in slots)
    return {
        "teacher_ci": payload.teacher_ci,
        "subject": subject,
        "semester": semester,
        "group_code": normalize_group_code(group),
        "designation_type": payload.designation_type or DesignationLoader._detect_designation_type(subject),
        "schedule_json": slots,
        "monthly_hours": payload.monthly_hours,
        "semester_hours": payload.semester_hours,
        "weekly_hours": weekly,
        "weekly_hours_calculated": weekly,
        "schedule_raw": _schedule_raw(slots),
        "contract_start_date": payload.contract_start_date,
        "contract_end_date": payload.contract_end_date,
    }


def _require_teacher(db: Session, ci: str) -> Teacher:
    teacher = db.get(Teacher, ci)
    if teacher is None:
        raise DesignationNotFound("Docente no encontrado")
    return teacher


def _require_designation(db: Session, designation_id: int) -> Designation:
    item = db.get(Designation, designation_id)
    if item is None:
        raise DesignationNotFound("Designación no encontrada")
    return item


def _ensure_unique(db: Session, fields: dict[str, Any], period: str, exclude_id: int | None = None) -> None:
    query = db.query(Designation.id).filter(
        Designation.teacher_ci == fields["teacher_ci"],
        Designation.subject == fields["subject"],
        Designation.semester == fields["semester"],
        Designation.group_code == fields["group_code"],
        Designation.academic_period == period,
    )
    if exclude_id is not None:
        query = query.filter(Designation.id != exclude_id)
    if query.first() is not None:
        raise DesignationBlocked(DUPLICATE_MESSAGE, [_blocker("duplicate_designation", DUPLICATE_MESSAGE)])


def _flush_unique(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        # Lost a race against another write of the same unique key.
        db.rollback()
        raise DesignationBlocked(DUPLICATE_MESSAGE, [_blocker("duplicate_designation", DUPLICATE_MESSAGE)]) from exc


def _unique_messages(blockers: list[DesignationChangeBlocker]) -> list[DesignationChangeBlocker]:
    seen: set[str] = set()
    return [b for b in blockers if not (b.message in seen or seen.add(b.message))]


def _unique_regenerate(items: list[DesignationChangeRegeneration]) -> list[DesignationChangeRegeneration]:
    seen: set[tuple] = set()
    result = []
    for item in items:
        key = (item.planilla, item.month, item.year)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _mutation(db: Session, item: Designation, regenerate=None, warnings=None) -> DesignationAdminMutation:
    teacher = db.get(Teacher, item.teacher_ci)
    base = _item(_usage(db, [item.id]), item, teacher.full_name if teacher else item.teacher_ci)
    return DesignationAdminMutation(**base.model_dump(), regenerate=regenerate or [], warnings=warnings or [])


def _json(value: Any) -> Any:
    return value.isoformat() if isinstance(value, date) else value


def snapshot(item: Designation) -> dict[str, Any]:
    return {name: _json(getattr(item, name)) for name in ("academic_period", *TRACKED_FIELDS)}


def create_designation(db: Session, payload: DesignationWriteRequest) -> DesignationAdminMutation:
    _require_teacher(db, payload.teacher_ci)
    period = (payload.academic_period or app_settings_service.get_active_academic_period(db)).strip()
    if not PERIOD_RE.match(period):
        raise DesignationInvalid(["El período debe usar el formato I/AAAA o II/AAAA."])
    fields = _normalized_fields(payload)
    _ensure_unique(db, fields, period)
    start, end = _window(period, fields["contract_start_date"], fields["contract_end_date"])
    blockers, regenerate = _PayrollIndex.load(db).check(_kind(fields["designation_type"]), start, end)
    if blockers:
        raise DesignationBlocked(PAID_MESSAGE, blockers)
    item = Designation(academic_period=period, **fields)
    db.add(item)
    _flush_unique(db)
    return _mutation(db, item, regenerate)


def update_designation(
    db: Session, designation_id: int, payload: DesignationWriteRequest
) -> tuple[DesignationAdminMutation, dict[str, dict[str, Any]]]:
    item = _require_designation(db, designation_id)
    _require_teacher(db, payload.teacher_ci)
    fields = _normalized_fields(payload)
    changes = {
        name: {"before": _json(getattr(item, name)), "after": _json(value)}
        for name, value in fields.items()
        if getattr(item, name) != value
    }
    if not changes:
        return _mutation(db, item), {}
    usage = _usage(db, [item.id])
    if DATE_FIELDS & changes.keys() and item.id in usage.contracts:
        raise DesignationBlocked(
            "No se pueden cambiar las fechas de esta designación.",
            [_blocker("contract_dates_locked", CONTRACT_DATES_LOCKED)],
        )
    old_blockers, old_regenerate = _lock(usage, item)
    new_start, new_end = _window(item.academic_period, fields["contract_start_date"], fields["contract_end_date"])
    new_blockers, new_regenerate = usage.payroll.check(_kind(fields["designation_type"]), new_start, new_end)
    blockers = _unique_messages(old_blockers + new_blockers)
    if blockers:
        raise DesignationBlocked(PAID_MESSAGE, blockers)
    _ensure_unique(db, fields, item.academic_period, exclude_id=item.id)
    for name, value in fields.items():
        setattr(item, name, value)
    _flush_unique(db)
    return _mutation(db, item, _unique_regenerate(old_regenerate + new_regenerate)), changes


def finalize_designation(db: Session, designation_id: int, end_date: date) -> DesignationAdminMutation:
    item = _require_designation(db, designation_id)
    structural: list[DesignationChangeBlocker] = []
    if item.contract_start_date and end_date < item.contract_start_date:
        structural.append(_blocker(
            "before_contract_start",
            f"La designación empieza el {item.contract_start_date.isoformat()}; el fin no puede ser anterior.",
        ))
    if item.contract_end_date and end_date > item.contract_end_date:
        structural.append(_blocker(
            "after_contract_end",
            f"La designación ya termina el {item.contract_end_date.isoformat()}; solo podés adelantar el fin.",
        ))
    if structural:
        raise DesignationBlocked("No se puede finalizar en esa fecha.", structural)
    kind = _kind(item.designation_type)
    if kind == "practice":
        rows = db.query(PracticeAttendanceLog.date).filter(
            PracticeAttendanceLog.designation_id == item.id,
            PracticeAttendanceLog.date > end_date,
            PracticeAttendanceLog.status.in_(PRACTICE_PRESENT),
        )
    else:
        rows = db.query(AttendanceRecord.date).filter(
            AttendanceRecord.designation_id == item.id,
            AttendanceRecord.date > end_date,
            AttendanceRecord.status.in_(REGULAR_PRESENT),
        )
    dates = sorted({row[0] for row in rows})
    blockers: list[DesignationChangeBlocker] = []
    if dates:
        blockers.append(_blocker(
            "attendance_after_end",
            "El docente tiene asistencia registrada después de esa fecha "
            f"({', '.join(day.isoformat() for day in dates)}). Elegí una fecha posterior.",
            dates,
        ))
    usage = _usage(db, [item.id])
    _start, old_end = _window(item.academic_period, item.contract_start_date, item.contract_end_date)
    payroll_blockers, regenerate = usage.payroll.check(kind, end_date + timedelta(days=1), old_end)
    blockers.extend(payroll_blockers)
    if blockers:
        raise DesignationBlocked("No se puede finalizar en esa fecha.", blockers)
    warnings = [CONTRACT_FINALIZE_WARNING] if item.id in usage.contracts else []
    item.contract_end_date = end_date
    db.flush()
    return _mutation(db, item, regenerate, warnings)


def delete_designation(db: Session, designation_id: int) -> dict[str, Any]:
    item = _require_designation(db, designation_id)
    blockers = _delete_blockers(_usage(db, [item.id]), item)
    if blockers:
        raise DesignationBlocked("No se puede eliminar esta designación.", blockers)
    deleted = {"id": item.id, **snapshot(item)}
    db.delete(item)
    db.flush()
    return deleted
