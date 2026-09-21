import importlib.util
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.database import Base


REVISION = "a9c1e3f5b703"
PREDECESSOR = "f8b0d2e4a602"
TABLE = "academic_schedule_assignments"


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / name}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/a9c1e3f5b703_add_academic_schedule_assignments.py"
    spec = importlib.util.spec_from_file_location("academic_schedule_assignment_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_assignment_table(
    engine,
    weakened=False,
    timestamp_defaults=("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP"),
):
    metadata, table = _module()._schema()
    for column_name, default in zip(("created_at", "updated_at"), timestamp_defaults):
        table.c[column_name].server_default = (
            sa.DefaultClause(sa.text(default)) if default is not None else None
        )
    if weakened:
        constraint = next(
            item for item in table.constraints
            if item.name == "ck_academic_schedule_assignment_date_order"
        )
        table.constraints.remove(constraint)
        table.append_constraint(sa.CheckConstraint(
            "true", name="ck_academic_schedule_assignment_date_order"
        ))
    metadata.create_all(engine, tables=[table])


def _table_snapshot(engine):
    inspector = sa.inspect(engine)
    return {
        "columns": [
            (item["name"], str(item["type"]), item["nullable"], item.get("default"))
            for item in inspector.get_columns(TABLE)
        ],
        "primary_key": inspector.get_pk_constraint(TABLE),
        "checks": inspector.get_check_constraints(TABLE),
        "foreign_keys": inspector.get_foreign_keys(TABLE),
        "indexes": inspector.get_indexes(TABLE),
        "unique_constraints": inspector.get_unique_constraints(TABLE),
    }


@pytest.fixture
def postgres_assignment_migration(monkeypatch):
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


def test_assignment_migration_fresh_sqlite_upgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "assignment-fresh.sqlite3")
    command.upgrade(config, REVISION)
    inspector = sa.inspect(engine)
    assert TABLE in inspector.get_table_names()
    assert {item["name"] for item in inspector.get_indexes(TABLE)} == {
        "ix_academic_schedule_assignments_block_dates",
        "ix_academic_schedule_assignments_teacher_dates",
    }
    engine.dispose()


def test_assignment_migration_adopts_exact_compatible_table(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "assignment-compatible.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _create_assignment_table(engine)
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
    engine.dispose()


@pytest.mark.parametrize(
    "reflected_default",
    [
        "now()",
        "pg_catalog.now()",
        "CURRENT_TIMESTAMP",
        "(CURRENT_TIMESTAMP)",
        "transaction_timestamp()",
        "(now())::timestamp without time zone",
    ],
)
def test_assignment_migration_normalizes_current_timestamp_reflection_variants(
    reflected_default,
):
    module = _module()
    assert module._server_default_signature(reflected_default) == ("current_timestamp",)


@pytest.mark.parametrize(
    "timestamp_defaults",
    [
        (None, "CURRENT_TIMESTAMP"),
        ("CURRENT_TIMESTAMP", None),
        (None, None),
    ],
)
def test_assignment_migration_rejects_missing_timestamp_defaults_without_mutation(
    tmp_path, monkeypatch, timestamp_defaults
):
    engine, config = _config(tmp_path, monkeypatch, "assignment-missing-default.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _create_assignment_table(engine, timestamp_defaults=timestamp_defaults)
    before = _table_snapshot(engine)
    with pytest.raises(RuntimeError, match="server default"):
        command.upgrade(config, REVISION)
    assert _table_snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


@pytest.mark.parametrize("incompatible_default", ["CURRENT_DATE", "'2000-01-01 00:00:00'"])
def test_assignment_migration_rejects_incompatible_timestamp_default_without_mutation(
    tmp_path, monkeypatch, incompatible_default
):
    engine, config = _config(tmp_path, monkeypatch, "assignment-wrong-default.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _create_assignment_table(
        engine, timestamp_defaults=(incompatible_default, "CURRENT_TIMESTAMP")
    )
    before = _table_snapshot(engine)
    with pytest.raises(RuntimeError, match="column created_at has incompatible server default"):
        command.upgrade(config, REVISION)
    assert _table_snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


def test_assignment_migration_rejects_weakened_check_without_stamping(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "assignment-weakened.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _create_assignment_table(engine, weakened=True)
    before = sa.inspect(engine).get_check_constraints(TABLE)
    with pytest.raises(RuntimeError, match="check constraint .* definition differs"):
        command.upgrade(config, REVISION)
    assert sa.inspect(engine).get_check_constraints(TABLE) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


def test_assignment_migration_rejects_partial_schema_unchanged(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "assignment-partial.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text(f"CREATE TABLE {TABLE} (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match=f"Incompatible pre-existing table {TABLE}"):
        command.upgrade(config, REVISION)
    assert [item["name"] for item in sa.inspect(engine).get_columns(TABLE)] == ["id"]
    engine.dispose()


def test_assignment_migration_refuses_destructive_downgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "assignment-downgrade.sqlite3")
    command.upgrade(config, REVISION)
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREDECESSOR)
    assert TABLE in sa.inspect(engine).get_table_names()
    engine.dispose()


def test_assignment_migration_matches_model_constraints_and_indexes():
    _metadata, migrated = _module()._schema()
    model = Base.metadata.tables[TABLE]
    assert {
        (constraint.name, str(constraint.sqltext))
        for constraint in migrated.constraints if isinstance(constraint, sa.CheckConstraint)
    } == {
        (constraint.name, str(constraint.sqltext))
        for constraint in model.constraints if isinstance(constraint, sa.CheckConstraint)
    }
    assert {
        (index.name, tuple(column.name for column in index.columns), index.unique)
        for index in migrated.indexes
    } == {
        (index.name, tuple(column.name for column in index.columns), index.unique)
        for index in model.indexes
    }


def test_postgresql_assignment_exact_adoption(postgres_assignment_migration):
    engine, config = postgres_assignment_migration
    command.upgrade(config, PREDECESSOR)
    _create_assignment_table(engine)
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION


@pytest.mark.parametrize(
    "timestamp_defaults",
    [
        (None, "CURRENT_TIMESTAMP"),
        ("CURRENT_TIMESTAMP", None),
        (None, None),
        ("CURRENT_DATE", "CURRENT_TIMESTAMP"),
    ],
)
def test_postgresql_assignment_default_attacks_rejected_without_mutation(
    postgres_assignment_migration, timestamp_defaults
):
    engine, config = postgres_assignment_migration
    command.upgrade(config, PREDECESSOR)
    _create_assignment_table(engine, timestamp_defaults=timestamp_defaults)
    before = _table_snapshot(engine)
    with pytest.raises(RuntimeError, match="server default"):
        command.upgrade(config, REVISION)
    assert _table_snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR


def test_postgresql_assignment_weakened_check_attack_rejected(postgres_assignment_migration):
    engine, config = postgres_assignment_migration
    command.upgrade(config, PREDECESSOR)
    _create_assignment_table(engine, weakened=True)
    with pytest.raises(RuntimeError, match="check constraint .* definition differs"):
        command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR


def test_postgresql_assignment_fresh_upgrade_and_check(postgres_assignment_migration):
    _engine, config = postgres_assignment_migration
    command.upgrade(config, "head")
    command.check(config)
