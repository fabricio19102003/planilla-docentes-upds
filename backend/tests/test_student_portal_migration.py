import sqlalchemy as sa
from alembic import command

from tests.test_academic_records_migration import _config

REVISION = "e2f4a6c8d0b1"
TABLES = ("student_accounts", "reenrollment_windows", "reenrollment_requests", "reenrollment_request_items")


def test_upgrade_creates_the_student_portal_tables(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, "d1e3f5a7b9c2")
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

        assert foreign_keys("student_accounts") == {
            ("student_id", "students", "RESTRICT"), ("temporary_issued_by", "users", "SET NULL"),
        }
        assert foreign_keys("reenrollment_requests") == {
            ("student_id", "students", "RESTRICT"), ("window_id", "reenrollment_windows", "RESTRICT"),
            ("main_group_id", "academic_groups", "RESTRICT"), ("handled_by", "users", "SET NULL"),
        }
        assert foreign_keys("reenrollment_request_items") == {
            ("request_id", "reenrollment_requests", "CASCADE"), ("group_id", "academic_groups", "RESTRICT"),
        }
        assert [u["column_names"] for u in inspector.get_unique_constraints("reenrollment_requests")] == [
            ["student_id", "window_id"],
        ]
