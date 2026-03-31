"""
Tests for AttendanceEngine service (T-006).

Two test layers:
  1. Unit tests  — pure Python, no DB. Uses lightweight mock objects to test
     match_teacher_day() and _find_covering_record() in isolation.
  2. Integration tests — in-memory SQLite DB tests for save_results()
     and get_month_summary().

All 9 edge cases from the spec are covered.
"""
from __future__ import annotations

from datetime import date, time
from typing import Optional
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base
from app.models.attendance import AttendanceRecord
from app.models.designation import Designation
from app.models.teacher import Teacher  # noqa: F401 — needed for FK registration
import app.models  # noqa: F401 — register all models for create_all

from app.services.attendance_engine import AttendanceEngine, SlotResult, TOLERANCE_MINUTES


# ---------------------------------------------------------------------------
# Lightweight mock helpers (no DB required for unit tests)
# ---------------------------------------------------------------------------


def make_bio_record(
    entry: Optional[str],
    exit_: Optional[str],
    rec_id: int = 1,
    teacher_ci: str = "12345",
    rec_date: date = date(2026, 3, 3),  # Monday
) -> MagicMock:
    """
    Build a lightweight BiometricRecord-like mock.
    entry / exit_ are "HH:MM" strings or None.
    """
    rec = MagicMock()
    rec.id = rec_id
    rec.teacher_ci = teacher_ci
    rec.date = rec_date
    rec.entry_time = _t(entry)
    rec.exit_time = _t(exit_)
    return rec


def make_designation(
    desig_id: int,
    teacher_ci: str,
    subject: str,
    group_code: str,
    schedule: list[dict],
) -> MagicMock:
    """Build a lightweight Designation-like mock with schedule_json."""
    d = MagicMock()
    d.id = desig_id
    d.teacher_ci = teacher_ci
    d.subject = subject
    d.group_code = group_code
    d.schedule_json = schedule
    return d


def _t(s: Optional[str]) -> Optional[time]:
    """Parse 'HH:MM' to time, or return None."""
    if s is None:
        return None
    h, m = s.split(":")
    return time(int(h), int(m))


def _slot(dia: str, start: str, end: str, horas: int = 2) -> dict:
    """Build a schedule slot dict matching the JSON structure."""
    return {
        "dia": dia,
        "hora_inicio": start,
        "hora_fin": end,
        "duracion_minutos": 90,
        "horas_academicas": horas,
    }


# Monday 2026-03-02
MONDAY = date(2026, 3, 2)
# Tuesday 2026-03-03
TUESDAY = date(2026, 3, 3)
# Saturday 2026-03-07
SATURDAY = date(2026, 3, 7)

TEACHER_CI = "12345678"

engine_svc = AttendanceEngine()


# ===========================================================================
# Unit tests — _find_covering_record
# ===========================================================================


