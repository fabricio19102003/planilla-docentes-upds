import json
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings

REVISION = "b3d5f7a9c1e2"
PREDECESSOR = "d7e9a1b3c5f7"


def _config(tmp_path, monkeypatch):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / 'aliases.sqlite'}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def _log(connection, details, created_at):
    connection.execute(
        sa.text(
            "INSERT INTO activity_logs (action, category, description, details, status, created_at) "
            "VALUES ('update_teacher', 'teachers', 'x', :details, 'success', :created_at)"
        ),
        {"details": json.dumps(details), "created_at": created_at},
    )


def test_upgrade_creates_aliases_from_logged_ci_changes(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        for ci in ("333", "900"):
            connection.execute(
                sa.text("INSERT INTO teachers (ci, full_name, created_at) VALUES (:ci, 'D', CURRENT_TIMESTAMP)"),
                {"ci": ci},
            )
        _log(connection, {"old_ci": "111", "new_ci": "222"}, datetime(2026, 9, 1))
        _log(connection, {"old_ci": "222", "new_ci": "333"}, datetime(2026, 9, 2))
        _log(connection, {"old_ci": "900", "new_ci": "900"}, datetime(2026, 9, 3))
        _log(connection, {"old_ci": "500", "new_ci": "600"}, datetime(2026, 9, 4))
        _log(connection, {"fields_updated": ["phone"]}, datetime(2026, 9, 5))

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT previous_ci, teacher_ci, changed_at FROM teacher_ci_aliases ORDER BY previous_ci")
        ).all()
    assert [(previous, teacher) for previous, teacher, _ in rows] == [("111", "333"), ("222", "333")]
    assert str(rows[0][2]).startswith("2026-09-01")


def test_upgrade_on_empty_database_reaches_head_with_alias_table(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)

    command.upgrade(config, "head")

    with engine.connect() as connection:
        assert "teacher_ci_aliases" in sa.inspect(connection).get_table_names()
        assert connection.scalar(sa.text("SELECT count(*) FROM teacher_ci_aliases")) == 0
