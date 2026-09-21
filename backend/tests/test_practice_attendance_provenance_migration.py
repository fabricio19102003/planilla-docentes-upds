import importlib.util
import os
from datetime import date, datetime, time
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from app.config import settings


REVISION = "d2f4a6b8e017"
PREDECESSOR = "c1e3f5a7d906"


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/d2f4a6b8e017_add_published_practice_attendance_provenance.py"
    spec = importlib.util.spec_from_file_location("practice_attendance_provenance_migration", path)
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


def _column_snapshot(engine):
    return [
        (item["name"], str(item["type"]), item["nullable"], item.get("default"), item["primary_key"])
        for item in sa.inspect(engine).get_columns("practice_attendance_logs")
    ]


def _insert_legacy(connection):
    metadata = sa.MetaData()
    metadata.reflect(connection, only=("teachers", "designations", "practice_attendance_logs"))
    connection.execute(metadata.tables["teachers"].insert().values(
        ci="PRACTICE-1", full_name="Practice Teacher", created_at=datetime(2026, 1, 1)
    ))
    designation = metadata.tables["designations"]
    values = {
        "id": 29, "teacher_ci": "PRACTICE-1", "subject": "Practice Subject",
        "semester": "1", "group_code": "A", "schedule_json": [],
        "created_at": datetime(2026, 1, 1), "academic_period": "I/2026",
        "designation_type": "practice",
    }
    connection.execute(designation.insert().values(**{k: v for k, v in values.items() if k in designation.c}))
    connection.execute(metadata.tables["practice_attendance_logs"].insert().values(
        id=73, teacher_ci="PRACTICE-1", designation_id=29,
        date=date(2026, 3, 2), scheduled_start=time(8), scheduled_end=time(9),
        academic_hours=1, status="attended", created_at=datetime(2026, 3, 2),
        updated_at=datetime(2026, 3, 2),
    ))


def test_upgrade_preserves_legacy_ids_and_enforces_xor(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "practice-provenance.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        _insert_legacy(connection)
    command.upgrade(config, REVISION)

    module = _module()
    _metadata, target = module._schema(target=True)
    helpers = module._validation_helpers()
    assert helpers._validate_table(sa.inspect(engine), target) == []
    with engine.connect() as connection:
        row = connection.execute(sa.text(
            "SELECT id, designation_id, published_schedule_assignment_id FROM practice_attendance_logs"
        )).mappings().one()
        assert dict(row) == {"id": 73, "designation_id": 29, "published_schedule_assignment_id": None}
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO practice_attendance_logs "
            "(teacher_ci, designation_id, published_schedule_assignment_id, date, scheduled_start, "
            "scheduled_end, academic_hours, status, created_at, updated_at) VALUES "
            "('PRACTICE-1', NULL, NULL, '2026-03-03', '08:00', '09:00', 1, 'absent', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    engine.dispose()


@pytest.mark.parametrize("attack", ["nullable", "default", "check", "index", "foreign_key"])
def test_incompatible_adoption_is_rejected_before_mutation(tmp_path, monkeypatch, attack):
    engine, config = _config(tmp_path, monkeypatch, f"practice-adoption-{attack}.sqlite3")
    command.upgrade(config, PREDECESSOR)
    module = _module()
    with engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE practice_attendance_logs"))
        _metadata, target = module._schema(target=True)
        if attack == "nullable":
            target.c.designation_id.nullable = False
        elif attack == "default":
            target.c.status.server_default = sa.DefaultClause(sa.text("'absent'"))
        elif attack == "check":
            target.constraints.remove(next(item for item in target.constraints if isinstance(item, sa.CheckConstraint)))
        elif attack == "index":
            target.indexes.remove(next(item for item in target.indexes if item.name == "uq_practice_attendance_log_published_source"))
        else:
            foreign_key = next(
                item for item in target.foreign_key_constraints
                if tuple(element.parent.name for element in item.elements) == ("published_schedule_assignment_id",)
            )
            foreign_key.ondelete = "CASCADE"
        target.create(connection)
    before = _column_snapshot(engine)
    with pytest.raises(RuntimeError, match="Incompatible pre-existing practice_attendance_logs"):
        command.upgrade(config, REVISION)
    assert _column_snapshot(engine) == before
    engine.dispose()


def test_restore_required_downgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "practice-downgrade.sqlite3")
    command.upgrade(config, REVISION)
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREDECESSOR)
    engine.dispose()


def test_postgres_fresh_upgrade_and_alembic_check(monkeypatch):
    url = os.getenv("ATTENDANCE_PROVENANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ATTENDANCE_PROVENANCE_TEST_POSTGRES_URL is not configured")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    command.upgrade(config, "head")
    command.check(config)
    assert "published_schedule_assignment_id" in {
        item["name"] for item in sa.inspect(engine).get_columns("practice_attendance_logs")
    }
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO teachers (ci, full_name, created_at) "
            "VALUES ('PRACTICE-PUBLISHED', 'Published Practice Teacher', CURRENT_TIMESTAMP)"
        ))
        connection.execute(sa.text("SET session_replication_role = replica"))
        connection.execute(sa.text(
            "INSERT INTO academic_schedule_published_assignments "
            "(id, publication_block_id, source_assignment_id, teacher_ci, teacher_name, effective_from) "
            "VALUES (191, 999, 601, 'PRACTICE-PUBLISHED', 'Published Practice Teacher', '2026-03-01')"
        ))
        connection.execute(sa.text("SET session_replication_role = origin"))
        connection.execute(sa.text(
            "INSERT INTO practice_attendance_logs "
            "(teacher_ci, designation_id, published_schedule_assignment_id, date, scheduled_start, "
            "scheduled_end, academic_hours, status, created_at, updated_at) VALUES "
            "('PRACTICE-PUBLISHED', NULL, 191, '2026-03-02', '08:00', '09:00', 1, "
            "'attended', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO practice_attendance_logs "
            "(teacher_ci, designation_id, published_schedule_assignment_id, date, scheduled_start, "
            "scheduled_end, academic_hours, status, created_at, updated_at) VALUES "
            "('PRACTICE-PUBLISHED', NULL, 191, '2026-03-02', '08:00', '09:00', 1, "
            "'attended', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO practice_attendance_logs "
            "(teacher_ci, designation_id, published_schedule_assignment_id, date, scheduled_start, "
            "scheduled_end, academic_hours, status, created_at, updated_at) VALUES "
            "('PRACTICE-PUBLISHED', NULL, NULL, '2026-03-03', '08:00', '09:00', 1, "
            "'absent', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text(
            "DELETE FROM academic_schedule_published_assignments WHERE id = 191"
        ))
    engine.dispose()
