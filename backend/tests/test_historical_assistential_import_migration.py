from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.database import Base


PREDECESSOR = "e3a5c7f9b128"
REVISION = "f4b6d8e0a219"


def _config(tmp_path, monkeypatch, name: str):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / name}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/f4b6d8e0a219_add_historical_schedule_import_receipts.py"
    spec = importlib.util.spec_from_file_location("historical_import_receipt_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capacity_shape(engine) -> tuple[bool, set[str]]:
    inspector = sa.inspect(engine)
    columns = {item["name"]: item for item in inspector.get_columns("classrooms")}
    checks = {item.get("name") for item in inspector.get_check_constraints("classrooms")}
    return bool(columns["capacity"]["nullable"]), checks


def test_malicious_lookalike_receipt_is_rejected_before_capacity_mutation(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "malicious-lookalike.sqlite3")
    command.upgrade(config, PREDECESSOR)
    before = _capacity_shape(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("""
            CREATE TABLE historical_schedule_imports (
                id TEXT,
                idempotency_key VARCHAR(64),
                preview_digest VARCHAR(64),
                input_digest VARCHAR(64),
                pre_state_digest VARCHAR(64),
                applied_state_digest VARCHAR(64),
                academic_period VARCHAR(30),
                effective_from DATE,
                actor_id INTEGER,
                policy VARCHAR(80),
                source_hashes JSON,
                counts JSON,
                result JSON,
                created_at DATETIME
            )
        """))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing"):
        command.upgrade(config, REVISION)
    assert _capacity_shape(engine) == before
    engine.dispose()


def test_receipt_adoption_rejects_unexpected_index_before_mutation(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "malicious-index.sqlite3")
    command.upgrade(config, PREDECESSOR)
    before = _capacity_shape(engine)
    _metadata, table = _module()._schema()
    table.create(engine)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE INDEX ix_historical_schedule_imports_unexpected ON historical_schedule_imports(policy)"
        ))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing"):
        command.upgrade(config, REVISION)
    assert _capacity_shape(engine) == before
    engine.dispose()


def test_exact_precreated_receipt_is_adopted_and_validated(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "exact-adoption.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _metadata, table = _module()._schema()
    table.create(engine)
    command.upgrade(config, REVISION)
    assert not _module()._validate_receipt(sa.inspect(engine), table)
    nullable, checks = _capacity_shape(engine)
    assert nullable is True
    assert "ck_classroom_capacity_by_type" in checks
    assert "ck_classroom_capacity_positive" not in checks
    engine.dispose()


def test_capacity_migration_preserves_existing_physical_rows(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "capacity-preservation.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("""
            INSERT INTO classrooms
                (id, code, name, campus, capacity, classroom_type, resources, active, created_at, updated_at)
            VALUES
                (901, 'KEEP-42', 'Existing room', 'Central', 42, 'classroom', '[]', 1,
                 CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """))
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        row = connection.execute(sa.text(
            "SELECT capacity, classroom_type FROM classrooms WHERE id = 901"
        )).one()
    assert row == (42, "classroom")
    engine.dispose()


def test_classroom_adoption_rejects_unexpected_index_before_receipt_creation(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "malicious-classroom-index.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE INDEX ix_classrooms_unexpected ON classrooms(classroom_type)"
        ))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing classrooms"):
        command.upgrade(config, REVISION)
    inspector = sa.inspect(engine)
    assert not inspector.has_table("historical_schedule_imports")
    assert _capacity_shape(engine)[0] is False
    engine.dispose()


def test_capacity_target_matches_orm_contract():
    module = _module()
    migrated = module._classroom_schema(target=True)
    model = Base.metadata.tables["classrooms"]
    assert migrated.c.capacity.nullable is model.c.capacity.nullable is True
    signature = module._validation_helper()._check_signature
    migrated_checks = {
        item.name: signature(item.sqltext)
        for item in migrated.constraints if isinstance(item, sa.CheckConstraint)
    }
    model_checks = {
        item.name: signature(item.sqltext)
        for item in model.constraints if isinstance(item, sa.CheckConstraint)
    }
    assert migrated_checks == model_checks
