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
from app.database import Base


REVISION = "c1e3f5a7d906"
PREDECESSOR = "b0d2e4f6c804"


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/c1e3f5a7d906_add_published_attendance_provenance.py"
    spec = importlib.util.spec_from_file_location("attendance_provenance_migration", path)
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


def _snapshot(engine):
    inspector = sa.inspect(engine)
    def index_signature(item):
        options = item.get("dialect_options") or {}
        where = options.get("sqlite_where")
        if where is None:
            where = options.get("postgresql_where")
        return (
            item.get("name"),
            tuple(item.get("column_names") or ()),
            bool(item.get("unique", False)),
            str(where or "") if where is None else str(where),
        )

    return {
        "columns": [
            (item["name"], str(item["type"]), item["nullable"], item.get("default"))
            for item in inspector.get_columns("attendance_records")
        ],
        "pk": inspector.get_pk_constraint("attendance_records"),
        "checks": inspector.get_check_constraints("attendance_records"),
        "foreign_keys": inspector.get_foreign_keys("attendance_records"),
        "indexes": [index_signature(item) for item in inspector.get_indexes("attendance_records")],
        "unique": inspector.get_unique_constraints("attendance_records"),
    }


@pytest.fixture
def postgres_attendance_migration(monkeypatch):
    url = os.getenv("ATTENDANCE_PROVENANCE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("ATTENDANCE_PROVENANCE_TEST_POSTGRES_URL is not configured")
    parsed = sa.engine.make_url(url)
    if parsed.get_backend_name() != "postgresql" or "test" not in (parsed.database or ""):
        pytest.fail("ATTENDANCE_PROVENANCE_TEST_POSTGRES_URL must target a dedicated PostgreSQL test database")
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


def _insert_legacy_row(connection, record_id=41):
    metadata = sa.MetaData()
    metadata.reflect(connection, only=("teachers", "designations", "attendance_records"))
    teachers = metadata.tables["teachers"]
    designations = metadata.tables["designations"]
    attendance = metadata.tables["attendance_records"]
    connection.execute(teachers.insert().values(
        ci="LEGACY-1", full_name="Legacy Teacher", created_at=datetime(2026, 1, 1)
    ))
    designation_values = {
        "id": 17,
        "teacher_ci": "LEGACY-1",
        "subject": "Legacy Subject",
        "semester": "1",
        "group_code": "A",
        "schedule_json": [{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30", "horas_academicas": 2}],
        "created_at": datetime(2026, 1, 1),
    }
    if "academic_period" in designations.c:
        designation_values["academic_period"] = "I/2026"
    if "designation_type" in designations.c:
        designation_values["designation_type"] = "regular"
    connection.execute(designations.insert().values(**designation_values))
    connection.execute(attendance.insert().values(
        id=record_id,
        teacher_ci="LEGACY-1",
        designation_id=17,
        date=date(2026, 3, 2),
        scheduled_start=time(8, 0),
        scheduled_end=time(9, 30),
        status="ATTENDED",
        academic_hours=2,
        late_minutes=0,
        month=3,
        year=2026,
        created_at=datetime(2026, 3, 2, 10, 0),
    ))


def test_migration_preserves_legacy_ids_and_matches_model(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "attendance-provenance.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        _insert_legacy_row(connection)

    command.upgrade(config, REVISION)

    module = _module()
    inspector = sa.inspect(engine)
    _metadata, expected = module._schema(target=True)
    assert module._validate_table(inspector, expected) == []
    model = Base.metadata.tables["attendance_records"]
    assert set(model.c.keys()) == set(expected.c.keys())
    assert {item.name for item in model.indexes} == {item.name for item in expected.indexes}
    with engine.connect() as connection:
        row = connection.execute(sa.text(
            "SELECT id, designation_id, published_schedule_assignment_id FROM attendance_records"
        )).mappings().one()
        assert dict(row) == {
            "id": 41,
            "designation_id": 17,
            "published_schedule_assignment_id": None,
        }
    engine.dispose()


def test_migration_enforces_xor_and_source_specific_uniqueness(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "attendance-constraints.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        _insert_legacy_row(connection)
    command.upgrade(config, REVISION)

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO attendance_records "
                "(teacher_ci, designation_id, published_schedule_assignment_id, date, scheduled_start, "
                "scheduled_end, status, academic_hours, late_minutes, month, year, created_at) "
                "VALUES ('LEGACY-1', NULL, NULL, '2026-03-03', '08:00', '09:30', "
                "'ABSENT', 0, 0, 3, 2026, CURRENT_TIMESTAMP)"
            ))

    with engine.begin() as connection:
        attendance = sa.Table("attendance_records", sa.MetaData(), autoload_with=connection)
        with pytest.raises(IntegrityError):
            connection.execute(attendance.insert().values(
                teacher_ci="LEGACY-1",
                designation_id=17,
                date=date(2026, 3, 2),
                scheduled_start=time(8, 0),
                scheduled_end=time(9, 30),
                status="ATTENDED",
                academic_hours=2,
                late_minutes=0,
                month=3,
                year=2026,
                created_at=datetime(2026, 3, 2, 10, 0),
            ))
    engine.dispose()


def test_migration_adopts_exact_target_schema(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "attendance-adoption.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE attendance_records"))
        _metadata, target = _module()._schema(target=True)
        target.create(connection)

    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
    engine.dispose()


@pytest.mark.parametrize("attack", ["nullable", "default", "check", "index", "foreign_key"])
def test_migration_rejects_incompatible_target_before_mutation(tmp_path, monkeypatch, attack):
    engine, config = _config(tmp_path, monkeypatch, f"attendance-attack-{attack}.sqlite3")
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE attendance_records"))
        _metadata, target = _module()._schema(target=True)
        if attack == "nullable":
            target.c.designation_id.nullable = False
        elif attack == "default":
            target.c.status.server_default = sa.DefaultClause(sa.text("'ATTENDED'"))
        elif attack == "check":
            constraint = next(item for item in target.constraints if isinstance(item, sa.CheckConstraint))
            target.constraints.remove(constraint)
        elif attack == "index":
            index = next(item for item in target.indexes if item.name == "uq_attendance_record_published_source")
            target.indexes.remove(index)
        elif attack == "foreign_key":
            constraint = next(
                item for item in target.foreign_key_constraints
                if tuple(element.parent.name for element in item.elements) == ("published_schedule_assignment_id",)
            )
            constraint.ondelete = "CASCADE"
        target.create(connection)
    before = _snapshot(engine)

    with pytest.raises(RuntimeError, match="Incompatible pre-existing attendance_records"):
        command.upgrade(config, REVISION)

    assert _snapshot(engine) == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


def test_migration_refuses_destructive_downgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "attendance-downgrade.sqlite3")
    command.upgrade(config, REVISION)
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREDECESSOR)
    assert "published_schedule_assignment_id" in {
        item["name"] for item in sa.inspect(engine).get_columns("attendance_records")
    }
    engine.dispose()


