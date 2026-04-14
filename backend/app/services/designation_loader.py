"""
Service: Designation Loader
Loads designation JSON files into the database.

Supported JSON formats
----------------------
1. UPDS Official format (Designaciones_UPDS_*.json) — direct array with uppercase keys:
   [{"CI": 6593630, "NOMBRE COMPLETO": "...", "MATERIAS": "...", "HORARIO": "...", ...}]
   Teachers are created with REAL CIs (no TEMP needed).

2. New format (designacion_new.json) — direct array:
   [{"docente": ..., "materias": ..., "carga_horaria": ..., "mes": ..., "semana": ...,
     "horario": "...(raw string)...", "horario_detalle": [{"dia": "Lunes", ...}], ...}]

3. Old format (designaciones_normalizadas.json) — dict with wrapper:
   {"metadata": {...}, "designaciones": [...old entries...]}
   Kept for backwards compatibility during transition.

Strategy for teacher CI resolution:
  - UPDS Official format: has real CIs — use them directly
  - New/Old formats: no CI → create teachers with TEMP-{slug} CI
  - When biometric data arrives (CI + name), call link_teachers_by_name()
    to promote TEMP records to real CIs using fuzzy name matching
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, exists, select, text
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.utils.helpers import calc_academic_hours, normalize_group_code

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DesignationLoadResult:
    teachers_created: int = 0
    teachers_reused: int = 0
    designations_loaded: int = 0
    skipped_no_schedule: int = 0
    skipped_no_time: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def total_skipped(self) -> int:
        return self.skipped_no_schedule + self.skipped_no_time

    def __str__(self) -> str:
        return (
            f"DesignationLoadResult("
            f"teachers_created={self.teachers_created}, "
            f"teachers_reused={self.teachers_reused}, "
            f"designations_loaded={self.designations_loaded}, "
            f"skipped={self.total_skipped}, "
            f"warnings={len(self.warnings)})"
        )


# ---------------------------------------------------------------------------
# Name normalisation helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Uppercase, strip accents/diacritics, collapse whitespace."""
    nfkd = unicodedata.normalize("NFD", name)
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return " ".join(stripped.upper().split())


