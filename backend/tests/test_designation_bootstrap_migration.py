from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.database import Base


REVISION = "c6e8f0a2b431"
PREDECESSOR = "f4b6d8e0a219"
TABLE = "designation_bootstrap_receipts"


def _config(tmp_path, monkeypatch, name: str):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / name}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/c6e8f0a2b431_add_designation_bootstrap_receipts.py"
    spec = importlib.util.spec_from_file_location("designation_bootstrap_receipt_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_creates_receipt_matching_orm_contract(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "bootstrap-receipt.sqlite3")
    command.upgrade(config, "head")
    inspector = sa.inspect(engine)

    assert inspector.has_table(TABLE)
    migrated_columns = {item["name"] for item in inspector.get_columns(TABLE)}
    assert migrated_columns == set(Base.metadata.tables[TABLE].columns.keys())
    uniques = {tuple(sorted(item["column_names"])) for item in inspector.get_unique_constraints(TABLE)}
    assert uniques == {
        ("operation_key",),
        ("preview_digest",),
        ("draft_id",),
    }
    foreign_keys = {
        (tuple(item["constrained_columns"]), item["referred_table"], item["options"].get("ondelete"))
        for item in inspector.get_foreign_keys(TABLE)
    }
    assert foreign_keys == {
        (("program_id",), "academic_programs", "RESTRICT"),
        (("draft_id",), "academic_schedule_drafts", "RESTRICT"),
        (("actor_id",), "users", "RESTRICT"),
    }
    engine.dispose()


def test_migration_adopts_exact_precreated_receipt(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "bootstrap-exact-adoption.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _metadata, receipt = _module()._schema()
    receipt.create(engine)

    command.upgrade(config, REVISION)

    assert not _module()._validate_receipt(sa.inspect(engine), receipt)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == REVISION
    engine.dispose()


@pytest.mark.parametrize("mismatch", ["columns", "type", "nullability", "constraint", "index"])
def test_migration_rejects_incompatible_precreated_receipt_without_altering_it(
    tmp_path, monkeypatch, mismatch,
):
    engine, config = _config(tmp_path, monkeypatch, f"bootstrap-incompatible-{mismatch}.sqlite3")
    command.upgrade(config, PREDECESSOR)
    module = _module()
    if mismatch == "columns":
        with engine.begin() as connection:
            connection.execute(sa.text(f"CREATE TABLE {TABLE} (id INTEGER PRIMARY KEY)"))
    else:
        _metadata, receipt = module._schema()
        if mismatch == "type":
            receipt.c.content_digest.type = sa.Integer()
        elif mismatch == "nullability":
            receipt.c.actor_id.nullable = True
        elif mismatch == "constraint":
            check = next(
                item for item in receipt.constraints
                if item.name == "ck_designation_bootstrap_receipt_counts_nonnegative"
            )
            receipt.constraints.remove(check)
        receipt.create(engine)
        if mismatch == "index":
            with engine.begin() as connection:
                connection.execute(sa.text(
                    f"CREATE INDEX ix_{TABLE}_unexpected ON {TABLE}(content_digest)"
                ))
    before_columns = [item["name"] for item in sa.inspect(engine).get_columns(TABLE)]
    before_indexes = {item["name"] for item in sa.inspect(engine).get_indexes(TABLE)}

    with pytest.raises(RuntimeError, match="Incompatible pre-existing"):
        command.upgrade(config, REVISION)

    inspector = sa.inspect(engine)
    assert inspector.has_table(TABLE)
    assert [item["name"] for item in inspector.get_columns(TABLE)] == before_columns
    assert {item["name"] for item in inspector.get_indexes(TABLE)} == before_indexes
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == PREDECESSOR
    engine.dispose()


def test_receipt_migration_is_irreversible_audit_evidence(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "bootstrap-no-downgrade.sqlite3")
    command.upgrade(config, REVISION)
    with pytest.raises(RuntimeError, match="audit evidence"):
        command.downgrade(config, "f4b6d8e0a219")
    assert sa.inspect(engine).has_table(TABLE)
    engine.dispose()
