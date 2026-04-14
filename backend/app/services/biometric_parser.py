"""
Service: Biometric Parser
Parses hierarchical XLS biometric reports into structured records.

XLS Block Structure per teacher:
  Row N+0: "Nombre " | _ | _ | TEACHER_NAME | ... | "Número de Tarjeta" | _ | _ | 0
  Row N+1: "ID" | _ | "Fecha" | "Turno" | "Entrada" | "Salida" | ... | "Trabajado" | ...
  Row N+2..K: data rows (CI | _ | dd/mm/yyyy | shift | HH:MM | HH:MM | ... | HH:MM | ...)
  Row K+1:  "Horas totales" | _ | _ | _ | float_hrs | _ | "Tiempo total" | _ | _ | HH:MM

Column indices in data rows:
  0 = CI (string with numeric value)
  2 = Fecha (dd/mm/yyyy)
  3 = Turno (shift)
  4 = Entrada (HH:MM or empty)
  5 = Salida (HH:MM or empty)
  9 = Trabajado (HH:MM or empty — can exceed 24h, e.g. '35:57' in totals row)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any, Optional

import xlrd
from sqlalchemy.orm import Session

from app.models.biometric import BiometricRecord, BiometricUpload
from app.utils.helpers import parse_time_str

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------


@dataclass
class BiometricEntry:
    """A single attendance record for one teacher on one day (one entry/exit pair)."""

    teacher_name: str
    ci: str
    date: date
    entry_time: Optional[time]
    exit_time: Optional[time]
    worked_minutes: Optional[int]
    shift: Optional[str]


@dataclass
class BiometricParseResult:
    """Full result of parsing one biometric XLS file."""

    metadata: dict[str, Any]
    records: dict[str, list[BiometricEntry]]  # keyed by CI string
    stats: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_date(raw: Optional[str]) -> Optional[date]:
    """Parse a date string in dd/mm/yyyy format. Returns None on failure."""
    if not raw or not raw.strip():
        return None
    try:
        day, month, year = raw.strip().split("/")
        return date(int(year), int(month), int(day))
    except (ValueError, AttributeError):
        return None


def _parse_worked_minutes(raw: Optional[str]) -> Optional[int]:
    """
    Parse 'Trabajado' cell value (HH:MM) into total minutes.
    Hours can exceed 24 (e.g. '35:57' in the totals row — ignored at that level).
    Returns None for empty or malformed values.
    """
    if not raw or not raw.strip():
        return None
    try:
        parts = raw.strip().split(":")
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours * 60 + minutes
    except (ValueError, IndexError, AttributeError):
        return None


def _cell_str(sheet: xlrd.sheet.Sheet, row: int, col: int) -> str:
    """Return cell value as a stripped string, or '' for empty/non-text cells."""
    cell = sheet.cell(row, col)
    if cell.ctype == xlrd.XL_CELL_EMPTY:
        return ""
    val = cell.value
    if isinstance(val, float):
        # Numeric cell — convert to integer string when whole number
        return str(int(val)) if val == int(val) else str(val)
    return str(val).strip()


# ---------------------------------------------------------------------------
# Main parser class
# ---------------------------------------------------------------------------


class BiometricParser:
    """Parses hierarchical biometric XLS reports into structured records."""

    def parse_file(self, file_path: str) -> BiometricParseResult:
        """
        Parse a biometric XLS file.

        Returns a BiometricParseResult with:
          - metadata: {department, date_from, date_to}
          - records: dict[CI, list[BiometricEntry]]
          - stats: {total_teachers, total_records, date_range}
          - warnings: list of non-fatal issues found during parsing
        """
        warnings: list[str] = []

        try:
            wb = xlrd.open_workbook(file_path, logfile=open("/dev/null", "w"))  # suppress xlrd warnings
        except Exception:
            wb = xlrd.open_workbook(file_path)

        sheet = wb.sheet_by_index(0)
        logger.info("Opened biometric file: %s (%d rows)", file_path, sheet.nrows)

        # ── Step 1: Extract metadata ──────────────────────────────────────
        metadata = self._extract_metadata(sheet, warnings)

        # ── Step 2: Find block boundaries ────────────────────────────────
        nombre_rows: list[int] = []
        horas_rows: list[int] = []

        for r in range(sheet.nrows):
            val = sheet.cell_value(r, 0)
            if isinstance(val, str) and val.startswith("Nombre"):
                nombre_rows.append(r)
            elif isinstance(val, str) and val.strip() == "Horas totales":
                horas_rows.append(r)

        if len(nombre_rows) != len(horas_rows):
            warnings.append(
                f"Block count mismatch: {len(nombre_rows)} Nombre rows vs "
                f"{len(horas_rows)} Horas totales rows. Using min count."
            )

        n_blocks = min(len(nombre_rows), len(horas_rows))
        logger.info("Found %d teacher blocks", n_blocks)

        # ── Step 3: Parse each teacher block ─────────────────────────────
        records: dict[str, list[BiometricEntry]] = {}
        total_record_count = 0

        for i in range(n_blocks):
            block_start = nombre_rows[i]
            block_end = horas_rows[i]

            try:
                entries, ci, block_warnings = self._parse_teacher_block(
                    sheet, block_start, block_end
                )
                warnings.extend(block_warnings)

                if ci:
                    if entries:  # only register teachers who have at least one attendance record
                        if ci not in records:
                            records[ci] = []
                        records[ci].extend(entries)
                        total_record_count += len(entries)
                    # else: teacher exists in file but had zero attendance rows — skip silently
                else:
                    warnings.append(f"Block at row {block_start}: could not extract CI, skipping.")

            except Exception as exc:
                teacher_name = _cell_str(sheet, block_start, 3)
                warnings.append(
                    f"Block at row {block_start} ({teacher_name!r}): parse error — {exc}"
                )
                logger.exception("Error parsing block at row %d", block_start)

        # ── Step 4: Build stats ───────────────────────────────────────────
        stats = {
            "total_teachers": len(records),
            "total_records": total_record_count,
            "date_range": f"{metadata.get('date_from')} → {metadata.get('date_to')}",
        }

        logger.info(
            "Parse complete: %d teachers, %d records, %d warnings",
            stats["total_teachers"],
            stats["total_records"],
            len(warnings),
        )

        return BiometricParseResult(
            metadata=metadata,
            records=records,
            stats=stats,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_metadata(
        self, sheet: xlrd.sheet.Sheet, warnings: list[str]
    ) -> dict[str, Any]:
        """Extract department and date range from the top rows of the file."""
        metadata: dict[str, Any] = {
            "department": None,
            "date_from": None,
            "date_to": None,
        }

        for r in range(min(10, sheet.nrows)):
            col0 = _cell_str(sheet, r, 0)

            if col0 == "Departamento":
                metadata["department"] = _cell_str(sheet, r, 3) or None

            elif col0 == "Desde":
                raw_from = _cell_str(sheet, r, 3)
                raw_to = _cell_str(sheet, r, 9)
                metadata["date_from"] = _parse_date(raw_from)
                metadata["date_to"] = _parse_date(raw_to)
                if not metadata["date_from"]:
                    warnings.append(f"Could not parse 'Desde' date: {raw_from!r}")
                if not metadata["date_to"]:
                    warnings.append(f"Could not parse 'Hasta' date: {raw_to!r}")

        return metadata

    def _parse_teacher_block(
        self,
        sheet: xlrd.sheet.Sheet,
        block_start: int,
        block_end: int,
    ) -> tuple[list[BiometricEntry], Optional[str], list[str]]:
        """
        Parse a single teacher block between block_start (Nombre row) and
        block_end (Horas totales row, exclusive).

        Returns (entries, ci, warnings).
        """
        warnings: list[str] = []
        entries: list[BiometricEntry] = []

        # Row N+0: "Nombre " row → teacher name at col 3
        teacher_name = _cell_str(sheet, block_start, 3).strip()
        if not teacher_name:
            warnings.append(f"Row {block_start}: empty teacher name")

        # Data rows start at N+2 (skip Nombre row + header row)
        data_start = block_start + 2

        # Extract CI from the first data row (col 0)
        ci: Optional[str] = None
        if data_start < block_end:
            raw_ci = _cell_str(sheet, data_start, 0)
            if raw_ci:
                ci = raw_ci.strip()

        if not ci:
            warnings.append(f"Block at row {block_start} ({teacher_name!r}): no CI found")
            return entries, ci, warnings

        # Parse each data row
        for r in range(data_start, block_end):
            row_ci = _cell_str(sheet, r, 0)

            # Skip rows that aren't data rows (safety check)
            if not row_ci or row_ci in ("ID", "Horas totales", "Nombre "):
                continue

            raw_date = _cell_str(sheet, r, 2)
            raw_shift = _cell_str(sheet, r, 3)
            raw_entry = _cell_str(sheet, r, 4)
            raw_exit = _cell_str(sheet, r, 5)
            raw_worked = _cell_str(sheet, r, 9)

            # Skip days with NO attendance at all (no entry AND no exit)
            if not raw_entry and not raw_exit:
                continue

            # Parse date
            parsed_date = _parse_date(raw_date)
            if not parsed_date:
                warnings.append(
                    f"Row {r} ({teacher_name!r}): invalid date {raw_date!r}, skipping row"
                )
                continue

            # Parse times
            entry_time = parse_time_str(raw_entry) if raw_entry else None
            exit_time = parse_time_str(raw_exit) if raw_exit else None

            # Parse worked minutes
            worked_minutes = _parse_worked_minutes(raw_worked) if raw_worked else None

            # Shift (stored as-is; always "ADMINISTRATIVOS(08:00-19:00)" in practice)
            shift = raw_shift if raw_shift else None

            entries.append(
                BiometricEntry(
                    teacher_name=teacher_name,
                    ci=ci,
                    date=parsed_date,
                    entry_time=entry_time,
                    exit_time=exit_time,
                    worked_minutes=worked_minutes,
                    shift=shift,
                )
            )

        return entries, ci, warnings

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    def save_to_db(
        self,
        db: Session,
        parse_result: BiometricParseResult,
        month: int,
        year: int,
        filename: str,
        ci_alias_map: dict[str, str] | None = None,
    ) -> BiometricUpload:
        """
        Persist parsed biometric data to the database.

        Creates one BiometricUpload and N BiometricRecord rows.
        Returns the created BiometricUpload (flushed, not yet committed).

        Parameters
        ----------
        ci_alias_map : dict[str, str] | None
            Optional mapping of ``{bio_ci → real_teacher_ci}`` produced during
            biometric upload when a bio CI doesn't match any teacher directly but
            the teacher was found by name matching.  When provided, records are
            stored using the real teacher CI so the attendance engine can find them.
        """
        if ci_alias_map is None:
            ci_alias_map = {}

        upload = BiometricUpload(
            filename=filename,
            month=month,
            year=year,
            total_records=parse_result.stats["total_records"],
            total_teachers=parse_result.stats["total_teachers"],
            status="completed",
        )
        db.add(upload)
        db.flush()  # get upload.id without full commit

        for ci, entries in parse_result.records.items():
            # Use aliased CI if available (handles CI mismatches between systems)
            real_ci = ci_alias_map.get(ci, ci)
            if real_ci != ci:
                logger.info(
                    "save_to_db: bio CI %s aliased to teacher CI %s (%s)",
                    ci,
                    real_ci,
                    entries[0].teacher_name if entries else "?",
                )
            for entry in entries:
                record = BiometricRecord(
                    upload_id=upload.id,
                    teacher_ci=real_ci,
                    teacher_name=entry.teacher_name,
                    date=entry.date,
                    entry_time=entry.entry_time,
                    exit_time=entry.exit_time,
                    worked_minutes=entry.worked_minutes,
                    shift=entry.shift,
                )
                db.add(record)

        logger.info(
            "Saved BiometricUpload id=%d: %d records for %d teachers (%d CI aliases applied)",
            upload.id,
            parse_result.stats["total_records"],
            parse_result.stats["total_teachers"],
            len(ci_alias_map),
        )

        return upload