def names_match(name1: str, name2: str) -> bool:
    """
    Return True if two names likely refer to the same person.

    Matching rules (evaluated in order, first match wins):
      1. Exact match after normalization.
      2. All tokens from the shorter name are found in the longer name,
         with at least 3 tokens in the shorter name AND at least 2 "real name" tokens
         (token length >= 4, to reject preposition-only matches like "DE LA CRUZ" where
         only CRUZ qualifies — 1 real token is not enough to identify a person).
         Example: "YHAGO DE SOUZA" (3 tokens, real: YHAGO+SOUZA=2) ⊆ "YHAGO DE SOUZA FROTA" → MATCH.
         Counter-example: "DE LA CRUZ" (3 tokens, real: CRUZ=1) ⊆ "JUAN DE LA CRUZ PEREZ" → NO MATCH.
         Counter-example: "ABNER FLORES" (2 tokens) ⊄ match for "ABNER FLORES MAMANI"
         because 2-token subsets are too ambiguous (many people share any 2-token name).
      3. At least 3 shared tokens AND >= 80% token overlap relative to the shorter name,
         AND at least 2 shared tokens must be "real name" tokens (≥4 chars).

    Rationale:
      - Rule 2 handles biometric systems that truncate compound surnames: the shorter
        form (from one system) must be a complete subset of the longer form (in the other).
      - Rule 3 is the fallback for near-matches where names differ by middle names or
        ordering.
      - Substring matching has been removed — it produces too many false positives
        when teachers share common surnames (e.g., "GARCIA" matching unrelated people).
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    if n1 == n2:
        return True

    tokens1 = set(n1.split())
    tokens2 = set(n2.split())

    if not tokens1 or not tokens2:
        return False

    # Rule 2: all tokens from the shorter name are present in the longer name.
    # Requires at least 3 tokens in the shorter name to avoid ambiguous 2-token
    # matches (e.g. "ABNER FLORES" should NOT match "ABNER FLORES MAMANI" because
    # any two-token partial name could match too many unrelated people).
    # Additionally requires at least 2 "real name" tokens (≥4 chars) to prevent
    # preposition-only matches like "DE LA CRUZ" ⊆ "JUAN DE LA CRUZ PEREZ"
    # where shorter has only CRUZ(4) as a real name token — not enough to identify.
    shorter = tokens1 if len(tokens1) <= len(tokens2) else tokens2
    longer = tokens2 if len(tokens1) <= len(tokens2) else tokens1
    if len(shorter) >= 3 and shorter <= longer:
        real_name_tokens = [t for t in shorter if len(t) >= 4]
        if len(real_name_tokens) >= 2:
            return True

    shared = tokens1 & tokens2
    min_len = min(len(tokens1), len(tokens2))

    # Rule 3: at least 3 shared tokens AND 80%+ overlap relative to the shorter name,
    # AND at least 2 of the shared tokens must be "real name" tokens (≥4 chars).
    # This prevents "DE LA CRUZ" (3 shared, 100% overlap) from matching
    # "JUAN DE LA CRUZ PEREZ" when the shared set contains mostly prepositions.
    if len(shared) >= 3 and len(shared) / min_len >= 0.8:
        real_shared_tokens = [t for t in shared if len(t) >= 4]
        if len(real_shared_tokens) >= 2:
            return True

    return False


def _make_temp_ci(full_name: str) -> str:
    """
    Generate a deterministic TEMP CI from a teacher name.

    Format: TEMP-{8-char hex digest of normalised name}
    Max length: 13 chars — fits inside String(20).
    """
    normalised = normalize_name(full_name)
    digest = hashlib.sha256(normalised.encode()).hexdigest()[:8]
    return f"TEMP-{digest}"


def _calc_duration(hora_inicio: str, hora_fin: str) -> int:
    """Calculate duration in minutes between two HH:MM strings. Returns 0 on error."""
    try:
        t_inicio = datetime.strptime(hora_inicio, "%H:%M")
        t_fin = datetime.strptime(hora_fin, "%H:%M")
        mins = int((t_fin - t_inicio).total_seconds() / 60)
        return max(mins, 0)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Main loader class
# ---------------------------------------------------------------------------

class DesignationLoader:
    """Loads normalized designation JSON into the database."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_from_json(
        self,
        db: Session,
        json_path: str,
        academic_period: str | None = None,
    ) -> DesignationLoadResult:
        """
        Load designations from a JSON file.

        Supports two formats automatically detected at runtime:
        - New format (designacion_new.json): top-level JSON array
        - Old format (designaciones_normalizadas.json): dict with "designaciones" key

        Steps
        -----
        1. Read and validate JSON file.
        2. Detect format (array → new, dict → old).
        3. For each designation entry:
           a. Skip entries without schedule (prácticas clínicas sin docente).
           b. Create or reuse a Teacher row using a TEMP CI derived from the name.
           c. Transform horario_detalle (new format) into the internal schedule_json
              format with lowercase days, duracion_minutos, and horas_academicas.
           d. Normalize group code (e.g. "M-06" → "M-6").
           e. Create a Designation row with schedule_json.
        4. Commit the session and return load statistics.
        """
        if academic_period is None:
            academic_period = settings.ACTIVE_ACADEMIC_PERIOD

        result = DesignationLoadResult()
        path = Path(json_path)

        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")

        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)

        # ---- Detect format ----
        if isinstance(data, list):
            entries: list[dict[str, Any]] = data
            # Sub-detect: UPDS official format vs old new format
            if entries and ("NOMBRE COMPLETO" in entries[0] or "CI" in entries[0]):
                format_type = "upds_official"
                logger.info(
                    "Detected UPDS OFFICIAL format — %d entries from %s",
                    len(entries),
                    path.name,
                )
            else:
                format_type = "new"
                logger.info(
                    "Detected NEW format (direct array) — %d entries from %s",
                    len(entries),
                    path.name,
                )
        else:
            entries = data.get("designaciones", [])
            format_type = "old"
            logger.info(
                "Detected OLD format (dict wrapper) — %d entries from %s",
                len(entries),
                path.name,
            )

        # Cache of name → CI to avoid repeated DB lookups within this run
        name_to_ci: dict[str, str] = {}

        for entry in entries:
            # ── UPDS official personal-data fields (initialized to None for non-upds formats) ──
            teacher_ci_str: str | None = None
            teacher_email: str | None = None
            teacher_phone: str | None = None
            teacher_bank: str | None = None
            teacher_account: str | None = None
            teacher_nit: str | None = None
            teacher_retention: str | None = None

            # ── Field extraction by format ──
            if format_type == "upds_official":
                docente_raw = entry.get("NOMBRE COMPLETO")
                ci_raw = entry.get("CI")
                subject = entry.get("MATERIAS", "")
                semester = entry.get("SEMESTRE", "")
                raw_group = entry.get("GRUPO", "")
                semester_hours = entry.get("CARGA HORARIA SEMESTRAL")
                monthly_hours = entry.get("CARGA HORARIA MENSUAL")
                weekly_hours = entry.get("CARGA HORARIA SEMANAL")
                schedule_raw = entry.get("HORARIO", "")

                # Parse HORARIO string into schedule_json
                schedule_json = self._parse_horario_string(schedule_raw or "")
                weekly_hours_calculated = sum(
                    s.get("horas_academicas", 0) for s in schedule_json
                )

                # Personal data for teacher update
                teacher_ci_str = str(ci_raw).strip() if ci_raw is not None else None
                teacher_email = str(entry.get("CORREO", "")).strip() or None
                teacher_phone = str(entry.get("NÚMERO DE TELÉFONO", "")).strip() or None
                teacher_bank = (
                    str(entry.get("BANCO", "")).strip().title() or None
                )
                teacher_account = (
                    str(entry.get("NÚMERO CUENTA BANCARIA", "")).strip() or None
                )

                nit_raw = str(entry.get("NIT", "")).strip().upper()
                if nit_raw in ("RETENCION", "RETENCIÓN"):
                    teacher_retention = "RETENCION"
                elif nit_raw and nit_raw not in ("NONE", ""):
                    teacher_nit = nit_raw

            elif format_type == "new":
                docente_raw = entry.get("docente")
                # New format: horario_detalle is the parsed schedule array
                horario_detalle: list[dict] = entry.get("horario_detalle") or []
                # Transform to internal format expected by attendance_engine
                schedule_json = self._transform_horario_detalle(horario_detalle)
                subject = entry.get("materias", "")
                semester = entry.get("semestre", "")
                semester_hours = entry.get("carga_horaria")
                monthly_hours = entry.get("mes")
                weekly_hours = entry.get("semana")
                schedule_raw = entry.get("horario")  # raw string
                raw_group = entry.get("grupo", "")
                # Calculate total weekly academic hours from the transformed slots
                weekly_hours_calculated = sum(
                    slot.get("horas_academicas", 0) for slot in schedule_json
                )
            else:
                # Old format: horario is already the parsed schedule array
                docente_raw = entry.get("docente")
                schedule_json = entry.get("horario") or []
                subject = entry.get("materia", "")
                semester = entry.get("semestre", "")
                semester_hours = entry.get("carga_horaria_semestral")
                monthly_hours = entry.get("carga_horaria_mensual")
                weekly_hours = entry.get("carga_horaria_semanal")
                schedule_raw = entry.get("horario_raw")
                raw_group = entry.get("grupo", "")
                weekly_hours_calculated = entry.get("total_horas_academicas_semanal_calculado")

            # ---- Skip: no schedule ----
            if not schedule_json:
                if not docente_raw:
                    # Prácticas clínicas sin docente asignado
                    result.skipped_no_schedule += 1
                    logger.debug("Skipped entry without docente or schedule: %s", subject)
                else:
                    # Docente exists but no schedule slots
                    result.skipped_no_time += 1
                    result.warnings.append(
                        f"Sin horario para docente '{docente_raw}' — materia '{subject}'"
                    )
                continue

            # ---- Skip: has schedule but docente is null ----
            if not docente_raw:
                result.skipped_no_schedule += 1
                logger.debug(
                    "Skipped entry with schedule but no docente: %s %s",
                    subject,
                    raw_group,
                )
                continue

            docente_name: str = docente_raw.strip().upper()
            if not docente_name:
                result.skipped_no_schedule += 1
                continue

            # ---- Normalize group code (strips leading zeros: M-06 → M-6) ----
            group_code = normalize_group_code(raw_group) if raw_group else raw_group

            # ---- Resolve or create Teacher ----
            if format_type == "upds_official" and teacher_ci_str:
                # Use real CI directly — no TEMP needed
                teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci_str).first()
                if teacher is None:
                    teacher = Teacher(
                        ci=teacher_ci_str,
                        full_name=docente_name,
                        email=(
                            teacher_email
                            if teacher_email and "@" in teacher_email
                            else None
                        ),
                        phone=teacher_phone,
                        bank=teacher_bank,
                        account_number=teacher_account,
                        nit=teacher_nit,
                        invoice_retention=teacher_retention,
                    )
                    db.add(teacher)
                    db.flush()
                    result.teachers_created += 1
                    name_to_ci[normalize_name(docente_name)] = teacher_ci_str
                else:
                    # Update teacher with new personal data if provided
                    if teacher_email and "@" in teacher_email:
                        teacher.email = teacher_email
                    if teacher_phone:
                        teacher.phone = teacher_phone
                    if teacher_bank:
                        teacher.bank = teacher_bank
                    if teacher_account:
                        teacher.account_number = teacher_account
                    if teacher_nit:
                        teacher.nit = teacher_nit
                    if teacher_retention:
                        teacher.invoice_retention = teacher_retention
                    result.teachers_reused += 1
                    name_to_ci[normalize_name(docente_name)] = teacher.ci
                # Use the real CI for designation
                teacher_ci = teacher_ci_str
            else:
                teacher_ci = self._get_or_create_teacher(
                    db=db,
                    full_name=docente_name,
                    name_to_ci_cache=name_to_ci,
                    result=result,
                )

            # ---- Create or update Designation ----
            designation = (
                db.query(Designation)
                .filter(
                    Designation.teacher_ci == teacher_ci,
                    Designation.subject == subject,
                    Designation.semester == semester,
                    Designation.group_code == group_code,
                    Designation.academic_period == academic_period,
                )
                .first()
            )

            if designation is None:
                designation = Designation(
                    teacher_ci=teacher_ci,
                    subject=subject,
                    semester=semester,
                    group_code=group_code,
                    academic_period=academic_period,
                    schedule_json=schedule_json,
                    semester_hours=semester_hours,
                    monthly_hours=monthly_hours,
                    weekly_hours=weekly_hours,
                    weekly_hours_calculated=weekly_hours_calculated,
                    schedule_raw=schedule_raw,
                )
                db.add(designation)
            else:
                designation.schedule_json = schedule_json
                designation.semester_hours = semester_hours
                designation.monthly_hours = monthly_hours
                designation.weekly_hours = weekly_hours
                designation.weekly_hours_calculated = weekly_hours_calculated
                designation.schedule_raw = schedule_raw

            result.designations_loaded += 1

        db.commit()

        logger.info(
            "Load complete — teachers_created=%d, reused=%d, designations=%d, skipped=%d, warnings=%d",
            result.teachers_created,
            result.teachers_reused,
            result.designations_loaded,
            result.total_skipped,
            len(result.warnings),
        )
        return result

    @staticmethod
    def _transform_horario_detalle(horario_detalle: list[dict]) -> list[dict]:
        """
        Transform new-format horario_detalle slots into the internal schedule_json format.

        Input (new format):
            {"dia": "Lunes", "hora_inicio": "06:30", "hora_fin": "08:00"}

        Output (internal format, as expected by attendance_engine):
            {"dia": "lunes", "hora_inicio": "06:30", "hora_fin": "08:00",
             "duracion_minutos": 90, "horas_academicas": 2}
        """
        result_slots = []
        for slot in horario_detalle:
            dia = (slot.get("dia") or "").lower()
            hora_inicio = slot.get("hora_inicio", "")
            hora_fin = slot.get("hora_fin", "")

            # Calculate duration in minutes
            duracion_minutos = 0
            try:
                fmt = "%H:%M"
                t_inicio = datetime.strptime(hora_inicio, fmt)
                t_fin = datetime.strptime(hora_fin, fmt)
                duracion_minutos = int((t_fin - t_inicio).total_seconds() / 60)
                if duracion_minutos < 0:
                    duracion_minutos = 0
            except (ValueError, TypeError):
                pass

            horas_academicas = calc_academic_hours(duracion_minutos)

            result_slots.append({
                "dia": dia,
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "duracion_minutos": duracion_minutos,
                "horas_academicas": horas_academicas,
            })
        return result_slots

    @staticmethod
    def _parse_horario_string(horario_raw: str) -> list[dict]:
        """Parse UPDS HORARIO string into schedule_json slots.

        Input examples::

            "LUNES 06:30 - 08:00\\n MARTES 06:30 - 08:55\\n VIERNES 06:30-08:00"
            "MARTES 15:55-17:25\\n MIERCOLES 15:10-17:25\\n JUVES: 15:55-17:25"

        Output::

            [{"dia": "lunes", "hora_inicio": "06:30", "hora_fin": "08:00",
              "duracion_minutos": 90, "horas_academicas": 2}, ...]

        Edge cases handled:
        - Tight format: ``06:30-08:00`` (no spaces around dash)
        - Spaced-one-side: ``06:30 -08:00`` or ``06:30- 08:00``
        - Trailing colon after day: ``JUVES: 15:55``
        - Extra colon in time: ``07:15: - 08:00`` (parsed with relaxed pattern)
        - Day name typos: JUVES → JUEVES
        - Dot separator: ``17:30-18.15`` (dot → colon)
        - AM/PM suffix: parsed then converted to 24-hour
        - Incomplete end time (``08:10 - 40``): skipped with warning
        - "A" instead of "-": ``16:05 A 17:35`` — handled via secondary pattern
        """
        if not horario_raw:
            return []

        # Known day name corrections (typos found in real data)
        DAY_CORRECTIONS: dict[str, str] = {
            "JUVES": "JUEVES",
            "JEVES": "JUEVES",
            "LUNE": "LUNES",
            "MARTE": "MARTES",
            "MIERCOLE": "MIERCOLES",
            "VIERNE": "VIERNES",
            "SABDO": "SABADO",
        }

        slots: list[dict] = []
        lines = [line.strip() for line in horario_raw.split("\n") if line.strip()]

        for line in lines:
            # Normalize: uppercase, collapse internal spaces slightly
            line_up = line.upper().strip()

            # Replace dot-as-colon in time part only (e.g. "18.15" → "18:15")
            # Only replace dots surrounded by digits (avoids G.E. group codes)
            line_up = re.sub(r'(\d)\.(\d)', r'\1:\2', line_up)

            # Remove trailing colon at end of line
            line_up = line_up.rstrip(":")

            # Pattern 1: DAY[: ] HH:MM[ ]-[ ]HH:MM [AM|PM]  (standard and tight)
            # Handles: "LUNES 06:30 - 08:00", "JUVES: 15:55-17:25", "06:30 -08:00"
            # Also handles single trailing AM/PM: "LUNES 03:00-05:00 PM"
            match = re.match(
                r'([A-ZÁÉÍÓÚÑ]+)[:\s]+(\d{1,2}:\d{2})(?:\s*[:\s])?\s*-\s*(\d{1,2}:\d{2})(?:\s*(AM|PM))?',
                line_up,
            )

            # Pattern 2: DAY[: ] HH:MM AM|PM - HH:MM AM|PM  (12-hour format)
            if not match:
                match = re.match(
                    r'([A-ZÁÉÍÓÚÑ]+)[:\s]+(\d{1,2}:\d{2})\s*(AM|PM)\s*-\s*(\d{1,2}:\d{2})\s*(AM|PM)',
                    line_up,
                )
                if match:
                    day_raw = match.group(1)
                    time_start_str = match.group(2)
                    ampm_start = match.group(3)
                    time_end_str = match.group(4)
                    ampm_end = match.group(5)
                    # Convert to 24-hour
                    try:
                        t_start_12 = datetime.strptime(f"{time_start_str} {ampm_start}", "%I:%M %p")
                        t_end_12 = datetime.strptime(f"{time_end_str} {ampm_end}", "%I:%M %p")
                        hora_inicio = t_start_12.strftime("%H:%M")
                        hora_fin = t_end_12.strftime("%H:%M")
                    except ValueError:
                        logger.warning("_parse_horario_string: cannot parse 12h time in: %r", line)
                        continue

                    day_name = DAY_CORRECTIONS.get(day_raw, day_raw)
                    day_lower = unicodedata.normalize("NFD", day_name.lower())
                    day_lower = "".join(
                        c for c in day_lower if unicodedata.category(c) != "Mn"
                    )

                    duracion_minutos = _calc_duration(hora_inicio, hora_fin)
                    slots.append({
                        "dia": day_lower,
                        "hora_inicio": hora_inicio,
                        "hora_fin": hora_fin,
                        "duracion_minutos": duracion_minutos,
                        "horas_academicas": calc_academic_hours(duracion_minutos),
                    })
                    continue

            # Pattern 3: DAY[: ] HH:MM A HH:MM  ("A" as separator)
            if not match:
                match = re.match(
                    r'([A-ZÁÉÍÓÚÑ]+)[:\s]+(\d{1,2}:\d{2})\s+A\s+(\d{1,2}:\d{2})',
                    line_up,
                )

            if not match:
                logger.warning("_parse_horario_string: could not parse line: %r", line)
                continue

            day_raw = match.group(1)
            hora_inicio = match.group(2)
            hora_fin = match.group(3)

            # Validate both times are full HH:MM (reject "08:10 - 40")
            if not re.match(r'^\d{1,2}:\d{2}$', hora_fin):
                logger.warning(
                    "_parse_horario_string: incomplete end time in: %r — skipping", line
                )
                continue

            # Pad single-digit hours: "8:00" → "08:00"
            if len(hora_inicio) == 4:
                hora_inicio = "0" + hora_inicio
            if len(hora_fin) == 4:
                hora_fin = "0" + hora_fin

            # Handle single trailing AM/PM from Pattern 1 group 4
            # e.g. "LUNES 03:00-05:00 PM" → both times are PM
            # If only end time carries AM/PM, apply it to start time too
            # (university classes don't span across AM/PM boundary)
            trailing_period: str | None = (
                match.group(4)
                if (match.lastindex is not None and match.lastindex >= 4)
                else None
            )
            if trailing_period:
                try:
                    start_h, start_m = map(int, hora_inicio.split(":"))
                    end_h, end_m = map(int, hora_fin.split(":"))
                    if trailing_period == "PM":
                        if start_h < 12:
                            start_h += 12
                        if end_h < 12:
                            end_h += 12
                    elif trailing_period == "AM":
                        if start_h == 12:
                            start_h = 0
                        if end_h == 12:
                            end_h = 0
                    hora_inicio = f"{start_h:02d}:{start_m:02d}"
                    hora_fin = f"{end_h:02d}:{end_m:02d}"
                except (ValueError, AttributeError):
                    logger.warning(
                        "_parse_horario_string: cannot apply AM/PM conversion for: %r", line
                    )

            # Fix day typos
            day_name = DAY_CORRECTIONS.get(day_raw, day_raw)

            # Normalize: remove accents for internal storage
            day_lower = unicodedata.normalize("NFD", day_name.lower())
            day_lower = "".join(
                c for c in day_lower if unicodedata.category(c) != "Mn"
            )

            duracion_minutos = _calc_duration(hora_inicio, hora_fin)

            slots.append({
                "dia": day_lower,
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "duracion_minutos": duracion_minutos,
                "horas_academicas": calc_academic_hours(duracion_minutos),
            })

        return slots

    def load_from_excel(
        self,
        db: Session,
        excel_path: str,
        academic_period: str | None = None,
    ) -> DesignationLoadResult:
        """
        Alternative entry point: parse the Excel directly.

        For now, delegates to load_from_json with the pre-parsed JSON file
        located next to the excel (or in the project root).
        """
        excel_p = Path(excel_path)
        # Convention: JSON lives next to the Excel with a fixed name
        json_path = excel_p.parent / "designacion_new.json"
        logger.info(
            "load_from_excel called — delegating to load_from_json (%s)", json_path
        )
        return self.load_from_json(db=db, json_path=str(json_path), academic_period=academic_period)

    def link_teachers_by_name(
        self,
        db: Session,
        ci_name_map: dict[str, str],
    ) -> int:
        """
        Promote TEMP CI teachers to real CIs using biometric data.

        Parameters
        ----------
        ci_name_map : dict[str, str]
            Mapping  ``{ci: full_name}``  obtained from the biometric parser.

        Returns
        -------
        int
            Number of teachers whose CI was successfully updated.

        Algorithm
        ---------
        For each TEMP teacher (CI starts with "TEMP-"):
          1. Search ci_name_map for a name that passes ``names_match()``.
          2. If found:
             a. Update Teacher.ci = real_ci  (and full_name if empty).
             b. Cascade-update Designation.teacher_ci via ORM relationship.
          3. If not found: leave as TEMP and log a warning.
        """
        temp_teachers: list[Teacher] = (
            db.query(Teacher)
            .filter(Teacher.ci.like("TEMP-%"))
            .all()
        )

        if not temp_teachers:
            logger.info("link_teachers_by_name: no TEMP teachers found — nothing to do")
            return 0

        updated = 0

        try:
            for teacher in temp_teachers:
                matched_ci: str | None = None
                matched_name: str | None = None

                for real_ci, real_name in ci_name_map.items():
                    if names_match(teacher.full_name, real_name):
                        matched_ci = real_ci
                        matched_name = real_name
                        break

                if matched_ci is None:
                    logger.warning(
                        "link_teachers_by_name: no match for TEMP teacher '%s' (%s)",
                        teacher.full_name,
                        teacher.ci,
                    )
                    continue

                existing = db.query(Teacher).filter(Teacher.ci == matched_ci).first()
                if existing:
                    logger.info(
                        "Real CI %s already in DB — merging designations from %s",
                        matched_ci,
                        teacher.ci,
                    )
                    self._merge_temp_teacher_into_existing(
                        db=db,
                        temp_teacher=teacher,
                        real_teacher=existing,
                    )
                else:
                    old_ci = teacher.ci

                    # Strategy: create a new Teacher row with the real CI first,
                    # then migrate all FK references, then delete the TEMP teacher.
                    # This avoids the PostgreSQL "cannot update PK with non-deferrable
                    # FK constraints" problem.
                    real_teacher = Teacher(
                        ci=matched_ci,
                        full_name=matched_name or teacher.full_name,
                        email=teacher.email,
                        phone=teacher.phone,
                        gender=teacher.gender,
                        external_permanent=teacher.external_permanent,
                        academic_level=teacher.academic_level,
                        profession=teacher.profession,
                        specialty=teacher.specialty,
                        bank=teacher.bank,
                        account_number=teacher.account_number,
                        sap_code=teacher.sap_code,
                        invoice_retention=teacher.invoice_retention,
                    )
                    db.add(real_teacher)
                    db.flush()  # insert real teacher row so FK target exists

                    # Migrate all referencing rows to the new real CI
                    db.query(AttendanceRecord).filter(
                        AttendanceRecord.teacher_ci == old_ci
                    ).update({"teacher_ci": matched_ci}, synchronize_session=False)
                    db.query(BiometricRecord).filter(
                        BiometricRecord.teacher_ci == old_ci
                    ).update({"teacher_ci": matched_ci}, synchronize_session=False)
                    db.query(Designation).filter(
                        Designation.teacher_ci == old_ci
                    ).update({"teacher_ci": matched_ci}, synchronize_session=False)
                    # Also migrate users and detail_requests so login CI stays consistent
                    db.execute(
                        text("UPDATE users SET teacher_ci = :new WHERE teacher_ci = :old"),
                        {"new": matched_ci, "old": old_ci},
                    )
                    db.execute(
                        text("UPDATE users SET ci = :new WHERE ci = :old AND role = 'docente'"),
                        {"new": matched_ci, "old": old_ci},
                    )
                    db.execute(
                        text("UPDATE detail_requests SET teacher_ci = :new WHERE teacher_ci = :old"),
                        {"new": matched_ci, "old": old_ci},
                    )

                    # Now safe to delete the TEMP teacher (no more FK refs)
                    db.delete(teacher)
                    db.flush()

                updated += 1
                logger.info(
                    "Linked '%s': TEMP → %s", matched_name or teacher.full_name, matched_ci
                )

            db.commit()
        except Exception:
            db.rollback()
            raise

        logger.info("link_teachers_by_name: updated %d teachers", updated)
        return updated

    def get_teacher_designations(
        self,
        db: Session,
        teacher_ci: str,
    ) -> list[Designation]:
        """Return all Designation rows for a given teacher CI."""
        return (
            db.query(Designation)
            .filter(Designation.teacher_ci == teacher_ci)
            .all()
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_create_teacher(
        self,
        db: Session,
        full_name: str,
        name_to_ci_cache: dict[str, str],
        result: DesignationLoadResult,
    ) -> str:
        """
        Return the CI for a teacher, creating a TEMP record if necessary.

        Uses an in-memory cache keyed by normalised name so that multiple
        designations for the same teacher don't cause redundant DB hits or
        duplicate inserts within a single load run.
        """
        normalised = normalize_name(full_name)
        temp_ci = _make_temp_ci(full_name)

        if normalised in name_to_ci_cache:
            result.teachers_reused += 1
            return name_to_ci_cache[normalised]

        existing_by_name = self._find_teacher_by_normalized_name(db, normalised)
        if existing_by_name is not None:
            if not existing_by_name.ci.startswith("TEMP-") and existing_by_name.ci != temp_ci:
                warning = (
                    f"Posible homónimo: '{full_name}' reutiliza CI real '{existing_by_name.ci}' "
                    f"en lugar de TEMP '{temp_ci}'"
                )
                logger.warning(warning)
                result.warnings.append(warning)
            result.teachers_reused += 1
            name_to_ci_cache[normalised] = existing_by_name.ci
            return existing_by_name.ci

        # Check DB (in case a previous load already inserted this teacher)
        existing = db.query(Teacher).filter(Teacher.ci == temp_ci).first()
        if existing:
            result.teachers_reused += 1
            name_to_ci_cache[normalised] = temp_ci
            return temp_ci

        # Create new TEMP teacher
        teacher = Teacher(ci=temp_ci, full_name=full_name)
        db.add(teacher)
        db.flush()  # assign PK without committing the transaction

        result.teachers_created += 1
        name_to_ci_cache[normalised] = temp_ci
        logger.debug("Created TEMP teacher: ci=%s name='%s'", temp_ci, full_name)
        return temp_ci

    def _find_teacher_by_normalized_name(
        self,
        db: Session,
        normalised_name: str,
    ) -> Teacher | None:
        """Find an existing teacher by normalized full name."""
        teachers = db.query(Teacher).order_by(Teacher.ci).all()
        for teacher in teachers:
            if normalize_name(teacher.full_name) == normalised_name:
                return teacher
        return None

    def _merge_temp_teacher_into_existing(
        self,
        db: Session,
        temp_teacher: Teacher,
        real_teacher: Teacher,
    ) -> None:
        """Merge a TEMP teacher into an existing real teacher without violating designation uniqueness."""
        temp_designations = (
            db.query(Designation)
            .filter(Designation.teacher_ci == temp_teacher.ci)
            .all()
        )

        real_designations = {
            (designation.subject, designation.semester, designation.group_code): designation
            for designation in db.query(Designation)
            .filter(Designation.teacher_ci == real_teacher.ci)
            .all()
        }

        for temp_designation in temp_designations:
            key = (
                temp_designation.subject,
                temp_designation.semester,
                temp_designation.group_code,
            )
            real_designation = real_designations.get(key)

            if real_designation is not None:
                temp_attendance = aliased(AttendanceRecord)
                real_attendance = aliased(AttendanceRecord)

                colliding_temp_attendance_ids = [
                    row_id
                    for (row_id,) in db.execute(
                        select(temp_attendance.id)
                        .where(temp_attendance.designation_id == temp_designation.id)
                        .where(
                            exists(
                                select(1).where(
                                    and_(
                                        real_attendance.designation_id == real_designation.id,
                                        real_attendance.teacher_ci == real_teacher.ci,
                                        real_attendance.date == temp_attendance.date,
                                        real_attendance.scheduled_start == temp_attendance.scheduled_start,
                                    )
                                )
                            )
                        )
                    )
                ]

                if colliding_temp_attendance_ids:
                    db.query(AttendanceRecord).filter(
                        AttendanceRecord.id.in_(colliding_temp_attendance_ids)
                    ).delete(synchronize_session=False)

                db.query(AttendanceRecord).filter(
                    AttendanceRecord.designation_id == temp_designation.id
                ).update(
                    {
                        "teacher_ci": real_teacher.ci,
                        "designation_id": real_designation.id,
                    },
                    synchronize_session=False,
                )
                db.delete(temp_designation)
                continue

            db.query(Designation).filter(
                Designation.id == temp_designation.id
            ).update({"teacher_ci": real_teacher.ci}, synchronize_session=False)

        db.query(AttendanceRecord).filter(
            AttendanceRecord.teacher_ci == temp_teacher.ci
        ).update({"teacher_ci": real_teacher.ci}, synchronize_session=False)
        db.query(BiometricRecord).filter(
            BiometricRecord.teacher_ci == temp_teacher.ci
        ).update({"teacher_ci": real_teacher.ci}, synchronize_session=False)
        # Also migrate users and detail_requests so login CI stays consistent
        db.execute(
            text("UPDATE users SET teacher_ci = :new WHERE teacher_ci = :old"),
            {"new": real_teacher.ci, "old": temp_teacher.ci},
        )
        db.execute(
            text("UPDATE users SET ci = :new WHERE ci = :old AND role = 'docente'"),
            {"new": real_teacher.ci, "old": temp_teacher.ci},
        )
        db.execute(
            text("UPDATE detail_requests SET teacher_ci = :new WHERE teacher_ci = :old"),
            {"new": real_teacher.ci, "old": temp_teacher.ci},
        )

        db.delete(temp_teacher)
