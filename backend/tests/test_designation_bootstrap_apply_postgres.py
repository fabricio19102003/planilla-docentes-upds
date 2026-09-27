from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event
from time import sleep

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401 — register complete metadata for the PostgreSQL harness
from app.models.academic_management import (
    AcademicScheduleAssignment, AcademicScheduleBlock, AcademicScheduleDraft,
)
from app.models.activity_log import ActivityLog
from app.models.designation_bootstrap import DesignationBootstrapReceipt
from app.models.user import User
from app.services import designation_bootstrap_apply as apply_service
from app.services.designation_bootstrap_preview import build_designation_bootstrap_preview
from tests.test_designation_bootstrap_preview import _official, _salary, _seed


EFFECTIVE_DATE = date(2026, 8, 21)


def _postgres():
    url = os.getenv("DESIGNATION_BOOTSTRAP_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("DESIGNATION_BOOTSTRAP_TEST_POSTGRES_URL is not configured")
    parsed = sa.engine.make_url(url)
    if parsed.get_backend_name() != "postgresql" or "test" not in (parsed.database or ""):
        pytest.fail("DESIGNATION_BOOTSTRAP_TEST_POSTGRES_URL must target a dedicated PostgreSQL test database")
    engine = sa.create_engine(url, pool_size=8, max_overflow=4)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _seed_apply(Session):
    official = _official(include_practice=False)
    salary = _salary(hours=())
    with Session.begin() as db:
        _seed(db)
        actor = User(
            ci="ADMIN-PG-BOOTSTRAP",
            full_name="PostgreSQL Bootstrap Admin",
            password_hash="not-used",
            role="admin",
            is_active=True,
        )
        db.add(actor)
        db.flush()
        actor_id = actor.id
    with Session() as db:
        preview = build_designation_bootstrap_preview(
            db,
            official_content=official,
            salary_content=salary,
            academic_period="II/2026",
            effective_date=EFFECTIVE_DATE,
            program_identity="MED",
        )
    assert preview["can_apply"] is True
    return actor_id, official, salary, preview["preview_digest"]


def _apply(Session, actor_id, official, salary, digest):
    with Session() as db:
        db.execute(sa.text("SET LOCAL lock_timeout = '10s'"))
        db.execute(sa.text("SET LOCAL statement_timeout = '20s'"))
        actor = db.get(User, actor_id)
        result = apply_service.apply_designation_bootstrap(
            db,
            official_content=official,
            salary_content=salary,
            academic_period="II/2026",
            effective_date=EFFECTIVE_DATE,
            program_identity="MED",
            confirmation_digest=digest,
            actor=actor,
        )
        db.commit()
        return result


def test_postgresql_exact_apply_race_creates_one_complete_graph(monkeypatch):
    engine, Session = _postgres()
    try:
        actor_id, official, salary, digest = _seed_apply(Session)
        barrier = Barrier(2)

        def contender():
            barrier.wait(timeout=10)
            return _apply(Session, actor_id, official, salary, digest)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: contender(), range(2)))

        assert sorted(item["status"] for item in results) == ["applied", "replayed"]
        assert len({item["draft_id"] for item in results}) == 1
        with Session() as db:
            assert db.query(DesignationBootstrapReceipt).count() == 1
            assert db.query(AcademicScheduleDraft).count() == 1
            assert db.query(AcademicScheduleBlock).count() == 1
            assert db.query(AcademicScheduleAssignment).count() == 1
            assert db.query(ActivityLog).filter_by(action="apply_designation_bootstrap").count() == 1
    finally:
        engine.dispose()


def test_postgresql_table_locks_block_teacher_classroom_and_catalog_phantoms(monkeypatch):
    engine, Session = _postgres()
    try:
        actor_id, official, salary, digest = _seed_apply(Session)
        locks_held = Event()
        release_apply = Event()
        original_lock = apply_service._lock_postgresql_tables

        def observed_lock(db):
            original_lock(db)
            locks_held.set()
            if not release_apply.wait(timeout=10):
                raise AssertionError("Timed out waiting to release bootstrap table locks")

        monkeypatch.setattr(apply_service, "_lock_postgresql_tables", observed_lock)

        def insert_phantom(sql, parameters):
            with Session() as db:
                db.execute(sa.text("SET LOCAL lock_timeout = '10s'"))
                db.execute(sa.text("SET LOCAL statement_timeout = '20s'"))
                db.execute(sa.text(sql), parameters)
                db.commit()
                return "inserted"

        inserts = (
            (
                "INSERT INTO teachers (ci, full_name, created_at, updated_at) "
                "VALUES (:key, 'Phantom teacher', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                {"key": "PG-PHANTOM-T"},
            ),
            (
                "INSERT INTO classrooms "
                "(code, name, campus, capacity, classroom_type, resources, active, created_at, updated_at) "
                "VALUES (:key, 'Phantom room', 'Test', 20, 'classroom', '[]', true, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                {"key": "PG-PHANTOM-R"},
            ),
            (
                "INSERT INTO academic_subjects (code, name, active, created_at, updated_at) "
                "VALUES (:key, 'Phantom subject', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                {"key": "PG-PHANTOM-S"},
            ),
        )
        with ThreadPoolExecutor(max_workers=4) as executor:
            apply_future = executor.submit(_apply, Session, actor_id, official, salary, digest)
            assert locks_held.wait(timeout=10)
            insert_futures = [executor.submit(insert_phantom, sql, params) for sql, params in inserts]
            sleep(0.5)
            assert all(not future.done() for future in insert_futures)
            release_apply.set()
            result = apply_future.result(timeout=15)
            assert result["status"] == "applied"
            assert [future.result(timeout=15) for future in insert_futures] == ["inserted"] * 3

        with Session() as db:
            assert db.query(DesignationBootstrapReceipt).count() == 1
            assert db.query(AcademicScheduleDraft).count() == 1
            assert db.query(AcademicScheduleBlock).count() == 1
            assert db.query(AcademicScheduleAssignment).count() == 1
    finally:
        release_apply.set()
        engine.dispose()


def test_postgresql_apply_observes_actor_revoked_after_table_locks(monkeypatch):
    engine, Session = _postgres()
    release_apply = Event()
    try:
        actor_id, official, salary, digest = _seed_apply(Session)
        locks_held = Event()
        original_lock = apply_service._lock_postgresql_tables

        def observed_lock(db):
            original_lock(db)
            locks_held.set()
            if not release_apply.wait(timeout=10):
                raise AssertionError("Timed out waiting to revalidate bootstrap actor")

        monkeypatch.setattr(apply_service, "_lock_postgresql_tables", observed_lock)
        with ThreadPoolExecutor(max_workers=2) as executor:
            apply_future = executor.submit(_apply, Session, actor_id, official, salary, digest)
            assert locks_held.wait(timeout=10)
            with Session.begin() as db:
                db.execute(sa.update(User).where(User.id == actor_id).values(is_active=False))
            release_apply.set()
            with pytest.raises(apply_service.DesignationBootstrapApplyError, match="invalid_actor"):
                apply_future.result(timeout=15)

        with Session() as db:
            assert db.query(DesignationBootstrapReceipt).count() == 0
            assert db.query(AcademicScheduleDraft).count() == 0
    finally:
        release_apply.set()
        engine.dispose()