class TestFindCoveringRecord:
    """Tests for the low-level coverage checker."""

    def test_on_time_returns_attended(self):
        """Entry exactly at slot start → ATTENDED."""
        rec = make_bio_record("08:00", "10:00")
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is not None
        _, status, late_min, obs = result
        assert status == "ATTENDED"
        assert late_min == 0
        assert obs is None

    def test_early_arrival_returns_attended(self):
        """Entry well before slot start → ATTENDED (no penalty for early)."""
        rec = make_bio_record("07:00", "10:00")
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is not None
        _, status, late_min, _ = result
        assert status == "ATTENDED"
        assert late_min == 0

    def test_within_tolerance_returns_attended(self):
        """Entry exactly at tolerance limit (start + 5 min) → ATTENDED."""
        rec = make_bio_record("08:05", "10:00")
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is not None
        _, status, late_min, _ = result
        assert status == "ATTENDED"
        assert late_min == 0

    def test_just_over_tolerance_returns_late(self):
        """Entry at start + 6 min → LATE (not absent — still gets paid)."""
        rec = make_bio_record("08:06", "10:00")
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is not None
        _, status, late_min, obs = result
        assert status == "LATE"
        assert late_min == 6
        assert obs is not None
        assert "6 min" in obs

    def test_very_late_returns_late_not_absent(self):
        """Entry 30 min late → LATE (not absent). Business rule: still gets paid."""
        rec = make_bio_record("08:30", "10:00")
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is not None
        _, status, late_min, _ = result
        assert status == "LATE"
        assert late_min == 30

    def test_no_exit_returns_no_exit(self):
        """Entry exists but no exit → NO_EXIT (still paid)."""
        rec = make_bio_record("08:00", None)
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is not None
        _, status, late_min, obs = result
        assert status == "NO_EXIT"
        assert late_min == 0
        assert obs is not None
        assert "Sin registro de salida" in obs

    def test_no_exit_late_returns_no_exit_with_late_minutes(self):
        """Late entry + no exit → NO_EXIT with late_minutes recorded."""
        rec = make_bio_record("08:20", None)
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is not None
        _, status, late_min, obs = result
        assert status == "NO_EXIT"
        assert late_min == 20
        assert "20 min" in obs

    def test_absent_when_no_records(self):
        """Empty bio list → None (ABSENT)."""
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [])
        assert result is None

    def test_entry_after_class_ended_is_not_covering(self):
        """Entry at 10:01 for a slot that ends at 10:00 → None (ABSENT)."""
        rec = make_bio_record("10:01", "12:00")
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is None

    def test_exit_before_class_started_is_not_covering(self):
        """Exit at 07:59 for a slot starting at 08:00 → None (pair is for earlier block)."""
        rec = make_bio_record("06:00", "07:59")
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is None

    def test_no_entry_record_is_skipped(self):
        """Record with entry_time=None → data error, skip and return None."""
        rec = make_bio_record(None, "10:00")
        result = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), [rec])
        assert result is None

    def test_single_mark_covers_two_consecutive_slots(self):
        """
        Teacher enters 07:55, exits 12:05.
        Slot A: 08:00–10:00  →  ATTENDED
        Slot B: 10:10–12:00  →  ATTENDED

        _find_covering_record is called once per slot, always against the same list.
        Both calls should return the same record as covering.
        """
        rec = make_bio_record("07:55", "12:05")
        bio = [rec]

        res_a = engine_svc._find_covering_record(_t("08:00"), _t("10:00"), bio)
        res_b = engine_svc._find_covering_record(_t("10:10"), _t("12:00"), bio)

        assert res_a is not None
        assert res_b is not None
        _, status_a, _, _ = res_a
        _, status_b, _, _ = res_b
        assert status_a == "ATTENDED"
        assert status_b == "ATTENDED"

    def test_best_covering_record_prefers_closest_with_exit(self):
        """When multiple records cover a slot, the closest matching entry with exit wins."""
        broad_no_exit = make_bio_record("08:00", None, rec_id=1)
        closer_with_exit = make_bio_record("12:05", "14:00", rec_id=2)

        result = engine_svc._find_covering_record(
            _t("12:10"),
            _t("14:00"),
            [broad_no_exit, closer_with_exit],
        )

        assert result is not None
        rec, status, late_min, _ = result
        assert rec.id == 2
        assert status == "ATTENDED"
        assert late_min == 0


# ===========================================================================
# Unit tests — match_teacher_day
# ===========================================================================


