"""Intensive (summer/winter) courses: opening, enrollment with capacity locking, price and closing (phase 3 S1, S2)."""
from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.academic_management import AcademicSubject
from app.models.intensive_courses import IntensiveCourse, IntensiveCourseSettings, IntensiveEnrollment
from app.models.student_portal import StudentAccount
from app.models.teacher import Teacher
from app.models.user import User
from app.services import academic_records_service
from app.services import reenrollment_eligibility as eligibility
from app.services.reenrollment import bolivia_today

NOT_CONFIGURED = "Configurá las tarifas de cursos intensivos antes de abrir un curso"
NOT_FOUND = "Curso intensivo no encontrado"
CLOSED = "El curso intensivo está cerrado"
NO_HOURS = "Las horas de teoría y práctica no pueden ser ambas cero"
BAD_DATES = "La fecha de fin debe ser igual o posterior a la de inicio"
SETTINGS_ID = 1


# ── Settings and price ───────────────────────────────────────────────────────

def get_settings(db: Session) -> IntensiveCourseSettings:
    """The single settings row; the migration creates it, databases built from the models get it on first read."""
    settings = db.get(IntensiveCourseSettings, SETTINGS_ID)
    if settings is None:
        settings = IntensiveCourseSettings(id=SETTINGS_ID, margin_factor=Decimal("1.10"), min_price=1200,
                                           max_price=1600)
        db.add(settings)
        db.flush()
    return settings


def _number(value: Any) -> Optional[float]:
    return None if value is None else float(value)


def settings_payload(settings: IntensiveCourseSettings) -> dict[str, Any]:
    return {
        "theory_hourly_rate": _number(settings.theory_hourly_rate),
        "practice_hourly_rate": _number(settings.practice_hourly_rate),
        "margin_factor": _number(settings.margin_factor),
        "min_price": settings.min_price, "max_price": settings.max_price,
        "is_configured": is_configured(settings),
    }


def is_configured(settings: IntensiveCourseSettings) -> bool:
    return settings.theory_hourly_rate is not None and settings.practice_hourly_rate is not None


