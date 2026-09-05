import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql

from app.config import settings
from app.database import Base


START_REVISION = "b8c4d2e6f901"
TARGET_TABLES = {
    "activity_logs",
    "app_settings",
    "billing_publications",
    "billing_publication_revisions",
    "notifications",
    "practice_attendance_logs",
    "practice_planilla_outputs",
    "reports",
}


def _runtime_schema_migration_module():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "c9d0e1f2a3b4_complete_runtime_schema.py"
    spec = importlib.util.spec_from_file_location("complete_runtime_schema_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(url: str, monkeypatch) -> Config:
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return config


def _engine_and_config(tmp_path, monkeypatch, name: str):
    url = f"sqlite:///{tmp_path / name}"
    return sa.create_engine(url), _config(url, monkeypatch)


def _create_pre_runtime_schema(engine) -> None:
    tables = [table for name, table in Base.metadata.tables.items() if name not in TARGET_TABLES]
    Base.metadata.create_all(engine, tables=tables)


def _head(config: Config) -> str:
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


def test_postgresql_double_precision_reflection_matches_float_without_weakening_numeric():
    migration = _runtime_schema_migration_module()

    assert migration._type_signature(postgresql.DOUBLE_PRECISION(precision=53)) == ("float",)
    assert migration._type_signature(sa.Float()) == ("float",)
    assert migration._type_signature(sa.Numeric(12, 2)) == ("numeric", 12, 2)


def test_empty_database_upgrade_to_head_creates_every_model_table(tmp_path, monkeypatch):
    engine, config = _engine_and_config(tmp_path, monkeypatch, "fresh-runtime.sqlite3")

    # A genuinely empty database must be fully owned by Alembic from base to
    # the dynamically discovered packaged head.
    command.upgrade(config, "head")

    inspector = sa.inspect(engine)
    assert set(Base.metadata.tables).issubset(inspector.get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == _head(config)
    engine.dispose()


def test_upgrade_adopts_compatible_precreated_tables_without_data_loss(tmp_path, monkeypatch):
    engine, config = _engine_and_config(tmp_path, monkeypatch, "compatible-runtime.sqlite3")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO app_settings (key, value, updated_at) "
                "VALUES ('MIGRATION_SENTINEL', 'preserve-me', CURRENT_TIMESTAMP)"
            )
        )
    command.stamp(config, START_REVISION)

    command.upgrade(config, "head")

    with engine.connect() as connection:
        assert connection.scalar(
            sa.text("SELECT value FROM app_settings WHERE key = 'MIGRATION_SENTINEL'")
        ) == "preserve-me"
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == _head(config)
    engine.dispose()


def test_upgrade_rejects_incompatible_precreated_table_before_creating_missing_tables(tmp_path, monkeypatch):
    engine, config = _engine_and_config(tmp_path, monkeypatch, "incompatible-runtime.sqlite3")
    _create_pre_runtime_schema(engine)
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE activity_logs ("
                "id INTEGER PRIMARY KEY, action INTEGER NOT NULL)"
            )
        )
    command.stamp(config, START_REVISION)

    with pytest.raises(RuntimeError, match="Incompatible pre-existing table activity_logs"):
        command.upgrade(config, "head")

    inspector = sa.inspect(engine)
    assert "app_settings" not in inspector.get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == START_REVISION
    engine.dispose()


def test_downgrade_is_non_destructive_and_requires_restore(tmp_path, monkeypatch):
    engine, config = _engine_and_config(tmp_path, monkeypatch, "blocked-downgrade.sqlite3")
    Base.metadata.create_all(engine)
    command.stamp(config, START_REVISION)
    command.upgrade(config, "head")
    head = _head(config)

    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, START_REVISION)

    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == head
        assert "activity_logs" in sa.inspect(connection).get_table_names()
    engine.dispose()
