import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from pathlib import Path
from threading import Barrier, Event, current_thread
from time import sleep

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.academic_management import (
    AcademicGroup,
    AcademicProgram,
    AcademicScheduleAssignment,
    AcademicScheduleBlock,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSubject,
    Classroom,
    SubjectOffering,
    TeacherAvailability,
)
from app.models.teacher import Teacher
from app.models.user import User
from app.services import academic_schedule_publication_service as service
from app.services import academic_management_service as management
from app.services.auth_service import auth_service


def test_postgresql_concurrent_same_sequence_publish_allows_only_one(monkeypatch):
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
    command.upgrade(config, "head")
    Session = sessionmaker(bind=engine)
    with Session.begin() as db:
        program = AcademicProgram(code="PUB-CON", name="Publication concurrency")
        subject = AcademicSubject(code="PUB-CON-101", name="Publication concurrency")
        teacher = Teacher(ci="PUB-CON-T", full_name="Publication Concurrent Teacher")
        user = User(
            ci="PUB-CON-ADMIN", full_name="Publication Admin",
            password_hash=auth_service.hash_password("testpass123"), role="admin", is_active=True,
        )
        db.add_all([program, subject, teacher, user])
        db.flush()
        offering = SubjectOffering(
            subject_id=subject.id, program_id=program.id, academic_period="I/2027",
            semester=1, theory_hours=10, practice_hours=0,
        )
        room = Classroom(
            code="PUB-CON-R", name="Room", campus="Central", capacity=30,
            classroom_type="classroom", resources=[],
        )
        group = AcademicGroup(
            program_id=program.id, academic_period="I/2027", semester=1,
            shift="Morning", code="A", expected_size=10,
        )
        db.add_all([offering, room, group])
        db.flush()
        drafts = [
            AcademicScheduleDraft(
                program_id=program.id, academic_period="I/2027", name=f"Candidate {index}",
                normalized_name=f"candidate {index}", status="draft",
            ) for index in range(2)
        ]
        db.add_all(drafts)
        db.flush()
        for draft in drafts:
            block = AcademicScheduleBlock(
                draft_id=draft.id, offering_id=offering.id, group_id=group.id,
                classroom_id=room.id, activity_type="theory", weekday="monday",
                start_time=time(8), end_time=time(9),
            )
            db.add(block)
            db.flush()
            db.add(AcademicScheduleAssignment(
                block_id=block.id, teacher_ci=teacher.ci,
                effective_from=date(2027, 1, 1), effective_to=None,
            ))
        db.add(TeacherAvailability(
            teacher_ci=teacher.ci, academic_period="I/2027", weekday="monday",
            start_time=time(7), end_time=time(12), active=True,
        ))
        db.flush()
        draft_ids = [draft.id for draft in drafts]
        user_id = user.id
    with Session() as db:
        previews = [service.preview_publication(db, draft_id, date(2027, 2, 1)) for draft_id in draft_ids]
    assert [item["sequence"] for item in previews] == [1, 1]
    barrier = Barrier(2)

    def publish(index):
        db = Session()
        try:
            barrier.wait(timeout=10)
            service.publish(
                db, draft_ids[index], date(2027, 2, 1), previews[index]["digest"], user_id
            )
            return "published"
        except HTTPException as exc:
            return f"conflict:{exc.status_code}"
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(publish, range(2)))
    assert sorted(results) == ["conflict:409", "published"]
    with Session() as db:
        rows = db.query(AcademicSchedulePublication).all()
        assert [(row.effective_from, row.sequence) for row in rows] == [(date(2027, 2, 1), 1)]
    engine.dispose()


