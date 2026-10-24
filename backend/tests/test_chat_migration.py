from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings

REVISION = "c5e7a9b1d3f4"
PREDECESSOR = "c4e6a8b0d2f4"
TABLES = ("chat_conversations", "chat_messages", "chat_attachments")


def _config(tmp_path, monkeypatch):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / 'chat.sqlite'}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def test_upgrade_creates_chat_tables_on_top_of_the_alias_migration(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    with engine.connect() as connection:
        assert not set(TABLES) & set(sa.inspect(connection).get_table_names())

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        assert set(TABLES) <= set(inspector.get_table_names())
        columns = {c["name"] for c in inspector.get_columns("chat_conversations")}
        assert {"id", "teacher_ci", "admin_last_read_message_id", "docente_last_read_message_id"} <= columns
        assert {"conversation_id", "sender_user_id", "sender_role", "body", "created_at"} <= {
            c["name"] for c in inspector.get_columns("chat_messages")
        }
        assert {"message_id", "stored_filename", "original_filename", "content_type", "size_bytes"} <= {
            c["name"] for c in inspector.get_columns("chat_attachments")
        }
        for table in TABLES:
            assert connection.scalar(sa.text(f"SELECT count(*) FROM {table}")) == 0


def test_conversation_is_unique_per_teacher_and_cascades_with_the_teacher(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        unique = [u["column_names"] for u in inspector.get_unique_constraints("chat_conversations")]
        unique += [i["column_names"] for i in inspector.get_indexes("chat_conversations") if i["unique"]]
        assert ["teacher_ci"] in unique
        foreign_keys = {fk["referred_table"]: fk for fk in inspector.get_foreign_keys("chat_conversations")}
        assert foreign_keys["teachers"]["options"].get("ondelete") == "CASCADE"
        message_fks = {fk["referred_table"]: fk for fk in inspector.get_foreign_keys("chat_messages")}
        assert message_fks["users"]["options"].get("ondelete") == "SET NULL"
        assert message_fks["chat_conversations"]["options"].get("ondelete") == "CASCADE"


def test_upgrade_accepts_a_compatible_preexisting_conversation_table(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    command.upgrade(config, REVISION)
    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM alembic_version"))
        connection.execute(sa.text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": PREDECESSOR})

    command.upgrade(config, REVISION)

    with engine.connect() as connection:
        assert set(TABLES) <= set(sa.inspect(connection).get_table_names())


def test_upgrade_rejects_an_incompatible_preexisting_table(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, body TEXT)"))

    with pytest.raises(RuntimeError, match="Incompatible pre-existing chat_messages"):
        command.upgrade(config, REVISION)


def test_downgrade_requires_an_approved_backup(tmp_path, monkeypatch):
    _, config = _config(tmp_path, monkeypatch)
    command.upgrade(config, REVISION)

    with pytest.raises(RuntimeError, match="approved backup"):
        command.downgrade(config, PREDECESSOR)


def test_upgrade_on_empty_database_reaches_head_with_chat_tables(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch)

    command.upgrade(config, "head")

    with engine.connect() as connection:
        assert set(TABLES) <= set(sa.inspect(connection).get_table_names())
