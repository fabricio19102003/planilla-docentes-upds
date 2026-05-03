import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import SessionLocal, create_tables, engine
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
    billing_publication_router,
    activity_log_router,
    contracts_router,
    admin_router,
    admin_settings_router,
    practice_attendance_router,
    practice_planilla_router,
)
from app.scheduling.routers.curriculum import router as scheduling_router
from app.scheduling.routers.scheduling import router as scheduling_v2_router
from app.scheduling.routers.rooms import router as rooms_router
from app.scheduling.routers.slots import router as slots_router
from app.scheduling.routers.designations import router as scheduling_designations_router

logger = logging.getLogger(__name__)


def _run_column_migrations() -> None:
    """Ensure all new columns exist on an existing database.

    ``create_all()`` does not ALTER existing tables, so every time a new
    ``mapped_column`` is added to a model we need a manual migration here.
    This function is idempotent and safe to call multiple times.
    """
    try:
        from sqlalchemy import text, inspect as sa_inspect

        with engine.connect() as conn:
            inspector = sa_inspect(engine)

            # users.must_change_password
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            if "must_change_password" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT FALSE"))
                logger.info("Added column users.must_change_password")

            # billing_publications.billing_snapshot + version
            if inspector.has_table("billing_publications"):
                bp_cols = {c["name"] for c in inspector.get_columns("billing_publications")}
                if "billing_snapshot" not in bp_cols:
                    conn.execute(text("ALTER TABLE billing_publications ADD COLUMN billing_snapshot JSONB"))
                    logger.info("Added column billing_publications.billing_snapshot")
                if "version" not in bp_cols:
                    conn.execute(text("ALTER TABLE billing_publications ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))
                    logger.info("Added column billing_publications.version")

            # planilla_outputs.payment_overrides_json + start_date/end_date
            if inspector.has_table("planilla_outputs"):
                po_cols = {c["name"] for c in inspector.get_columns("planilla_outputs")}
                if "payment_overrides_json" not in po_cols:
                    conn.execute(text("ALTER TABLE planilla_outputs ADD COLUMN payment_overrides_json JSONB"))
                    logger.info("Added column planilla_outputs.payment_overrides_json")
                if "start_date" not in po_cols:
                    conn.execute(text("ALTER TABLE planilla_outputs ADD COLUMN start_date DATE"))
                    logger.info("Added column planilla_outputs.start_date")
                if "end_date" not in po_cols:
                    conn.execute(text("ALTER TABLE planilla_outputs ADD COLUMN end_date DATE"))
                    logger.info("Added column planilla_outputs.end_date")
                if "discount_mode" not in po_cols:
                    conn.execute(text("ALTER TABLE planilla_outputs ADD COLUMN discount_mode VARCHAR(20) NOT NULL DEFAULT 'attendance'"))
                    logger.info("Added column planilla_outputs.discount_mode")

            # teachers.nit
            teacher_cols = {c["name"] for c in inspector.get_columns("teachers")}
            if "nit" not in teacher_cols:
                conn.execute(text("ALTER TABLE teachers ADD COLUMN nit VARCHAR(50)"))
                logger.info("Added column teachers.nit")

            # designations.academic_period
            # NOTE: we intentionally hardcode the default here instead of
            # reading app_settings — this runs during startup migration
            # before the SessionLocal for app_settings is even used, and
            # the DEFAULT only backfills existing rows (new rows come from
            # the upload flow which reads the live setting).
            if inspector.has_table("designations"):
                desig_cols = {c["name"] for c in inspector.get_columns("designations")}
                if "designation_type" not in desig_cols:
                    conn.execute(text(
                        "ALTER TABLE designations ADD COLUMN designation_type VARCHAR(20) NOT NULL DEFAULT 'regular'"
                    ))
                    logger.info("Added column designations.designation_type")
                if "academic_period" not in desig_cols:
                    conn.execute(text(
                        "ALTER TABLE designations ADD COLUMN academic_period VARCHAR(20) NOT NULL DEFAULT 'I/2026'"
                    ))
                    logger.info("Added column designations.academic_period")

                    # Drop old unique constraint (didn't include period) and create new one
                    try:
                        conn.execute(text(
                            "ALTER TABLE designations DROP CONSTRAINT IF EXISTS "
                            "uq_designation_teacher_subject_semester_group"
                        ))
                        conn.execute(text(
                            "ALTER TABLE designations ADD CONSTRAINT "
                            "uq_designation_teacher_subject_semester_group_period "
                            "UNIQUE (teacher_ci, subject, semester, group_code, academic_period)"
                        ))
                        logger.info("Updated designations unique constraint to include academic_period")
                    except Exception as constraint_exc:
                        logger.warning("Could not update designations constraint: %s", constraint_exc)

                # ─── E6: Scheduling FK columns on designations ────────────
                if "source" not in desig_cols:
                    conn.execute(text(
                        "ALTER TABLE designations ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'legacy_import'"
                    ))
                    logger.info("Added column designations.source")
                if "status" not in desig_cols:
                    conn.execute(text(
                        "ALTER TABLE designations ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'confirmed'"
                    ))
                    logger.info("Added column designations.status")
                if "academic_period_id" not in desig_cols:
                    conn.execute(text(
                        "ALTER TABLE designations ADD COLUMN academic_period_id INTEGER REFERENCES academic_periods(id) ON DELETE RESTRICT"
                    ))
                    logger.info("Added column designations.academic_period_id")
                if "subject_id" not in desig_cols:
                    conn.execute(text(
                        "ALTER TABLE designations ADD COLUMN subject_id INTEGER REFERENCES subjects(id) ON DELETE RESTRICT"
                    ))
                    logger.info("Added column designations.subject_id")
                if "group_id" not in desig_cols:
                    conn.execute(text(
                        "ALTER TABLE designations ADD COLUMN group_id INTEGER REFERENCES groups(id) ON DELETE RESTRICT"
                    ))
                    logger.info("Added column designations.group_id")

                # FK-based unique constraint (E6)
                try:
                    conn.execute(text(
                        "ALTER TABLE designations ADD CONSTRAINT "
                        "uq_designation_teacher_period_subject_group_fk "
                        "UNIQUE (teacher_ci, academic_period_id, subject_id, group_id)"
                    ))
                    logger.info("Added FK-based unique constraint on designations")
                except Exception:
                    pass  # Already exists or NULLable columns — OK

            conn.commit()
    except Exception as exc:
        logger.warning("Column migration check failed (may be first run): %s", exc)


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

    # Ensure new columns exist on existing databases (create_all doesn't add columns)
    _run_column_migrations()

    # Seed default business settings if the table is empty.
    # This must run AFTER create_tables() so the ``app_settings`` table exists.
    try:
        from app.models.app_setting import AppSetting
        from app.services import app_settings_service

        db = SessionLocal()
        try:
            # Per-key upsert: only seed keys that don't already exist.
            # This survives partial seeds and future additions of new keys.
            existing_keys = {row[0] for row in db.query(AppSetting.key).all()}
            defaults_spec = [
                ("ACTIVE_ACADEMIC_PERIOD", "I/2026", "Período académico activo (ej: I/2026, II/2025)"),
                ("COMPANY_NAME", "UNIPANDO S.R.L.", "Nombre de la empresa para el encabezado de planilla salarios"),
                ("COMPANY_NIT", "456850023", "NIT de la empresa para el encabezado de planilla salarios"),
                ("HOURLY_RATE", "70.0", "Tarifa por hora académica en Bs (docentes de teoría)"),
                ("PRACTICE_HOURLY_RATE", "50.0", "Tarifa por hora académica en Bs (docentes asistenciales / prácticas)"),
            ]
            added = 0
            for key, value, desc in defaults_spec:
                if key not in existing_keys:
                    db.add(AppSetting(key=key, value=value, description=desc))
                    added += 1
            if added:
                db.commit()
                app_settings_service.invalidate_cache()
                logger.info("Seeded %d missing app settings", added)
        finally:
            db.close()
    except Exception as exc:
        logger.exception("Failed to seed app_settings on startup: %s", exc)

    # Seed default shifts (M, T, N) if they don't exist
    try:
        from app.scheduling.services.shift_service import ShiftService

        db = SessionLocal()
        try:
            shift_svc = ShiftService()
            shift_svc.seed_defaults(db)
        finally:
            db.close()
    except Exception as exc:
        logger.exception("Failed to seed shifts on startup: %s", exc)

    # Create default admin users if none exist (admin, daniel, pedro)
    try:
        from app.services.auth_service import auth_service

        db = SessionLocal()
        try:
            auth_service.create_default_admin(db)
        finally:
            db.close()
    except Exception as exc:
        logger.exception("Failed to create default admin on startup: %s", exc)

    # Fix any unlinked docente users on startup
    try:
        from app.models.user import User as UserModel
        from app.models.teacher import Teacher as TeacherModel

        db = SessionLocal()
        try:
            unlinked = db.query(UserModel).filter(
                UserModel.role == "docente",
                UserModel.teacher_ci.is_(None),
            ).all()

            if unlinked:
                linked = 0
                for user in unlinked:
                    # Only exact CI match — name matching is too dangerous for payroll data
                    teacher = db.query(TeacherModel).filter(TeacherModel.ci == user.ci).first()
                    if teacher:
                        user.teacher_ci = teacher.ci
                        linked += 1
                if linked:
                    db.commit()
                    logger.info("Startup: linked %d docente users to teachers", linked)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to link users on startup: %s", exc)

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
app.include_router(billing_publication_router)
app.include_router(activity_log_router)
app.include_router(contracts_router)
app.include_router(admin_router)
app.include_router(admin_settings_router)
app.include_router(practice_attendance_router)
app.include_router(practice_planilla_router)
app.include_router(scheduling_router)
app.include_router(scheduling_v2_router)
app.include_router(rooms_router)
app.include_router(slots_router)
app.include_router(scheduling_designations_router)


@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint — verifies the API is running."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "service": settings.APP_TITLE,
    }
