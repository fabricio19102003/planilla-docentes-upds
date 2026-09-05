"""
Test configuration and shared fixtures.
Phase 2 will add fixtures for DB session, test client, sample data.
"""
import pytest
import os
import tempfile

# ── Test env defaults ─────────────────────────────────────────────────────────
# Ensure DATABASE_URL and ASYNC_DATABASE_URL are set before any app module is
# imported (pydantic-settings requires them at instantiation time).
# Tests can override via TEST_DATABASE_URL / environment variables.
_TEST_DB_FILE = os.path.join(tempfile.gettempdir(), "planilla_docentes_upds_test.sqlite")
_DEFAULT_DB_URL = f"sqlite:///{_TEST_DB_FILE}"
_DEFAULT_ASYNC_DB_URL = f"sqlite+aiosqlite:///{_TEST_DB_FILE}"

os.environ.setdefault("DATABASE_URL", _DEFAULT_DB_URL)
os.environ.setdefault("ASYNC_DATABASE_URL", _DEFAULT_ASYNC_DB_URL)
# ─────────────────────────────────────────────────────────────────────────────

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db


# Test database URL (defaults to SQLite smoke DB to avoid external dependencies)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", _DEFAULT_DB_URL)


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create an isolated session whose commits/rollbacks stay inside a savepoint."""
    connection = test_engine.connect()
    if test_engine.dialect.name == "sqlite":
        # pysqlite otherwise defers BEGIN until the first write. Releasing the
        # first SAVEPOINT would then commit test data outside our rollback.
        connection.exec_driver_sql("BEGIN")
        transaction = None
    else:
        transaction = connection.begin()
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
        join_transaction_mode="create_savepoint",
    )
    session = TestingSessionLocal()

    yield session

    session.close()
    if transaction is not None:
        transaction.rollback()
    else:
        connection.rollback()
    connection.close()


@pytest.fixture(scope="function")
def admin_token(db_session) -> str:
    """
    Create a test admin user in the DB and return a valid JWT token.

    The token uses sub=str(user.id) matching the production auth_service.create_access_token
    convention (see app/routers/auth.py line 36).
    """
    from app.models.user import User
    from app.services.auth_service import auth_service

    # Check if test admin already exists (e.g. from seed_core_data in the same session)
    existing = db_session.query(User).filter(User.ci == "TEST_ADMIN_9999").first()
    if existing is None:
        admin = User(
            ci="TEST_ADMIN_9999",
            full_name="Test Admin",
            password_hash=auth_service.hash_password("testpass123"),
            role="admin",
            is_active=True,
        )
        db_session.add(admin)
        db_session.flush()
        user_id = admin.id
    else:
        user_id = existing.id

    token = auth_service.create_access_token(data={"sub": str(user_id), "role": "admin"})
    return token


@pytest.fixture(scope="function")
def client(db_session, admin_token):
    """
    Test client with DB dependency override and admin JWT pre-set.

    All requests will include the Authorization: Bearer header so endpoints
    protected by require_admin or get_current_user work without 401 errors.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Do not enter the lifespan context here. Startup seeding uses the app's
    # independent SessionLocal connection, which would contend with the
    # per-test transaction and is not part of endpoint contract tests.
    test_client = TestClient(app)
    test_client.headers["Authorization"] = f"Bearer {admin_token}"
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()
