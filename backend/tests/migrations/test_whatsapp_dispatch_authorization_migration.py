import importlib.util
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.models.billing_notification import BillingWhatsAppDispatchAuthorization

REVISION = "a2c4e6f8b003"
PREDECESSOR = "a2c4e6f8b002"
COLUMNS = {
    "id": (sa.Integer(), False), "activation_id": (sa.Integer(), False), "job_id": (sa.Integer(), False),
    "creator_user_id": (sa.Integer(), False), "state": (sa.String(16), False), "expires_at": (sa.DateTime(), False),
    "attestation_code": (sa.String(48), True), "release_actor_user_id": (sa.Integer(), True),
    "release_key_hash": (sa.String(64), True), "release_request_digest": (sa.String(64), True),
    "released_at": (sa.DateTime(), True), "consumed_at": (sa.DateTime(), True),
    "cancel_key_hash": (sa.String(64), True), "cancel_request_digest": (sa.String(64), True),
    "cancelled_at": (sa.DateTime(), True), "revoked_at": (sa.DateTime(), True),
    "terminal_reason": (sa.String(64), True), "created_at": (sa.DateTime(), False), "updated_at": (sa.DateTime(), False),
}
FOREIGN_KEYS = {
    (("activation_id",), "billing_whatsapp_activation_tests", ("id",), "RESTRICT"),
    (("job_id",), "billing_notification_jobs", ("id",), "RESTRICT"),
    (("creator_user_id",), "users", ("id",), "RESTRICT"),
    (("release_actor_user_id",), "users", ("id",), "RESTRICT"),
}


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[2]
    url = f"sqlite:///{tmp_path / name}"
    engine = sa.create_engine(url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return engine, config


def _module():
    path = Path(__file__).parents[2] / "alembic/versions/a2c4e6f8b003_add_whatsapp_dispatch_authorizations.py"
    spec = importlib.util.spec_from_file_location("authorization_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _normalize(expression):
    return "".join(expression.split()).casefold().strip("()")


def _assert_exact_schema(inspector, module):
    columns = {item["name"]: item for item in inspector.get_columns("billing_whatsapp_dispatch_authorizations")}
    assert set(columns) == set(COLUMNS)
    for name, (type_, nullable) in COLUMNS.items():
        assert columns[name]["type"]._type_affinity is type_._type_affinity
        assert columns[name]["nullable"] is nullable or (name == "id" and columns[name]["nullable"] is True)
        assert getattr(columns[name]["type"], "length", None) == getattr(type_, "length", None)
    assert inspector.get_pk_constraint("billing_whatsapp_dispatch_authorizations")["constrained_columns"] == ["id"]
    foreign_keys = {(tuple(item["constrained_columns"]), item["referred_table"], tuple(item["referred_columns"]), (item.get("options") or {}).get("ondelete")) for item in inspector.get_foreign_keys("billing_whatsapp_dispatch_authorizations")}
    assert foreign_keys == FOREIGN_KEYS
    assert {(item["name"], tuple(item["column_names"])) for item in inspector.get_unique_constraints("billing_whatsapp_dispatch_authorizations")} == {("uq_whatsapp_dispatch_authorization_activation", ("activation_id",)), ("uq_whatsapp_dispatch_authorization_job", ("job_id",))}
    assert {item["name"]: _normalize(item["sqltext"]) for item in inspector.get_check_constraints("billing_whatsapp_dispatch_authorizations")} == {name: _normalize(expression) for name, expression in module._CHECKS}
    assert {(item["name"], tuple(item["column_names"]), item["unique"]) for item in inspector.get_indexes("billing_whatsapp_dispatch_authorizations")} == {("ix_whatsapp_dispatch_authorization_claim", ("state", "expires_at", "job_id"), False)}


def _authorization_fixture(module):
    metadata = sa.MetaData()
    for name in ("users", "billing_notification_jobs", "billing_whatsapp_activation_tests"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
    return metadata, module.authorization_table(metadata)


def test_authorization_model_declares_finite_one_shot_contract():
    table = BillingWhatsAppDispatchAuthorization.__table__
    assert {"activation_id", "job_id", "creator_user_id", "state", "expires_at", "released_at", "consumed_at", "cancelled_at", "revoked_at"}.issubset(table.c.keys())
    assert {item.name for item in table.constraints if isinstance(item, sa.UniqueConstraint)} >= {"uq_whatsapp_dispatch_authorization_activation", "uq_whatsapp_dispatch_authorization_job"}


def test_fresh_upgrade_creates_exact_schema_and_refuses_downgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "authorization.sqlite3")
    command.upgrade(config, REVISION)
    _assert_exact_schema(sa.inspect(engine), _module())
    with pytest.raises(RuntimeError, match="approved backup"):
        command.downgrade(config, PREDECESSOR)
    engine.dispose()


def test_db_insert_rejects_unsupported_authorization_state():
    module = _module()
    metadata, table = _authorization_fixture(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        metadata.create_all(connection)
        for name in ("users", "billing_notification_jobs", "billing_whatsapp_activation_tests"):
            connection.execute(sa.text(f"INSERT INTO {name} (id) VALUES (1)"))
        values = {"activation_id": 1, "job_id": 1, "creator_user_id": 1, "state": "pending", "expires_at": datetime(2030, 1, 1, 1), "created_at": datetime(2030, 1, 1), "updated_at": datetime(2030, 1, 1)}
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(sa.insert(table), {**values, "state": "unsupported"})
    engine.dispose()


def test_state_lifecycle_checks_reject_invalid_timestamps_and_duplicate_bindings():
    metadata, table = _authorization_fixture(_module())
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        metadata.create_all(connection)
        for name in ("users", "billing_notification_jobs", "billing_whatsapp_activation_tests"):
            connection.execute(sa.text(f"INSERT INTO {name} (id) VALUES (1), (2)"))
        now = datetime(2030, 1, 1)
        values = {"activation_id": 1, "job_id": 1, "creator_user_id": 1, "state": "pending", "expires_at": datetime(2030, 1, 1, 1), "created_at": now, "updated_at": now}
        connection.execute(sa.insert(table), values)
        for state, timestamps in (("pending", {"released_at": now}), ("authorized", {}), ("consumed", {"released_at": now}), ("cancelled", {"cancelled_at": now}), ("expired", {}), ("revoked", {})):
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(sa.insert(table), {**values, "id": 2, "activation_id": 2, "job_id": 2, "state": state, **timestamps})
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(sa.insert(table), {**values, "id": 3, "job_id": 2})
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(sa.insert(table), {**values, "id": 4, "activation_id": 2})
    engine.dispose()


def test_compatible_precreated_table_is_adopted(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "compatible.sqlite3")
    command.upgrade(config, PREDECESSOR)
    module = _module()
    module.authorization_table(module._schema_metadata()).create(engine)
    command.upgrade(config, REVISION)
    _assert_exact_schema(sa.inspect(engine), _module())
    engine.dispose()


def test_incompatible_precreated_table_fails_closed(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "incompatible.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE billing_whatsapp_dispatch_authorizations (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing"):
        command.upgrade(config, REVISION)
    engine.dispose()


def test_postgresql_reflection_accepts_constraint_backing_indexes_and_rejects_unrelated_indexes():
    module = _module()
    table = module.authorization_table(module._schema_metadata())
    inspector = type("Inspector", (), {
        "get_columns": lambda self, _: [{"name": c.name, "type": c.type, "nullable": c.nullable} for c in table.columns],
        "get_pk_constraint": lambda self, _: {"constrained_columns": ["id"]},
        "get_unique_constraints": lambda self, _: [{"name": c.name, "column_names": [x.name for x in c.columns]} for c in table.constraints if isinstance(c, sa.UniqueConstraint)],
        "get_check_constraints": lambda self, _: [{"name": c.name, "sqltext": str(c.sqltext)} for c in table.constraints if isinstance(c, sa.CheckConstraint)],
        "get_foreign_keys": lambda self, _: [{"constrained_columns": [x.parent.name], "referred_table": x.column.table.name, "referred_columns": [x.column.name], "options": {"ondelete": x.ondelete}} for c in table.foreign_key_constraints for x in c.elements],
        "get_indexes": lambda self, _: [
            {"name": "ix_whatsapp_dispatch_authorization_claim", "column_names": ["state", "expires_at", "job_id"], "unique": False},
            {"name": "uq_whatsapp_dispatch_authorization_activation", "column_names": ["activation_id"], "unique": True, "duplicates_constraint": "uq_whatsapp_dispatch_authorization_activation"},
            {"name": "uq_whatsapp_dispatch_authorization_job", "column_names": ["job_id"], "unique": True, "duplicates_constraint": "uq_whatsapp_dispatch_authorization_job"},
        ],
    })()
    module._validate_authorization_table(inspector)
    indexes = inspector.get_indexes(module._TABLE)
    inspector.get_indexes = lambda _: [*indexes, {"name": "ix_unrelated", "column_names": ["state"], "unique": False}]
    with pytest.raises(RuntimeError, match="Incompatible pre-existing.*index"):
        module._validate_authorization_table(inspector)
