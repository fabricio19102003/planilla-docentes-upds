import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.database import Base

REVISION = "e7a9c1d3f501"
PREDECESSOR = "a2c4e6f8b003"
TABLES = {
    "academic_programs", "academic_subjects", "subject_offerings",
    "academic_groups", "classrooms", "teacher_availability",
}


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / name}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/e7a9c1d3f501_add_academic_management_catalogs.py"
    spec = importlib.util.spec_from_file_location("academic_management_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _academic_model_tables():
    return [Base.metadata.tables[name] for name in TABLES]


def _deployed_migration_tables():
    _metadata, tables = _module()._schema()
    return list(tables.values())


def test_academic_management_migration_upgrades_sqlite(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "academic-management.sqlite3")
    command.upgrade(config, REVISION)

    inspector = sa.inspect(engine)
    assert TABLES.issubset(inspector.get_table_names())
    assert {item["name"] for item in inspector.get_check_constraints("teacher_availability")} == {
        "ck_teacher_availability_weekday", "ck_teacher_availability_time_order"
    }
    assert inspector.get_unique_constraints("teacher_availability") == []
    assert {item["name"] for item in inspector.get_unique_constraints("academic_groups")} == {
        "uq_academic_group_identity"
    }
    engine.dispose()


def test_compatible_precreated_tables_are_adopted_without_data_loss(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "compatible-academic-management.sqlite3")
    command.upgrade(config, PREDECESSOR)
    metadata, tables = _module()._schema()
    metadata.create_all(engine, tables=list(tables.values()))
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO academic_programs (id, code, name, active, created_at, updated_at) "
            "VALUES (101, 'SENTINEL', 'Preservar', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT name FROM academic_programs WHERE id = 101")) == "Preservar"
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
    engine.dispose()


def test_incompatible_precreated_table_is_rejected_before_mutation(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "incompatible-academic-management.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE academic_programs (id INTEGER PRIMARY KEY, code INTEGER)"))

    with pytest.raises(RuntimeError, match="Incompatible pre-existing table academic_programs"):
        command.upgrade(config, REVISION)

    inspector = sa.inspect(engine)
    assert "academic_subjects" not in inspector.get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


def test_downgrade_refuses_destructive_removal(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "academic-management-downgrade.sqlite3")
    command.upgrade(config, REVISION)

    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREDECESSOR)

    assert TABLES.issubset(sa.inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
    engine.dispose()


def test_migration_contract_matches_orm_unique_constraints_and_indexes():
    _metadata, migration_tables = _module()._schema()
    for name in TABLES:
        model = Base.metadata.tables[name]
        migrated = migration_tables[name]
        model_unique = {
            (constraint.name, tuple(column.name for column in constraint.columns))
            for constraint in model.constraints if isinstance(constraint, sa.UniqueConstraint)
        }
        migration_unique = {
            (constraint.name, tuple(column.name for column in constraint.columns))
            for constraint in migrated.constraints if isinstance(constraint, sa.UniqueConstraint)
        }
        assert migration_unique == model_unique
        assert {
            (index.name, tuple(column.name for column in index.columns), index.unique)
            for index in migrated.indexes
        } == {
            (index.name, tuple(column.name for column in index.columns), index.unique)
            for index in model.indexes
        }
