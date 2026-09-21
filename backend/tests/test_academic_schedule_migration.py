import importlib.util
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.database import Base

REVISION = "f8b0d2e4a602"
PREDECESSOR = "e7a9c1d3f501"
TABLES = {"academic_schedule_drafts", "academic_schedule_blocks"}


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / name}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/f8b0d2e4a602_add_academic_schedule_drafts.py"
    spec = importlib.util.spec_from_file_location("academic_schedule_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_schedule_tables(engine, weakened_constraint=None):
    _metadata, tables = _module()._schema()
    if weakened_constraint:
        target = next(
            table for table in tables.values()
            if any(constraint.name == weakened_constraint for constraint in table.constraints)
        )
        original = next(
            constraint for constraint in target.constraints
            if constraint.name == weakened_constraint
        )
        target.constraints.remove(original)
        target.append_constraint(sa.CheckConstraint("true", name=weakened_constraint))
    _metadata.create_all(engine, tables=[tables[name] for name in ("academic_schedule_drafts", "academic_schedule_blocks")])


@pytest.fixture
def postgres_migration(tmp_path, monkeypatch):
    del tmp_path
    url = os.getenv("ACADEMIC_SCHEDULE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ACADEMIC_SCHEDULE_TEST_POSTGRES_URL is not configured")
    parsed = sa.engine.make_url(url)
    if parsed.get_backend_name() != "postgresql" or "test" not in (parsed.database or ""):
        pytest.fail("ACADEMIC_SCHEDULE_TEST_POSTGRES_URL must target a dedicated PostgreSQL test database")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    yield engine, config
    engine.dispose()


def test_academic_schedule_migration_upgrades_sqlite(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "academic-schedule.sqlite3")
    command.upgrade(config, REVISION)
    inspector = sa.inspect(engine)
    assert TABLES.issubset(inspector.get_table_names())
    assert {item["name"] for item in inspector.get_check_constraints("academic_schedule_blocks")} == {
        "ck_academic_schedule_block_activity_type",
        "ck_academic_schedule_block_time_order",
        "ck_academic_schedule_block_weekday",
    }
    engine.dispose()


def test_compatible_precreated_schedule_tables_are_adopted(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "compatible-academic-schedule.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _create_schedule_tables(engine)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO academic_programs (id, code, name, active, created_at, updated_at) "
            "VALUES (901, 'SCHEDULE', 'Programa', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        connection.execute(sa.text(
            "INSERT INTO academic_schedule_drafts "
            "(id, program_id, academic_period, name, normalized_name, status, created_at, updated_at) "
            "VALUES (902, 901, 'II/2026', 'Preservar', 'preservar', 'draft', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT name FROM academic_schedule_drafts WHERE id = 902")) == "Preservar"
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
    engine.dispose()


@pytest.mark.parametrize(
    "constraint_name",
    ["ck_academic_schedule_draft_status", "ck_academic_schedule_block_time_order"],
)
def test_same_name_weakened_sqlite_check_is_rejected_without_schema_mutation(
    tmp_path, monkeypatch, constraint_name
):
    engine, config = _config(tmp_path, monkeypatch, f"weakened-{constraint_name}.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _create_schedule_tables(engine, constraint_name)
    before = {
        table: sa.inspect(engine).get_check_constraints(table)
        for table in TABLES
    }

    with pytest.raises(RuntimeError, match=rf"check constraint {constraint_name} definition differs"):
        command.upgrade(config, REVISION)

    inspector = sa.inspect(engine)
    assert {table: inspector.get_check_constraints(table) for table in TABLES} == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


def test_incompatible_schedule_table_is_rejected_before_mutation(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "incompatible-academic-schedule.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE academic_schedule_drafts (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing table academic_schedule_drafts"):
        command.upgrade(config, REVISION)
    inspector = sa.inspect(engine)
    assert "academic_schedule_blocks" not in inspector.get_table_names()
    assert [column["name"] for column in inspector.get_columns("academic_schedule_drafts")] == ["id"]
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


def test_schedule_downgrade_refuses_destructive_removal(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "academic-schedule-downgrade.sqlite3")
    command.upgrade(config, REVISION)
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREDECESSOR)
    assert TABLES.issubset(sa.inspect(engine).get_table_names())
    engine.dispose()


def test_schedule_migration_contract_matches_orm_constraints_and_indexes():
    _metadata, migration_tables = _module()._schema()
    for name in TABLES:
        model = Base.metadata.tables[name]
        migrated = migration_tables[name]
        assert {
            (constraint.name, tuple(column.name for column in constraint.columns))
            for constraint in migrated.constraints if isinstance(constraint, sa.UniqueConstraint)
        } == {
            (constraint.name, tuple(column.name for column in constraint.columns))
            for constraint in model.constraints if isinstance(constraint, sa.UniqueConstraint)
        }
        assert {
            (index.name, tuple(column.name for column in index.columns), index.unique)
            for index in migrated.indexes
        } == {
            (index.name, tuple(column.name for column in index.columns), index.unique)
            for index in model.indexes
        }


def test_postgresql_exact_compatible_constraints_are_adopted(postgres_migration):
    engine, config = postgres_migration
    command.upgrade(config, PREDECESSOR)
    _create_schedule_tables(engine)
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION


@pytest.mark.parametrize(
    "constraint_name",
    ["ck_academic_schedule_draft_status", "ck_academic_schedule_block_time_order"],
)
def test_postgresql_same_name_weakened_check_is_rejected_without_stamping(
    postgres_migration, constraint_name
):
    engine, config = postgres_migration
    command.upgrade(config, PREDECESSOR)
    _create_schedule_tables(engine, constraint_name)
    with pytest.raises(RuntimeError, match=rf"check constraint {constraint_name} definition differs"):
        command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR


def test_postgresql_partial_schema_rejection_is_non_mutating(postgres_migration):
    engine, config = postgres_migration
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE academic_schedule_drafts (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing table academic_schedule_drafts"):
        command.upgrade(config, REVISION)
    inspector = sa.inspect(engine)
    assert "academic_schedule_blocks" not in inspector.get_table_names()
    assert [column["name"] for column in inspector.get_columns("academic_schedule_drafts")] == ["id"]
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR


def test_postgresql_fresh_upgrade_and_alembic_check_are_clean(postgres_migration):
    _engine, config = postgres_migration
    command.upgrade(config, "head")
    command.check(config)
