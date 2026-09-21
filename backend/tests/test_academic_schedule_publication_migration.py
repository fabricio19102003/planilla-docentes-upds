import importlib.util
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.database import Base


REVISION = "b0d2e4f6c804"
PREDECESSOR = "a9c1e3f5b703"
TABLES = (
    "academic_schedule_publications",
    "academic_schedule_published_blocks",
    "academic_schedule_published_assignments",
)


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/b0d2e4f6c804_add_academic_schedule_publications.py"
    spec = importlib.util.spec_from_file_location("academic_schedule_publication_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / name}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def _create_tables(engine, attack=None):
    metadata, tables = _module()._schema()
    publications, blocks, _assignments = tables
    if attack == "missing_default":
        publications.c.created_at.server_default = None
    elif attack == "incompatible_default":
        publications.c.created_at.server_default = sa.DefaultClause(
            sa.text("'2000-01-01 00:00:00'")
        )
    elif attack == "unexpected_default":
        publications.c.sequence.server_default = sa.DefaultClause(sa.text("1"))
    elif attack == "check":
        constraint = next(
            item for item in publications.constraints
            if item.name == "ck_academic_schedule_publication_sequence"
        )
        publications.constraints.remove(constraint)
        publications.append_constraint(sa.CheckConstraint(
            "sequence >= 0", name="ck_academic_schedule_publication_sequence"
        ))
    elif attack == "index":
        index = next(iter(blocks.indexes))
        blocks.indexes.remove(index)
    elif attack == "foreign_key":
        constraint = next(
            item for item in blocks.foreign_key_constraints
            if tuple(element.parent.name for element in item.elements) == ("publication_id",)
        )
        constraint.ondelete = "RESTRICT"
    metadata.create_all(engine, tables=list(tables))


def _snapshot(engine):
    inspector = sa.inspect(engine)
    result = {}
    for table in TABLES:
        if not inspector.has_table(table):
            continue
        result[table] = {
            "columns": [
                (item["name"], str(item["type"]), item["nullable"], item.get("default"))
                for item in inspector.get_columns(table)
            ],
            "pk": inspector.get_pk_constraint(table),
            "checks": inspector.get_check_constraints(table),
            "foreign_keys": inspector.get_foreign_keys(table),
            "indexes": inspector.get_indexes(table),
            "unique": inspector.get_unique_constraints(table),
        }
    result["draft_checks"] = sa.inspect(engine).get_check_constraints("academic_schedule_drafts")
    return result


@pytest.fixture
def postgres_publication_migration(monkeypatch):
    url = os.getenv("ACADEMIC_SCHEDULE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ACADEMIC_SCHEDULE_TEST_POSTGRES_URL is not configured")
    parsed = sa.engine.make_url(url)
    if parsed.get_backend_name() != "postgresql" or "test" not in (parsed.database or ""):
        pytest.fail("ACADEMIC_SCHEDULE_TEST_POSTGRES_URL must target a dedicated PostgreSQL test database")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    yield engine, config
    engine.dispose()


def test_publication_migration_fresh_upgrade_and_model_parity(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "publication-fresh.sqlite3")
    command.upgrade(config, REVISION)
    module = _module()
    _metadata, tables = module._schema()
    inspector = sa.inspect(engine)
    for table in tables:
        assert module._validate_table(inspector, table) == []
        model = Base.metadata.tables[table.name]
        assert set(model.c.keys()) == set(table.c.keys())
        assert {item.name for item in model.indexes} == {item.name for item in table.indexes}
        assert {item.name for item in model.constraints if item.name} == {
            item.name for item in table.constraints if item.name
        }
    draft_check = next(
        item for item in inspector.get_check_constraints("academic_schedule_drafts")
        if item["name"] == "ck_academic_schedule_draft_status"
    )
    assert "published" in draft_check["sqltext"]
    engine.dispose()


def test_publication_migration_adopts_exact_compatible_tables(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "publication-compatible.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _create_tables(engine)
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
    engine.dispose()


@pytest.mark.parametrize(
    "value",
    [
        "now()",
        "pg_catalog.now()",
        "CURRENT_TIMESTAMP",
        "current_timestamp()",
        "transaction_timestamp()",
        "pg_catalog.transaction_timestamp()",
    ],
)
def test_publication_migration_accepts_semantic_timestamp_default_variants(value):
    module = _module()
    assert module._default_signature(value) == ("current_timestamp",)


@pytest.mark.parametrize(
    "attack",
    [
        "missing_default",
        "incompatible_default",
        "unexpected_default",
        "check",
        "index",
        "foreign_key",
    ],
)
def test_publication_migration_rejects_incompatible_tables_before_mutation(
    tmp_path, monkeypatch, attack
):
    engine, config = _config(tmp_path, monkeypatch, f"publication-{attack}.sqlite3")
    command.upgrade(config, PREDECESSOR)
    _create_tables(engine, attack)
    before = _snapshot(engine)
    with pytest.raises(RuntimeError, match="Incompatible pre-existing table"):
        command.upgrade(config, REVISION)
    assert _snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


def test_publication_migration_refuses_destructive_downgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "publication-downgrade.sqlite3")
    command.upgrade(config, REVISION)
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREDECESSOR)
    assert set(TABLES).issubset(sa.inspect(engine).get_table_names())
    engine.dispose()


def test_postgresql_publication_exact_adoption(postgres_publication_migration):
    engine, config = postgres_publication_migration
    command.upgrade(config, PREDECESSOR)
    _create_tables(engine)
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION


@pytest.mark.parametrize(
    "attack",
    [
        "missing_default",
        "incompatible_default",
        "unexpected_default",
        "check",
        "index",
        "foreign_key",
    ],
)
def test_postgresql_publication_attacks_reject_without_mutation(
    postgres_publication_migration, attack
):
    engine, config = postgres_publication_migration
    command.upgrade(config, PREDECESSOR)
    _create_tables(engine, attack)
    before = _snapshot(engine)
    with pytest.raises(RuntimeError, match="Incompatible pre-existing table"):
        command.upgrade(config, REVISION)
    assert _snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR


def test_postgresql_publication_fresh_upgrade_and_check(postgres_publication_migration):
    _engine, config = postgres_publication_migration
    command.upgrade(config, "head")
    command.check(config)
