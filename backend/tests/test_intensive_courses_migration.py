import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import command

from app.database import Base
from tests.test_academic_records_migration import _config

REVISION = "f3a5b7c9d1e3"
PREDECESSOR = "e2f4a6c8d0b1"
TABLES = ("intensive_course_settings", "intensive_courses", "intensive_enrollments")


def _module():
    path = next((Path(__file__).parents[1] / "alembic/versions").glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location("intensive_courses_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_the_intensive_course_tables_and_the_default_settings(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    with engine.connect() as connection:
        assert not set(TABLES) & set(sa.inspect(connection).get_table_names())
    engine.dispose()  # a pooled SQLite connection keeps the pre-upgrade schema

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        assert set(TABLES) <= set(inspector.get_table_names())

        def foreign_keys(table):
            return {(fk["constrained_columns"][0], fk["referred_table"], fk["options"].get("ondelete"))
                    for fk in inspector.get_foreign_keys(table)}

        assert foreign_keys("intensive_courses") == {
            ("subject_id", "academic_subjects", "RESTRICT"), ("teacher_ci", "teachers", "RESTRICT"),
            ("created_by", "users", "SET NULL"), ("closed_by", "users", "SET NULL"),
        }
        assert foreign_keys("intensive_enrollments") == {
            ("course_id", "intensive_courses", "CASCADE"), ("student_id", "students", "RESTRICT"),
        }
        assert foreign_keys("intensive_course_settings") == {("updated_by", "users", "SET NULL")}
        assert [u["column_names"] for u in inspector.get_unique_constraints("intensive_courses")] == [
            ["term_code", "subject_id"]]
        assert [u["column_names"] for u in inspector.get_unique_constraints("intensive_enrollments")] == [
            ["course_id", "student_id"]]
        # One settings row with the margin and price limits; the rates stay unconfigured.
        row = connection.execute(sa.text(
            "SELECT id, theory_hourly_rate, practice_hourly_rate, margin_factor, min_price, max_price "
            "FROM intensive_course_settings")).all()
        assert [(r[0], r[1], r[2], float(r[3]), r[4], r[5]) for r in row] == [(1, None, None, 1.1, 1200, 1600)]
        for table in ("intensive_courses", "intensive_enrollments"):
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
