"""Teacher change for legacy designations ("Cambiar docente").

A change from date D ends the outgoing designation on D-1 and creates an identical
designation for the incoming teacher from D. Designation contract dates already cut
attendance and payroll per day, so no schema change is needed and every existing
designation keeps paying exactly what it pays today until a change is applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.billing_publication import BillingPublication
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.schemas.designation_change import (
    DesignationChangeBlocker,
    DesignationChangeImpact,
    DesignationChangeItem,
    DesignationChangePreview,
    DesignationChangeRegeneration,
    DesignationChangeRequest,
    DesignationChangeResult,
    DesignationChangeTeacherImpact,
)
from app.services import app_settings_service
from app.services.payroll_schedule_source_service import payroll_schedule_sources
from app.services.payroll_simulation_service import hours_by_teacher, month_bounds, teacher_impacts

REGULAR_PRESENT = ("ATTENDED", "LATE", "NO_EXIT")
PRACTICE_PRESENT = ("attended", "late")
PLANILLA_LABEL = {"regular": "teoría", "practice": "práctica"}
STRUCTURAL_BLOCKERS = {"same_teacher", "before_contract_start", "after_contract_end", "incoming_has_designation"}


class DesignationChangeNotFound(Exception):
    pass


class DesignationChangeBlocked(Exception):
    def __init__(self, preview: DesignationChangePreview):
        super().__init__("blocked")
        self.preview = preview


@dataclass
class _Plan:
    period: str
    effective_from: date
    incoming: Teacher
    designations: list[Designation]


def _kind(designation: Designation) -> str:
    return "practice" if designation.designation_type == "practice" else "regular"


def _resolve(db: Session, request: DesignationChangeRequest) -> _Plan:
    period = request.academic_period or app_settings_service.get_active_academic_period(db)
    incoming = db.get(Teacher, request.incoming_teacher_ci)
    if incoming is None:
        raise DesignationChangeNotFound("Docente entrante no encontrado")
    query = db.query(Designation).filter(Designation.academic_period == period)
    if request.scope == "designation":
        designation = query.filter(Designation.id == request.designation_id).one_or_none()
        if designation is None:
            raise DesignationChangeNotFound("Designación no encontrada en el período")
        designations = [designation]
    else:
        designations = (
            query.filter(
                Designation.teacher_ci == request.outgoing_teacher_ci,
                or_(Designation.contract_end_date.is_(None), Designation.contract_end_date >= request.effective_from),
            )
            .order_by(Designation.id)
            .all()
        )
        if not designations:
            raise DesignationChangeNotFound("El docente saliente no tiene designaciones activas en esa fecha")
    return _Plan(period, request.effective_from, incoming, designations)


def _designation_blockers(db: Session, plan: _Plan) -> list[DesignationChangeBlocker]:
    blockers: list[DesignationChangeBlocker] = []
    day = plan.effective_from
    for item in plan.designations:
        label = f"{item.subject} ({item.group_code})"
        if item.teacher_ci == plan.incoming.ci:
            blockers.append(DesignationChangeBlocker(
                code="same_teacher", designation_id=item.id,
                message=f"{label}: el docente entrante ya es el titular de esta designación.",
            ))
            continue
        if item.contract_start_date and day <= item.contract_start_date:
            blockers.append(DesignationChangeBlocker(
                code="before_contract_start", designation_id=item.id,
                message=(f"{label}: la designación empieza el {item.contract_start_date.isoformat()}; "
                         "el cambio debe ser posterior a esa fecha."),
            ))
        if item.contract_end_date and day > item.contract_end_date:
            blockers.append(DesignationChangeBlocker(
                code="after_contract_end", designation_id=item.id,
                message=f"{label}: la designación terminó el {item.contract_end_date.isoformat()}.",
            ))
        duplicate = (
            db.query(Designation.id)
            .filter(
                Designation.teacher_ci == plan.incoming.ci,
                Designation.subject == item.subject,
                Designation.semester == item.semester,
                Designation.group_code == item.group_code,
                Designation.academic_period == item.academic_period,
            )
            .first()
        )
        if duplicate is not None:
            blockers.append(DesignationChangeBlocker(
                code="incoming_has_designation", designation_id=item.id,
                message=f"{label}: el docente entrante ya tiene una designación de esta materia y grupo.",
            ))
        if _kind(item) == "practice":
            rows = (
                db.query(PracticeAttendanceLog.date)
                .filter(
                    PracticeAttendanceLog.designation_id == item.id,
                    PracticeAttendanceLog.date >= day,
                    PracticeAttendanceLog.status.in_(PRACTICE_PRESENT),
                )
                .all()
            )
        else:
            rows = (
                db.query(AttendanceRecord.date)
                .filter(
                    AttendanceRecord.designation_id == item.id,
                    AttendanceRecord.date >= day,
                    AttendanceRecord.status.in_(REGULAR_PRESENT),
                )
                .all()
            )
        dates = sorted({row[0] for row in rows})
        if dates:
            blockers.append(DesignationChangeBlocker(
                code="outgoing_attendance_after_change", designation_id=item.id, dates=dates,
                message=(f"{label}: el docente saliente tiene asistencia registrada desde la fecha del cambio "
                         f"({', '.join(d.isoformat() for d in dates)}). Revisá la fecha del cambio."),
            ))
    return blockers


def _payroll_checks(
    db: Session, plan: _Plan
) -> tuple[list[DesignationChangeBlocker], list[DesignationChangeRegeneration]]:
    blockers: list[DesignationChangeBlocker] = []
    regenerate: list[DesignationChangeRegeneration] = []
    day = plan.effective_from
    kinds = sorted({_kind(item) for item in plan.designations})
    ends = [item.contract_end_date for item in plan.designations]
    last_day = None if any(end is None for end in ends) else max(ends)
    models = {"regular": PlanillaOutput, "practice": PracticePlanillaOutput}
    for kind in kinds:
        for output in db.query(models[kind]).order_by(models[kind].year, models[kind].month).all():
            month_start, month_end = month_bounds(output.year, output.month)
            start = output.start_date or month_start
            end = output.end_date or month_end
            if end < day or (last_day is not None and start > last_day):
                continue
            if output.status == "approved":
                blockers.append(DesignationChangeBlocker(
                    code="payroll_approved",
                    message=(f"La planilla de {PLANILLA_LABEL[kind]} {output.month}/{output.year} ya está aprobada "
                             "y cubre la fecha del cambio. Rechazala o elegí una fecha posterior."),
                ))
            else:
                regenerate.append(DesignationChangeRegeneration(
                    planilla=kind, month=output.month, year=output.year, status=output.status,
                ))
        publications = (
            db.query(BillingPublication)
            .filter(BillingPublication.planilla_type == kind, BillingPublication.status == "published")
            .order_by(BillingPublication.year, BillingPublication.month)
            .all()
        )
        for publication in publications:
            month_start, month_end = month_bounds(publication.year, publication.month)
            if month_end < day or (last_day is not None and month_start > last_day):
                continue
            blockers.append(DesignationChangeBlocker(
                code="billing_published",
                message=(f"La facturación de {PLANILLA_LABEL[kind]} {publication.month}/{publication.year} "
                         "ya está publicada y cubre la fecha del cambio."),
            ))
    return blockers, regenerate


def _mutate(db: Session, plan: _Plan) -> tuple[list[int], list[int]]:
    ended: list[int] = []
    created: list[Designation] = []
    for item in plan.designations:
        original_end = item.contract_end_date
        item.contract_end_date = plan.effective_from - timedelta(days=1)
        ended.append(item.id)
        created.append(Designation(
            teacher_ci=plan.incoming.ci,
            subject=item.subject,
            semester=item.semester,
            group_code=item.group_code,
            academic_period=item.academic_period,
            schedule_json=item.schedule_json,
            semester_hours=item.semester_hours,
            monthly_hours=item.monthly_hours,
            weekly_hours=item.weekly_hours,
            weekly_hours_calculated=item.weekly_hours_calculated,
            schedule_raw=item.schedule_raw,
            designation_type=item.designation_type,
            contract_start_date=plan.effective_from,
            contract_end_date=original_end,
        ))
    db.add_all(created)
    db.flush()
    return ended, [item.id for item in created]


def _activities(plan: _Plan) -> set[str]:
    return {"practice" if _kind(item) == "practice" else "theory" for item in plan.designations}


def _hours(db: Session, plan: _Plan, teachers: set[str]) -> dict:
    start, end = month_bounds(plan.effective_from.year, plan.effective_from.month)
    return hours_by_teacher(db, plan.period, start, end, _activities(plan), teachers)


def _published_warnings(db: Session, plan: _Plan) -> list[str]:
    start, end = month_bounds(plan.effective_from.year, plan.effective_from.month)
    warnings = []
    for activity in sorted(_activities(plan)):
        published = {
            (s.subject.casefold().strip(), s.group_code.casefold().strip(), str(s.semester).casefold().strip())
            for s in payroll_schedule_sources(
                db, academic_period=plan.period, period_start=start, period_end=end, activity_kind=activity,
            )
            if s.source_kind == "published"
        }
        for item in plan.designations:
            scope = (item.subject.casefold().strip(), item.group_code.casefold().strip(), str(item.semester).casefold().strip())
            if scope in published:
                warnings.append(
                    f"{item.subject} ({item.group_code}) se paga desde el horario publicado: cambiá también el "
                    "docente en el módulo de horarios para que la planilla lo refleje."
                )
    return warnings


def _evaluate(db: Session, request: DesignationChangeRequest) -> tuple[_Plan, DesignationChangePreview]:
    plan = _resolve(db, request)
    blockers = _designation_blockers(db, plan)
    payroll_blockers, regenerate = _payroll_checks(db, plan)
    blockers.extend(payroll_blockers)
    teachers = {item.teacher_ci for item in plan.designations} | {plan.incoming.ci}
    before = _hours(db, plan, teachers)
    if any(b.code in STRUCTURAL_BLOCKERS for b in blockers):
        after = dict(before)
    else:
        # Simulate the change with the real payroll source and discard it.
        savepoint = db.begin_nested()
        try:
            _mutate(db, plan)
            after = _hours(db, plan, teachers)
        finally:
            savepoint.rollback()
    keys = set(before) | set(after) | {(ci, activity) for ci in teachers for activity in _activities(plan)}
    items = [
        DesignationChangeItem(
            designation_id=item.id, subject=item.subject, semester=str(item.semester), group_code=item.group_code,
            designation_type=item.designation_type, outgoing_teacher_ci=item.teacher_ci,
            incoming_teacher_ci=plan.incoming.ci, outgoing_until=plan.effective_from - timedelta(days=1),
            incoming_from=plan.effective_from, incoming_until=item.contract_end_date,
        )
        for item in plan.designations
    ]
    preview = DesignationChangePreview(
        can_apply=not blockers,
        items=items,
        blockers=blockers,
        warnings=_published_warnings(db, plan),
        regenerate=regenerate,
        impact=DesignationChangeImpact(
            month=plan.effective_from.month, year=plan.effective_from.year,
            teachers=[DesignationChangeTeacherImpact(**item) for item in teacher_impacts(db, before, after, keys)],
        ),
    )
    return plan, preview


def preview_change(db: Session, request: DesignationChangeRequest) -> DesignationChangePreview:
    _plan, preview = _evaluate(db, request)
    return preview


def apply_change(db: Session, request: DesignationChangeRequest) -> DesignationChangeResult:
    plan, preview = _evaluate(db, request)
    if not preview.can_apply:
        raise DesignationChangeBlocked(preview)
    ended, created = _mutate(db, plan)
    return DesignationChangeResult(
        ended_designation_ids=ended,
        created_designation_ids=created,
        regenerate=preview.regenerate,
        impact=preview.impact,
    )


def list_teacher_designations(db: Session, academic_period: str, teacher_ci: str) -> list[Designation]:
    return (
        db.query(Designation)
        .filter(Designation.academic_period == academic_period, Designation.teacher_ci == teacher_ci)
        .order_by(Designation.subject, Designation.group_code, Designation.id)
        .all()
    )
