"""
Tests for BiometricParser service.

Two test layers:
  1. Unit tests  — pure Python, no file I/O (test helpers and data structures)
  2. Integration tests — parse the REAL .xls biometric file

Integration tests use the real file so they also serve as acceptance tests for T-004.
"""
from __future__ import annotations

import os
from datetime import date, time
from pathlib import Path

import pytest

from app.services.biometric_parser import (
    BiometricEntry,
    BiometricParseResult,
    BiometricParser,
    _parse_date,
    _parse_worked_minutes,
    _cell_str,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_REPO_ROOT = _HERE.parent.parent  # backend/tests -> backend -> repo root
REAL_XLS = _REPO_ROOT / "reporte biometrico marzo_docentes.xls"


# ---------------------------------------------------------------------------
# Unit tests — pure helpers, no file I/O
# ---------------------------------------------------------------------------


class TestParseDateHelper:
    def test_valid_date(self):
        assert _parse_date("02/03/2026") == date(2026, 3, 2)

    def test_valid_date_end_of_month(self):
        assert _parse_date("20/03/2026") == date(2026, 3, 20)

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_extra_whitespace(self):
        assert _parse_date("  05/03/2026  ") == date(2026, 3, 5)

    def test_invalid_format_returns_none(self):
        assert _parse_date("2026-03-02") is None  # ISO format not supported

    def test_nonsense_returns_none(self):
        assert _parse_date("not-a-date") is None


class TestParseWorkedMinutesHelper:
    def test_typical_time(self):
        assert _parse_worked_minutes("03:57") == 3 * 60 + 57

    def test_two_hours_56_min(self):
        assert _parse_worked_minutes("02:56") == 2 * 60 + 56

    def test_zero(self):
        assert _parse_worked_minutes("0:00") == 0

    def test_exceeds_24h_total_row(self):
        # Totals row can show e.g. '35:57'
        assert _parse_worked_minutes("35:57") == 35 * 60 + 57

    def test_empty_returns_none(self):
        assert _parse_worked_minutes("") is None

    def test_none_returns_none(self):
        assert _parse_worked_minutes(None) is None

    def test_malformed_returns_none(self):
        assert _parse_worked_minutes("not-time") is None


class TestBiometricEntryDataclass:
    def test_creation(self):
        entry = BiometricEntry(
            teacher_name="JUAN PEREZ",
            ci="12345678",
            date=date(2026, 3, 5),
            entry_time=time(8, 10),
            exit_time=time(12, 7),
            worked_minutes=237,
            shift="ADMINISTRATIVOS(08:00-19:00)",
        )
        assert entry.ci == "12345678"
        assert entry.worked_minutes == 237

    def test_entry_only_record(self):
        """Entry without exit is valid (employee clocked in but not out)."""
        entry = BiometricEntry(
            teacher_name="MARIA GOMEZ",
            ci="87654321",
            date=date(2026, 3, 12),
            entry_time=time(15, 4),
            exit_time=None,
            worked_minutes=None,
            shift=None,
        )
        assert entry.exit_time is None
        assert entry.worked_minutes is None


# ---------------------------------------------------------------------------
# Integration tests — real XLS file
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not REAL_XLS.exists(),
    reason=f"Real biometric XLS not found at {REAL_XLS}",
)
class TestBiometricParserRealFile:
    """Acceptance tests against the real biometric report for March 2026."""

    @pytest.fixture(scope="class")
    def parse_result(self) -> BiometricParseResult:
        parser = BiometricParser()
        return parser.parse_file(str(REAL_XLS))

    # ── Stats ──────────────────────────────────────────────────────────────

    def test_teacher_count(self, parse_result):
        """Must find 72 teachers WITH attendance (19 of 91 had zero records in the period)."""
        assert parse_result.stats["total_teachers"] == 72, (
            f"Expected 72 teachers with attendance, got {parse_result.stats['total_teachers']}"
        )

    def test_total_records(self, parse_result):
        """Must find 1084 attendance records (entry-only + full pairs)."""
        assert parse_result.stats["total_records"] == 1084, (
            f"Expected 1084 records, got {parse_result.stats['total_records']}"
        )

    def test_no_warnings(self, parse_result):
        """Clean parse should produce zero warnings."""
        assert parse_result.warnings == [], (
            f"Unexpected warnings: {parse_result.warnings}"
        )

    # ── Metadata ───────────────────────────────────────────────────────────

    def test_metadata_department(self, parse_result):
        assert parse_result.metadata["department"] == "DOCENTES MEDICINA"

    def test_metadata_date_from(self, parse_result):
        assert parse_result.metadata["date_from"] == date(2026, 3, 2)

    def test_metadata_date_to(self, parse_result):
        assert parse_result.metadata["date_to"] == date(2026, 3, 20)

    # ── Records structure ──────────────────────────────────────────────────

    def test_records_keyed_by_ci(self, parse_result):
        """All record keys must be non-empty strings."""
        for ci in parse_result.records:
            assert isinstance(ci, str)
            assert ci.strip() != ""

    def test_each_ci_has_at_least_one_record(self, parse_result):
        for ci, entries in parse_result.records.items():
            assert len(entries) > 0, f"CI {ci!r} has no entries"

    def test_all_entries_are_biometric_entry(self, parse_result):
        for ci, entries in parse_result.records.items():
            for entry in entries:
                assert isinstance(entry, BiometricEntry)

    def test_all_entries_have_valid_date(self, parse_result):
        for ci, entries in parse_result.records.items():
            for entry in entries:
                assert isinstance(entry.date, date), (
                    f"CI {ci!r}: entry date is not a date object: {entry.date!r}"
                )

    def test_dates_within_report_range(self, parse_result):
        date_from = parse_result.metadata["date_from"]
        date_to = parse_result.metadata["date_to"]
        for ci, entries in parse_result.records.items():
            for entry in entries:
                assert date_from <= entry.date <= date_to, (
                    f"CI {ci!r}: date {entry.date} out of report range "
                    f"{date_from}..{date_to}"
                )

    def test_no_empty_both_entry_and_exit(self, parse_result):
        """Records where BOTH entry and exit are None must NOT exist."""
        for ci, entries in parse_result.records.items():
            for entry in entries:
                assert not (entry.entry_time is None and entry.exit_time is None), (
                    f"CI {ci!r} on {entry.date}: both entry and exit are None"
                )

    def test_entry_only_records_included(self, parse_result):
        """Records with entry but no exit must be included (144 expected)."""
        entry_only = [
            entry
            for entries in parse_result.records.values()
            for entry in entries
            if entry.entry_time is not None and entry.exit_time is None
        ]
        assert len(entry_only) == 144, (
            f"Expected 144 entry-only records, got {len(entry_only)}"
        )

    def test_first_teacher_ci_and_name(self, parse_result):
        """First teacher block: CI=10752810, name='YHAGO DE SOUZA'."""
        ci = "10752810"
        assert ci in parse_result.records, f"CI {ci!r} not found in records"
        entries = parse_result.records[ci]
        assert entries[0].teacher_name.strip() == "YHAGO DE SOUZA"

    def test_first_teacher_record_values(self, parse_result):
        """Validate specific known record: 05/03/2026 entry=08:10 exit=12:07 worked=237min."""
        entries = parse_result.records["10752810"]
        # Find the 05/03 08:10 record
        target = next(
            (e for e in entries if e.date == date(2026, 3, 5) and e.entry_time == time(8, 10)),
            None,
        )
        assert target is not None, "Expected record for 05/03/2026 08:10 not found"
        assert target.exit_time == time(12, 7)
        assert target.worked_minutes == 3 * 60 + 57  # 237 minutes

    def test_worked_minutes_positive_when_present(self, parse_result):
        """Any worked_minutes value must be non-negative."""
        for ci, entries in parse_result.records.items():
            for entry in entries:
                if entry.worked_minutes is not None:
                    assert entry.worked_minutes >= 0, (
                        f"CI {ci!r} on {entry.date}: negative worked_minutes"
                    )

    def test_teacher_with_no_attendance(self, parse_result):
        """
        'Eddy Quette' (CI=10853506) has zero attendance in the report period.
        Such a teacher should NOT appear in records (all rows had no entry/exit).
        """
        assert "10853506" not in parse_result.records, (
            "CI 10853506 (Eddy Quette) should be absent — no attendance rows in the XLS"
        )

    def test_ci_are_strings(self, parse_result):
        """CIs must be strings, not floats or ints."""
        for ci in parse_result.records:
            assert isinstance(ci, str), f"CI is not a string: {ci!r}"
            # Should not contain decimal point
            assert "." not in ci, f"CI looks like a float: {ci!r}"
