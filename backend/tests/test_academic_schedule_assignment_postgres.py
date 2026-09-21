import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from pathlib import Path
from threading import Barrier

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
    AcademicSubject,
    Classroom,
    SubjectOffering,
    TeacherAvailability,
)
from app.models.teacher import Teacher
from app.services import academic_management_service as service


def test_postgresql_concurrent_double_booking_allows_only_one_assignment(monkeypatch):
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
        program = AcademicProgram(code="CON", name="Concurrency")
        subject = AcademicSubject(code="CON-101", name="Concurrency")
        teacher = Teacher(ci="CONCURRENT-1", full_name="Concurrent Teacher")
        db.add_all([program, subject, teacher])
        db.flush()
        offering = SubjectOffering(
            subject_id=subject.id, program_id=program.id, academic_period="II/2026",
            semester=1, theory_hours=10, practice_hours=0,
        )
        groups = [
            AcademicGroup(
                program_id=program.id, academic_period="II/2026", semester=1,
                shift="Morning", code=code, expected_size=10,
            ) for code in ("A", "B")
        ]
        rooms = [
            Classroom(
                code=f"CON-{code}", name=f"Room {code}", campus="Central",
                capacity=20, classroom_type="classroom", resources=[],
            ) for code in ("A", "B")
        ]
        draft = AcademicScheduleDraft(
            program_id=program.id, academic_period="II/2026", name="Concurrent",
            normalized_name="concurrent", status="draft",
        )
        db.add_all([offering, *groups, *rooms, draft])
        db.flush()
        blocks = [
            AcademicScheduleBlock(
                draft_id=draft.id, offering_id=offering.id, group_id=groups[index].id,
                classroom_id=rooms[index].id, activity_type="theory", weekday="monday",
                start_time=time(8, 0), end_time=time(9, 0),
            ) for index in range(2)
        ]
        db.add_all(blocks)
        db.add(TeacherAvailability(
            teacher_ci=teacher.ci, academic_period="II/2026", weekday="monday",
            start_time=time(7, 0), end_time=time(12, 0), active=True,
        ))
        db.flush()
        draft_id = draft.id
        block_ids = [block.id for block in blocks]

    barrier = Barrier(2)

    def assign(block_id):
        db = Session()
        try:
            barrier.wait(timeout=10)
            service.create_schedule_assignment(db, draft_id, block_id, {
                "teacher_ci": "CONCURRENT-1",
                "effective_from": date(2026, 1, 1),
                "effective_to": None,
            })
            return "created"
        except HTTPException as exc:
            return f"conflict:{exc.status_code}"
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(assign, block_ids))

    assert sorted(results) == ["conflict:409", "created"]
    with Session() as db:
        assert db.query(AcademicScheduleAssignment).count() == 1
    engine.dispose()
