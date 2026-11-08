"""Classroom and laboratory reservations (odd/tasks/classroom-reservations.md).

A teacher reserves one room for one date, from a start time and a number of academic
periods. A reservation is confirmed on creation when its half-open range overlaps
neither a published class of that room nor another confirmed reservation. The room
row is locked first, so two concurrent requests for the same room are serialized.
"""
from __future__ import annotations

from datetime import date, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.academic_management import Classroom
from app.models.classroom_reservation import ClassroomReservation
from app.models.teacher import Teacher
from app.services.academic_schedule_conflicts_service import DAY_END, DAY_START
from app.services.academic_schedule_view_service import WEEKDAYS, schedule_blocks
from app.services.app_settings_service import get_academic_hour_minutes, get_active_academic_period
from app.services.reenrollment import BOLIVIA

BOOKABLE_TYPES = ("classroom", "laboratory")
MAX_PERIODS = 8
STEP_MINUTES = 5

NOT_BOOKABLE = "El aula o laboratorio no está disponible para reservas."
PAST = "No se puede reservar en una fecha u hora pasada."
WINDOW = f"La reserva debe quedar entre las {DAY_START} y las {DAY_END}."
STEP = "La hora de inicio debe ser múltiplo de 5 minutos."
CLASS_CONFLICT = "El aula está ocupada por una clase de {start} a {end}."
RESERVATION_CONFLICT = "El aula ya está reservada de {start} a {end}."
NOT_FOUND = "Reserva no encontrada."
ALREADY_CANCELLED = "La reserva ya fue cancelada."
STARTED = "No se puede cancelar una reserva que ya comenzó."
RANGE_ORDER = "La fecha final no puede ser anterior a la inicial."
RANGE_LENGTH = "El rango no puede superar 31 días."
MAX_RANGE_DAYS = 31


def bolivia_now() -> datetime:
    return datetime.now(BOLIVIA)


def _minutes(value: time | str) -> int:
    if isinstance(value, str):
        value = time.fromisoformat(value)
    return value.hour * 60 + value.minute


def _clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def bookable_rooms(db: Session) -> list[Classroom]:
    return db.query(Classroom).filter(
        Classroom.active.is_(True), Classroom.classroom_type.in_(BOOKABLE_TYPES)
    ).order_by(Classroom.classroom_type, Classroom.code).all()


def listed_rooms(db: Session, reservations: list[ClassroomReservation]) -> list[Classroom]:
    """Bookable rooms, then rooms no longer bookable that still hold one of ``reservations``."""
    rooms = bookable_rooms(db)
    listed = {room.id for room in rooms}
    extra = {row.classroom.id: row.classroom for row in reservations if row.classroom.id not in listed}
    return rooms + sorted(extra.values(), key=lambda room: room.code)


def _bookable_room(db: Session, classroom_id: int, *, lock: bool = False) -> Classroom:
    query = db.query(Classroom).filter(Classroom.id == classroom_id)
    if lock:
        query = query.with_for_update()
    room = query.one_or_none()
    if room is None or not room.active or room.classroom_type not in BOOKABLE_TYPES:
        raise HTTPException(404, detail=NOT_BOOKABLE)
    return room


def _classes_by_code(db: Session, day: date) -> dict[str, list[tuple[int, int, str]]]:
    """Published class blocks on ``day`` as (start, end, subject) minutes, by classroom code."""
    weekday = WEEKDAYS[day.weekday()]
    blocks = schedule_blocks(db, academic_period=get_active_academic_period(db), source="current", reference=day)
    by_code: dict[str, list[tuple[int, int, str]]] = {}
    for block in blocks:
        if block.classroom_code and block.weekday == weekday:
            by_code.setdefault(block.classroom_code, []).append(
                (_minutes(block.start_time), _minutes(block.end_time), block.subject_name))
    return {code: sorted(ranges) for code, ranges in by_code.items()}


def _class_ranges(db: Session, room: Classroom, day: date) -> list[tuple[int, int, str]]:
    return _classes_by_code(db, day).get(room.code, [])


def _confirmed_query(db: Session, day: date):
    return db.query(ClassroomReservation).filter(
        ClassroomReservation.reservation_date == day,
        ClassroomReservation.status == "confirmed",
    ).order_by(ClassroomReservation.start_time)


def _confirmed(db: Session, room: Classroom, day: date) -> list[ClassroomReservation]:
    return _confirmed_query(db, day).filter(ClassroomReservation.classroom_id == room.id).all()


def _busy(classes: list[tuple[int, int, str]], reservations: list[ClassroomReservation], teacher_ci: str) -> list[dict]:
    """Anonymous busy ranges: classes are "Ocupada", reservations "Reservada" (``mine`` for the caller's)."""
    busy = [
        {"start": start, "end": end, "kind": "class", "label": "Ocupada", "detail": subject, "mine": False}
        for start, end, subject in classes
    ] + [
        {"start": _minutes(row.start_time), "end": _minutes(row.end_time), "kind": "reservation",
         "label": "Reservada", "detail": None, "mine": row.teacher_ci == teacher_ci}
        for row in reservations
    ]
    busy.sort(key=lambda item: (item["start"], item["end"]))
    return busy


def _busy_out(busy: list[dict]) -> list[dict]:
    return [
        {"start_time": _clock(item["start"]), "end_time": _clock(item["end"]),
         **{key: item[key] for key in ("kind", "label", "detail", "mine")}}
        for item in busy
    ]