class TestMatchTeacherDay:
    """Tests for the per-day matching orchestrator."""

    def _monday_desig(self, subject: str = "ANATOMIA", horas: int = 2) -> MagicMock:
        return make_designation(
            desig_id=1,
            teacher_ci=TEACHER_CI,
            subject=subject,
            group_code="M-1",
            schedule=[_slot("lunes", "08:00", "10:00", horas)],
        )

    def _saturday_desig(self, subject: str = "FISIOLOGIA", horas: int = 3) -> MagicMock:
        return make_designation(
            desig_id=2,
            teacher_ci=TEACHER_CI,
            subject=subject,
            group_code="M-2",
            schedule=[_slot("sabado", "08:00", "11:00", horas)],
        )

    # ── Case 1: Normal on-time attendance ───────────────────────────────

    def test_normal_attendance_on_time(self):
        """Teacher arrives on time → ATTENDED, academic_hours set from slot."""
        bio = [make_bio_record("07:55", "10:05")]
        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [self._monday_desig()], bio
        )
        assert len(results) == 1
        r = results[0]
        assert r.status == "ATTENDED"
        assert r.academic_hours == 2
        assert r.late_minutes == 0
        assert r.observation is None

    # ── Case 2: Late attendance (still paid) ────────────────────────────

    def test_late_attendance_gets_hours(self):
        """Teacher arrives 15 min late → LATE status but academic_hours still awarded."""
        bio = [make_bio_record("08:15", "10:05")]
        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [self._monday_desig(horas=2)], bio
        )
        assert len(results) == 1
        r = results[0]
        assert r.status == "LATE"
        assert r.academic_hours == 2          # STILL GETS PAID
        assert r.late_minutes == 15
        assert r.observation is not None

    # ── Case 3: Absent (no biometric data) ──────────────────────────────

    def test_absent_no_biometric_data(self):
        """No biometric records → ABSENT, academic_hours = 0."""
        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [self._monday_desig()], []
        )
        assert len(results) == 1
        r = results[0]
        assert r.status == "ABSENT"
        assert r.academic_hours == 0
        assert r.biometric_record_id is None

    # ── Case 4: No exit recorded ─────────────────────────────────────────

    def test_no_exit_still_gets_hours(self):
        """Entry found, no exit → NO_EXIT status, hours still awarded."""
        bio = [make_bio_record("07:55", None)]
        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [self._monday_desig(horas=2)], bio
        )
        assert len(results) == 1
        r = results[0]
        assert r.status == "NO_EXIT"
        assert r.academic_hours == 2           # STILL GETS PAID
        assert r.observation is not None
        assert "Sin registro de salida" in r.observation

    # ── Case 5: Single mark covering two consecutive classes ─────────────

    def test_single_mark_covers_two_slots(self):
        """
        Teacher enters 07:55, exits 12:05.
        Two consecutive classes: 08:00–10:00 and 10:10–12:00.
        Both must be ATTENDED.
        """
        desig_a = make_designation(
            desig_id=10,
            teacher_ci=TEACHER_CI,
            subject="ANATOMIA",
            group_code="M-1",
            schedule=[_slot("lunes", "08:00", "10:00", 2)],
        )
        desig_b = make_designation(
            desig_id=11,
            teacher_ci=TEACHER_CI,
            subject="BIOQUIMICA",
            group_code="M-2",
            schedule=[_slot("lunes", "10:10", "12:00", 2)],
        )
        bio = [make_bio_record("07:55", "12:05")]

        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [desig_a, desig_b], bio
        )
        assert len(results) == 2
        statuses = {r.scheduled_start.strftime("%H:%M"): r.status for r in results}
        assert statuses["08:00"] == "ATTENDED"
        assert statuses["10:10"] == "ATTENDED"

    # ── Case 6: Multiple marks per day ────────────────────────────────────

    def test_multiple_marks_per_day(self):
        """
        Teacher has two pairs: (07:55–10:05) and (10:08–12:05).
        Two consecutive slots: 08:00–10:00 and 10:10–12:00.
        First pair covers slot A; second pair covers slot B.
        Both ATTENDED.
        """
        desig_a = make_designation(
            desig_id=20,
            teacher_ci=TEACHER_CI,
            subject="ANATOMIA",
            group_code="M-1",
            schedule=[_slot("lunes", "08:00", "10:00", 2)],
        )
        desig_b = make_designation(
            desig_id=21,
            teacher_ci=TEACHER_CI,
            subject="BIOQUIMICA",
            group_code="M-2",
            schedule=[_slot("lunes", "10:10", "12:00", 2)],
        )
        bio = [
            make_bio_record("07:55", "10:05", rec_id=1),
            make_bio_record("10:08", "12:05", rec_id=2),
        ]

        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [desig_a, desig_b], bio
        )
        assert len(results) == 2
        for r in results:
            assert r.status == "ATTENDED"

    # ── Case 7: Early arrival (way before class) ──────────────────────────

    def test_early_arrival_no_penalty(self):
        """Entry 2 hours before slot start → ATTENDED, no late penalty."""
        bio = [make_bio_record("06:00", "10:30")]
        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [self._monday_desig()], bio
        )
        assert len(results) == 1
        assert results[0].status == "ATTENDED"
        assert results[0].late_minutes == 0

    # ── Case 8: Entry after class ended (must NOT cover) ─────────────────

    def test_entry_after_class_ended_is_absent(self):
        """
        Slot: 08:00–10:00.  Entry: 10:01 — teacher arrived after class ended.
        Must be ABSENT (not LATE — they physically missed the class).
        """
        bio = [make_bio_record("10:01", "12:00")]
        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [self._monday_desig()], bio
        )
        assert len(results) == 1
        assert results[0].status == "ABSENT"
        assert results[0].academic_hours == 0

    # ── Case 9: Weekend class (sabado) ────────────────────────────────────

    def test_saturday_class_processed_identically(self):
        """
        Saturday classes follow the exact same logic as weekday classes.
        Entry at 08:10 for 08:00 slot = 10 min late > TOLERANCE (5) → LATE.
        academic_hours still awarded (same as weekday LATE rule).
        """
        bio = [make_bio_record("08:10", "11:05", rec_date=SATURDAY)]
        results = engine_svc.match_teacher_day(
            TEACHER_CI, SATURDAY, [self._saturday_desig(horas=3)], bio
        )
        assert len(results) == 1
        r = results[0]
        # 10 min > TOLERANCE_MINUTES → LATE, same rule as any weekday
        assert r.status == "LATE"
        assert r.late_minutes == 10
        assert r.academic_hours == 3   # still gets paid

    def test_saturday_class_on_time(self):
        """Saturday on-time attendance → ATTENDED."""
        bio = [make_bio_record("07:55", "11:05", rec_date=SATURDAY)]
        results = engine_svc.match_teacher_day(
            TEACHER_CI, SATURDAY, [self._saturday_desig(horas=3)], bio
        )
        assert len(results) == 1
        r = results[0]
        assert r.status == "ATTENDED"
        assert r.academic_hours == 3

    # ── No scheduled class for that day ──────────────────────────────────

    def test_no_classes_today_returns_empty(self):
        """Teacher has no classes scheduled on the given day → empty list."""
        # Designation is for lunes, but we pass a martes date
        desig = self._monday_desig()  # only 'lunes' in schedule
        tuesday = date(2026, 3, 3)  # Tuesday
        results = engine_svc.match_teacher_day(
            TEACHER_CI, tuesday, [desig], []
        )
        assert results == []

    # ── Only-exit record (data error) ─────────────────────────────────────

    def test_only_exit_no_entry_is_absent(self):
        """
        Record has exit but no entry → data anomaly.
        _find_covering_record skips such records → slot = ABSENT.
        """
        bio = [make_bio_record(None, "10:00")]
        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [self._monday_desig()], bio
        )
        assert len(results) == 1
        assert results[0].status == "ABSENT"

    # ── Absent for all days in month ──────────────────────────────────────

    def test_teacher_with_no_biometric_data_at_all(self):
        """Teacher has designations but zero biometric records → all ABSENT."""
        # Two slots on Monday
        desig_a = make_designation(
            desig_id=30,
            teacher_ci=TEACHER_CI,
            subject="ANATOMIA",
            group_code="M-1",
            schedule=[_slot("lunes", "08:00", "10:00", 2)],
        )
        desig_b = make_designation(
            desig_id=31,
            teacher_ci=TEACHER_CI,
            subject="BIOQUIMICA",
            group_code="M-2",
            schedule=[_slot("lunes", "10:10", "12:00", 2)],
        )
        results = engine_svc.match_teacher_day(
            TEACHER_CI, MONDAY, [desig_a, desig_b], []
        )
        assert len(results) == 2
        assert all(r.status == "ABSENT" for r in results)
        assert all(r.academic_hours == 0 for r in results)


