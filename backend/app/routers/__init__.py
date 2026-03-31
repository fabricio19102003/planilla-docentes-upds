from app.routers.teachers import router as teachers_router
from app.routers.biometric import router as biometric_router
from app.routers.designations import router as designations_router
from app.routers.attendance import router as attendance_router
from app.routers.planilla import router as planilla_router

__all__ = [
    "teachers_router",
    "biometric_router",
    "designations_router",
    "attendance_router",
    "planilla_router",
]
