from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import app_settings_service
from app.utils.auth import require_admin


def require_medicine_schedule_assistant_enabled(db: Session = Depends(get_db)) -> None:
    if not app_settings_service.get_medicine_schedule_assistant_enabled(db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


# Lifecycle/query operations are added in later work units. Keeping the gate at
# router level makes every future operation dark by default.
router = APIRouter(
    prefix="/api/medicine-schedules",
    tags=["medicine-schedules"],
    dependencies=[Depends(require_medicine_schedule_assistant_enabled), Depends(require_admin)],
)


@router.get("/status", include_in_schema=False)
def medicine_schedule_status() -> dict[str, bool]:
    """Confirm that the dark-launched Medicine assistant is enabled."""
    return {"enabled": True}
