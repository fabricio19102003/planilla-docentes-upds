"""Router for scheduling module: academic periods, shifts, groups."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.auth import require_admin

from app.scheduling.schemas.academic_period import (
    AcademicPeriodCreate,
    AcademicPeriodUpdate,
    AcademicPeriodResponse,
)
from app.scheduling.schemas.shift import ShiftUpdate, ShiftResponse
from app.scheduling.schemas.group import (
    GroupCreate,
    GroupBulkCreate,
    GroupUpdate,
    GroupResponse,
)
from app.scheduling.services.period_service import PeriodService
from app.scheduling.services.shift_service import ShiftService
from app.scheduling.services.group_service import GroupService

router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])

period_svc = PeriodService()
shift_svc = ShiftService()
group_svc = GroupService()


# ─── Academic Period endpoints ────────────────────────────────────────

@router.post("/periods", response_model=AcademicPeriodResponse, status_code=201)
def create_period(
    data: AcademicPeriodCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    period = period_svc.create_period(
        db,
        code=data.code,
        name=data.name,
        year=data.year,
        semester_number=data.semester_number,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.commit()
    return AcademicPeriodResponse(
        id=period.id,
        code=period.code,
        name=period.name,
        year=period.year,
        semester_number=period.semester_number,
        start_date=period.start_date,
        end_date=period.end_date,
        is_active=period.is_active,
        status=period.status,
        group_count=0,
    )


@router.get("/periods", response_model=list[AcademicPeriodResponse])
def list_periods(
    status: str | None = Query(default=None, description="Filter by status: planning, active, closed"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return period_svc.list_periods(db, status_filter=status)


@router.get("/periods/active", response_model=AcademicPeriodResponse | None)
def get_active_period(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    period = period_svc.get_active_period(db)
    if not period:
        return None
    return period_svc.get_period(db, period.id)


@router.get("/periods/{period_id}", response_model=AcademicPeriodResponse)
def get_period(
    period_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return period_svc.get_period(db, period_id)


@router.put("/periods/{period_id}", response_model=AcademicPeriodResponse)
def update_period(
    period_id: int,
    data: AcademicPeriodUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    period_svc.update_period(db, period_id, **fields)
    db.commit()
    return period_svc.get_period(db, period_id)


@router.post("/periods/{period_id}/activate", response_model=AcademicPeriodResponse)
def activate_period(
    period_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    period_svc.activate_period(db, period_id)
    db.commit()
    return period_svc.get_period(db, period_id)


@router.post("/periods/{period_id}/close", response_model=AcademicPeriodResponse)
def close_period(
    period_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    period_svc.close_period(db, period_id)
    db.commit()
    return period_svc.get_period(db, period_id)


# ─── Shift endpoints ─────────────────────────────────────────────────

@router.get("/shifts", response_model=list[ShiftResponse])
def list_shifts(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return shift_svc.list_all(db)


@router.put("/shifts/{shift_id}", response_model=ShiftResponse)
def update_shift(
    shift_id: int,
    data: ShiftUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    shift = shift_svc.update(db, shift_id, **fields)
    db.commit()
    return ShiftResponse(
        id=shift.id,
        code=shift.code,
        name=shift.name,
        start_time=shift.start_time.strftime("%H:%M"),
        end_time=shift.end_time.strftime("%H:%M"),
        display_order=shift.display_order,
    )


# ─── Group endpoints ─────────────────────────────────────────────────

@router.post("/groups", response_model=GroupResponse, status_code=201)
def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    group = group_svc.create_group(
        db,
        academic_period_id=data.academic_period_id,
        semester_id=data.semester_id,
        shift_id=data.shift_id,
        number=data.number,
        is_special=data.is_special,
        student_count=data.student_count,
    )
    db.commit()
    # Re-fetch to get joined fields
    results = group_svc.list_by_period(db, data.academic_period_id, semester_id=data.semester_id)
    return next((r for r in results if r["id"] == group.id), results[-1])


@router.post("/groups/bulk", response_model=list[GroupResponse], status_code=201)
def create_groups_bulk(
    data: GroupBulkCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    groups_data = [
        {
            "shift_id": g.shift_id,
            "number": g.number,
            "is_special": g.is_special,
            "student_count": g.student_count,
        }
        for g in data.groups
    ]
    group_svc.create_bulk(
        db,
        academic_period_id=data.academic_period_id,
        semester_id=data.semester_id,
        groups_data=groups_data,
    )
    db.commit()
    return group_svc.list_by_period(db, data.academic_period_id, semester_id=data.semester_id)


@router.get("/groups", response_model=list[GroupResponse])
def list_groups(
    period_id: int = Query(..., description="Academic period ID"),
    semester_id: int | None = Query(default=None, description="Optional semester filter"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return group_svc.list_by_period(db, period_id, semester_id=semester_id)


@router.put("/groups/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: int,
    data: GroupUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    fields = data.model_dump(exclude_unset=True)
    group = group_svc.update(db, group_id, **fields)
    db.commit()
    # Re-fetch with joined info
    results = group_svc.list_by_period(db, group.academic_period_id)
    return next((r for r in results if r["id"] == group.id), results[-1])


@router.delete("/groups/{group_id}")
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = group_svc.delete(db, group_id)
    db.commit()
    return result
