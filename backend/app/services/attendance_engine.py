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
import unicodedata
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord
from app.models.designation import Designation
from app.services import app_settings_service
from app.services.effective_schedule_service import EffectiveScheduleSlot, effective_schedule_slots
from app.utils.helpers import parse_time_str, time_to_minutes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOLERANCE_MINUTES = 5

# Maps Python's weekday() (0=Monday … 5=Saturday, 6=Sunday) to Spanish day names.
# Values are stored WITHOUT accents so they match the normalized form produced by
# _normalize_day().  schedule_json may store accented variants ("miércoles", "sábado")
# which are normalized before comparison.
WEEKDAY_MAP: dict[int, str] = {
    0: "lunes",
    1: "martes",
    2: "miercoles",
    3: "jueves",
    4: "viernes",
    5: "sabado",
    6: "domingo",
}


def _normalize_day(day: str) -> str:
    """Strip accents and lowercase for reliable day name matching.

    Handles schedule_json entries like "Miércoles", "miércoles", "miercoles",
    "Sábado", "sabado", etc. — all normalize to the same ASCII lowercase form.
    """
    s = unicodedata.normalize("NFD", day)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.strip().lower()


# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------


@dataclass
class SlotResult:
    """Result for a single teacher / date / scheduled-slot combination."""

    designation_id: int | None
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
    published_schedule_assignment_id: int | None = None

    @property
    def source_kind(self) -> str:
        return "legacy" if self.designation_id is not None else "published"

    @property
    def source_id(self) -> int:
        source_id = self.designation_id or self.published_schedule_assignment_id
        if source_id is None:  # pragma: no cover - constructor invariant
            raise ValueError("Attendance result source identity is missing")
        return source_id


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

        # ── Step 2: Resolve the active schedule from immutable publications
        #              plus deterministic legacy fallback for each target date. ──
        academic_period = app_settings_service.get_active_academic_period(db)

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
            slots_by_teacher: dict[str, list[EffectiveScheduleSlot]] = {}
            for slot in effective_schedule_slots(db, academic_period, target_date):
                if _normalize_day(slot.weekday) == weekday_name:
                    slots_by_teacher.setdefault(slot.teacher_ci, []).append(slot)

            for ci, teacher_slots in slots_by_teacher.items():
                teacher_bio = bio_index.get(ci, {}).get(target_date, [])

                day_results = self.match_schedule_slots(
                    teacher_ci=ci,
                    target_date=target_date,
                    slots=teacher_slots,
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
        day_slots: list[EffectiveScheduleSlot] = []
        for desig in designations:
            contract_start = getattr(desig, "contract_start_date", None)
            contract_end = getattr(desig, "contract_end_date", None)
            if isinstance(contract_start, date) and target_date < contract_start:
                continue
            if isinstance(contract_end, date) and target_date > contract_end:
                continue
            schedule: list[dict] = desig.schedule_json or []
            for slot in schedule:
                if _normalize_day(slot.get("dia", "")) == weekday_name:
                    slot_start = parse_time_str(slot.get("hora_inicio", ""))
                    slot_end = parse_time_str(slot.get("hora_fin", ""))
                    if slot_start is None or slot_end is None:
                        logger.warning(
                            "Designation %d has unparseable time slot: %s – %s",
                            desig.id,
                            slot.get("hora_inicio"),
                            slot.get("hora_fin"),
                        )
                        continue
                    day_slots.append(EffectiveScheduleSlot(
                        source_type="legacy",
                        teacher_ci=teacher_ci,
                        subject=desig.subject,
                        group_code=desig.group_code,
                        semester=str(getattr(desig, "semester", "")),
                        activity_type="theory",
                        weekday=weekday_name,
                        start_time=slot_start,
                        end_time=slot_end,
                        academic_hours=int(slot.get("horas_academicas", 0)),
                        designation_id=desig.id,
                        effective_from=contract_start if isinstance(contract_start, date) else None,
                        effective_to=contract_end if isinstance(contract_end, date) else None,
                    ))
        return self.match_schedule_slots(
            teacher_ci=teacher_ci,
            target_date=target_date,
            slots=day_slots,
            biometric_records=biometric_records,
        )

    def match_schedule_slots(
        self,
        teacher_ci: str,
        target_date: date,
        slots: list[EffectiveScheduleSlot],
        biometric_records: list[BiometricRecord],
    ) -> list[SlotResult]:
        """Apply the unchanged biometric algorithm to either schedule source."""
        results: list[SlotResult] = []
        day_slots = sorted(slots, key=lambda item: item.start_time)
        if not day_slots:
            return results

        # Sort biometric records by entry_time (records with no entry go last)
        bio_sorted = sorted(
            biometric_records,
            key=lambda r: r.entry_time if r.entry_time is not None else time(23, 59),
        )

        # ── Match each slot ─────────────────────────────────────────────
        for slot in day_slots:
            covering = self._find_covering_record(slot.start_time, slot.end_time, bio_sorted)

            if covering is not None:
                bio_rec, status, late_min, obs = covering
                results.append(
                    SlotResult(
                        designation_id=slot.designation_id,
                        teacher_ci=teacher_ci,
                        date=target_date,
                        scheduled_start=slot.start_time,
                        scheduled_end=slot.end_time,
                        actual_entry=bio_rec.entry_time,
                        actual_exit=bio_rec.exit_time,
                        status=status,
                        academic_hours=slot.academic_hours,   # Always awarded unless ABSENT
                        late_minutes=late_min,
                        observation=obs,
                        biometric_record_id=bio_rec.id,
                        subject=slot.subject,
                        group_code=slot.group_code,
                        published_schedule_assignment_id=slot.published_assignment_id,
                    )
                )
            else:
                results.append(
                    SlotResult(
                        designation_id=slot.designation_id,
                        teacher_ci=teacher_ci,
                        date=target_date,
                        scheduled_start=slot.start_time,
                        scheduled_end=slot.end_time,
                        actual_entry=None,
                        actual_exit=None,
                        status="ABSENT",
                        academic_hours=0,
                        late_minutes=0,
                        observation=(
                            f"Sin registro biométrico para "
                            f"{slot.start_time.strftime('%H:%M')}"
                            f"-{slot.end_time.strftime('%H:%M')}"
                        ),
                        biometric_record_id=None,
                        subject=slot.subject,
                        group_code=slot.group_code,
                        published_schedule_assignment_id=slot.published_assignment_id,
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

        Uses upsert semantics on the source-specific natural key so re-processing
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
        def persisted_key(row: AttendanceRecord) -> tuple[object, ...]:
            source_kind = "legacy" if row.designation_id is not None else "published"
            source_id = row.designation_id or row.published_schedule_assignment_id
            return (row.teacher_ci, source_kind, source_id, row.date, row.scheduled_start)

        def result_key(row: SlotResult) -> tuple[object, ...]:
            return (row.teacher_ci, row.source_kind, row.source_id, row.date, row.scheduled_start)

        existing_by_key = {persisted_key(row): row for row in existing_rows}
        incoming_keys = {result_key(row) for row in results}

        for r in results:
            key = result_key(r)
            record = existing_by_key.get(key)

            if record is None:
                record = AttendanceRecord(
                    teacher_ci=r.teacher_ci,
                    designation_id=r.designation_id,
                    published_schedule_assignment_id=r.published_schedule_assignment_id,
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