def test_postgresql_draft_rename_and_publication_follow_one_lock_order(monkeypatch):
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
    command.upgrade(config, "head")
    Session = sessionmaker(bind=engine)
    with Session.begin() as db:
        program = AcademicProgram(code="LOCK-ORDER", name="Lock order")
        subject = AcademicSubject(code="LOCK-101", name="Lock order")
        teacher = Teacher(ci="LOCK-T", full_name="Lock Order Teacher")
        user = User(
            ci="LOCK-ADMIN", full_name="Lock Admin",
            password_hash=auth_service.hash_password("testpass123"), role="admin", is_active=True,
        )
        db.add_all([program, subject, teacher, user])
        db.flush()
        offering = SubjectOffering(
            subject_id=subject.id, program_id=program.id, academic_period="I/2027",
            semester=1, theory_hours=10, practice_hours=0,
        )
        room = Classroom(
            code="LOCK-R", name="Room", campus="Central", capacity=30,
            classroom_type="classroom", resources=[],
        )
        group = AcademicGroup(
            program_id=program.id, academic_period="I/2027", semester=1,
            shift="Morning", code="A", expected_size=10,
        )
        draft = AcademicScheduleDraft(
            program_id=program.id, academic_period="I/2027", name="Before rename",
            normalized_name="before rename", status="draft",
        )
        db.add_all([offering, room, group, draft])
        db.flush()
        block = AcademicScheduleBlock(
            draft_id=draft.id, offering_id=offering.id, group_id=group.id,
            classroom_id=room.id, activity_type="theory", weekday="monday",
            start_time=time(8), end_time=time(9),
        )
        db.add(block)
        db.flush()
        db.add_all([
            AcademicScheduleAssignment(
                block_id=block.id, teacher_ci=teacher.ci,
                effective_from=date(2027, 1, 1), effective_to=None,
            ),
            TeacherAvailability(
                teacher_ci=teacher.ci, academic_period="I/2027", weekday="monday",
                start_time=time(7), end_time=time(12), active=True,
            ),
        ])
        db.flush()
        draft_id = draft.id
        program_id = program.id
        user_id = user.id
    with Session() as db:
        preview = service.preview_publication(db, draft_id, date(2027, 2, 1))

    update_holds_draft = Event()
    release_update = Event()
    publication_started = Event()
    original_lock_row = management._lock_row

    def observed_lock_row(db, model, entity_id):
        row = original_lock_row(db, model, entity_id)
        if model is AcademicScheduleDraft and current_thread().name.startswith("draft-update"):
            update_holds_draft.set()
            if not release_update.wait(timeout=10):
                raise AssertionError("Timed out waiting to release the draft update")
        return row

    monkeypatch.setattr(management, "_lock_row", observed_lock_row)

    def rename_draft():
        with Session() as db:
            db.execute(sa.text("SET LOCAL lock_timeout = '4s'"))
            db.execute(sa.text("SET LOCAL statement_timeout = '8s'"))
            management.update_schedule_draft(db, draft_id, {
                "program_id": program_id,
                "academic_period": "I/2027",
                "name": "After rename",
            })
            return "updated"

    def publish_draft():
        publication_started.set()
        with Session() as db:
            db.execute(sa.text("SET LOCAL lock_timeout = '4s'"))
            db.execute(sa.text("SET LOCAL statement_timeout = '8s'"))
            service.publish(
                db, draft_id, date(2027, 2, 1), preview["digest"], user_id
            )
            return "published"

    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="draft-update") as update_pool,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="draft-publication") as publish_pool,
    ):
        update_future = update_pool.submit(rename_draft)
        assert update_holds_draft.wait(timeout=10)
        publish_future = publish_pool.submit(publish_draft)
        assert publication_started.wait(timeout=10)
        sleep(0.5)
        release_update.set()
        assert sorted([
            update_future.result(timeout=10), publish_future.result(timeout=10)
        ]) == ["published", "updated"]

    with Session() as db:
        stored = db.get(AcademicScheduleDraft, draft_id)
        assert stored is not None
        assert stored.name == "After rename"
        assert stored.status == "published"
        assert db.query(AcademicSchedulePublication).filter_by(source_draft_id=draft_id).count() == 1
    engine.dispose()
