import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.database import Base

REVISION = "d1e3f5a7b9c2"
PREDECESSOR = "c5e7a9b1d3f4"
TABLES = (
    "curriculum_plans", "curriculum_subjects", "academic_terms",
    "academic_history_imports", "students", "student_subject_records",
)


def _config(tmp_path, monkeypatch):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / 'academic-records.sqlite'}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def _module():
    path = next((Path(__file__).parents[1] / "alembic/versions").glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location("academic_records_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_the_academic_record_tables(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    with engine.connect() as connection:
        assert not set(TABLES) & set(sa.inspect(connection).get_table_names())

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        assert set(TABLES) <= set(inspector.get_table_names())
        records = {fk["referred_table"]: fk for fk in inspector.get_foreign_keys("student_subject_records")}
        assert records["teachers"]["options"].get("ondelete") == "SET NULL"
        assert records["students"]["options"].get("ondelete") == "RESTRICT"
        unique = [u["column_names"] for u in inspector.get_unique_constraints("student_subject_records")]
        assert ["legacy_registration_id"] in unique
        for table in TABLES:
            assert connection.scalar(sa.text(f"SELECT count(*) FROM {table}")) == 0


def test_migration_tables_match_the_orm_columns():
    migration = {table.name: table for table in _module()._tables(sa.MetaData())}
    for name in TABLES:
        orm = Base.metadata.tables[name]
        assert set(migration[name].columns.keys()) == set(orm.columns.keys()), name
        for column in orm.columns:
            assert migration[name].columns[column.name].nullable is column.nullable, (name, column.name)
        orm_unique = {c.name for c in orm.constraints if isinstance(c, sa.UniqueConstraint)}
        migration_unique = {c.name for c in migration[name].constraints if isinstance(c, sa.UniqueConstraint)}
        assert orm_unique == migration_unique, name


def test_upgrade_accepts_compatible_preexisting_tables(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, REVISION)
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE alembic_version SET version_num = :v"), {"v": PREDECESSOR})

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION


def test_upgrade_rejects_an_incompatible_preexisting_table(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE students (id INTEGER PRIMARY KEY, nombre TEXT)"))

    with pytest.raises(RuntimeError, match="students"):
        command.upgrade(config, REVISION)


def test_downgrade_refuses(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, REVISION)
    with pytest.raises(RuntimeError, match="backup"):
        command.downgrade(config, PREDECESSOR)
    with engine.connect() as connection:
        assert set(TABLES) <= set(sa.inspect(connection).get_table_names())
