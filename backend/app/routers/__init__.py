from app.routers.teachers import router as teachers_router
from app.routers.biometric import router as biometric_router
from app.routers.designations import router as designations_router
from app.routers.attendance import router as attendance_router
from app.routers.planilla import router as planilla_router
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.detail_requests import router as detail_requests_router
from app.routers.docente_portal import router as docente_portal_router
from app.routers.reports import router as reports_router

__all__ = [
    "teachers_router",
    "biometric_router",
    "designations_router",
    "attendance_router",
    "planilla_router",
    "auth_router",
    "users_router",
    "detail_requests_router",
    "docente_portal_router",
    "reports_router",
]
