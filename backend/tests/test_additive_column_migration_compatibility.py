import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings


CONSENT_MIGRATION = "a2c4e6f8b001"
PREVIOUS_MIGRATION = "f1a2b3c4d5e6"


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


def _create_legacy_whatsapp_schema(engine: sa.Engine) -> None:
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE teachers (ci VARCHAR(20) PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(
            sa.text(
                "CREATE TABLE whatsapp_preferences ("
                "teacher_ci VARCHAR(20) PRIMARY KEY, phone_e164 VARCHAR(16) NOT NULL, "
                "is_verified BOOLEAN NOT NULL, consent_evidence TEXT, "
                "consent_revision INTEGER NOT NULL, opt_out_evidence TEXT, opted_out_at DATETIME)"
            )
        )


def test_consent_lifecycle_migration_upgrades_a_fresh_database_to_its_schema_head(
    tmp_path,
    monkeypatch,
):
    engine, config = _config(tmp_path, monkeypatch, "whatsapp-consent-fresh.sqlite3")

    command.upgrade(config, CONSENT_MIGRATION)

    inspector = sa.inspect(engine)
    assert inspector.has_table("whatsapp_preferences")
    assert inspector.has_table("whatsapp_consent_revisions")
    assert {"consent_source", "consented_at"}.issubset(
        {column["name"] for column in inspector.get_columns("whatsapp_preferences")}
    )
    assert "ck_whatsapp_preference_revision_nonnegative" in {
        check["name"] for check in inspector.get_check_constraints("whatsapp_preferences")
    }
    engine.dispose()


def test_consent_lifecycle_migration_adds_metadata_without_backfilling_legacy_preferences(
    tmp_path,
    monkeypatch,
):
    engine, config = _config(tmp_path, monkeypatch, "whatsapp-consent-legacy.sqlite3")
    _create_legacy_whatsapp_schema(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO teachers (ci) VALUES ('legacy-teacher')"))
        connection.execute(
            sa.text(
                "INSERT INTO whatsapp_preferences "
                "(teacher_ci, phone_e164, is_verified, consent_evidence, consent_revision) "
                "VALUES ('legacy-teacher', '+59170000000', 1, 'legacy-record', 1)"
            )
        )
    command.stamp(config, PREVIOUS_MIGRATION)

    command.upgrade(config, CONSENT_MIGRATION)

    inspector = sa.inspect(engine)
    assert {"consent_source", "consented_at"}.issubset(
        {column["name"] for column in inspector.get_columns("whatsapp_preferences")}
    )
    assert inspector.has_table("whatsapp_consent_revisions")
    assert "uq_whatsapp_consent_teacher_revision" in {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("whatsapp_consent_revisions")
    }
    with engine.connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT consent_source, consented_at FROM whatsapp_preferences "
                "WHERE teacher_ci = 'legacy-teacher'"
            )
        ).one()
        assert row == (None, None)
    engine.dispose()


def _create_compatible_consent_history_schema(engine: sa.Engine, *, revision_check: str = "revision > 0") -> None:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE whatsapp_consent_revisions ("
                "id INTEGER PRIMARY KEY, teacher_ci VARCHAR(20) NOT NULL "
                "REFERENCES teachers(ci) ON DELETE CASCADE, revision INTEGER NOT NULL, "
                "event_type VARCHAR(24) NOT NULL, phone_e164 VARCHAR(16) NOT NULL, "
                "is_verified BOOLEAN NOT NULL, consent_evidence TEXT, consent_source VARCHAR(32), "
                "consented_at DATETIME, opt_out_evidence TEXT, opted_out_at DATETIME, "
                "actor_user_id INTEGER REFERENCES users(id) ON DELETE RESTRICT, "
                "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                f"CONSTRAINT ck_whatsapp_consent_revision_positive CHECK ({revision_check}), "
                "CONSTRAINT uq_whatsapp_consent_teacher_revision UNIQUE (teacher_ci, revision))"
            )
        )
        connection.execute(
            sa.text(
                "CREATE INDEX ix_whatsapp_consent_revisions_teacher_ci "
                "ON whatsapp_consent_revisions (teacher_ci)"
            )
        )


