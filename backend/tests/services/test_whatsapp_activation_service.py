import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.models.billing_notification import BillingNotificationJob, BillingWhatsAppActivationTest


ACTIVATION_MIGRATION = "a2c4e6f8b002"
PREVIOUS_MIGRATION = "a2c4e6f8b001"


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[2]
    url = f"sqlite:///{tmp_path / name}"
    engine = sa.create_engine(url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return engine, config


def _migration_module():
    path = Path(__file__).parents[2] / "alembic/versions/a2c4e6f8b002_add_whatsapp_activation_tests.py"
    spec = importlib.util.spec_from_file_location("activation_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_activation_persistence_declares_bounded_and_private_binding():
    table = BillingWhatsAppActivationTest.__table__
    assert BillingWhatsAppActivationTest.__tablename__ == "billing_whatsapp_activation_tests"
    assert "recipient_e164" not in table.c
    assert {"recipient_hmac", "recipient_masked"}.issubset(table.c.keys())
    assert BillingNotificationJob.__table__.c.intent_type.default.arg == "ordinary"
    checks = {constraint.name: str(constraint.sqltext) for constraint in table.constraints if isinstance(constraint, sa.CheckConstraint)}
    assert "consent_revision > 0" in checks["ck_whatsapp_activation_consent_revision_positive"]
    assert "artifact_size > 0" in checks["ck_whatsapp_activation_artifact_size_positive"]
    assert "'cancelled'" in checks["ck_whatsapp_activation_status"]
    unique = {constraint.name for constraint in table.constraints if isinstance(constraint, sa.UniqueConstraint)}
    assert {"uq_whatsapp_activation_actor_key", "uq_whatsapp_activation_batch", "uq_whatsapp_activation_job", "uq_whatsapp_activation_media_token"}.issubset(unique)


def test_activation_migration_fresh_upgrade_creates_constrained_schema(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-fresh.sqlite3")
    command.upgrade(config, ACTIVATION_MIGRATION)
    inspector = sa.inspect(engine)
    assert inspector.has_table("billing_whatsapp_activation_tests")
    assert {"intent_type", "recipient_hmac", "recipient_masked"}.issubset(
        {column["name"] for column in inspector.get_columns("billing_notification_jobs")}
        | {column["name"] for column in inspector.get_columns("billing_whatsapp_activation_tests")}
    )
    assert {"uq_whatsapp_activation_actor_key", "uq_whatsapp_activation_batch", "uq_whatsapp_activation_job", "uq_whatsapp_activation_media_token"}.issubset(
        {item["name"] for item in inspector.get_unique_constraints("billing_whatsapp_activation_tests")}
    )
    assert ("intent_type", "status", "lease_expires_at") in {
        tuple(item["column_names"]) for item in inspector.get_indexes("billing_notification_jobs")
    }
    engine.dispose()


def test_activation_migration_backfills_legacy_jobs_and_refuses_destructive_downgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-legacy.sqlite3")
    command.upgrade(config, PREVIOUS_MIGRATION)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO billing_notification_jobs (batch_id, teacher_ci, channel, status, attempts, created_at, updated_at) VALUES (1, 'legacy', 'whatsapp', 'queued', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
    command.upgrade(config, ACTIVATION_MIGRATION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT intent_type FROM billing_notification_jobs WHERE id = 1")) == "ordinary"
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREVIOUS_MIGRATION)
    assert sa.inspect(engine).has_table("billing_whatsapp_activation_tests")
    engine.dispose()


def test_activation_migration_rejects_incompatible_preexisting_adoption(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-adoption.sqlite3")
    command.upgrade(config, PREVIOUS_MIGRATION)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE billing_whatsapp_activation_tests (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing billing_whatsapp_activation_tests columns"):
        command.upgrade(config, ACTIVATION_MIGRATION)
    engine.dispose()


class _PostgreSQLActivationInspector:
    def __init__(self):
        self.bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()
        table = BillingWhatsAppActivationTest.__table__
        self.columns = [{"name": column.name, "type": column.type, "nullable": column.nullable} for column in table.columns]
        self.pk = {"constrained_columns": ["id"]}
        self.foreign_keys = [{"constrained_columns": [item.parent.name], "referred_table": item.column.table.name, "referred_columns": [item.column.name], "options": {"ondelete": item.ondelete}} for foreign_key in table.foreign_key_constraints for item in foreign_key.elements]
        self.indexes = [{"name": "ix_whatsapp_activation_status", "column_names": ["status"]}]

    def get_columns(self, _table): return self.columns
    def get_pk_constraint(self, _table): return self.pk
    def get_unique_constraints(self, _table): return [{"name": item.name, "column_names": [column.name for column in item.columns]} for item in BillingWhatsAppActivationTest.__table__.constraints if isinstance(item, sa.UniqueConstraint)]
    def get_check_constraints(self, _table): return [{"name": item.name, "sqltext": str(item.sqltext)} for item in BillingWhatsAppActivationTest.__table__.constraints if isinstance(item, sa.CheckConstraint)]
    def get_foreign_keys(self, _table): return self.foreign_keys
    def get_indexes(self, _table): return self.indexes


def test_activation_adoption_requires_exact_postgresql_pk_fks_and_indexes():
    module = _migration_module()
    inspector = _PostgreSQLActivationInspector()
    module._validate_activation_table(inspector)
    for attribute, bad, message in (
        ("pk", {"constrained_columns": ["actor_user_id"]}, "primary key"),
        ("indexes", [], "index"),
    ):
        setattr(inspector, attribute, bad)
        with pytest.raises(RuntimeError, match=message):
            module._validate_activation_table(inspector)
        setattr(inspector, attribute, _PostgreSQLActivationInspector().__dict__[attribute])
    for target, action in (("wrong_table", "RESTRICT"), ("users", "CASCADE")):
        bad = [dict(item, options=dict(item["options"])) for item in inspector.foreign_keys]
        bad[0].update(referred_table=target, options={"ondelete": action})
        inspector.foreign_keys = bad
        with pytest.raises(RuntimeError, match="foreign keys"):
            module._validate_activation_table(inspector)
        inspector.foreign_keys = _PostgreSQLActivationInspector().foreign_keys