def update_settings(db: Session, values: dict[str, Any], actor: User) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replace the settings; returns the payloads before and after for the activity log."""
    settings = get_settings(db)
    before = settings_payload(settings)
    settings.theory_hourly_rate = values["theory_hourly_rate"]
    settings.practice_hourly_rate = values["practice_hourly_rate"]
    settings.margin_factor = values["margin_factor"]
    settings.min_price = values["min_price"]
    settings.max_price = values["max_price"]
    settings.updated_by = actor.id
    db.flush()
    return before, settings_payload(settings)


def _require_configured(settings: IntensiveCourseSettings) -> None:
    if not is_configured(settings):
        raise HTTPException(status_code=409, detail=NOT_CONFIGURED)


def teacher_pay(settings: IntensiveCourseSettings, theory_hours: int, practice_hours: int) -> Decimal:
    _require_configured(settings)
    return (theory_hours * Decimal(str(settings.theory_hourly_rate))
            + practice_hours * Decimal(str(settings.practice_hourly_rate)))


def compute_price(pay: Decimal, enrolled: int, factor: Decimal, minimum: int, maximum: int) -> int:
    """Price per student: pay with margin shared among the enrolled, rounded half up to whole bolivianos and clamped.

    With nobody enrolled yet the price shown is the one for a single student.
    """
    share = pay * Decimal(str(factor)) / max(enrolled, 1)
    return max(minimum, min(maximum, int(share.quantize(Decimal(1), rounding=ROUND_HALF_UP))))


def _price(settings: IntensiveCourseSettings, course: IntensiveCourse, enrolled: int) -> dict[str, Any]:
    if course.status == "closed":
        return {"amount": course.final_price, "is_final": True}
    amount = compute_price(teacher_pay(settings, course.theory_hours, course.practice_hours), enrolled,
                           settings.margin_factor, settings.min_price, settings.max_price)
    return {"amount": amount, "is_final": False}


# ── Payloads ─────────────────────────────────────────────────────────────────

def _enrolled_counts(db: Session, course_ids: list[int]) -> dict[int, int]:
    if not course_ids:
        return {}
    return dict(
        db.query(IntensiveEnrollment.course_id, func.count())
        .filter(IntensiveEnrollment.course_id.in_(course_ids)).group_by(IntensiveEnrollment.course_id).all()
    )


def _is_enrollment_open(course: IntensiveCourse) -> bool:
    return course.status == "open" and course.enrollment_starts_on <= bolivia_today() <= course.enrollment_ends_on


def _base_payload(course: IntensiveCourse, settings: IntensiveCourseSettings, enrolled: int) -> dict[str, Any]:
    return {
        "id": course.id, "term_code": course.term_code,
        "subject": {"id": course.subject.id, "code": course.subject.code, "name": course.subject.name},
        "capacity": course.capacity, "enrolled": enrolled, "free": max(course.capacity - enrolled, 0),
        "is_full": enrolled >= course.capacity,
        "enrollment_starts_on": course.enrollment_starts_on, "enrollment_ends_on": course.enrollment_ends_on,
        "is_enrollment_open": _is_enrollment_open(course), "theory_hours": course.theory_hours,
        "practice_hours": course.practice_hours, "status": course.status, "price": _price(settings, course, enrolled),
    }


def admin_payload(course: IntensiveCourse, settings: IntensiveCourseSettings, enrolled: int) -> dict[str, Any]:
    return {
        **_base_payload(course, settings, enrolled),
        "teacher": {"ci": course.teacher.ci, "full_name": course.teacher.full_name},
        "teacher_pay": float(teacher_pay(settings, course.theory_hours, course.practice_hours)),
        "closed_at": course.closed_at,
    }


def student_payload(course: IntensiveCourse, settings: IntensiveCourseSettings, enrolled: int) -> dict[str, Any]:
    # Teacher pay stays out of the portal: students only see the resulting price.
    return {**_base_payload(course, settings, enrolled), "teacher_name": course.teacher.full_name}


def _courses(db: Session):
    return db.query(IntensiveCourse).options(joinedload(IntensiveCourse.subject), joinedload(IntensiveCourse.teacher))


def _one(db: Session, course_id: int, *, lock: bool = False) -> IntensiveCourse:
    query = _courses(db).filter(IntensiveCourse.id == course_id)
    if lock:
        # The row lock serializes enroll, cancel, close and capacity changes of one course (no-op on SQLite,
        # which serializes writers anyway). Counting only happens after it is held.
        query = query.with_for_update(of=IntensiveCourse).populate_existing()
    course = query.one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return course


def _enrolled(db: Session, course_id: int) -> int:
    return db.query(func.count(IntensiveEnrollment.id)).filter(IntensiveEnrollment.course_id == course_id).scalar()


# ── Staff ────────────────────────────────────────────────────────────────────

def list_courses(db: Session, term_code: Optional[str], status: Optional[str]) -> list[dict[str, Any]]:
    query = _courses(db)
    if term_code:
        query = query.filter(IntensiveCourse.term_code == term_code)
    if status:
        query = query.filter(IntensiveCourse.status == status)
    courses = query.order_by(IntensiveCourse.term_code.desc(), IntensiveCourse.id).all()
    settings = get_settings(db)
    counts = _enrolled_counts(db, [c.id for c in courses])
    return [admin_payload(c, settings, counts.get(c.id, 0)) for c in courses]


def course_detail(db: Session, course_id: int) -> dict[str, Any]:
    course = _one(db, course_id)
    enrollments = (
        db.query(IntensiveEnrollment).options(joinedload(IntensiveEnrollment.student))
        .filter(IntensiveEnrollment.course_id == course.id).order_by(IntensiveEnrollment.id).all()
    )
    return {
        **admin_payload(course, get_settings(db), len(enrollments)),
        "students": [
            {"student_id": e.student.id, "document_number": e.student.document_number,
             "full_name": e.student.full_name, "is_foreign": e.student.is_foreign, "enrolled_at": e.enrolled_at}
            for e in enrollments
        ],
    }


def _teacher(db: Session, teacher_ci: str) -> Teacher:
    teacher = db.get(Teacher, teacher_ci)
    if teacher is None:
        raise HTTPException(status_code=422, detail=f"El docente {teacher_ci} no existe")
    return teacher


def _check_hours(theory: int, practice: int) -> None:
    if theory == 0 and practice == 0:
        raise HTTPException(status_code=422, detail=NO_HOURS)


def create_course(db: Session, data: dict[str, Any], actor: User) -> IntensiveCourse:
    _require_configured(get_settings(db))
    subject = db.query(AcademicSubject).filter(AcademicSubject.code == data["subject_code"]).one_or_none()
    if subject is None:
        raise HTTPException(status_code=422, detail=f"La materia {data['subject_code']} no existe en el catálogo")
    teacher = _teacher(db, data["teacher_ci"])
    theory, practice = data.get("theory_hours"), data.get("practice_hours")
    if theory is None or practice is None:
        slot = next((s for s in academic_records_service.load_default_curriculum(db).subjects
                     if s.subject_id == subject.id), None)
        if slot is None:
            raise HTTPException(
                status_code=422, detail=f"La materia {subject.code} no está en el plan de estudios; indicá las horas")
        theory = slot.theory_hours if theory is None else theory
        practice = slot.practice_hours if practice is None else practice
    _check_hours(theory, practice)
    duplicate = f"Ya existe un curso intensivo de {subject.code} para {data['term_code']}"
    if db.query(IntensiveCourse.id).filter_by(term_code=data["term_code"], subject_id=subject.id).first():
        raise HTTPException(status_code=409, detail=duplicate)
    course = IntensiveCourse(
        term_code=data["term_code"], subject_id=subject.id, teacher_ci=teacher.ci, capacity=data["capacity"],
        enrollment_starts_on=data["enrollment_starts_on"], enrollment_ends_on=data["enrollment_ends_on"],
        theory_hours=theory, practice_hours=practice, status="open", created_by=actor.id,
    )
    db.add(course)
    try:
        db.flush()
    except IntegrityError as exc:  # the same course opened twice at once
        db.rollback()
        raise HTTPException(status_code=409, detail=duplicate) from exc
    db.refresh(course)
    return course


def update_course(db: Session, course_id: int, changes: dict[str, Any]) -> IntensiveCourse:
    course = _one(db, course_id, lock=True)
    if course.status == "closed":
        raise HTTPException(status_code=409, detail=CLOSED)
    teacher_ci = changes.get("teacher_ci", course.teacher_ci)
    _teacher(db, teacher_ci)
    starts = changes.get("enrollment_starts_on", course.enrollment_starts_on)
    ends = changes.get("enrollment_ends_on", course.enrollment_ends_on)
    if ends < starts:
        raise HTTPException(status_code=422, detail=BAD_DATES)
    theory = changes.get("theory_hours", course.theory_hours)
    practice = changes.get("practice_hours", course.practice_hours)
    _check_hours(theory, practice)
    capacity = changes.get("capacity", course.capacity)
    enrolled = _enrolled(db, course.id)
    if capacity < enrolled:
        raise HTTPException(status_code=409, detail=f"La capacidad no puede ser menor a los {enrolled} inscritos")
    if teacher_ci != course.teacher_ci:
        course.teacher_ci = teacher_ci
        db.flush()
        db.refresh(course)  # reload the teacher relationship for the payload
    course.capacity, course.enrollment_starts_on, course.enrollment_ends_on = capacity, starts, ends
    course.theory_hours, course.practice_hours = theory, practice
    db.flush()
    return course


def close_course(db: Session, course_id: int, actor: User) -> IntensiveCourse:
    course = _one(db, course_id, lock=True)
    if course.status == "closed":
        raise HTTPException(status_code=409, detail=CLOSED)
    enrolled = _enrolled(db, course.id)
    price = _price(get_settings(db), course, enrolled)["amount"]
    course.status, course.final_enrolled, course.final_price = "closed", enrolled, price
    course.closed_at, course.closed_by = datetime.utcnow(), actor.id
    db.flush()
    return course


# ── Students ─────────────────────────────────────────────────────────────────

def _eligible_codes(db: Session, account: StudentAccount) -> set[str]:
    result = eligibility.evaluate(db, account.student)
    return {item["code"] for item in result["recursado"] + result["pending"] if item["code"]}


def student_view(db: Session, account: StudentAccount) -> dict[str, Any]:
    settings = get_settings(db)
    mine = {
        e.course_id: e for e in
        db.query(IntensiveEnrollment).filter(IntensiveEnrollment.student_id == account.student_id).all()
    }
    codes = _eligible_codes(db, account)
    offered = [] if not codes else (
        _courses(db).join(AcademicSubject, AcademicSubject.id == IntensiveCourse.subject_id)
        .filter(IntensiveCourse.status == "open", AcademicSubject.code.in_(codes), IntensiveCourse.id.not_in(mine))
        .order_by(IntensiveCourse.term_code.desc(), IntensiveCourse.id).all()
    )
    enrolled_in = (
        _courses(db).filter(IntensiveCourse.id.in_(list(mine))).order_by(IntensiveCourse.id).all() if mine else []
    )
    counts = _enrolled_counts(db, [c.id for c in offered + enrolled_in])
    return {
        "courses": [student_payload(c, settings, counts.get(c.id, 0)) for c in offered],
        "enrollments": [
            {**student_payload(c, settings, counts.get(c.id, 0)), "enrolled_at": mine[c.id].enrolled_at}
            for c in enrolled_in
        ],
    }


def enroll(db: Session, account: StudentAccount, course_id: int) -> dict[str, Any]:
    _one(db, course_id)  # 404 before doing the eligibility work
    codes = _eligible_codes(db, account)
    course = _one(db, course_id, lock=True)
    if course.status == "closed":
        raise HTTPException(status_code=409, detail=CLOSED)
    if not _is_enrollment_open(course):
        raise HTTPException(status_code=409, detail="La inscripción al curso intensivo no está abierta")
    if course.subject.code not in codes:
        raise HTTPException(status_code=422,
                            detail=f"{course.subject.code} no está entre tus materias a recursar o pendientes")
    already = "Ya estás inscrito en este curso intensivo"
    if db.query(IntensiveEnrollment.id).filter_by(course_id=course.id, student_id=account.student_id).first():
        raise HTTPException(status_code=409, detail=already)
    enrolled = _enrolled(db, course.id)
    if enrolled + 1 > course.capacity:
        raise HTTPException(status_code=409, detail="El curso intensivo ya no tiene cupos")
    db.add(IntensiveEnrollment(course_id=course.id, student_id=account.student_id))
    try:
        db.flush()
    except IntegrityError as exc:  # the same student enrolling twice at once
        db.rollback()
        raise HTTPException(status_code=409, detail=already) from exc
    return student_payload(course, get_settings(db), enrolled + 1)


def cancel(db: Session, account: StudentAccount, course_id: int) -> dict[str, Any]:
    course = _one(db, course_id, lock=True)
    if course.status == "closed":
        raise HTTPException(status_code=409, detail=CLOSED)
    enrollment = db.query(IntensiveEnrollment).filter_by(course_id=course.id, student_id=account.student_id).first()
    if enrollment is None:
        raise HTTPException(status_code=409, detail="No estás inscrito en este curso intensivo")
    db.delete(enrollment)
    db.flush()
    return student_payload(course, get_settings(db), _enrolled(db, course.id))