def test_consent_lifecycle_migration_refuses_precreated_sqlite_history_when_fk_actions_cannot_be_proven(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "whatsapp-consent-history.sqlite3")
    _create_legacy_whatsapp_schema(engine)
    _create_compatible_consent_history_schema(engine)
    command.stamp(config, PREVIOUS_MIGRATION)

    with pytest.raises(RuntimeError, match="foreign-key actions on SQLite"):
        command.upgrade(config, CONSENT_MIGRATION)
    engine.dispose()


def _migration_module():
    path = Path(__file__).parents[1] / "alembic/versions/a2c4e6f8b001_add_whatsapp_consent_lifecycle.py"
    spec = importlib.util.spec_from_file_location("consent_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _PostgreSQLHistoryInspector:
    def __init__(self, columns, *, check="revision > 0"):
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        self.columns = columns
        self.check = check

    def get_columns(self, _table):
        return self.columns

    def get_pk_constraint(self, _table):
        return {"constrained_columns": ["id"]}

    def get_unique_constraints(self, _table):
        return [{"column_names": ["teacher_ci", "revision"]}]

    def get_check_constraints(self, _table):
        return [{"name": "ck_whatsapp_consent_revision_positive", "sqltext": self.check}]

    def get_indexes(self, _table):
        return [{"name": "ix_whatsapp_consent_revisions_teacher_ci", "column_names": ["teacher_ci"]}]

    def get_foreign_keys(self, _table):
        return [
            {"constrained_columns": ["teacher_ci"], "referred_table": "teachers", "referred_columns": ["ci"], "options": {"ondelete": "CASCADE"}},
            {"constrained_columns": ["actor_user_id"], "referred_table": "users", "referred_columns": ["id"], "options": {"ondelete": "RESTRICT"}},
        ]


def _postgresql_history_columns():
    from sqlalchemy.dialects import postgresql

    signatures = [
        ("id", sa.Integer(), False), ("teacher_ci", sa.String(20), False),
        ("revision", sa.Integer(), False), ("event_type", sa.String(24), False),
        ("phone_e164", sa.String(16), False), ("is_verified", sa.Boolean(), False),
        ("consent_evidence", sa.Text(), True), ("consent_source", sa.String(32), True),
        ("consented_at", postgresql.TIMESTAMP(), True), ("opt_out_evidence", sa.Text(), True),
        ("opted_out_at", postgresql.TIMESTAMP(), True), ("actor_user_id", sa.Integer(), True),
        ("created_at", postgresql.TIMESTAMP(), False),
    ]
    return [{"name": name, "type": type_, "nullable": nullable} for name, type_, nullable in signatures]


def test_consent_lifecycle_migration_adopts_postgresql_history_reflection():
    _migration_module()._validate_existing_history(
        _PostgreSQLHistoryInspector(_postgresql_history_columns())
    )


@pytest.mark.parametrize(("column", "type_", "nullable"), [
    ("phone_e164", sa.String(15), False),
    ("created_at", sa.String(), False),
    ("revision", sa.Integer(), True),
])
def test_consent_lifecycle_migration_rejects_incompatible_postgresql_history_columns(column, type_, nullable):
    columns = _postgresql_history_columns()
    next(item for item in columns if item["name"] == column).update(type=type_, nullable=nullable)

    with pytest.raises(RuntimeError, match="columns"):
        _migration_module()._validate_existing_history(_PostgreSQLHistoryInspector(columns))


def test_consent_lifecycle_migration_rejects_wrong_postgresql_history_check():
    with pytest.raises(RuntimeError, match="check constraint"):
        _migration_module()._validate_existing_history(
            _PostgreSQLHistoryInspector(_postgresql_history_columns(), check="revision >= 0")
        )


def test_consent_lifecycle_migration_downgrade_refuses_destructive_history_removal(
    tmp_path,
    monkeypatch,
):
    engine, config = _config(tmp_path, monkeypatch, "whatsapp-consent-downgrade.sqlite3")
    _create_legacy_whatsapp_schema(engine)
    command.stamp(config, PREVIOUS_MIGRATION)
    command.upgrade(config, CONSENT_MIGRATION)

    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREVIOUS_MIGRATION)
    assert sa.inspect(engine).has_table("whatsapp_consent_revisions")
    engine.dispose()
