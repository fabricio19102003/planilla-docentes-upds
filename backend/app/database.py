from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from typing import Generator

from app.config import settings


# SQLAlchemy 2.0 declarative base
class Base(DeclarativeBase):
    pass


# Sync engine (psycopg2)
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,  # Set True for SQL debug logging
    pool_pre_ping=True,  # Verify connections before use
    pool_size=5,
    max_overflow=10,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator:
    """FastAPI dependency: yields a DB session and ensures it's closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables defined in Base.metadata. Called at app startup."""
    # Import all models to ensure they're registered in Base.metadata
    import app.models  # noqa: F401
    import app.scheduling.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