# ===========================================================================
# Parametrized coverage rule tests
# ===========================================================================


@pytest.mark.parametrize(
    "entry_str, exit_str, slot_start, slot_end, expected_status, expected_late",
    [
        # On time
        ("08:00", "10:00", "08:00", "10:00", "ATTENDED", 0),
        # Early
        ("07:00", "10:00", "08:00", "10:00", "ATTENDED", 0),
        # Within tolerance (exactly 5 min late)
        ("08:05", "10:00", "08:00", "10:00", "ATTENDED", 0),
        # Just over tolerance (6 min late)
        ("08:06", "10:00", "08:00", "10:00", "LATE", 6),
        # Very late but before class ends
        ("09:30", "10:00", "08:00", "10:00", "LATE", 90),
        # No exit
        ("08:00", None,    "08:00", "10:00", "NO_EXIT", 0),
        # Late + no exit
        ("08:20", None,    "08:00", "10:00", "NO_EXIT", 20),
        # Entry after class ends → ABSENT (no result)
        ("10:01", "12:00", "08:00", "10:00", None, None),
        # Exit before class starts → ABSENT
        ("06:00", "07:59", "08:00", "10:00", None, None),
    ],
    ids=[
        "on_time",
        "early",
        "within_tolerance_5min",
        "just_over_tolerance_6min",
        "very_late_90min",
        "no_exit_on_time",
        "no_exit_late_20min",
        "entry_after_class_ends",
        "exit_before_class_starts",
    ],
)
def test_coverage_parametrized(
    entry_str, exit_str, slot_start, slot_end, expected_status, expected_late
):
    rec = make_bio_record(entry_str, exit_str)
    result = engine_svc._find_covering_record(_t(slot_start), _t(slot_end), [rec])

    if expected_status is None:
        assert result is None, f"Expected None (ABSENT) but got {result}"
    else:
        assert result is not None, "Expected a covering record but got None"
        _, status, late_min, _ = result
        assert status == expected_status
        assert late_min == expected_late


