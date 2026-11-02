import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import command

from app.database import Base
from tests.test_academic_records_migration import _config

REVISION = "a4b6c8d0e2f5"
PREDECESSOR = "f3a5b7c9d1e3"
TABLES = ("migration_document_types", "student_migration_documents")


def _module():
    path = next((Path(__file__).parents[1] / "alembic/versions").glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location("migration_documents_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_the_migration_document_tables(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    with engine.connect() as connection:
        assert not set(TABLES) & set(sa.inspect(connection).get_table_names())
    engine.dispose()  # a pooled SQLite connection keeps the pre-upgrade schema

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        assert set(TABLES) <= set(inspector.get_table_names())
        foreign_keys = {(fk["constrained_columns"][0], fk["referred_table"], fk["options"].get("ondelete"))
                        for fk in inspector.get_foreign_keys("student_migration_documents")}
        assert foreign_keys == {
            ("student_id", "students", "RESTRICT"), ("document_type_id", "migration_document_types", "RESTRICT"),
            ("recorded_by", "users", "SET NULL"),
        }
        assert [u["column_names"] for u in inspector.get_unique_constraints("student_migration_documents")] == [
            ["student_id", "document_type_id"]]
        assert [u["column_names"] for u in inspector.get_unique_constraints("migration_document_types")] == [["name"]]
        for table in TABLES:
            assert connection.scalar(sa.text(f"SELECT count(*) FROM {table}")) == 0


def test_migration_tables_match_the_orm_columns():
    migration = {table.name: table for table in _module()._tables(sa.MetaData())}
    for name in TABLES:
        orm = Base.metadata.tables[name]
        assert set(migration[name].columns.keys()) == set(orm.columns.keys()), name
        for column in orm.columns:
            assert migration[name].columns[column.name].nullable is column.nullable, (name, column.name)
        for kind in (sa.UniqueConstraint, sa.CheckConstraint):
            assert {c.name for c in orm.constraints if isinstance(c, kind)} == {
                c.name for c in migration[name].constraints if isinstance(c, kind)}, name

