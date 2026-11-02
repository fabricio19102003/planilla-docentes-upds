"""PostgreSQL: two students racing for the last place of a group; only one gets it (student-portal S5)."""
import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.academic_management import AcademicGroup
from app.models.academic_records import CurriculumPlan, Student
from app.models.student_portal import ReenrollmentRequest, ReenrollmentWindow, StudentAccount
from app.services import academic_history_import as importer
from app.services import reenrollment
from app.models.user import User
from tests.test_academic_history_import import _csv, _row

URL_VARIABLE = "REENROLLMENT_TEST_POSTGRES_URL"


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


def _seed(Session):
    term = {"literal": "Primer Semestre", "year": "2026", "offer": "2026/1/1"}
    with Session.begin() as db:
        rows = []
        for n, document in enumerate(("RACE-A", "RACE-B")):
            student = {"EstudianteNroDocumento": document, "EstudianteTipoDocumento": "CI", "EstudianteNombre": "R",
                       "EstudianteApellidos": document, "EstudianteNacionalidad": "Boliviana"}
            rows.append(_row(student, 90_000 + n, "Anatomía Humana II MRF-0200", "Aprobado", 70, **term))
        content = _csv(rows)
        importer.apply(db, content, "race.csv", hashlib.sha256(content).hexdigest(), None)
        plan = db.query(CurriculumPlan).one()
        group = AcademicGroup(program_id=plan.program_id, academic_period="I/2027", semester=3, shift="M",
                              code="M-01", expected_size=1)
        today = reenrollment.bolivia_today()
        db.add_all([group, ReenrollmentWindow(term_code="I/2027", starts_on=today - timedelta(days=1),
                                              ends_on=today + timedelta(days=1))])
        accounts = [StudentAccount(student_id=s.id, password_hash="x", must_change_password=False, is_active=True,
                                   token_version=0) for s in db.query(Student).order_by(Student.document_number)]
        db.add_all(accounts)
        db.flush()
        return group.id, [a.id for a in accounts]


def _race(Session, group_id, account_ids):
    first_submitted = threading.Event()

    def first():
        with Session() as db:
            reenrollment.submit(db, db.get(StudentAccount, account_ids[0]), group_id, [])
            first_submitted.set()
            time.sleep(1.5)  # hold the transaction open while the second student tries
            db.commit()
            return "ok"

    def second():
        first_submitted.wait(10)
        with Session() as db:
            try:
                reenrollment.submit(db, db.get(StudentAccount, account_ids[1]), group_id, [])
                db.commit()
                return "ok"
            except HTTPException as exc:
                db.rollback()
                return (exc.status_code, exc.detail)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(first), pool.submit(second)]
        return [future.result(timeout=30) for future in results]


def test_the_last_place_goes_to_one_student_only(monkeypatch):
    engine = _engine(monkeypatch)
    Session = sessionmaker(bind=engine)
    group_id, account_ids = _seed(Session)

    assert _race(Session, group_id, account_ids) == ["ok", (409, "El grupo M-01 ya no tiene cupos")]
    with Session() as db:
        assert db.query(ReenrollmentRequest).count() == 1


def test_reopening_an_observed_request_waits_for_a_student_taking_the_last_place(monkeypatch):
    engine = _engine(monkeypatch)
    Session = sessionmaker(bind=engine)
    group_id, account_ids = _seed(Session)
    with Session.begin() as db:
        staff = User(ci="RACE-STAFF", full_name="Registro", role="admin", is_active=True, password_hash="x")
        db.add(staff)
        db.flush()
        observed = reenrollment.submit(db, db.get(StudentAccount, account_ids[0]), group_id, [])
        reenrollment.handle(db, observed, staff, "observada", "pago_pendiente", "Falta el pago")
        observed_id, staff_id = observed.id, staff.id
    student_submitted = threading.Event()

    def student():
        with Session() as db:
            reenrollment.submit(db, db.get(StudentAccount, account_ids[1]), group_id, [])
            student_submitted.set()
            time.sleep(1.5)  # hold the place uncommitted while staff reopen the observed request
            db.commit()
            return "ok"

    def staff_reopens():
        student_submitted.wait(10)
        with Session() as db:
            try:
                reenrollment.handle(db, db.get(ReenrollmentRequest, observed_id), db.get(User, staff_id), "pendiente")
                db.commit()
                return "ok"
            except HTTPException as exc:
                db.rollback()
                return (exc.status_code, exc.detail)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(student), pool.submit(staff_reopens)]
        assert [f.result(timeout=30) for f in results] == ["ok", (409, "El grupo M-01 ya no tiene cupos")]
    with Session() as db:
        assert db.get(ReenrollmentRequest, observed_id).status == "observada"
        assert reenrollment._taken(db, [group_id]) == {group_id: 1}
