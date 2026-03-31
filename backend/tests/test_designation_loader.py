"""
Tests for DesignationLoader service.

Two test layers:
  1. Unit tests  — pure Python, no DB (test helpers and data structures)
  2. Integration tests — real SQLite in-memory DB (no PostgreSQL needed)

Integration tests load the REAL designaciones_normalizadas.json so they
also serve as acceptance tests for T-005.
"""
from __future__ import annotations

import json
import os
from datetime import date, time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base
from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord, BiometricUpload
from app.models.teacher import Teacher       # noqa: F401  — needed to register in metadata
from app.models.designation import Designation  # noqa: F401
# Register remaining models so create_all doesn't fail on FK refs
import app.models  # noqa: F401

from app.services.designation_loader import (
    DesignationLoader,
    DesignationLoadResult,
    normalize_name,
    names_match,
    _make_temp_ci,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Resolve path to the real JSON regardless of where pytest is invoked from
_HERE = Path(__file__).parent
_REPO_ROOT = _HERE.parent.parent  # backend/tests → backend → repo root
REAL_JSON = _REPO_ROOT / "designaciones_normalizadas.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sqlite_engine():
    """In-memory SQLite engine — no PostgreSQL required for tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # SQLite doesn't support PostgreSQL JSON column natively via
    # sqlalchemy.dialects.postgresql.JSON, so we patch it before create_all.
    from sqlalchemy.dialects.postgresql import JSON as PG_JSON
    from sqlalchemy import JSON as SA_JSON
    # Monkey-patch: replace PG JSON with generic SA JSON in the Designation model
    for col in Designation.__table__.columns:
        if isinstance(col.type, PG_JSON):
            col.type = SA_JSON()
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(sqlite_engine) -> Session:
    """Fresh session per test, rolled back after."""
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="module")
def loader() -> DesignationLoader:
    return DesignationLoader()


# ---------------------------------------------------------------------------
# Unit tests — helpers only, no DB
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_strips_accents(self):
        assert normalize_name("MARÍA") == "MARIA"

    def test_uppercases(self):
        assert normalize_name("abner flores") == "ABNER FLORES"

    def test_collapses_whitespace(self):
        assert normalize_name("  Juan   Pérez  ") == "JUAN PEREZ"

    def test_combined(self):
        assert normalize_name("Ñoño García-López") == "NONO GARCIA-LOPEZ"


class TestNamesMatch:
    def test_exact(self):
        assert names_match("ABNER FLORES MAMANI", "ABNER FLORES MAMANI")

    def test_accent_difference(self):
        assert names_match("MARIA GARCIA", "MARÍA GARCÍA")

    def test_partial_subset(self):
        # Biometric might store only two surnames
        assert names_match("ABNER FLORES MAMANI", "ABNER FLORES")

    def test_token_overlap_two_tokens(self):
        assert names_match("JUAN CARLOS PEREZ LUNA", "PEREZ LUNA RODRIGO")

    def test_no_match_single_common_token(self):
        assert not names_match("JUAN GARCIA", "PEDRO GARCIA")

    def test_no_match_different_names(self):
        assert not names_match("PEDRO ALVARADO", "MARIA CONDORI")


class TestMakeTempCi:
    def test_starts_with_temp(self):
        ci = _make_temp_ci("ABNER FLORES MAMANI")
        assert ci.startswith("TEMP-")

    def test_deterministic(self):
        ci1 = _make_temp_ci("ABNER FLORES MAMANI")
        ci2 = _make_temp_ci("ABNER FLORES MAMANI")
        assert ci1 == ci2

    def test_different_names_different_ci(self):
        ci1 = _make_temp_ci("ABNER FLORES MAMANI")
        ci2 = _make_temp_ci("JUAN PEREZ LUNA")
        assert ci1 != ci2

    def test_max_length_fits_column(self):
        ci = _make_temp_ci("VERY LONG TEACHER NAME THAT MIGHT OVERFLOW")
        assert len(ci) <= 20, f"CI too long: {ci!r}"


class TestDesignationLoadResult:
    def test_total_skipped(self):
        r = DesignationLoadResult(skipped_no_schedule=43, skipped_no_time=1)
        assert r.total_skipped == 44

    def test_str(self):
        r = DesignationLoadResult(teachers_created=130, designations_loaded=399)
        s = str(r)
        assert "teachers_created=130" in s
        assert "designations_loaded=399" in s


# ---------------------------------------------------------------------------
# Integration tests — real JSON file + SQLite in-memory DB
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not REAL_JSON.exists(),
    reason=f"Real JSON not found at {REAL_JSON}",
)
class TestLoadFromJson:
    def test_file_not_found_raises(self, loader, db):
        with pytest.raises(FileNotFoundError):
            loader.load_from_json(db, "/nonexistent/path/designaciones.json")

    def test_load_returns_result(self, loader, db):
        result = loader.load_from_json(db, str(REAL_JSON))
        assert isinstance(result, DesignationLoadResult)

    def test_designations_count(self, loader, db):
        """
        The JSON contains 399 'parsed_successfully' entries.
        Of those, 2 have docente=null (with schedule) → skipped by loader.
        Expected: 397 designations loaded.
        """
        result = loader.load_from_json(db, str(REAL_JSON))
        assert result.designations_loaded == 397, (
            f"Expected 397 designations (399 in JSON minus 2 null-docente), got {result.designations_loaded}"
        )

    def test_skipped_no_schedule(self, loader, db):
        """
        The JSON already filtered the 43+1 schedule-less entries from the parser.
        Inside the JSON, only 2 entries have docente=null (with schedule) → skipped.
        """
        result = loader.load_from_json(db, str(REAL_JSON))
        assert result.skipped_no_schedule == 2, (
            f"Expected 2 skipped_no_schedule (null docente with schedule), got {result.skipped_no_schedule}"
        )

    def test_teachers_created(self, loader, db):
        """
        Expect exactly 130 unique teachers.
        teachers_reused counts the same teacher's additional designations (not new teachers).
        """
        result = loader.load_from_json(db, str(REAL_JSON))
        # On first load, reused means the in-memory cache hit (same teacher, different designation)
        # teachers_created = unique teacher records created = ~130
        assert 125 <= result.teachers_created <= 135, (
            f"Expected ~130 unique teachers, got {result.teachers_created}"
        )
        # reused + created = total designation assignments = 397
        assert result.teachers_created + result.teachers_reused == 397, (
            "teachers_created + teachers_reused must equal total designations loaded"
        )

    def test_schedule_json_stored_correctly(self, loader, db):
        """First designation for ABNER FLORES MAMANI should have 3 schedule slots."""
        loader.load_from_json(db, str(REAL_JSON))

        temp_ci = _make_temp_ci("ABNER FLORES MAMANI")
        designations = (
            db.query(Designation)
            .filter(Designation.teacher_ci == temp_ci)
            .order_by(Designation.id)
            .all()
        )
        assert len(designations) > 0, "ABNER FLORES MAMANI should have designations"
        first = designations[0]
        assert isinstance(first.schedule_json, list)
        assert len(first.schedule_json) == 3  # lunes, martes, viernes

        slot = first.schedule_json[0]
        assert slot["dia"] == "lunes"
        assert slot["hora_inicio"] == "06:30"
        assert slot["hora_fin"] == "08:00"

    def test_all_temp_cis(self, loader, db):
        """After loading from JSON alone, ALL teacher CIs should be TEMP-."""
        loader.load_from_json(db, str(REAL_JSON))
        non_temp = (
            db.query(Teacher)
            .filter(~Teacher.ci.like("TEMP-%"))
            .count()
        )
        assert non_temp == 0, f"{non_temp} teachers have non-TEMP CI after JSON-only load"

    def test_idempotent_load(self, loader, db):
        """Loading twice must not double-create teachers."""
        r1 = loader.load_from_json(db, str(REAL_JSON))
        teacher_count_after_first = db.query(Teacher).count()
        designation_count_after_first = db.query(Designation).count()
        r2 = loader.load_from_json(db, str(REAL_JSON))
        assert r2.teachers_created == 0, "Second load must not create new teachers"
        # On second load all teacher lookups hit the DB or in-memory cache → all reused
        assert r2.teachers_reused == r2.designations_loaded, (
            "Second load: every designation assignment must reuse an existing teacher"
        )
        assert db.query(Teacher).count() == teacher_count_after_first
        assert db.query(Designation).count() == designation_count_after_first


# ---------------------------------------------------------------------------
# Integration tests — link_teachers_by_name
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not REAL_JSON.exists(),
    reason=f"Real JSON not found at {REAL_JSON}",
)
class TestLinkTeachersByName:
    def test_exact_match_updates_ci(self, loader, db):
        loader.load_from_json(db, str(REAL_JSON))

        # Simulate biometric providing the real CI for ABNER FLORES MAMANI
        ci_name_map = {"1234567": "ABNER FLORES MAMANI"}
        updated = loader.link_teachers_by_name(db, ci_name_map)
        assert updated == 1

        teacher = db.query(Teacher).filter(Teacher.ci == "1234567").first()
        assert teacher is not None
        assert teacher.full_name == "ABNER FLORES MAMANI"

    def test_designations_follow_ci_update(self, loader, db):
        loader.load_from_json(db, str(REAL_JSON))

        ci_name_map = {"9999999": "ABNER FLORES MAMANI"}
        loader.link_teachers_by_name(db, ci_name_map)

        designations = (
            db.query(Designation)
            .filter(Designation.teacher_ci == "9999999")
            .all()
        )
        assert len(designations) >= 2, (
            "ABNER FLORES MAMANI should have multiple designations transferred"
        )

    def test_accent_normalisation_match(self, loader, db):
        loader.load_from_json(db, str(REAL_JSON))

        # Biometric might store accented version
        ci_name_map = {"8888888": "ÁBNER FLÓRES MAMANI"}
        updated = loader.link_teachers_by_name(db, ci_name_map)
        assert updated == 1

    def test_no_temp_teachers_returns_zero(self, loader, db):
        # Don't load anything → no TEMP teachers
        count = loader.link_teachers_by_name(db, {"123": "WHOEVER"})
        assert count == 0

    def test_merge_collision_repoints_attendance_and_deletes_temp_designation(self, loader, db):
        temp_ci = _make_temp_ci("ABNER FLORES MAMANI")

        real_teacher = Teacher(ci="1234567", full_name="ABNER FLORES MAMANI")
        temp_teacher = Teacher(ci=temp_ci, full_name="ABNER FLORES MAMANI")
        db.add_all([real_teacher, temp_teacher])
        db.flush()

        real_designation = Designation(
            teacher_ci=real_teacher.ci,
            subject="ANATOMIA",
            semester="1",
            group_code="M-1",
            schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "10:00"}],
        )
        temp_designation = Designation(
            teacher_ci=temp_teacher.ci,
            subject="ANATOMIA",
            semester="1",
            group_code="M-1",
            schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "10:00"}],
        )
        db.add_all([real_designation, temp_designation])
        db.flush()

        upload = BiometricUpload(filename="bio.xls", month=3, year=2026, total_records=1, total_teachers=1)
        db.add(upload)
        db.flush()

        biometric = BiometricRecord(
            upload_id=upload.id,
            teacher_ci=temp_teacher.ci,
            teacher_name=temp_teacher.full_name,
            date=date(2026, 3, 2),
            entry_time=time(8, 0),
            exit_time=time(10, 0),
        )
        db.add(biometric)
        db.flush()

        attendance = AttendanceRecord(
            teacher_ci=temp_teacher.ci,
            designation_id=temp_designation.id,
            date=date(2026, 3, 2),
            scheduled_start=time(8, 0),
            scheduled_end=time(10, 0),
            actual_entry=time(8, 0),
            actual_exit=time(10, 0),
            status="ATTENDED",
            academic_hours=2,
            late_minutes=0,
            observation=None,
            biometric_record_id=biometric.id,
            month=3,
            year=2026,
        )
        db.add(attendance)
        db.commit()

        updated = loader.link_teachers_by_name(db, {real_teacher.ci: real_teacher.full_name})

        assert updated == 1
        assert db.query(Teacher).filter(Teacher.ci == temp_teacher.ci).first() is None
        assert db.query(Designation).filter(Designation.id == temp_designation.id).first() is None

        merged_attendance = db.query(AttendanceRecord).one()
        assert merged_attendance.teacher_ci == real_teacher.ci
        assert merged_attendance.designation_id == real_designation.id

        merged_biometric = db.query(BiometricRecord).one()
        assert merged_biometric.teacher_ci == real_teacher.ci

    def test_merge_collision_keeps_real_attendance_and_deletes_temp_duplicate(self, loader, db):
        temp_ci = _make_temp_ci("ABNER FLORES MAMANI")

        real_teacher = Teacher(ci="1234567", full_name="ABNER FLORES MAMANI")
        temp_teacher = Teacher(ci=temp_ci, full_name="ABNER FLORES MAMANI")
        db.add_all([real_teacher, temp_teacher])
        db.flush()

        real_designation = Designation(
            teacher_ci=real_teacher.ci,
            subject="ANATOMIA",
            semester="1",
            group_code="M-1",
            schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "10:00"}],
        )
        temp_designation = Designation(
            teacher_ci=temp_teacher.ci,
            subject="ANATOMIA",
            semester="1",
            group_code="M-1",
            schedule_json=[{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "10:00"}],
        )
        db.add_all([real_designation, temp_designation])
        db.flush()

        real_attendance = AttendanceRecord(
            teacher_ci=real_teacher.ci,
            designation_id=real_designation.id,
            date=date(2026, 3, 2),
            scheduled_start=time(8, 0),
            scheduled_end=time(10, 0),
            actual_entry=time(8, 0),
            actual_exit=time(10, 0),
            status="ATTENDED",
            academic_hours=2,
            late_minutes=0,
            observation="real",
            biometric_record_id=None,
            month=3,
            year=2026,
        )
        temp_attendance = AttendanceRecord(
            teacher_ci=temp_teacher.ci,
            designation_id=temp_designation.id,
            date=date(2026, 3, 2),
            scheduled_start=time(8, 0),
            scheduled_end=time(10, 0),
            actual_entry=time(8, 5),
            actual_exit=time(10, 0),
            status="LATE",
            academic_hours=2,
            late_minutes=5,
            observation="temp",
            biometric_record_id=None,
            month=3,
            year=2026,
        )
        db.add_all([real_attendance, temp_attendance])
        db.commit()

        updated = loader.link_teachers_by_name(db, {real_teacher.ci: real_teacher.full_name})

        assert updated == 1
        records = db.query(AttendanceRecord).all()
        assert len(records) == 1
        assert records[0].teacher_ci == real_teacher.ci
        assert records[0].designation_id == real_designation.id
        assert records[0].observation == "real"

    def test_reimport_after_relink_reuses_real_teacher_by_name(self, loader, db, tmp_path):
        docente_name = "ABNER FLORES MAMANI"
        temp_ci = _make_temp_ci(docente_name)

        initial_payload = {
            "designaciones": [
                {
                    "docente": docente_name,
                    "materia": "ANATOMIA",
                    "semestre": "1",
                    "grupo": "M-1",
                    "horario": [{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "10:00"}],
                }
            ]
        }
        json_path = tmp_path / "designaciones.json"
        json_path.write_text(json.dumps(initial_payload), encoding="utf-8")

        loader.load_from_json(db, str(json_path))
        assert db.query(Teacher).filter(Teacher.ci == temp_ci).first() is not None

        loader.link_teachers_by_name(db, {"7654321": docente_name})
        assert db.query(Teacher).filter(Teacher.ci == temp_ci).first() is None
        assert db.query(Teacher).filter(Teacher.ci == "7654321").first() is not None

        reimport_result = loader.load_from_json(db, str(json_path))

        assert reimport_result.teachers_created == 0
        assert db.query(Teacher).count() == 1
        assert db.query(Teacher).filter(Teacher.ci == "7654321").count() == 1
        assert db.query(Designation).filter(Designation.teacher_ci == "7654321").count() == 1

    def test_load_from_json_warns_when_exact_name_matches_existing_real_ci(self, loader, db, tmp_path):
        real_teacher = Teacher(ci="5555555", full_name="MARIA PEREZ")
        db.add(real_teacher)
        db.commit()

        payload = {
            "designaciones": [
                {
                    "docente": "MARIA PEREZ",
                    "materia": "ANATOMIA",
                    "semestre": "1",
                    "grupo": "M-1",
                    "horario": [{"dia": "lunes", "hora_inicio": "08:00", "hora_fin": "10:00"}],
                }
            ]
        }
        json_path = tmp_path / "designaciones_homonimo.json"
        json_path.write_text(json.dumps(payload), encoding="utf-8")

        result = loader.load_from_json(db, str(json_path))

        assert result.teachers_created == 0
        assert result.teachers_reused == 1
        assert len(result.warnings) == 1
        assert "Posible homónimo" in result.warnings[0]
        assert db.query(Designation).filter(Designation.teacher_ci == real_teacher.ci).count() == 1


# ---------------------------------------------------------------------------
# Integration tests — get_teacher_designations
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not REAL_JSON.exists(),
    reason=f"Real JSON not found at {REAL_JSON}",
)
class TestGetTeacherDesignations:
    def test_returns_list(self, loader, db):
        loader.load_from_json(db, str(REAL_JSON))
        temp_ci = _make_temp_ci("ABNER FLORES MAMANI")
        result = loader.get_teacher_designations(db, temp_ci)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_unknown_ci_returns_empty(self, loader, db):
        loader.load_from_json(db, str(REAL_JSON))
        result = loader.get_teacher_designations(db, "CI-INEXISTENTE")
        assert result == []
