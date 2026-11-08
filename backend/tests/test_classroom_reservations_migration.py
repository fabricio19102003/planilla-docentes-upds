import sqlalchemy as sa
from alembic import command

from app.database import Base
from tests.test_academic_records_migration import _config

REVISION = "b5c7d9e1f3a6"
PREDECESSOR = "a4b6c8d0e2f5"
TABLE = "classroom_reservations"


def test_upgrade_creates_an_empty_reservations_table_matching_the_orm(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    with engine.connect() as connection:
        assert TABLE not in sa.inspect(connection).get_table_names()
    engine.dispose()  # a pooled SQLite connection keeps the pre-upgrade schema

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        orm = Base.metadata.tables[TABLE]
        columns = {column["name"]: column for column in inspector.get_columns(TABLE)}
        assert set(columns) == set(orm.columns.keys())
        for column in orm.columns:
            assert columns[column.name]["nullable"] is column.nullable, column.name
        foreign_keys = {(fk["constrained_columns"][0], fk["referred_table"], fk["options"].get("ondelete"))
                        for fk in inspector.get_foreign_keys(TABLE)}
        assert foreign_keys == {
            ("classroom_id", "classrooms", "RESTRICT"), ("teacher_ci", "teachers", "RESTRICT"),
            ("created_by_user_id", "users", "SET NULL"),
        }
        assert {index["name"] for index in inspector.get_indexes(TABLE)} == {index.name for index in orm.indexes}
        assert {check["name"] for check in inspector.get_check_constraints(TABLE)} == {
            constraint.name for constraint in orm.constraints if isinstance(constraint, sa.CheckConstraint)}
        assert connection.scalar(sa.text(f"SELECT count(*) FROM {TABLE}")) == 0