def _free_minutes(busy: list[dict]) -> int:
    """Minutes of the day window not covered by any busy range (overlaps count once)."""
    window_start, window_end = _minutes(DAY_START), _minutes(DAY_END)
    covered, cursor = 0, window_start
    for item in busy:
        start, end = max(item["start"], cursor), min(item["end"], window_end)
        if end > start:
            covered += end - start
            cursor = end
    return window_end - window_start - covered


def _day_frame(db: Session, day: date) -> dict:
    return {"date": day, "academic_hour_minutes": get_academic_hour_minutes(db),
            "day_start": DAY_START, "day_end": DAY_END}


def availability(db: Session, classroom_id: int, day: date, teacher_ci: str) -> dict:
    room = _bookable_room(db, classroom_id)
    busy = _busy(_class_ranges(db, room, day), _confirmed(db, room, day), teacher_ci)
    return {"classroom": room, **_day_frame(db, day), "busy": _busy_out(busy)}


def day_availability(db: Session, day: date, teacher_ci: str) -> dict:
    """Busy ranges and free minutes of every bookable room on ``day``."""
    classes = _classes_by_code(db, day)
    reservations: dict[int, list[ClassroomReservation]] = {}
    for row in _confirmed_query(db, day).all():
        reservations.setdefault(row.classroom_id, []).append(row)
    rooms = []
    for room in bookable_rooms(db):
        busy = _busy(classes.get(room.code, []), reservations.get(room.id, []), teacher_ci)
        rooms.append({"classroom": room, "busy": _busy_out(busy), "free_minutes": _free_minutes(busy)})
    return {**_day_frame(db, day), "rooms": rooms}


def reserve(db: Session, *, teacher: Teacher, user_id: int | None, classroom_id: int, day: date,
            start: time, periods: int) -> ClassroomReservation:
    begin = _minutes(start)
    if begin % STEP_MINUTES or start.second or start.microsecond:
        raise HTTPException(422, detail=STEP)
    end = begin + periods * get_academic_hour_minutes(db)
    if begin < _minutes(DAY_START) or end > _minutes(DAY_END):
        raise HTTPException(422, detail=WINDOW)
    now = bolivia_now()
    if day < now.date() or (day == now.date() and begin <= now.hour * 60 + now.minute):
        raise HTTPException(422, detail=PAST)

    room = _bookable_room(db, classroom_id, lock=True)
    for class_start, class_end, _subject in _class_ranges(db, room, day):
        if begin < class_end and class_start < end:
            raise HTTPException(409, detail=CLASS_CONFLICT.format(start=_clock(class_start), end=_clock(class_end)))
    for row in _confirmed(db, room, day):
        row_start, row_end = _minutes(row.start_time), _minutes(row.end_time)
        if begin < row_end and row_start < end:
            raise HTTPException(409, detail=RESERVATION_CONFLICT.format(start=_clock(row_start), end=_clock(row_end)))

    reservation = ClassroomReservation(
        classroom_id=room.id, teacher_ci=teacher.ci, reservation_date=day,
        start_time=start, end_time=time(end // 60, end % 60),
        academic_periods=periods, status="confirmed", created_by_user_id=user_id,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _with_relations(db: Session):
    return db.query(ClassroomReservation).options(
        joinedload(ClassroomReservation.classroom), joinedload(ClassroomReservation.teacher)
    )


def with_relations(db: Session, reservation_id: int) -> ClassroomReservation:
    return _with_relations(db).filter(ClassroomReservation.id == reservation_id).one()


def upcoming_for_teacher(db: Session, teacher_ci: str) -> list[ClassroomReservation]:
    return _with_relations(db).filter(
        ClassroomReservation.teacher_ci == teacher_ci,
        ClassroomReservation.status == "confirmed",
        ClassroomReservation.reservation_date >= bolivia_now().date(),
    ).order_by(ClassroomReservation.reservation_date, ClassroomReservation.start_time).all()


def cancel(db: Session, *, teacher_ci: str, reservation_id: int) -> ClassroomReservation:
    row = db.query(ClassroomReservation).filter(
        ClassroomReservation.id == reservation_id, ClassroomReservation.teacher_ci == teacher_ci
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(404, detail=NOT_FOUND)
    if row.status == "cancelled":
        raise HTTPException(409, detail=ALREADY_CANCELLED)
    now = bolivia_now()
    if datetime.combine(row.reservation_date, row.start_time) <= now.replace(tzinfo=None):
        raise HTTPException(422, detail=STARTED)
    row.status = "cancelled"
    row.cancelled_at = now.replace(tzinfo=None)
    db.flush()
    return row


def in_range(db: Session, date_from: date, date_to: date) -> list[ClassroomReservation]:
    if date_to < date_from:
        raise HTTPException(422, detail=RANGE_ORDER)
    if (date_to - date_from).days >= MAX_RANGE_DAYS:
        raise HTTPException(422, detail=RANGE_LENGTH)
    return _with_relations(db).join(ClassroomReservation.classroom).filter(
        ClassroomReservation.status == "confirmed",
        ClassroomReservation.reservation_date.between(date_from, date_to),
    ).order_by(ClassroomReservation.reservation_date, ClassroomReservation.start_time, Classroom.code).all()
