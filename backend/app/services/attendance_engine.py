"""
Service: Attendance Engine
THE core matching engine for the Planilla Docentes UPDS system.

Matches biometric entry/exit records against scheduled class slots
to produce an attendance result for each teacher/day/slot combination.

Business Rules:
  - ATTENDED : arrived within TOLERANCE_MINUTES of slot start (or earlier)
  - LATE     : arrived >TOLERANCE_MINUTES late — still counts for pay
  - NO_EXIT  : entry found, no exit recorded — still counts for pay
  - ABSENT   : no biometric record covers the slot at all

Coverage Rule:
  A biometric (entry, exit) pair COVERS a slot when ALL conditions hold:
    1. entry_time is NOT None  (records with no entry are data errors — skipped)
    2. entry_time <= slot_end  (teacher arrived before class was over)
    3. exit_time is NULL  OR  exit_time >= slot_start
       (teacher didn't leave before class even started)

Academic hours are awarded for ATTENDED, LATE, and NO_EXIT.  ABSENT = 0.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord
from app.models.designation import Designation
from app.utils.helpers import parse_time_str, time_to_minutes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOLERANCE_MINUTES = 5

# Maps Python's weekday() (0=Monday … 5=Saturday, 6=Sunday) to Spanish day names
WEEKDAY_MAP: dict[int, str] = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo",
}


# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------


@dataclass
class SlotResult:
    """Result for a single teacher / date / scheduled-slot combination."""

    designation_id: int
    teacher_ci: str
    date: date
    scheduled_start: time
    scheduled_end: time
    actual_entry: Optional[time]
    actual_exit: Optional[time]
    status: str             # ATTENDED | LATE | ABSENT | NO_EXIT
    academic_hours: int     # 0 when ABSENT; slot's horas_academicas otherwise
    late_minutes: int       # 0 unless LATE (or NO_EXIT with late arrival)
    observation: Optional[str]
    biometric_record_id: Optional[int]
    subject: str            # for reporting
    group_code: str         # for reporting


@dataclass
class ProcessResult:
    """Summary statistics returned by process_month()."""

    upload_id: int
    month: int
    year: int
    total_slots: int = 0
    attended: int = 0
    late: int = 0
    absent: int = 0
    no_exit: int = 0
    records_saved: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def present(self) -> int:
        """Slots where the teacher was physically present (ATTENDED + LATE + NO_EXIT)."""
        return self.attended + self.late + self.no_exit


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


class AttendanceEngine:
    """
    Core attendance matching engine.

    Usage::

        engine = AttendanceEngine()
        result = engine.process_month(db, upload_id=1, month=3, year=2026)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_month(
        self,
        db: Session,
        upload_id: int,
        month: int,
        year: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ProcessResult:
        """
        Process an entire month of attendance.

        Steps
        -----
        1. Load all BiometricRecord rows for this upload, indexed by (ci, date).
        2. Load all Designation rows from DB, indexed by teacher_ci.
        3. For each calendar date in the range (configurable or full month):
           a. Determine the day of week.
           b. For each teacher that has at least one class on that day:
              - Retrieve their biometric records for that date.
              - Run match_teacher_day().
              - Accumulate SlotResult list.
        4. Bulk-save results to attendance_records table.
        5. Return a ProcessResult with summary statistics.

        Args:
            start_date: Optional start of the attendance period (inclusive).
                        If provided with end_date, overrides full-month iteration.
            end_date:   Optional end of the attendance period (inclusive).
                        March 2026 exceptional range: date(2026,3,2) – date(2026,3,20).
                        Normal months: 21st of prev month to 20th of current month.
        """
        summary = ProcessResult(upload_id=upload_id, month=month, year=year)

        # ── Step 1: Load biometric records ─────────────────────────────
        bio_rows: list[BiometricRecord] = (
            db.query(BiometricRecord)
            .filter(BiometricRecord.upload_id == upload_id)
            .all()
        )

        # Index: teacher_ci → date → list[BiometricRecord]
        bio_index: dict[str, dict[date, list[BiometricRecord]]] = {}
        for row in bio_rows:
            bio_index.setdefault(row.teacher_ci, {}).setdefault(row.date, []).append(row)

        logger.info(
            "process_month: loaded %d biometric records for %d teachers (upload_id=%d)",
            len(bio_rows),
            len(bio_index),
            upload_id,
        )

        # ── Step 2: Load all designations ──────────────────────────────
        all_designations: list[Designation] = db.query(Designation).all()

        # Index: teacher_ci → list[Designation]
        desig_index: dict[str, list[Designation]] = {}
        for d in all_designations:
            desig_index.setdefault(d.teacher_ci, []).append(d)

        logger.info(
            "process_month: loaded %d designations for %d teachers",
            len(all_designations),
            len(desig_index),
        )

        # ── Step 3: Build list of dates to process ─────────────────────
        if start_date is not None and end_date is not None:
            # Configurable date range (e.g. March 2026: 2–20, normal months: 21 prev–20 curr)
            dates_to_process: list[date] = []
            current = start_date
            while current <= end_date:
                dates_to_process.append(current)
                current += timedelta(days=1)
            logger.info(
                "process_month: using configurable range %s – %s (%d days)",
                start_date,
                end_date,
                len(dates_to_process),
            )
        else:
            # Default: full calendar month
            _, last_day = calendar.monthrange(year, month)
            dates_to_process = [date(year, month, day) for day in range(1, last_day + 1)]
            logger.info(
                "process_month: using full calendar month %d/%d (%d days)",
                month,
                year,
                last_day,
            )

        all_results: list[SlotResult] = []

        for target_date in dates_to_process:
            weekday_name = WEEKDAY_MAP[target_date.weekday()]

            # Collect teachers who have at least one slot on this weekday
            teachers_today: set[str] = set()
            for ci, designations in desig_index.items():
                for desig in designations:
                    schedule: list[dict] = desig.schedule_json or []
                    if any(slot.get("dia") == weekday_name for slot in schedule):
                        teachers_today.add(ci)
                        break  # one match per teacher is enough

            for ci in teachers_today:
                teacher_designations = desig_index.get(ci, [])
                teacher_bio = bio_index.get(ci, {}).get(target_date, [])

                day_results = self.match_teacher_day(
                    teacher_ci=ci,
                    target_date=target_date,
                    designations=teacher_designations,
                    biometric_records=teacher_bio,
                )
                all_results.extend(day_results)

        logger.info(
            "process_month: matched %d slot results across %d calendar days",
            len(all_results),
            len(dates_to_process),
        )

        # ── Step 4: Persist results ────────────────────────────────────
        records_saved = self.save_results(
            db, all_results, upload_id, month, year,
            start_date=start_date,
            end_date=end_date,
        )

        # ── Step 5: Build summary ──────────────────────────────────────
        summary.total_slots = len(all_results)
        summary.records_saved = records_saved
        for r in all_results:
            if r.status == "ATTENDED":
                summary.attended += 1
            elif r.status == "LATE":
                summary.late += 1
            elif r.status == "ABSENT":
                summary.absent += 1
            elif r.status == "NO_EXIT":
                summary.no_exit += 1

        logger.info(
            "process_month complete: total=%d attended=%d late=%d absent=%d no_exit=%d",
            summary.total_slots,
            summary.attended,
            summary.late,
            summary.absent,
            summary.no_exit,
        )
        return summary

    def match_teacher_day(
        self,
        teacher_ci: str,
        target_date: date,
        designations: list[Designation],
        biometric_records: list[BiometricRecord],
    ) -> list[SlotResult]:
        """
        Match one teacher's biometric records against their scheduled slots for one day.

        This is the CORE algorithm.  It is intentionally kept pure (no DB access)
        to make unit testing straightforward.

        Parameters
        ----------
        teacher_ci        : Teacher identifier
        target_date       : The date being processed
        designations      : ALL Designation objects for this teacher
                            (day filtering happens here internally)
        biometric_records : All BiometricRecord rows for this teacher on target_date

        Returns
        -------
        list[SlotResult] — one entry per scheduled slot on this weekday
        """
        weekday_name = WEEKDAY_MAP[target_date.weekday()]
        results: list[SlotResult] = []

        # ── Collect all slots scheduled for today ───────────────────────
        day_slots: list[tuple[Designation, dict]] = []
        for desig in designations:
            schedule: list[dict] = desig.schedule_json or []
            for slot in schedule:
                if slot.get("dia") == weekday_name:
                    day_slots.append((desig, slot))

        if not day_slots:
            return results  # Nothing scheduled today for this teacher

        # Sort slots by start time (ascending)
        day_slots.sort(
            key=lambda x: parse_time_str(x[1].get("hora_inicio", "00:00")) or time(0, 0)
        )

        # Sort biometric records by entry_time (records with no entry go last)
        bio_sorted = sorted(
            biometric_records,
            key=lambda r: r.entry_time if r.entry_time is not None else time(23, 59),
        )

        # ── Match each slot ─────────────────────────────────────────────
        for desig, slot in day_slots:
            slot_start = parse_time_str(slot.get("hora_inicio", ""))
            slot_end = parse_time_str(slot.get("hora_fin", ""))
            slot_hours: int = slot.get("horas_academicas", 0)

            if slot_start is None or slot_end is None:
                logger.warning(
                    "Designation %d has unparseable time slot: %s – %s",
                    desig.id,
                    slot.get("hora_inicio"),
                    slot.get("hora_fin"),
                )
                continue

            covering = self._find_covering_record(slot_start, slot_end, bio_sorted)

            if covering is not None:
                bio_rec, status, late_min, obs = covering
                results.append(
                    SlotResult(
                        designation_id=desig.id,
                        teacher_ci=teacher_ci,
                        date=target_date,
                        scheduled_start=slot_start,
                        scheduled_end=slot_end,
                        actual_entry=bio_rec.entry_time,
                        actual_exit=bio_rec.exit_time,
                        status=status,
                        academic_hours=slot_hours,   # Always awarded unless ABSENT
                        late_minutes=late_min,
                        observation=obs,
                        biometric_record_id=bio_rec.id,
                        subject=desig.subject,
                        group_code=desig.group_code,
                    )
                )
            else:
                results.append(
                    SlotResult(
                        designation_id=desig.id,
                        teacher_ci=teacher_ci,
                        date=target_date,
                        scheduled_start=slot_start,
                        scheduled_end=slot_end,
                        actual_entry=None,
                        actual_exit=None,
                        status="ABSENT",
                        academic_hours=0,
                        late_minutes=0,
                        observation=(
                            f"Sin registro biométrico para "
                            f"{slot.get('hora_inicio', '?')}"
                            f"-{slot.get('hora_fin', '?')}"
                        ),
                        biometric_record_id=None,
                        subject=desig.subject,
                        group_code=desig.group_code,
                    )
                )

        return results

    def save_results(
        self,
        db: Session,
        results: list[SlotResult],
        upload_id: int,
        month: int,
        year: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        """
        Persist SlotResults as AttendanceRecord rows.

        Uses upsert semantics on the natural key
        (teacher_ci, designation_id, date, scheduled_start) so re-processing
        updates existing rows instead of leaving stale attendance states behind.

        When start_date/end_date are provided (partial-range processing), the
        stale-row deletion is scoped to only that date range, preserving valid
        records outside the processed window.

        Returns the number of rows inserted or updated.
        """
        if not results:
            return 0

        saved = 0
        processed_teachers = {row.teacher_ci for row in results}

        # Load existing rows only within the processed date range (if given)
        existing_query = db.query(AttendanceRecord).filter(
            AttendanceRecord.month == month,
            AttendanceRecord.year == year,
            AttendanceRecord.teacher_ci.in_(processed_teachers),
        )
        if start_date is not None:
            existing_query = existing_query.filter(AttendanceRecord.date >= start_date)
        if end_date is not None:
            existing_query = existing_query.filter(AttendanceRecord.date <= end_date)

        existing_rows = existing_query.all()
        existing_by_key = {
            (row.teacher_ci, row.designation_id, row.date, row.scheduled_start): row
            for row in existing_rows
        }
        incoming_keys = {
            (row.teacher_ci, row.designation_id, row.date, row.scheduled_start)
            for row in results
        }

        for r in results:
            key = (r.teacher_ci, r.designation_id, r.date, r.scheduled_start)
            record = existing_by_key.get(key)

            if record is None:
                record = AttendanceRecord(
                    teacher_ci=r.teacher_ci,
                    designation_id=r.designation_id,
                    date=r.date,
                    scheduled_start=r.scheduled_start,
                    scheduled_end=r.scheduled_end,
                    actual_entry=r.actual_entry,
                    actual_exit=r.actual_exit,
                    status=r.status,
                    academic_hours=r.academic_hours,
                    late_minutes=r.late_minutes,
                    observation=r.observation,
                    biometric_record_id=r.biometric_record_id,
                    month=month,
                    year=year,
                )
                db.add(record)
                existing_by_key[key] = record
            else:
                record.scheduled_end = r.scheduled_end
                record.actual_entry = r.actual_entry
                record.actual_exit = r.actual_exit
                record.status = r.status
                record.academic_hours = r.academic_hours
                record.late_minutes = r.late_minutes
                record.observation = r.observation
                record.biometric_record_id = r.biometric_record_id
                record.month = month
                record.year = year

            saved += 1

        # Only delete stale rows that fall within the processed date range.
        # This prevents wiping valid data outside the range when reprocessing
        # a partial window (e.g., March 2–20 should not delete March 21–31 rows).
        stale_record_ids = [
            row.id
            for key, row in existing_by_key.items()
            if row.id is not None and key not in incoming_keys
        ]
        if stale_record_ids:
            db.query(AttendanceRecord).filter(
                AttendanceRecord.id.in_(stale_record_ids)
            ).delete(synchronize_session=False)

        db.flush()
        logger.info(
            "save_results: upserted %d attendance records and deleted %d stale rows "
            "(range: %s – %s)",
            saved,
            len(stale_record_ids),
            start_date or "month-start",
            end_date or "month-end",
        )
        return saved

    def get_month_summary(
        self,
        db: Session,
        month: int,
        year: int,
    ) -> dict:
        """
        Return attendance summary statistics for a processed month.

        Computed from the persisted attendance_records table so it always
        reflects the actual stored state, not just the latest engine run.
        """
        rows: list[AttendanceRecord] = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.month == month,
                AttendanceRecord.year == year,
            )
            .all()
        )

        total = len(rows)
        by_status: dict[str, int] = {"ATTENDED": 0, "LATE": 0, "ABSENT": 0, "NO_EXIT": 0}
        total_academic_hours = 0

        for r in rows:
            status = r.status.upper()
            if status in by_status:
                by_status[status] += 1
            total_academic_hours += r.academic_hours

        present = by_status["ATTENDED"] + by_status["LATE"] + by_status["NO_EXIT"]

        return {
            "month": month,
            "year": year,
            "total_slots": total,
            "by_status": by_status,
            "total_academic_hours": total_academic_hours,
            "attendance_rate": round(present / total * 100, 1) if total > 0 else 0.0,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_covering_record(
        self,
        slot_start: time,
        slot_end: time,
        bio_records: list[BiometricRecord],
    ) -> Optional[tuple[BiometricRecord, str, int, Optional[str]]]:
        """
        Find the best biometric record that covers the given scheduled slot.

        Coverage conditions (ALL must hold):
          C1. entry_time is NOT None  (records with no entry are data errors → skip)
          C2. entry_time <= slot_end  (teacher arrived before class was over)
          C3. exit_time is NULL  OR  exit_time >= slot_start
              (teacher didn't leave before class started)

        Returns
        -------
        (record, status, late_minutes, observation)  if a covering record exists
        None  if no record covers the slot (→ ABSENT)

        Status determination:
          NO_EXIT   : C1–C3 hold, but exit_time is NULL
          ATTENDED  : C1–C3 hold, entry_time <= slot_start + TOLERANCE_MINUTES
          LATE      : C1–C3 hold, entry_time > slot_start + TOLERANCE_MINUTES
        """
        slot_start_min = time_to_minutes(slot_start)
        slot_end_min = time_to_minutes(slot_end)
        tolerance_limit_min = slot_start_min + TOLERANCE_MINUTES

        best_match: Optional[tuple[tuple[int, int, int, int], tuple[BiometricRecord, str, int, Optional[str]]]] = None

        for rec in bio_records:
            # C1 — must have an entry time; no-entry records are data anomalies
            if rec.entry_time is None:
                continue

            entry_min = time_to_minutes(rec.entry_time)
            exit_min = (
                time_to_minutes(rec.exit_time) if rec.exit_time is not None else None
            )

            # C2 — teacher must have arrived before the slot ended
            if entry_min > slot_end_min:
                continue  # Arrived after class was over — cannot cover this slot

            # C3 — teacher must not have left before class started
            if exit_min is not None and exit_min < slot_start_min:
                continue  # Exited before slot started — pair is for an earlier block

            # ── Record covers the slot ──────────────────────────────────
            late_min = max(0, entry_min - slot_start_min)

            if rec.exit_time is None:
                # No exit recorded → NO_EXIT (still paid)
                if late_min > TOLERANCE_MINUTES:
                    obs = (
                        f"Llegada tardía ({late_min} min) + sin registro de salida. "
                        f"Entrada: {rec.entry_time.strftime('%H:%M')}"
                    )
                else:
                    obs = f"Sin registro de salida. Entrada: {rec.entry_time.strftime('%H:%M')}"
                match = (rec, "NO_EXIT", late_min, obs)
            elif entry_min <= tolerance_limit_min:
                # On time (early arrival or within tolerance window) → ATTENDED
                match = (rec, "ATTENDED", 0, None)
            else:
                # Late arrival (> TOLERANCE_MINUTES after slot start) → LATE (still paid)
                obs = (
                    f"Llegada tardía: {late_min} min después de "
                    f"{slot_start.strftime('%H:%M')}"
                )
                match = (rec, "LATE", late_min, obs)

            priority_bucket = 0 if entry_min == slot_start_min else 1 if entry_min <= tolerance_limit_min else 2
            distance_to_start = abs(entry_min - slot_start_min)
            exit_preference = 0 if rec.exit_time is not None else 1
            score = (priority_bucket, distance_to_start, late_min, exit_preference)

            if best_match is None or score < best_match[0]:
                best_match = (score, match)

        return best_match[1] if best_match is not None else None