# ===========================================================================
# Integration tests — save_results & get_month_summary (SQLite in-memory)
# ===========================================================================


@pytest.fixture(scope="module")
def sqlite_engine():
    """In-memory SQLite engine — no PostgreSQL needed."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # Patch PostgreSQL-specific JSON type to generic JSON for SQLite
    from sqlalchemy.dialects.postgresql import JSON as PG_JSON
    from sqlalchemy import JSON as SA_JSON

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


class TestSaveAndSummary:
    """Integration tests for persistence and summary helpers."""

    def _make_slot_result(
        self,
        status: str,
        hours: int,
        late_min: int = 0,
        slot_start: str = "08:00",
    ) -> SlotResult:
        return SlotResult(
            designation_id=1,
            teacher_ci="99999999",
            date=MONDAY,
            scheduled_start=_t(slot_start),
            scheduled_end=_t("10:00"),
            actual_entry=_t("08:00"),
            actual_exit=_t("10:00"),
            status=status,
            academic_hours=hours,
            late_minutes=late_min,
            observation=None,
            biometric_record_id=None,
            subject="ANATOMIA",
            group_code="M-1",
        )

    def _seed_teacher_and_designation(self, db: Session) -> None:
        """Insert the minimal Teacher + Designation rows required by FK constraints."""
        from app.models.teacher import Teacher as TeacherModel
        from app.models.designation import Designation as DesigModel
        from sqlalchemy.dialects.postgresql import JSON as PG_JSON
        from sqlalchemy import JSON as SA_JSON

        teacher = TeacherModel(ci="99999999", full_name="Docente Test")
        db.add(teacher)
        db.flush()

        desig = DesigModel(
            id=1,
            teacher_ci="99999999",
            subject="ANATOMIA",
            semester="PRIMERO",
            group_code="M-1",
            schedule_json=[_slot("lunes", "08:00", "10:00", 2)],
        )
        db.add(desig)
        db.flush()

    def _seed_teacher_and_designation_with_ids(
        self,
        db: Session,
        teacher_ci: str,
        designation_id: int,
    ) -> None:
        teacher = Teacher(ci=teacher_ci, full_name=f"Docente {teacher_ci}")
        db.add(teacher)
        db.flush()

        desig = Designation(
            id=designation_id,
            teacher_ci=teacher_ci,
            subject=f"MATERIA-{designation_id}",
            semester="PRIMERO",
            group_code=f"G-{designation_id}",
            schedule_json=[_slot("lunes", "08:00", "10:00", 2)],
        )
        db.add(desig)
        db.flush()

    def test_save_results_inserts_records(self, db: Session):
        """save_results() must persist SlotResult rows into attendance_records."""
        self._seed_teacher_and_designation(db)

        results = [
            self._make_slot_result("ATTENDED", 2),
            self._make_slot_result("ABSENT", 0, slot_start="10:10"),
        ]
        # Note: second slot needs different scheduled_start to avoid UniqueConstraint
        results[1].scheduled_start = _t("10:10")

        svc = AttendanceEngine()
        saved = svc.save_results(db, results, upload_id=1, month=3, year=2026)
        assert saved == 2

    def test_save_results_reprocessing_updates_existing_record(self, db: Session):
        """Running save_results() twice must update the existing natural-key row."""
        self._seed_teacher_and_designation(db)

        initial_results = [self._make_slot_result("ABSENT", 0)]
        reprocessed_results = [self._make_slot_result("ATTENDED", 2)]

        svc = AttendanceEngine()
        saved_first = svc.save_results(db, initial_results, upload_id=1, month=3, year=2026)
        saved_second = svc.save_results(db, reprocessed_results, upload_id=1, month=3, year=2026)

        record = db.query(AttendanceRecord).filter_by(teacher_ci="99999999").one()

        assert saved_first == 1
        assert saved_second == 1
        assert record.status == "ATTENDED"
        assert record.academic_hours == 2

    def test_save_results_reprocessing_deletes_stale_rows(self, db: Session):
        """Reprocessing the same scope must delete rows missing from the new result set."""
        self._seed_teacher_and_designation(db)

        svc = AttendanceEngine()
        initial_results = [
            self._make_slot_result("ATTENDED", 2, slot_start="08:00"),
            self._make_slot_result("ABSENT", 0, slot_start="10:10"),
        ]
        reprocessed_results = [
            self._make_slot_result("ATTENDED", 2, slot_start="08:00"),
        ]

        svc.save_results(db, initial_results, upload_id=1, month=3, year=2026)
        saved = svc.save_results(db, reprocessed_results, upload_id=1, month=3, year=2026)

        records = db.query(AttendanceRecord).order_by(AttendanceRecord.scheduled_start).all()

        assert saved == 1
        assert len(records) == 1
        assert records[0].scheduled_start == _t("08:00")
        assert records[0].status == "ATTENDED"

    def test_save_results_empty_batch_keeps_existing_rows(self, db: Session):
        self._seed_teacher_and_designation(db)

        svc = AttendanceEngine()
        svc.save_results(db, [self._make_slot_result("ATTENDED", 2)], upload_id=1, month=3, year=2026)

        saved = svc.save_results(db, [], upload_id=1, month=3, year=2026)

        assert saved == 0
        assert db.query(AttendanceRecord).count() == 1

    def test_save_results_deletes_stale_rows_only_for_processed_teachers(self, db: Session):
        self._seed_teacher_and_designation_with_ids(db, teacher_ci="99999999", designation_id=1)
        self._seed_teacher_and_designation_with_ids(db, teacher_ci="88888888", designation_id=2)

        svc = AttendanceEngine()
        initial_results = [
            self._make_slot_result("ATTENDED", 2, slot_start="08:00"),
            self._make_slot_result("ABSENT", 0, slot_start="10:10"),
            SlotResult(
                designation_id=2,
                teacher_ci="88888888",
                date=MONDAY,
                scheduled_start=_t("08:00"),
                scheduled_end=_t("10:00"),
                actual_entry=_t("08:00"),
                actual_exit=_t("10:00"),
                status="ATTENDED",
                academic_hours=2,
                late_minutes=0,
                observation=None,
                biometric_record_id=None,
                subject="ANATOMIA",
                group_code="M-1",
            ),
        ]
        svc.save_results(db, initial_results, upload_id=1, month=3, year=2026)

        saved = svc.save_results(db, [], upload_id=1, month=3, year=2026)

        assert saved == 0
        assert db.query(AttendanceRecord).count() == 3

        reprocessed_results = [
            self._make_slot_result("ATTENDED", 2, slot_start="08:00"),
        ]
        saved = svc.save_results(db, reprocessed_results, upload_id=1, month=3, year=2026)

        records = {
            (record.teacher_ci, record.scheduled_start): record
            for record in db.query(AttendanceRecord).order_by(AttendanceRecord.teacher_ci, AttendanceRecord.scheduled_start).all()
        }

        assert saved == 1
        assert set(records) == {
            ("99999999", _t("08:00")),
            ("88888888", _t("08:00")),
        }
        assert records[("99999999", _t("08:00"))].status == "ATTENDED"
        assert records[("88888888", _t("08:00"))].status == "ATTENDED"

    def test_get_month_summary_counts(self, db: Session):
        """get_month_summary() must return correct counts per status."""
        self._seed_teacher_and_designation(db)

        results = [
            self._make_slot_result("ATTENDED", 2, slot_start="08:00"),
            self._make_slot_result("LATE", 2, late_min=10, slot_start="10:10"),
            self._make_slot_result("ABSENT", 0, slot_start="11:00"),
            self._make_slot_result("NO_EXIT", 2, slot_start="12:00"),
        ]
        # Fix unique scheduled_start for each
        for i, r in enumerate(results):
            r.scheduled_start = _t(f"{8 + i}:00")

        svc = AttendanceEngine()
        svc.save_results(db, results, upload_id=1, month=3, year=2026)

        summary = svc.get_month_summary(db, month=3, year=2026)

        assert summary["total_slots"] == 4
        assert summary["by_status"]["ATTENDED"] == 1
        assert summary["by_status"]["LATE"] == 1
        assert summary["by_status"]["ABSENT"] == 1
        assert summary["by_status"]["NO_EXIT"] == 1
        assert summary["total_academic_hours"] == 6  # 2+2+0+2
        assert summary["attendance_rate"] == 75.0    # 3 present out of 4

    def test_get_month_summary_empty(self, db: Session):
        """get_month_summary() on a month with no records returns 0-filled dict."""
        svc = AttendanceEngine()
        summary = svc.get_month_summary(db, month=1, year=2099)
        assert summary["total_slots"] == 0
        assert summary["attendance_rate"] == 0.0