def test_postgresql_migration_preserves_rows_and_is_autogenerate_clean(postgres_attendance_migration):
    engine, config = postgres_attendance_migration
    command.upgrade(config, PREDECESSOR)
    with engine.begin() as connection:
        _insert_legacy_row(connection)
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        row = connection.execute(sa.text(
            "SELECT id, designation_id, published_schedule_assignment_id FROM attendance_records"
        )).mappings().one()
        assert dict(row) == {
            "id": 41,
            "designation_id": 17,
            "published_schedule_assignment_id": None,
        }
    command.upgrade(config, "head")
    command.check(config)


def test_postgresql_published_source_uniqueness_xor_and_restrict(postgres_attendance_migration):
    engine, config = postgres_attendance_migration
    command.upgrade(config, REVISION)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO teachers (ci, full_name, created_at) "
            "VALUES ('PUBLISHED-1', 'Published Teacher', CURRENT_TIMESTAMP)"
        ))
        connection.execute(sa.text("SET session_replication_role = replica"))
        connection.execute(sa.text(
            "INSERT INTO academic_schedule_published_assignments "
            "(id, publication_block_id, source_assignment_id, teacher_ci, teacher_name, effective_from) "
            "VALUES (91, 999, 501, 'PUBLISHED-1', 'Published Teacher', '2026-03-01')"
        ))
        connection.execute(sa.text("SET session_replication_role = origin"))
        attendance = sa.Table("attendance_records", sa.MetaData(), autoload_with=connection)
        connection.execute(attendance.insert().values(
            teacher_ci="PUBLISHED-1",
            designation_id=None,
            published_schedule_assignment_id=91,
            date=date(2026, 3, 2),
            scheduled_start=time(8),
            scheduled_end=time(9),
            status="ATTENDED",
            academic_hours=1,
            late_minutes=0,
            month=3,
            year=2026,
            created_at=datetime(2026, 3, 2, 10),
        ))

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            attendance = sa.Table("attendance_records", sa.MetaData(), autoload_with=connection)
            connection.execute(attendance.insert().values(
                teacher_ci="PUBLISHED-1",
                designation_id=None,
                published_schedule_assignment_id=91,
                date=date(2026, 3, 2),
                scheduled_start=time(8),
                scheduled_end=time(9),
                status="ATTENDED",
                academic_hours=1,
                late_minutes=0,
                month=3,
                year=2026,
                created_at=datetime(2026, 3, 2, 10),
            ))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO attendance_records "
                "(teacher_ci, designation_id, published_schedule_assignment_id, date, scheduled_start, "
                "scheduled_end, status, academic_hours, late_minutes, month, year, created_at) "
                "VALUES ('PUBLISHED-1', NULL, NULL, '2026-03-03', '08:00', '09:00', "
                "'ABSENT', 0, 0, 3, 2026, CURRENT_TIMESTAMP)"
            ))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(sa.text(
                "DELETE FROM academic_schedule_published_assignments WHERE id = 91"
            ))
