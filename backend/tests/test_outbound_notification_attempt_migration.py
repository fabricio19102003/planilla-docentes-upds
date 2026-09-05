import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings


def _migration_module():
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "a1b2c3d4e5f6_add_outbound_notification_attempts.py"
    )
    spec = importlib.util.spec_from_file_location("outbound_attempt_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate_engine(
    *,
    status_type=None,
    channel_nullable=False,
    status_default=None,
    include_unique=True,
    publication_ondelete="CASCADE",
    include_user_index=True,
):
    metadata = sa.MetaData()
    sa.Table("billing_publications", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
    constraints = []
    if include_unique:
        constraints.append(
            sa.UniqueConstraint(
                "idempotency_key", name="uq_outbound_notification_attempt_key"
            )
        )
    table = sa.Table(
        "outbound_notification_attempts",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column(
            "publication_id",
            sa.Integer,
            sa.ForeignKey(
                "billing_publications.id", ondelete=publication_ondelete
            ),
            nullable=False,
        ),
        sa.Column("publication_version", sa.Integer, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("channel", sa.String(20), nullable=channel_nullable),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column(
            "status",
            status_type if status_type is not None else sa.String(20),
            nullable=False,
            server_default=status_default,
        ),
        sa.Column("provider_message_id", sa.String(100), nullable=True),
        sa.Column("error_code", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        *constraints,
    )
    sa.Index("ix_outbound_notification_attempts_publication_id", table.c.publication_id)
    if include_user_index:
        sa.Index("ix_outbound_notification_attempts_user_id", table.c.user_id)
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    return engine


def test_compatible_existing_table_satisfies_full_contract():
    engine = _candidate_engine()

    _migration_module()._validate_existing_table(sa.inspect(engine))

    engine.dispose()


def test_fresh_upgrade_creates_the_full_validated_contract(tmp_path, monkeypatch):
    database_path = tmp_path / "fresh-outbound-attempt.sqlite3"
    url = f"sqlite:///{database_path}"
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)

    command.upgrade(config, "head")

    engine = sa.create_engine(url)
    _migration_module()._validate_existing_table(sa.inspect(engine))
    engine.dispose()


@pytest.mark.parametrize(
    ("kwargs", "contract_part"),
    [
        ({"status_type": sa.Integer()}, "columns"),
        ({"channel_nullable": True}, "columns"),
        ({"status_default": "'pending'"}, "columns"),
        ({"include_unique": False}, "unique constraints"),
        ({"publication_ondelete": "RESTRICT"}, "foreign keys"),
        ({"include_user_index": False}, "indexes"),
    ],
)
def test_incompatible_existing_table_fails_closed(kwargs, contract_part):
    engine = _candidate_engine(**kwargs)

    with pytest.raises(RuntimeError, match=contract_part):
        _migration_module()._validate_existing_table(sa.inspect(engine))

    engine.dispose()
