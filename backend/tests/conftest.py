"""
Test configuration and shared fixtures.
Phase 2 will add fixtures for DB session, test client, sample data.
"""
import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db


# Test database URL (defaults to SQLite smoke DB to avoid external dependencies)
_TEST_DB_FILE = os.path.join(tempfile.gettempdir(), "planilla_docentes_upds_test.sqlite")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", f"sqlite:///{_TEST_DB_FILE}")


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create a fresh DB session for each test, rolled back after."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
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
    with TestClient(app) as test_client:
        # Pre-set auth header for all requests from this client
        test_client.headers["Authorization"] = f"Bearer {admin_token}"
        yield test_client
    app.dependency_overrides.clear()
