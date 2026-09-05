import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

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
    medicine_schedules_router,
    twilio_whatsapp_router,
    billing_media_router,
)

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    return settings.APP_ENV.strip().lower() == "production"


def _validate_production_settings() -> None:
    if not _is_production():
        return

    errors: list[str] = []
    if settings.AUTO_SCHEMA_BOOTSTRAP:
        errors.append("AUTO_SCHEMA_BOOTSTRAP must be false")
    if len(settings.JWT_SECRET) < 64 or settings.JWT_SECRET == "planilla-docentes-upds-secret-key-change-in-production":
        errors.append("JWT_SECRET must be a non-default secret of at least 64 characters")

    def strong_bootstrap_password(value: str | None) -> bool:
        if value is None:
            return True
        return (
            len(value) >= 16
            and any(character.isupper() for character in value)
            and any(character.islower() for character in value)
            and any(character.isdigit() for character in value)
        )

    if not strong_bootstrap_password(settings.DOCENTE_DEFAULT_PASSWORD):
        errors.append("DOCENTE_DEFAULT_PASSWORD must contain 16+ characters, upper/lowercase, and a digit")
    if not strong_bootstrap_password(settings.ADMIN_DEFAULT_PASSWORD):
        errors.append("ADMIN_DEFAULT_PASSWORD must contain 16+ characters, upper/lowercase, and a digit")
    if any("localhost" in origin or "127.0.0.1" in origin for origin in settings.get_cors_origins()):
        errors.append("CORS_ORIGINS must not contain development origins")
    if settings.EMAIL_ENABLED and (not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL):
        errors.append("EMAIL_ENABLED requires RESEND_API_KEY and RESEND_FROM_EMAIL")
    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


def _verify_database_schema() -> None:
    """Fail unless the connected database exactly matches the packaged Alembic heads."""
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    alembic_config = AlembicConfig(str(alembic_ini))
    alembic_config.set_main_option("script_location", str(alembic_ini.parent / "alembic"))
    script = ScriptDirectory.from_config(alembic_config)
    expected_heads = set(script.get_heads())

    with engine.connect() as connection:
        current_heads = set(MigrationContext.configure(connection).get_current_heads())

    if not current_heads or current_heads != expected_heads:
        raise RuntimeError(
            "Database schema is not on the packaged Alembic head; "
            "run the separate migration gate before starting the API"
        )


