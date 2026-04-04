import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import SessionLocal, create_tables
from app.routers import (
    teachers_router,
    biometric_router,
    designations_router,
    attendance_router,
    planilla_router,
    auth_router,
    users_router,
    detail_requests_router,
    docente_portal_router,
    reports_router,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: runs on startup and shutdown.
    On startup: create all DB tables and seed default admin if needed.
    """
    try:
        create_tables()
    except Exception as exc:
        logger.exception("Failed to create tables on startup: %s", exc)

    # Create default admin user if none exists
    try:
        from app.services.auth_service import auth_service

        db = SessionLocal()
        try:
            auth_service.create_default_admin(db)
        finally:
            db.close()
    except Exception as exc:
        logger.exception("Failed to create default admin on startup: %s", exc)

    yield
    # Cleanup on shutdown (none needed for now)


app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware — allows frontend dev servers to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers — auth first, then protected routes
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(detail_requests_router)
app.include_router(docente_portal_router)
app.include_router(teachers_router)
app.include_router(biometric_router)
app.include_router(designations_router)
app.include_router(attendance_router)
app.include_router(planilla_router)
app.include_router(reports_router)


@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint — verifies the API is running."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "service": settings.APP_TITLE,
    }
