"""Admin API for curriculum, students and the legacy academic history import."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.academic_records import CurriculumPlan
from app.models.user import User
from app.schemas.academic_records import CurriculumPlanResponse, CurriculumPlanSummary
from app.services import academic_records_service as service
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/admin/academic-records", tags=["academic-records"])

CATEGORY = "academic_records"


@router.post("/curricula/default/load", response_model=CurriculumPlanResponse)
def load_default_curriculum(
    request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    plan = service.load_default_curriculum(db)
    log_activity(
        db, action="load_curriculum", category=CATEGORY,
        description=f"Cargó la malla curricular {plan.name}", user=admin,
        details={"plan_id": plan.id}, request=request,
    )
    db.commit()
    return service.serialize_plan(plan)


@router.get("/curricula", response_model=list[CurriculumPlanSummary])
def list_curricula(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return service.list_plans(db)


@router.get("/curricula/{plan_id}", response_model=CurriculumPlanResponse)
def get_curriculum(plan_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    plan = db.get(CurriculumPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan de estudio no encontrado")
    return service.serialize_plan(plan)

