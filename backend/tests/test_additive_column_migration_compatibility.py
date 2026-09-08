from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings


def _config(tmp_path, monkeypatch, name: str) -> tuple[sa.Engine, Config]:
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / name}"
    engine = sa.create_engine(url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return engine, config


def test_resolution_snapshot_migration_adopts_compatible_precreated_column_without_data_loss(
    tmp_path,
    monkeypatch,
):
    engine, config = _config(tmp_path, monkeypatch, "resolution-snapshot.sqlite3")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE detail_requests ("
                "id INTEGER PRIMARY KEY, resolution_snapshot JSON NULL)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO detail_requests (id, resolution_snapshot) "
                "VALUES (1, :snapshot)"
            ),
            {"snapshot": '{"kind":"hours_summary","total_records":1}'},
        )
    command.stamp(config, "dd4e5f6a7b8c")

    command.upgrade(config, "e1f2a3b4c5d6")

    with engine.connect() as connection:
        assert connection.scalar(
            sa.text("SELECT resolution_snapshot FROM detail_requests WHERE id = 1")
        ) == '{"kind":"hours_summary","total_records":1}'
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "e1f2a3b4c5d6"
    engine.dispose()


def test_worker_heartbeat_migration_adopts_compatible_precreated_column_without_data_loss(
    tmp_path,
    monkeypatch,
):
    engine, config = _config(tmp_path, monkeypatch, "worker-heartbeat.sqlite3")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE billing_notification_capacity_windows ("
                "id INTEGER PRIMARY KEY, worker_heartbeat_at DATETIME NULL)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO billing_notification_capacity_windows "
                "(id, worker_heartbeat_at) VALUES (1, '2026-09-08 12:00:00')"
            )
        )
    command.stamp(config, "e1f2a3b4c5d6")

    command.upgrade(config, "f1a2b3c4d5e6")

    with engine.connect() as connection:
        assert connection.scalar(
            sa.text(
                "SELECT worker_heartbeat_at FROM billing_notification_capacity_windows WHERE id = 1"
            )
        ) == "2026-09-08 12:00:00"
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "f1a2b3c4d5e6"
    engine.dispose()
