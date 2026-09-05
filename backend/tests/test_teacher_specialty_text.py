from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.config import settings
from app.database import Base
from app.models.teacher import Teacher


REVISION = "b8c4d2e6f901"
DOWN_REVISION = "f7a1b2c3d4e5"


def _config(url: str, monkeypatch) -> Config:
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return config


def _head(config: Config) -> str:
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    return head


def test_teacher_specialty_metadata_is_nullable_text():
    column = Teacher.__table__.c.specialty

    assert isinstance(column.type, sa.Text)
    assert column.nullable is True


def test_admin_create_and_update_preserve_long_specialty(client, db_session):
    create_specialty = "C" * 201
    update_specialty = "U" * 408

    created = client.post(
        "/api/teachers",
        json={"ci": "LONG-SPECIALTY", "full_name": "Long Specialty", "specialty": create_specialty},
    )
    assert created.status_code == 201
    assert created.json()["specialty"] == create_specialty

    updated = client.put(
        "/api/teachers/LONG-SPECIALTY",
        json={"specialty": update_specialty},
    )
    assert updated.status_code == 200
    assert updated.json()["specialty"] == update_specialty
    assert db_session.get(Teacher, "LONG-SPECIALTY").specialty == update_specialty


def test_specialty_migration_upgrade_and_guarded_downgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'specialty.sqlite3'}"
    engine = sa.create_engine(url)
    long_specialty = "S" * 408
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE teachers (ci VARCHAR(20) PRIMARY KEY, specialty VARCHAR(200) NULL)"
        ))
        connection.execute(
            sa.text("INSERT INTO teachers (ci, specialty) VALUES ('LONG', :specialty)"),
            {"specialty": long_specialty},
        )
        connection.execute(sa.text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(sa.text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": DOWN_REVISION})
    config = _config(url, monkeypatch)

    command.upgrade(config, REVISION)
    column = next(item for item in sa.inspect(engine).get_columns("teachers") if item["name"] == "specialty")
    assert isinstance(column["type"], sa.Text)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT specialty FROM teachers WHERE ci = 'LONG'")) == long_specialty

    with pytest.raises(RuntimeError, match="values exceed 200 characters"):
        command.downgrade(config, DOWN_REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
        connection.execute(sa.text("UPDATE teachers SET specialty = :specialty"), {"specialty": "S" * 200})
        connection.commit()

    command.downgrade(config, DOWN_REVISION)
    column = next(item for item in sa.inspect(engine).get_columns("teachers") if item["name"] == "specialty")
    assert isinstance(column["type"], sa.String)
    assert column["type"].length == 200
    engine.dispose()


def test_clean_migration_chain_ends_with_text_specialty(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'clean.sqlite3'}"
    engine = sa.create_engine(url)
    config = _config(url, monkeypatch)
    Base.metadata.create_all(engine)
    command.stamp(config, DOWN_REVISION)

    command.upgrade(config, "head")

    column = next(item for item in sa.inspect(engine).get_columns("teachers") if item["name"] == "specialty")
    assert isinstance(column["type"], sa.Text)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == _head(config)
    engine.dispose()