def _ensure_teacher_photo_storage() -> str:
    from app.services.teacher_photo_service import ensure_teacher_photos_dir

    return str(ensure_teacher_photos_dir())


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

            # billing_publications.billing_snapshot + version + planilla_type
            if inspector.has_table("billing_publications"):
                bp_cols = {c["name"] for c in inspector.get_columns("billing_publications")}
                if "billing_snapshot" not in bp_cols:
                    conn.execute(text("ALTER TABLE billing_publications ADD COLUMN billing_snapshot JSONB"))
                    logger.info("Added column billing_publications.billing_snapshot")
                if "version" not in bp_cols:
                    conn.execute(text("ALTER TABLE billing_publications ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))
                    logger.info("Added column billing_publications.version")
                if "planilla_type" not in bp_cols:
                    conn.execute(text(
                        "ALTER TABLE billing_publications ADD COLUMN planilla_type VARCHAR(20) NOT NULL DEFAULT 'regular'"
                    ))
                    logger.info("Added column billing_publications.planilla_type")

                # Drop old unique constraint (month, year) and replace with (month, year, planilla_type).
                # This is independent from column creation because a previous run may have added
                # the column but failed before replacing the constraint.
                unique_constraints = {
                    c["name"] for c in inspector.get_unique_constraints("billing_publications")
                }
                if "uq_billing_publication_month_year" in unique_constraints:
                    try:
                        conn.execute(text(
                            "ALTER TABLE billing_publications DROP CONSTRAINT IF EXISTS "
                            "uq_billing_publication_month_year"
                        ))
                        logger.info("Dropped old billing_publications unique constraint")
                    except Exception as constraint_exc:
                        logger.warning("Could not drop old billing_publications constraint: %s", constraint_exc)

                unique_constraints = {
                    c["name"] for c in inspector.get_unique_constraints("billing_publications")
                }
                if "uq_billing_publication_month_year_type" not in unique_constraints:
                    try:
                        conn.execute(text(
                            "ALTER TABLE billing_publications ADD CONSTRAINT "
                            "uq_billing_publication_month_year_type "
                            "UNIQUE (month, year, planilla_type)"
                        ))
                        logger.info("Updated billing_publications unique constraint to include planilla_type")
                    except Exception as constraint_exc:
                        logger.warning("Could not create billing_publications type-aware constraint: %s", constraint_exc)

                check_constraints = {
                    c["name"] for c in inspector.get_check_constraints("billing_publications")
                }
                if "ck_billing_publication_planilla_type" not in check_constraints:
                    try:
                        conn.execute(text(
                            "ALTER TABLE billing_publications ADD CONSTRAINT "
                            "ck_billing_publication_planilla_type "
                            "CHECK (planilla_type IN ('regular', 'practice'))"
                        ))
                        logger.info("Added billing_publications planilla_type check constraint")
                    except Exception as constraint_exc:
                        logger.warning("Could not create billing_publications planilla_type check constraint: %s", constraint_exc)

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
                if "excluded_days_json" not in po_cols:
                    conn.execute(text("ALTER TABLE planilla_outputs ADD COLUMN excluded_days_json JSONB"))
                    logger.info("Added column planilla_outputs.excluded_days_json")

            # practice_planilla_outputs.excluded_days_json
            if inspector.has_table("practice_planilla_outputs"):
                ppo_cols = {c["name"] for c in inspector.get_columns("practice_planilla_outputs")}
                if "excluded_days_json" not in ppo_cols:
                    conn.execute(text("ALTER TABLE practice_planilla_outputs ADD COLUMN excluded_days_json JSONB"))
                    logger.info("Added column practice_planilla_outputs.excluded_days_json")

            # teachers nullable profile/photo columns
            if inspector.has_table("teachers"):
                teacher_cols = {c["name"] for c in inspector.get_columns("teachers")}
                if "nit" not in teacher_cols:
                    conn.execute(text("ALTER TABLE teachers ADD COLUMN nit VARCHAR(50)"))
                    logger.info("Added column teachers.nit")
                if "photo_filename" not in teacher_cols:
                    conn.execute(text("ALTER TABLE teachers ADD COLUMN photo_filename VARCHAR(255)"))
                    logger.info("Added column teachers.photo_filename")
                if "photo_content_type" not in teacher_cols:
                    conn.execute(text("ALTER TABLE teachers ADD COLUMN photo_content_type VARCHAR(100)"))
                    logger.info("Added column teachers.photo_content_type")
                if "photo_updated_at" not in teacher_cols:
                    conn.execute(text("ALTER TABLE teachers ADD COLUMN photo_updated_at TIMESTAMP"))
                    logger.info("Added column teachers.photo_updated_at")

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
                if "contract_start_date" not in desig_cols:
                    conn.execute(text("ALTER TABLE designations ADD COLUMN contract_start_date DATE"))
                    logger.info("Added column designations.contract_start_date")
                if "contract_end_date" not in desig_cols:
                    conn.execute(text("ALTER TABLE designations ADD COLUMN contract_end_date DATE"))
                    logger.info("Added column designations.contract_end_date")

            conn.commit()
    except Exception as exc:
        logger.warning("Column migration check failed (may be first run): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: runs on startup and shutdown.
    Development may bootstrap schema for convenience. Production verifies an
    independently migrated Alembic head before running application seeds.
    """
    _validate_production_settings()

    if settings.AUTO_SCHEMA_BOOTSTRAP:
        try:
            create_tables()
        except Exception as exc:
            logger.exception("Failed to create tables on startup: %s", exc)

        # Development-only compatibility path. Production uses Alembic.
        _run_column_migrations()
    else:
        _verify_database_schema()
        logger.info("Database schema matches the packaged Alembic head")

    # Ensure local storage for public docente profile photos exists.
    _ensure_teacher_photo_storage()

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
                ("DOCENTE_CAN_EDIT_PROFILE", "false", "Permite a docentes editar sus datos de perfil desde el portal"),
                ("DOCENTE_CAN_EDIT_PHOTO", "false", "Permite a docentes subir o eliminar su propia foto de perfil"),
                ("MEDICINE_SCHEDULE_ASSISTANT_ENABLED", "false", "Habilita el asistente de horarios de Medicina"),
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
        if _is_production():
            raise

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
        if _is_production():
            raise

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
        if _is_production():
            raise

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

_ensure_teacher_photo_storage()
app.mount(
    "/uploads/teacher-photos",
    StaticFiles(directory=_ensure_teacher_photo_storage()),
    name="teacher-photos",
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
app.include_router(medicine_schedules_router)
app.include_router(twilio_whatsapp_router)
app.include_router(billing_media_router)


@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint — verifies the API is running."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "service": settings.APP_TITLE,
    }


@app.get("/ready", tags=["system"])
def readiness_check():
    """Verify database connectivity and writable persistent application paths."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        data_root = Path(__file__).resolve().parents[1] / "data"
        required_paths = [
            Path(settings.UPLOAD_DIR),
            data_root / "output",
            data_root / "reports",
            data_root / "contracts",
            data_root / "schedules",
            data_root / "retention_letters",
            data_root / "backups",
        ]
        unavailable = [path for path in required_paths if not path.is_dir() or not os.access(path, os.W_OK)]
        if unavailable:
            raise RuntimeError("persistent storage is unavailable")
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Service is not ready") from exc

    return {"status": "ready", "version": settings.APP_VERSION}
