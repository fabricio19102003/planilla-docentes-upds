from app.scheduling.routers.academic_periods import router as academic_periods_router
from app.scheduling.routers.room_management import router as room_management_router

__all__ = [
    "academic_periods_router",
    "room_management_router",
]
