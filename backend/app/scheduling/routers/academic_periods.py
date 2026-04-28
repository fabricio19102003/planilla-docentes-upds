from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.scheduling.services.academic_period_service import AcademicPeriodService
from app.scheduling.schemas.academic_period import AcademicPeriodCreate, AcademicPeriodResponse
from app.utils.auth import require_admin
from app.scheduling.models.academic_period import AcademicPeriod

router = APIRouter(prefix="/api/scheduling/academic-periods", tags=["scheduling"])


@router.get("/", response_model=list[AcademicPeriodResponse])
def list_academic_periods(db: Session = Depends(get_db)):
    return db.query(AcademicPeriod).order_by(AcademicPeriod.year, AcademicPeriod.semester_number).all()


@router.get("/active", response_model=AcademicPeriodResponse)
def get_active_academic_period(db: Session = Depends(get_db)):
    period = AcademicPeriodService.get_active_period(db)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active academic period configured")
    return period


@router.post("/", response_model=AcademicPeriodResponse, status_code=status.HTTP_201_CREATED)
def create_academic_period(
    payload: AcademicPeriodCreate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
) -> AcademicPeriodResponse:
    try:
        period = AcademicPeriodService.create_period(
            db=db,
            code=payload.code,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=payload.status,
            is_active=payload.is_active,
        )
        db.commit()
        db.refresh(period)
        return period
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{period_id}/activate", response_model=AcademicPeriodResponse)
def activate_academic_period(
    period_id: int,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
) -> AcademicPeriodResponse:
    try:
        period = AcademicPeriodService.activate_period(db=db, period_id=period_id)
        db.commit()
        db.refresh(period)
        return period
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
