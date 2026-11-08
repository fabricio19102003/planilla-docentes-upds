"""Classroom and laboratory reservations: teacher portal and admin endpoints."""
from __future__ import annotations

from datetime import date, time

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic_management import Classroom
from app.models.classroom_reservation import ClassroomReservation
from app.models.user import User
from app.routers.docente_portal import _get_teacher_or_raise
from app.services import classroom_reservation_service as service
from app.utils.auth import require_admin, require_docente

portal_router = APIRouter(prefix="/api/portal/classroom-reservations", tags=["classroom-reservations"])
admin_router = APIRouter(
    prefix="/api/admin/classroom-reservations", tags=["classroom-reservations"], dependencies=[Depends(require_admin)]
)


class ReservationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classroom_id: int
    day: date = Field(alias="date")
    start_time: time
    periods: int = Field(ge=1, le=service.MAX_PERIODS)


def room_out(room: Classroom) -> dict:
    return {"id": room.id, "code": room.code, "name": room.name, "capacity": room.capacity,
            "classroom_type": room.classroom_type}


def reservation_out(row: ClassroomReservation) -> dict:
    return {
        "id": row.id,
        "classroom": room_out(row.classroom),
        "date": row.reservation_date.isoformat(),
        "start_time": row.start_time.strftime("%H:%M"),
        "end_time": row.end_time.strftime("%H:%M"),
        "academic_periods": row.academic_periods,
        "status": row.status,
        "teacher_ci": row.teacher_ci,
        "teacher_name": row.teacher.full_name if row.teacher else None,
    }


@portal_router.get("/classrooms")
def list_bookable_rooms(_: User = Depends(require_docente), db: Session = Depends(get_db)):
    return [room_out(room) for room in service.bookable_rooms(db)]


@portal_router.get("/availability")
def room_availability(
    classroom_id: int,
    day: date = Query(alias="date"),
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
):
    teacher = _get_teacher_or_raise(current_user, db)
    result = service.availability(db, classroom_id, day, teacher.ci)
    return {**result, "classroom": room_out(result["classroom"]), "date": day.isoformat()}


@portal_router.get("/day")
def day_availability(
    day: date = Query(alias="date"),
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
):
    teacher = _get_teacher_or_raise(current_user, db)
    result = service.day_availability(db, day, teacher.ci)
    return {
        **result,
        "date": day.isoformat(),
        "rooms": [{**item, "classroom": room_out(item["classroom"])} for item in result["rooms"]],
    }


@portal_router.post("", status_code=status.HTTP_201_CREATED)
def create_reservation(
    payload: ReservationCreate,
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
):
    teacher = _get_teacher_or_raise(current_user, db)
    reservation = service.reserve(
        db, teacher=teacher, user_id=current_user.id, classroom_id=payload.classroom_id,
        day=payload.day, start=payload.start_time, periods=payload.periods,
    )
    db.commit()
    return reservation_out(service.with_relations(db, reservation.id))


@portal_router.get("/mine")
def my_reservations(current_user: User = Depends(require_docente), db: Session = Depends(get_db)):
    teacher = _get_teacher_or_raise(current_user, db)
    return [reservation_out(row) for row in service.upcoming_for_teacher(db, teacher.ci)]


@portal_router.post("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
):
    teacher = _get_teacher_or_raise(current_user, db)
    service.cancel(db, teacher_ci=teacher.ci, reservation_id=reservation_id)
    db.commit()
    return reservation_out(service.with_relations(db, reservation_id))


@admin_router.get("")
def list_reservations(date_from: date, date_to: date, db: Session = Depends(get_db)):
    reservations = service.in_range(db, date_from, date_to)
    return {
        "classrooms": [room_out(room) for room in service.listed_rooms(db, reservations)],
        "reservations": [reservation_out(row) for row in reservations],
    }
