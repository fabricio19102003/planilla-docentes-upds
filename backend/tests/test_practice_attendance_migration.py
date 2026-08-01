from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.config import settings


REVISION, DOWN_REVISION = "c4a8d7e2f901", "7d52c8e1a4f3"
INSERT_LOG = text(
    "INSERT INTO practice_attendance_logs "
    "(teacher_ci, designation_id, date, scheduled_start) "
    "VALUES ('CI-1', 1, '2026-08-01', '08:00:00')"
)


@pytest.fixture
def migration_db(tmp_path, monkeypatch):
    backend_dir = Path(__file__).parents[1]
    database_url = f"sqlite:///{tmp_path / 'pre_migration.sqlite3'}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE practice_attendance_logs ("
                "id INTEGER PRIMARY KEY, teacher_ci VARCHAR(20) NOT NULL, "
                "designation_id INTEGER NOT NULL, date DATE NOT NULL, "
                "scheduled_start TIME NOT NULL)"
            )
        )
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(
            text("INSERT INTO alembic_version VALUES (:revision)"),
            {"revision": DOWN_REVISION},
        )
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    yield config, engine
    engine.dispose()


def constraint_names(engine) -> set[str]:
    return {item["name"] for item in inspect(engine).get_unique_constraints("practice_attendance_logs")}


def test_sqlite_upgrade_enforces_unique_constraint_and_downgrade_reverses(migration_db):
    config, engine = migration_db
    with engine.begin() as connection:
        connection.execute(INSERT_LOG)

    command.upgrade(config, REVISION)
    assert "uq_practice_attendance_log" in constraint_names(engine)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(INSERT_LOG)

    command.downgrade(config, DOWN_REVISION)
    assert "uq_practice_attendance_log" not in constraint_names(engine)
    with engine.begin() as connection:
        connection.execute(INSERT_LOG)
        assert connection.scalar(text("SELECT count(*) FROM practice_attendance_logs")) == 2


def test_sqlite_upgrade_rejects_duplicates_without_modifying_them(migration_db):
    config, engine = migration_db
    with engine.begin() as connection:
        connection.execute(INSERT_LOG)
        connection.execute(INSERT_LOG)

    with pytest.raises(RuntimeError, match="existen registros duplicados"):
        command.upgrade(config, REVISION)

    assert "uq_practice_attendance_log" not in constraint_names(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM practice_attendance_logs")) == 2
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == DOWN_REVISION
