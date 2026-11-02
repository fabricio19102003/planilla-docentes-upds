"""Staff API for intensive (summer/winter) courses: settings, open, update, enrolled list and close."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import intensive_courses as service
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/admin/intensive-courses", tags=["intensive-courses"])

CATEGORY = "intensive_courses"
MAX_HOURS = 1000


class SettingsPayload(BaseModel):
    theory_hourly_rate: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    practice_hourly_rate: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    margin_factor: Decimal = Field(..., ge=1, max_digits=6, decimal_places=3)
    min_price: int = Field(..., gt=0)
    max_price: int = Field(..., gt=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.min_price > self.max_price:
            raise ValueError("El precio mínimo no puede superar al máximo")
        return self


class CourseCreate(BaseModel):
    term_code: str = Field(..., pattern=r"^(VER|INV)/[0-9]{4}$")
    subject_code: str = Field(..., min_length=1, max_length=30)
    teacher_ci: str = Field(..., min_length=1, max_length=20)
    capacity: int = Field(..., ge=1, le=1000)
    enrollment_starts_on: date
    enrollment_ends_on: date
    # Omitted hours are prefilled from the curriculum slot of the subject.
    theory_hours: Optional[int] = Field(None, ge=0, le=MAX_HOURS)
    practice_hours: Optional[int] = Field(None, ge=0, le=MAX_HOURS)

    @model_validator(mode="after")
    def _ordered(self):
        if self.enrollment_ends_on < self.enrollment_starts_on:
            raise ValueError(service.BAD_DATES)
        return self


class CourseUpdate(BaseModel):
    teacher_ci: Optional[str] = Field(None, min_length=1, max_length=20)
    capacity: Optional[int] = Field(None, ge=1, le=1000)
    enrollment_starts_on: Optional[date] = None
    enrollment_ends_on: Optional[date] = None
    theory_hours: Optional[int] = Field(None, ge=0, le=MAX_HOURS)
    practice_hours: Optional[int] = Field(None, ge=0, le=MAX_HOURS)


def _log(db: Session, request: Request, admin: User, action: str, description: str, details: dict) -> None:
    log_activity(db, action=action, category=CATEGORY, description=description, user=admin,
                 details=details, request=request)


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    result = service.settings_payload(service.get_settings(db))
    db.commit()  # the row is created on first read on databases built without the migration
    return result


@router.put("/settings")
def update_settings(payload: SettingsPayload, request: Request, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    before, after = service.update_settings(db, payload.model_dump(), admin)
    _log(db, request, admin, "update_intensive_course_settings", "Cambió las tarifas de cursos intensivos",
         {"before": before, "after": after})
    db.commit()
    return after


@router.get("")
def list_courses(
    term_code: Optional[str] = Query(None, max_length=30),
    status: Optional[Literal["open", "closed"]] = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return service.list_courses(db, term_code, status)


@router.post("", status_code=201)
def create_course(payload: CourseCreate, request: Request, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    course = service.create_course(db, payload.model_dump(), admin)
    _log(db, request, admin, "create_intensive_course",
         f"Abrió el curso intensivo de {course.subject.code} para {course.term_code}",
         {"course_id": course.id, "term_code": course.term_code, "subject_code": course.subject.code,
          "teacher_ci": course.teacher_ci, "capacity": course.capacity,
          "theory_hours": course.theory_hours, "practice_hours": course.practice_hours})
    db.commit()
    return service.course_detail(db, course.id)


@router.get("/{course_id}")
def get_course(course_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return service.course_detail(db, course_id)


@router.put("/{course_id}")
def update_course(course_id: int, payload: CourseUpdate, request: Request, db: Session = Depends(get_db),
                  admin: User = Depends(require_admin)):
    changes = {key: value for key, value in payload.model_dump().items() if value is not None}
    course = service.update_course(db, course_id, changes)
    _log(db, request, admin, "update_intensive_course",
         f"Cambió el curso intensivo de {course.subject.code} para {course.term_code}",
         {"course_id": course.id, "changes": {key: str(value) for key, value in changes.items()}})
    db.commit()
    return service.course_detail(db, course.id)


@router.post("/{course_id}/close")
def close_course(course_id: int, request: Request, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    course = service.close_course(db, course_id, admin)
    _log(db, request, admin, "close_intensive_course",
         f"Cerró la inscripción al curso intensivo de {course.subject.code} para {course.term_code}",
         {"course_id": course.id, "enrolled": course.final_enrolled, "price": course.final_price})
    db.commit()
    return service.course_detail(db, course.id)
