"""PostgreSQL: the last place of an intensive course goes to one student only (academic-phase3 S1, risk item 4)."""
import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.academic_management import AcademicSubject
from app.models.academic_records import Student
from app.models.intensive_courses import IntensiveCourse, IntensiveCourseSettings, IntensiveEnrollment
from app.models.student_portal import StudentAccount
from app.models.teacher import Teacher
from app.models.user import User
from app.services import academic_history_import as importer
from app.services import intensive_courses
from tests.test_academic_history_import import _csv, _row

URL_VARIABLE = "REENROLLMENT_TEST_POSTGRES_URL"
FULL = (409, "El curso intensivo ya no tiene cupos")


def _engine(monkeypatch):
    url = os.getenv(URL_VARIABLE)
    if not url:
        pytest.skip(f"{URL_VARIABLE} is not configured")
    parsed = sa.engine.make_url(url)
    if parsed.get_backend_name() != "postgresql" or "test" not in (parsed.database or ""):
        pytest.fail(f"{URL_VARIABLE} must target a dedicated PostgreSQL test database")
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
    return engine


def _seed(Session, capacity=1, students=2):
    """A LIN 0130 course with ``capacity`` places and ``students`` students who failed that subject."""
    today = intensive_courses.bolivia_today()
    term = {"literal": "Primer Semestre", "year": "2026", "offer": "2026/1/1"}
    with Session.begin() as db:
        rows = []
        for n in range(students):
            document = f"RACE-{n}"
            student = {"EstudianteNroDocumento": document, "EstudianteTipoDocumento": "CI", "EstudianteNombre": "R",
                       "EstudianteApellidos": document, "EstudianteNacionalidad": "Boliviana"}
            rows.append(_row(student, 70_000 + n, "Inglés Técnico I LIN-0130", "Reprobado", 30, **term))
        content = _csv(rows)
        importer.apply(db, content, "race.csv", hashlib.sha256(content).hexdigest(), None)
        subject = db.query(AcademicSubject).filter_by(code="LIN 0130").one()
        db.add(Teacher(ci="RACE-T", full_name="Docente"))
        students_ = db.query(Student).order_by(Student.document_number).all()
        accounts = [StudentAccount(student_id=s.id, password_hash="x", must_change_password=False, is_active=True,
                                   token_version=0) for s in students_]
        db.add_all(accounts)
        configured = db.get(IntensiveCourseSettings, 1)  # created by the migration, without rates
        configured.theory_hourly_rate, configured.practice_hourly_rate = Decimal("100"), Decimal("60")
        course = IntensiveCourse(
            term_code="VER/2027", subject_id=subject.id, teacher_ci="RACE-T", capacity=capacity,
            enrollment_starts_on=today - timedelta(days=1), enrollment_ends_on=today + timedelta(days=1),
            theory_hours=40, practice_hours=0, status="open")
        db.add(course)
        db.flush()
        return course.id, [a.student_id for a in accounts], subject.id


def _race(Session, course_id, student_ids):
    first_enrolled = threading.Event()

    def first():
        with Session() as db:
            intensive_courses.enroll(db, db.get(StudentAccount, _account(db, student_ids[0])), course_id)
            first_enrolled.set()
            time.sleep(1.5)  # hold the transaction open while the second student tries
            db.commit()
            return "ok"

    def second():
        first_enrolled.wait(10)
        with Session() as db:
            try:
                intensive_courses.enroll(db, db.get(StudentAccount, _account(db, student_ids[1])), course_id)
                db.commit()
                return "ok"
            except HTTPException as exc:
                db.rollback()
                return (exc.status_code, exc.detail)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(first), pool.submit(second)]
        return [future.result(timeout=30) for future in results]


def _account(db, student_id):
    return db.query(StudentAccount).filter_by(student_id=student_id).one().id


def test_the_last_place_goes_to_one_student_only(monkeypatch):
    engine = _engine(monkeypatch)
    Session = sessionmaker(bind=engine)
    course_id, student_ids, _ = _seed(Session)

    assert _race(Session, course_id, student_ids) == ["ok", FULL]
    with Session() as db:
        assert db.query(IntensiveEnrollment).count() == 1
        assert db.query(IntensiveEnrollment).one().student_id == student_ids[0]


def test_closing_waits_for_an_enrollment_in_flight_and_counts_it(monkeypatch):
    engine = _engine(monkeypatch)
    Session = sessionmaker(bind=engine)
    course_id, student_ids, _ = _seed(Session, capacity=2)
    with Session.begin() as db:
        staff = User(ci="RACE-STAFF", full_name="Registro", role="admin", is_active=True, password_hash="x")
        db.add(staff)
        db.flush()
        staff_id = staff.id
    enrolled = threading.Event()

    def student():
        with Session() as db:
            intensive_courses.enroll(db, db.get(StudentAccount, _account(db, student_ids[0])), course_id)
            enrolled.set()
            time.sleep(1.5)  # the place is uncommitted while staff close the enrollment
            db.commit()
            return "ok"

    def staff_closes():
        enrolled.wait(10)
        with Session() as db:
            closed = intensive_courses.close_course(db, course_id, db.get(User, staff_id))
            db.commit()
            return closed.final_enrolled

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(student), pool.submit(staff_closes)]
        assert [f.result(timeout=30) for f in results] == ["ok", 1]
    with Session() as db:
        course = db.get(IntensiveCourse, course_id)
        assert (course.status, course.final_enrolled) == ("closed", 1)


def test_lowering_the_capacity_waits_for_an_enrollment_in_flight(monkeypatch):
    engine = _engine(monkeypatch)
    Session = sessionmaker(bind=engine)
    course_id, student_ids, _ = _seed(Session, capacity=2)
    with Session.begin() as db:
        intensive_courses.enroll(db, db.get(StudentAccount, _account(db, student_ids[0])), course_id)
    enrolled = threading.Event()

    def student():
        with Session() as db:
            intensive_courses.enroll(db, db.get(StudentAccount, _account(db, student_ids[1])), course_id)
            enrolled.set()
            time.sleep(1.5)  # the second place is uncommitted while staff lower the capacity to one
            db.commit()
            return "ok"

    def staff_lowers():
        enrolled.wait(10)
        with Session() as db:
            try:
                intensive_courses.update_course(db, course_id, {"capacity": 1})
                db.commit()
                return "ok"
            except HTTPException as exc:
                db.rollback()
                return (exc.status_code, exc.detail)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(student), pool.submit(staff_lowers)]
        assert [f.result(timeout=30) for f in results] == [
            "ok", (409, "La capacidad no puede ser menor a los 2 inscritos")]
    with Session() as db:
        assert db.get(IntensiveCourse, course_id).capacity == 2
        assert db.query(IntensiveEnrollment).count() == 2
