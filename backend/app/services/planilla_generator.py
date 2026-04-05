"""
Service: Planilla Generator
Generates the monthly teacher payroll Excel file from scratch using openpyxl.

Design Decisions:
  - Generate from scratch (NOT clone template) — gives full control over layout.
  - One row per teacher × subject × group combination.
  - Two output sheets: "Planilla" (summary) and "Detalle" (granular slot view).
  - Payment rate: 70 Bs/academic hour (uniform for all types).
  - Supports payment_overrides with row keys "teacher_ci:designation_id"
    and teacher-total keys {teacher_ci: float} for admin adjustments.
  - Freeze panes at row 7, col 4 (so identity cols + headers always visible).

Payment Model C:
  - Base pay = designation.monthly_hours × 70 Bs
  - Deduct ONLY hours where status=ABSENT
  - Teachers without ANY biometric record get full pay (0 absences assumed)
  - Payable hours = max(0, monthly_hours - absent_hours)

Column Layout:
  A(1)–P(16)  : Identity columns (Semestre, Nombre, CI, ..., Banco)
  Q(17)–AU(47): Days 1–31 of the month (always 31 columns; empty for non-existent days)
  AV(48)      : Hrs Pagables (payable_hours = base - absent)
  AW(49)      : Grupo
  AX(50)      : Materia
  AY(51)      : Pago por Hora (70 Bs)
  AZ(52)      : Hrs Asignadas (base_monthly_hours from designation)
  BA(53)      : Hrs Descontadas (absent_hours)
  BB(54)      : Hrs Asistidas (attended hours, informational)
  BC(55)      : Total Pagable (payable_hours, verification)
  BD(56)      : Total Pago Calculado (payable_hours × 70 Bs)
  BE(57)      : Pago Ajustado (admin override, NULL = use BD)
  BF(58)      : Observaciones

Month name mapping (Spanish):
  1=Enero, 2=Febrero, 3=Marzo, 4=Abril, 5=Mayo, 6=Junio,
  7=Julio, 8=Agosto, 9=Septiembre, 10=Octubre, 11=Noviembre, 12=Diciembre
"""
from __future__ import annotations

import calendar
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord, BiometricUpload
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.teacher import Teacher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RATE_PER_HOUR: float = 70.0  # Bs per academic hour

# Spanish month names
MONTH_NAMES: dict[int, str] = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Day-of-week letter codes (Spanish abbreviations)
# Python weekday(): 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
WEEKDAY_LETTERS: dict[int, str] = {
    0: "L",   # Lunes
    1: "M",   # Martes
    2: "M",   # Miércoles
    3: "J",   # Jueves
    4: "V",   # Viernes
    5: "S",   # Sábado
    6: "D",   # Domingo
}

# Column indices (1-based) for identity fields
COL_SEMESTRE = 1         # A
COL_NOMBRE = 2           # B
COL_CI = 3               # C
COL_EMAIL = 4            # D
COL_PHONE = 5            # E
COL_MATERIA = 6          # F
COL_GRUPO = 7            # G
COL_TIPO_DOCENTE = 8     # H  Externo/Permanente
COL_GENERO = 9           # I
COL_SAP = 10             # J
COL_FACTURA = 11         # K
COL_CUENTA = 12          # L
COL_NIVEL_ACAD = 13      # M
COL_PROFESION = 14       # N
COL_ESPECIALIDAD = 15    # O
COL_BANCO = 16           # P

# Day columns: Q(17) = day 1 ... AU(47) = day 31
DAY_COL_START = 17       # Q
DAY_COL_END = 47         # AU  (DAY_COL_START + 30)

# Summary columns (after days)
COL_TOTAL_HORAS = 48     # AV
COL_GRUPO_RESUMEN = 49   # AW
COL_MATERIA_RESUMEN = 50 # AX
COL_PAGO_HORA = 51       # AY
COL_HRS_TEORIA = 52      # AZ
COL_HRS_PRACT_INT = 53   # BA
COL_HRS_PRACT_EXT = 54   # BB
COL_TOTAL_HRS_CHECK = 55 # BC
COL_PAGO_CALCULADO = 56  # BD
COL_PAGO_AJUSTADO = 57   # BE
COL_OBSERVACIONES = 58   # BF

TOTAL_COLS = 58  # BF

# Row layout in the worksheet
ROW_TITLE = 1
ROW_UNIVERSITY = 2
ROW_EMPTY = 3
ROW_SECTION_HEADERS = 4   # Merged section labels: DATOS DOCENTE | ASISTENCIA ... | RESUMEN
ROW_COL_HEADERS = 5       # Actual column names + day numbers
ROW_WEEKDAY = 6           # Day-of-week letters (L/M/M/J/V/S/D) under day columns
DATA_ROW_START = 7        # First data row

# ---------------------------------------------------------------------------
# Colors / Styles
# ---------------------------------------------------------------------------

COLOR_HEADER_BG = "1F4E79"          # Dark blue — main header
COLOR_SECTION_BG = "2E75B6"         # Medium blue — section headers
COLOR_COL_HEADER_BG = "BDD7EE"      # Light blue — column name headers
COLOR_WEEKDAY_BG = "DEEAF1"         # Very light blue — day-of-week row
COLOR_DAY_CLASS = "E2EFDA"          # Light green — day with classes
COLOR_DAY_ABSENT = "FCE4D6"         # Light red/orange — absent day
COLOR_DAY_LATE = "FFF2CC"           # Light yellow — late day
COLOR_DAY_WEEKEND = "F2F2F2"        # Light gray — weekend/no schedule
COLOR_SUMMARY_BG = "EDEDED"         # Light gray — summary columns header
COLOR_TOTAL_ROW = "FFE699"          # Amber — totals row
COLOR_WHITE = "FFFFFF"

THIN_SIDE = Side(border_style="thin", color="B8B8B8")
MEDIUM_SIDE = Side(border_style="medium", color="595959")

THIN_BORDER = Border(
    left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE
)
MEDIUM_BORDER = Border(
    left=MEDIUM_SIDE, right=MEDIUM_SIDE, top=MEDIUM_SIDE, bottom=MEDIUM_SIDE
)

# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------


@dataclass
class PlanillaRow:
    """One row in the planilla = one teacher × one subject × one group."""

    # Identity
    teacher_ci: str
    designation_id: int
    teacher_name: str
    email: Optional[str]
    phone: Optional[str]
    subject: str
    semester: str
    group_code: str
    teacher_type: Optional[str]        # Externo/Permanente
    gender: Optional[str]
    sap_code: Optional[str]
    invoice_retention: Optional[str]
    account_number: Optional[str]
    academic_level: Optional[str]
    profession: Optional[str]
    specialty: Optional[str]
    bank: Optional[str]

    # Daily hours: {day_of_month (1-31): academic_hours}
    daily_hours: dict[int, int] = field(default_factory=dict)

    # Status per day: {day_of_month: status_string}  — for background coloring
    daily_status: dict[int, str] = field(default_factory=dict)

    # Model C payment fields
    base_monthly_hours: int = 0        # From designation.monthly_hours (assigned load)
    absent_hours: int = 0              # Hours deducted for ABSENT slots
    payable_hours: int = 0             # base_monthly_hours - absent_hours (effective pay)

    # Legacy totals (kept for backward compat and Excel day-column sums)
    total_hours: int = 0               # payable_hours — used for payment calculation
    total_theory_hours: int = 0        # base_monthly_hours shown in summary
    total_practice_internal_hours: int = 0   # absent_hours shown as deductions
    total_practice_external_hours: int = 0   # attended hours (informational)

    # Payment
    rate_per_hour: float = RATE_PER_HOUR
    calculated_payment: float = 0.0

    # Observations
    observations: list[str] = field(default_factory=list)
    late_count: int = 0
    absent_count: int = 0
    has_biometric: bool = True         # False = no biometric records at all → full pay


@dataclass
class DetailRow:
    """One granular class-slot row for the Detalle sheet."""

    ci: str
    teacher_name: str
    date: date
    day_letter: str
    subject: str
    group_code: str
    semester: str
    scheduled_start: str
    scheduled_end: str
    academic_hours: int
    status: str
    observation: Optional[str]


@dataclass
class PlanillaResult:
    """Result returned by PlanillaGenerator.generate()."""

    file_path: str
    month: int
    year: int
    total_teachers: int
    total_rows: int
    total_hours: int
    total_payment: float
    planilla_output_id: Optional[int]
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main generator class
# ---------------------------------------------------------------------------


class PlanillaGenerator:
    """
    Generates the monthly teacher payroll Excel file.

    Usage::

        gen = PlanillaGenerator(output_dir="backend/data/output")
        result = gen.generate(db, month=3, year=2026)
        print(result.file_path)
    """

    def __init__(self, output_dir: str = "backend/data/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        db: Session,
        month: int,
        year: int,
        payment_overrides: Optional[dict[str, float]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> PlanillaResult:
        """
        Generate the planilla Excel for a given month/year.

        Steps:
          1. Build PlanillaRow list from attendance_records + designations + teachers.
          2. Create the Excel workbook (Planilla + Detalle sheets).
          3. Save to file.
          4. Persist/update PlanillaOutput record in DB.
          5. Return PlanillaResult.

        Args:
            db: SQLAlchemy session
            month: Month number (1–12)
            year: Calendar year
            payment_overrides: Optional {"teacher_ci:designation_id": override_amount}
                and/or {teacher_ci: teacher_total_override} for admin adjustments
            start_date: Optional start of attendance window to filter records
            end_date: Optional end of attendance window to filter records

        Returns:
            PlanillaResult with file path and statistics
        """
        if payment_overrides is None:
            payment_overrides = {}

        logger.info(
            "PlanillaGenerator.generate: month=%d year=%d start=%s end=%s",
            month, year, start_date, end_date,
        )

        # Step 1: Build data
        rows, detail_rows, warnings = self._build_planilla_data(
            db, month, year, start_date=start_date, end_date=end_date
        )
        logger.info("Built %d planilla rows with %d detail slots", len(rows), len(detail_rows))

        # Step 2: Create workbook
        wb = self._create_workbook(rows, detail_rows, month, year, payment_overrides)

        # Step 3: Save file
        month_name = MONTH_NAMES.get(month, str(month)).upper()
        filename = f"planilla_{month:02d}_{year}.xlsx"
        file_path = self.output_dir / filename
        wb.save(str(file_path))
        logger.info("Saved planilla to %s", file_path)

        # Step 4: Persist to DB — Model C: total payable hours
        total_hours = sum(r.payable_hours for r in rows)
        total_payment = self._calculate_total_payment(rows, payment_overrides)
        unique_teachers = len({r.teacher_ci for r in rows})

        planilla_output = self._persist_planilla_output(
            db=db,
            month=month,
            year=year,
            file_path=str(file_path),
            total_teachers=unique_teachers,
            total_hours=total_hours,
            total_payment=total_payment,
        )

        return PlanillaResult(
            file_path=str(file_path),
            month=month,
            year=year,
            total_teachers=unique_teachers,
            total_rows=len(rows),
            total_hours=total_hours,
            total_payment=total_payment,
            planilla_output_id=planilla_output.id if planilla_output else None,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Data building
    # ------------------------------------------------------------------

    def _build_planilla_data(
        self,
        db: Session,
        month: int,
        year: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> tuple[list[PlanillaRow], list[DetailRow], list[str]]:
        """
        Build PlanillaRow and DetailRow lists from DB data.

        Model C logic:
          - Iterates ALL designations (not just those with attendance records).
          - Teachers WITHOUT any biometric record for this period get full pay.
          - Teachers WITH biometric records: deduct only ABSENT hours from monthly_hours.

        Args:
            start_date: When provided, attendance records are filtered to >= start_date.
            end_date:   When provided, attendance records are filtered to <= end_date.
        """
        warnings: list[str] = []

        # ── Step 1: Load ALL designations ──────────────────────────────
        all_designations: list[Designation] = db.query(Designation).all()

        if not all_designations:
            warnings.append("No hay designaciones en la base de datos")
            return [], [], warnings

        # ── Step 2: Load attendance records for this period ─────────────
        att_query = db.query(AttendanceRecord).filter(
            AttendanceRecord.month == month,
            AttendanceRecord.year == year,
        )
        if start_date is not None:
            att_query = att_query.filter(AttendanceRecord.date >= start_date)
        if end_date is not None:
            att_query = att_query.filter(AttendanceRecord.date <= end_date)

        att_records: list[AttendanceRecord] = (
            att_query
            .order_by(AttendanceRecord.teacher_ci, AttendanceRecord.date)
            .all()
        )

        if not att_records:
            logger.info(
                "No attendance records found for %d/%d — all docentes get full pay (Model C)",
                month,
                year,
            )
            warnings.append(
                f"Sin registros de asistencia para {MONTH_NAMES.get(month)} {year} — "
                f"todos los docentes recibirán pago completo (sin biométrico)"
            )

        # ── Step 3: Index attendance by (teacher_ci, designation_id) ───
        att_index: dict[tuple[str, int], list[AttendanceRecord]] = {}
        for rec in att_records:
            key = (rec.teacher_ci, rec.designation_id)
            att_index.setdefault(key, []).append(rec)

        # ── Step 3b: Determine which teachers have REAL biometric data ──
        # CRITICAL: Scoped to this specific month/year period so that a teacher
        # with biometric data in March is NOT treated as "has bio" in April.
        # We join to BiometricUpload to filter by month+year.
        cis_with_biometric: set[str] = {
            row[0]
            for row in db.query(BiometricRecord.teacher_ci)
            .join(BiometricUpload, BiometricRecord.upload_id == BiometricUpload.id)
            .filter(BiometricUpload.month == month, BiometricUpload.year == year)
            .distinct()
            .all()
        }
        logger.info(
            "_build_planilla_data: %d teacher CIs with real biometric records",
            len(cis_with_biometric),
        )

        # ── Step 4: Bulk-load teachers ──────────────────────────────────
        all_teacher_cis = {d.teacher_ci for d in all_designations}
        teachers: dict[str, Teacher] = {
            t.ci: t
            for t in db.query(Teacher).filter(Teacher.ci.in_(all_teacher_cis)).all()
        }

        planilla_rows: list[PlanillaRow] = []
        detail_rows: list[DetailRow] = []

        # ── Step 5: One PlanillaRow per designation ─────────────────────
        for desig in all_designations:
            ci = desig.teacher_ci
            teacher = teachers.get(ci)

            if teacher is None:
                warnings.append(f"Docente CI {ci} no encontrado en la base (designación {desig.id})")
                continue

            key = (ci, desig.id)
            records = att_index.get(key, [])

            # A teacher "has biometric" if ANY attendance record exists for them this month.
            # If they have no attendance records at all, they get full pay.
            has_biometric = ci in cis_with_biometric

            row = self._build_row(teacher, desig, records, has_biometric=has_biometric)
            planilla_rows.append(row)

            # Build detail rows for each attendance slot (only when records exist)
            for rec in records:
                detail_rows.append(
                    DetailRow(
                        ci=ci,
                        teacher_name=teacher.full_name,
                        date=rec.date,
                        day_letter=WEEKDAY_LETTERS[rec.date.weekday()],
                        subject=desig.subject,
                        group_code=desig.group_code,
                        semester=desig.semester,
                        scheduled_start=rec.scheduled_start.strftime("%H:%M"),
                        scheduled_end=rec.scheduled_end.strftime("%H:%M"),
                        academic_hours=rec.academic_hours,
                        status=rec.status,
                        observation=rec.observation,
                    )
                )

        # Sort planilla rows: by teacher name, then subject, then group
        planilla_rows.sort(key=lambda r: (r.teacher_name, r.subject, r.group_code))
        detail_rows.sort(key=lambda r: (r.teacher_name, r.date, r.scheduled_start))

        logger.info(
            "_build_planilla_data: %d rows (%d with biometric, %d without), %d detail records",
            len(planilla_rows),
            len(cis_with_biometric),
            len({d.teacher_ci for d in all_designations} - cis_with_biometric),
            len(detail_rows),
        )
        return planilla_rows, detail_rows, warnings

    def _build_row(
        self,
        teacher: Teacher,
        desig: Designation,
        records: list[AttendanceRecord],
        has_biometric: bool = True,
    ) -> PlanillaRow:
        """
        Build a single PlanillaRow using Payment Model C.

        Model C rules:
          - Base pay = designation.monthly_hours × 70 Bs
          - Deduct ONLY hours where status=ABSENT
          - No biometric at all → full pay (has_biometric=False)
          - attended/late/no_exit hours in daily_hours are for display only
        """
        daily_hours: dict[int, int] = {}
        daily_status: dict[int, str] = {}
        attended_hours = 0   # for informational display only
        absent_hours = 0     # hours to deduct (Model C)
        late_count = 0
        absent_count = 0
        observations: list[str] = []

        for rec in records:
            day = rec.date.day
            hours = rec.academic_hours
            status = rec.status.upper()

            # Accumulate hours for the day (could have multiple slots on same day)
            # For absent slots, academic_hours=0 per engine logic, but we count
            # the SCHEDULED hours via designation — here we show 0 for absent days
            daily_hours[day] = daily_hours.get(day, 0) + hours

            # Track worst status for coloring: ABSENT > LATE > NO_EXIT > ATTENDED
            current_status = daily_status.get(day, "")
            if status == "ABSENT":
                daily_status[day] = "ABSENT"
                absent_count += 1
                # Absent slots have academic_hours=0 in the record; we need to
                # count the slot hours from the designation schedule for deduction.
                # The engine sets academic_hours=0 for ABSENT — we must compute
                # absent_hours from the slot's scheduled hours in schedule_json.
                absent_hours += self._get_slot_hours(desig, rec)
            elif status == "LATE" and current_status != "ABSENT":
                daily_status[day] = "LATE"
                late_count += 1
                attended_hours += hours
            elif status == "NO_EXIT" and current_status not in ("ABSENT", "LATE"):
                daily_status[day] = "NO_EXIT"
                attended_hours += hours
            elif status == "ATTENDED" and not current_status:
                daily_status[day] = "ATTENDED"
                attended_hours += hours

            if rec.observation:
                observations.append(f"Día {day}: {rec.observation}")

        # ── Model C payment calculation ─────────────────────────────────
        base_monthly_hours = desig.monthly_hours or 0

        if not has_biometric:
            # No biometric data at all → full pay, 0 deductions
            absent_hours = 0
            absent_count = 0

        payable_hours = max(0, base_monthly_hours - absent_hours)
        calculated_payment = payable_hours * RATE_PER_HOUR

        # Build observation summary
        obs_parts: list[str] = []
        if not has_biometric:
            obs_parts.append("Sin biométrico — pago completo")
        else:
            if late_count > 0:
                obs_parts.append(f"{late_count} tardanza{'s' if late_count > 1 else ''}")
            if absent_count > 0:
                obs_parts.append(f"{absent_count} ausencia{'s' if absent_count > 1 else ''}")
            if absent_hours > 0:
                obs_parts.append(f"{absent_hours}h descontadas")

        return PlanillaRow(
            teacher_ci=teacher.ci,
            designation_id=desig.id,
            teacher_name=teacher.full_name,
            email=teacher.email,
            phone=teacher.phone,
            subject=desig.subject,
            semester=desig.semester,
            group_code=desig.group_code,
            teacher_type=teacher.external_permanent,
            gender=teacher.gender,
            sap_code=teacher.sap_code,
            invoice_retention=teacher.invoice_retention,
            account_number=teacher.account_number,
            academic_level=teacher.academic_level,
            profession=teacher.profession,
            specialty=teacher.specialty,
            bank=teacher.bank,
            daily_hours=daily_hours,
            daily_status=daily_status,
            # Model C fields
            base_monthly_hours=base_monthly_hours,
            absent_hours=absent_hours,
            payable_hours=payable_hours,
            # Legacy totals mapped to Model C semantics for Excel columns
            total_hours=payable_hours,                        # used for payment sum
            total_theory_hours=base_monthly_hours,            # COL_HRS_TEORIA = assigned
            total_practice_internal_hours=absent_hours,       # COL_HRS_PRACT_INT = deducted
            total_practice_external_hours=attended_hours,     # COL_HRS_PRACT_EXT = attended (info)
            rate_per_hour=RATE_PER_HOUR,
            calculated_payment=calculated_payment,
            observations=obs_parts if obs_parts else [],
            late_count=late_count,
            absent_count=absent_count,
            has_biometric=has_biometric,
        )

    def _get_slot_hours(self, desig: Designation, rec: AttendanceRecord) -> int:
        """
        Find the scheduled academic_hours for an ABSENT slot.

        The engine sets academic_hours=0 for ABSENT records; we must recover
        the scheduled hours from the designation's schedule_json by matching
        the slot's weekday + scheduled_start time (and optionally hora_fin).

        Matching priority:
          1. day-of-week + hora_inicio (most specific — avoids cross-day false match)
          2. hora_inicio only (fallback when schedule_json lacks "dia" field)
        """
        schedule: list[dict] = desig.schedule_json or []
        rec_start_str = rec.scheduled_start.strftime("%H:%M")

        # Map Python weekday (0=Mon…6=Sun) → Spanish lowercase day name
        _WEEKDAY_MAP: dict[int, str] = {
            0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
            4: "viernes", 5: "sábado", 6: "domingo",
        }
        # Also handle common variants without accent
        _WEEKDAY_ALT: dict[int, str] = {
            2: "miercoles", 5: "sabado",
        }
        target_weekday = rec.date.weekday()
        target_day = _WEEKDAY_MAP.get(target_weekday, "")
        target_day_alt = _WEEKDAY_ALT.get(target_weekday, target_day)

        # Pass 1: match by weekday + hora_inicio (most accurate)
        for slot in schedule:
            if slot.get("hora_inicio", "") == rec_start_str:
                slot_dia = slot.get("dia", "").lower()
                if slot_dia in (target_day, target_day_alt):
                    return int(slot.get("horas_academicas", 0))

        # Pass 2: fallback — match by hora_inicio only (slot may lack "dia")
        for slot in schedule:
            if slot.get("hora_inicio", "") == rec_start_str:
                return int(slot.get("horas_academicas", 0))

        logger.debug(
            "Could not find schedule slot for absent record (designation=%d, start=%s, day=%s)",
            desig.id,
            rec_start_str,
            target_day,
        )
        return 0

    # ------------------------------------------------------------------
    # Workbook creation
    # ------------------------------------------------------------------

    def _create_workbook(
        self,
        rows: list[PlanillaRow],
        detail_rows: list[DetailRow],
        month: int,
        year: int,
        payment_overrides: dict[str, float],
    ) -> Workbook:
        """Create the complete Excel workbook with Planilla + Detalle sheets."""
        wb = Workbook()

        # Sheet 1: Planilla principal
        # wb.active is always non-None on a freshly created Workbook
        ws = wb.create_sheet(title="Planilla", index=0)
        # Remove the default empty sheet that Workbook() creates
        if len(wb.worksheets) > 1:
            default_sheet = wb.worksheets[1]
            del wb[default_sheet.title]

        self._write_headers(ws, month, year)
        last_data_row = self._write_data_rows(ws, rows, month, year, payment_overrides)
        self._write_totals_row(ws, rows, last_data_row + 1, payment_overrides)
        self._apply_formatting(ws, last_data_row + 1, month, year)

        # Sheet 2: Detalle granular
        ws_detail = wb.create_sheet(title="Detalle")
        self._write_detail_sheet(ws_detail, detail_rows, month, year)

        return wb

    # ------------------------------------------------------------------
    # Header writing
    # ------------------------------------------------------------------

    def _write_headers(self, ws, month: int, year: int) -> None:
        """
        Write rows 1–6: title, university, empty, section headers, col headers, weekday row.
        Also sets column widths.
        """
        month_name = MONTH_NAMES.get(month, str(month)).upper()
        total_cols = TOTAL_COLS
        last_col_letter = get_column_letter(total_cols)

        # ── Row 1: Title ───────────────────────────────────────────────
        ws.merge_cells(f"A{ROW_TITLE}:{last_col_letter}{ROW_TITLE}")
        title_cell = ws.cell(row=ROW_TITLE, column=1)
        title_cell.value = f"SIPAD — PLANILLA DOCENTE MEDICINA — {month_name} {year}"
        title_cell.font = Font(name="Calibri", size=14, bold=True, color=COLOR_WHITE)
        title_cell.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[ROW_TITLE].height = 24

        # ── Row 2: University ──────────────────────────────────────────
        ws.merge_cells(f"A{ROW_UNIVERSITY}:{last_col_letter}{ROW_UNIVERSITY}")
        univ_cell = ws.cell(row=ROW_UNIVERSITY, column=1)
        univ_cell.value = "Universidad Privada Domingo Savio — Facultad de Medicina"
        univ_cell.font = Font(name="Calibri", size=11, bold=True, color=COLOR_WHITE)
        univ_cell.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        univ_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[ROW_UNIVERSITY].height = 18

        # ── Row 3: Empty (spacer) ──────────────────────────────────────
        ws.row_dimensions[ROW_EMPTY].height = 6

        # ── Row 4: Section headers ─────────────────────────────────────
        self._write_section_headers(ws, month, month_name, year)

        # ── Row 5: Column headers (day numbers + identity names) ───────
        self._write_column_headers(ws, month, year)

        # ── Row 6: Weekday letters under day columns ───────────────────
        self._write_weekday_row(ws, month, year)

        # ── Column widths ──────────────────────────────────────────────
        self._set_column_widths(ws, month, year)

    def _write_section_headers(self, ws, month: int, month_name: str, year: int) -> None:
        """Row 4: Merged section labels."""
        row = ROW_SECTION_HEADERS

        # DATOS DOCENTE (cols A–P)
        ws.merge_cells(
            start_row=row, start_column=COL_SEMESTRE,
            end_row=row, end_column=COL_BANCO
        )
        cell = ws.cell(row=row, column=COL_SEMESTRE)
        cell.value = "DATOS DOCENTE"
        self._style_section_header(cell)

        # ASISTENCIA (cols Q–AU = 17-47)
        _, days_in_month = calendar.monthrange(year, month)
        ws.merge_cells(
            start_row=row, start_column=DAY_COL_START,
            end_row=row, end_column=DAY_COL_END
        )
        cell = ws.cell(row=row, column=DAY_COL_START)
        cell.value = f"ASISTENCIA {month_name} {year}"
        self._style_section_header(cell)

        # RESUMEN Y PAGOS (cols AV–BF = 48-58)
        ws.merge_cells(
            start_row=row, start_column=COL_TOTAL_HORAS,
            end_row=row, end_column=COL_OBSERVACIONES
        )
        cell = ws.cell(row=row, column=COL_TOTAL_HORAS)
        cell.value = "RESUMEN Y PAGOS"
        self._style_section_header(cell)

        ws.row_dimensions[row].height = 20

    def _write_column_headers(self, ws, month: int, year: int) -> None:
        """Row 5: Actual column headers including day numbers."""
        row = ROW_COL_HEADERS

        identity_headers = [
            "Semestre",
            "Apellidos y Nombres",
            "CI",
            "Correo Electrónico",
            "Nro. Celular",
            "Materia",
            "Grupo",
            "Tipo Docente",
            "Género",
            "Código SAP",
            "Factura/Retención",
            "Nro. Cuenta",
            "Nivel Académico",
            "Profesión",
            "Especialidad",
            "Banco",
        ]

        for i, header in enumerate(identity_headers, start=1):
            cell = ws.cell(row=row, column=i)
            cell.value = header
            self._style_col_header(cell)

        # Day number headers (1–31)
        _, days_in_month = calendar.monthrange(year, month)
        for day in range(1, 32):
            col = DAY_COL_START + (day - 1)
            cell = ws.cell(row=row, column=col)
            if day <= days_in_month:
                cell.value = day
            else:
                cell.value = None  # Month doesn't have this day
            self._style_col_header(cell, is_day=True)

        # Summary column headers — Model C semantics
        summary_headers = {
            COL_TOTAL_HORAS: "Hrs\nPagables",        # payable_hours (base - absent)
            COL_GRUPO_RESUMEN: "Grupo",
            COL_MATERIA_RESUMEN: "Materia",
            COL_PAGO_HORA: "Pago\n/Hora",
            COL_HRS_TEORIA: "Hrs\nAsignadas",         # base_monthly_hours (from designation)
            COL_HRS_PRACT_INT: "Hrs\nDescontadas",    # absent_hours (deducted)
            COL_HRS_PRACT_EXT: "Hrs\nAsistidas",      # attended hours (informational)
            COL_TOTAL_HRS_CHECK: "Total\nPagable",    # payable_hours (verification)
            COL_PAGO_CALCULADO: "Total Pago\nCalculado",
            COL_PAGO_AJUSTADO: "Pago\nAjustado",
            COL_OBSERVACIONES: "Observaciones",
        }
        for col, header in summary_headers.items():
            cell = ws.cell(row=row, column=col)
            cell.value = header
            self._style_col_header(cell, wrap=True)

        ws.row_dimensions[row].height = 30

    def _write_weekday_row(self, ws, month: int, year: int) -> None:
        """Row 6: Day-of-week letter under each day column."""
        row = ROW_WEEKDAY
        _, days_in_month = calendar.monthrange(year, month)

        for day in range(1, 32):
            col = DAY_COL_START + (day - 1)
            cell = ws.cell(row=row, column=col)
            if day <= days_in_month:
                d = date(year, month, day)
                cell.value = WEEKDAY_LETTERS[d.weekday()]
                cell.font = Font(name="Calibri", size=8, bold=True, color="595959")
                cell.fill = PatternFill("solid", fgColor=COLOR_WEEKDAY_BG)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = THIN_BORDER

        # Fill non-day columns in this row with empty styled cells
        for col in list(range(1, DAY_COL_START)) + list(range(DAY_COL_END + 1, TOTAL_COLS + 1)):
            cell = ws.cell(row=row, column=col)
            cell.fill = PatternFill("solid", fgColor=COLOR_WEEKDAY_BG)
            cell.border = THIN_BORDER

        ws.row_dimensions[row].height = 14

    def _set_column_widths(self, ws, month: int, year: int) -> None:
        """Set optimized column widths."""
        # Identity columns
        widths = {
            COL_SEMESTRE: 10,
            COL_NOMBRE: 28,
            COL_CI: 10,
            COL_EMAIL: 22,
            COL_PHONE: 12,
            COL_MATERIA: 28,
            COL_GRUPO: 8,
            COL_TIPO_DOCENTE: 12,
            COL_GENERO: 8,
            COL_SAP: 12,
            COL_FACTURA: 12,
            COL_CUENTA: 16,
            COL_NIVEL_ACAD: 14,
            COL_PROFESION: 16,
            COL_ESPECIALIDAD: 16,
            COL_BANCO: 14,
        }
        for col, width in widths.items():
            ws.column_dimensions[get_column_letter(col)].width = width

        # Day columns — narrow
        for day in range(1, 32):
            col = DAY_COL_START + (day - 1)
            ws.column_dimensions[get_column_letter(col)].width = 3.5

        # Summary columns
        summary_widths = {
            COL_TOTAL_HORAS: 8,
            COL_GRUPO_RESUMEN: 8,
            COL_MATERIA_RESUMEN: 22,
            COL_PAGO_HORA: 8,
            COL_HRS_TEORIA: 8,
            COL_HRS_PRACT_INT: 9,
            COL_HRS_PRACT_EXT: 9,
            COL_TOTAL_HRS_CHECK: 8,
            COL_PAGO_CALCULADO: 12,
            COL_PAGO_AJUSTADO: 12,
            COL_OBSERVACIONES: 30,
        }
        for col, width in summary_widths.items():
            ws.column_dimensions[get_column_letter(col)].width = width

    # ------------------------------------------------------------------
    # Data row writing
    # ------------------------------------------------------------------

    def _write_data_rows(
        self,
        ws,
        rows: list[PlanillaRow],
        month: int,
        year: int,
        payment_overrides: dict[str, float],
    ) -> int:
        """Write all data rows. Returns the row number of the last written row."""
        _, days_in_month = calendar.monthrange(year, month)

        for i, data in enumerate(rows):
            row_num = DATA_ROW_START + i
            self._write_data_row(
                ws,
                row_num,
                data,
                month,
                year,
                days_in_month,
                payment_overrides,
                rows,
            )

        last_row = DATA_ROW_START + len(rows) - 1
        return last_row if rows else DATA_ROW_START - 1

    def _write_data_row(
        self,
        ws,
        row_num: int,
        data: PlanillaRow,
        month: int,
        year: int,
        days_in_month: int,
        payment_overrides: dict[str, float],
        all_rows: list[PlanillaRow],
    ) -> None:
        """Write one teacher×designation data row."""
        override = self._get_row_override(data, payment_overrides, all_rows)

        # Alternate row background for readability
        is_even = (row_num - DATA_ROW_START) % 2 == 0
        row_bg = "FFFFFF" if is_even else "F5F8FA"

        base_font = Font(name="Calibri", size=9)
        base_align = Alignment(vertical="center", wrap_text=False)
        base_fill = PatternFill("solid", fgColor=row_bg)

        def write_identity(col: int, value) -> None:
            cell = ws.cell(row=row_num, column=col)
            cell.value = value
            cell.font = base_font
            cell.alignment = base_align
            cell.fill = base_fill
            cell.border = THIN_BORDER

        # Identity columns
        write_identity(COL_SEMESTRE, data.semester)
        write_identity(COL_NOMBRE, data.teacher_name)
        write_identity(COL_CI, data.teacher_ci)
        write_identity(COL_EMAIL, data.email)
        write_identity(COL_PHONE, data.phone)
        write_identity(COL_MATERIA, data.subject)
        write_identity(COL_GRUPO, data.group_code)
        write_identity(COL_TIPO_DOCENTE, data.teacher_type)
        write_identity(COL_GENERO, data.gender)
        write_identity(COL_SAP, data.sap_code)
        write_identity(COL_FACTURA, data.invoice_retention)
        write_identity(COL_CUENTA, data.account_number)
        write_identity(COL_NIVEL_ACAD, data.academic_level)
        write_identity(COL_PROFESION, data.profession)
        write_identity(COL_ESPECIALIDAD, data.specialty)
        write_identity(COL_BANCO, data.bank)

        # Day columns
        for day in range(1, 32):
            col = DAY_COL_START + (day - 1)
            cell = ws.cell(row=row_num, column=col)

            if day > days_in_month:
                # Day doesn't exist in this month — gray out
                cell.fill = PatternFill("solid", fgColor="EFEFEF")
                cell.border = THIN_BORDER
                continue

            hours = data.daily_hours.get(day, 0)
            status = data.daily_status.get(day, "")

            # Determine fill color based on status and day type
            if status == "ABSENT":
                fill_color = COLOR_DAY_ABSENT
            elif status == "LATE":
                fill_color = COLOR_DAY_LATE
            elif status in ("ATTENDED", "NO_EXIT"):
                fill_color = COLOR_DAY_CLASS
            elif hours > 0:
                fill_color = COLOR_DAY_CLASS
            else:
                # No class on this day — check if it's a weekend
                target_date = date(year, month, day)
                if target_date.weekday() >= 5:  # Saturday=5, Sunday=6
                    fill_color = "E8E8E8"   # Slightly darker gray for weekends
                else:
                    fill_color = COLOR_DAY_WEEKEND

            cell.value = hours if hours > 0 else None
            cell.font = Font(name="Calibri", size=9, bold=(hours > 0))
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.fill = PatternFill("solid", fgColor=fill_color)
            cell.border = THIN_BORDER

        # Summary columns
        def write_summary(col: int, value, is_currency: bool = False) -> None:
            cell = ws.cell(row=row_num, column=col)
            cell.value = value
            cell.font = base_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.fill = PatternFill("solid", fgColor="EBF3FB")
            cell.border = THIN_BORDER
            if is_currency:
                cell.number_format = '#,##0.00 "Bs"'

        # Model C column semantics:
        #   COL_TOTAL_HORAS     = payable_hours (base - absent) — primary hours field
        #   COL_HRS_TEORIA      = base_monthly_hours (assigned load from designation)
        #   COL_HRS_PRACT_INT   = absent_hours (hours deducted)
        #   COL_HRS_PRACT_EXT   = attended hours (informational, not used for payment)
        #   COL_TOTAL_HRS_CHECK = payable_hours (verification = base - deducted)
        write_summary(COL_TOTAL_HORAS, data.payable_hours)
        write_summary(COL_GRUPO_RESUMEN, data.group_code)
        write_summary(COL_MATERIA_RESUMEN, data.subject)
        write_summary(COL_PAGO_HORA, data.rate_per_hour, is_currency=True)
        write_summary(COL_HRS_TEORIA, data.base_monthly_hours)
        write_summary(COL_HRS_PRACT_INT, data.absent_hours if data.absent_hours > 0 else None)
        write_summary(COL_HRS_PRACT_EXT, data.total_practice_external_hours if data.total_practice_external_hours > 0 else None)
        write_summary(COL_TOTAL_HRS_CHECK, data.payable_hours)
        write_summary(COL_PAGO_CALCULADO, data.calculated_payment, is_currency=True)

        # Pago Ajustado
        adj_cell = ws.cell(row=row_num, column=COL_PAGO_AJUSTADO)
        adj_cell.value = override if override is not None else None
        adj_cell.font = Font(name="Calibri", size=9, bold=(override is not None), color="C00000" if override is not None else "000000")
        adj_cell.alignment = Alignment(horizontal="center", vertical="center")
        adj_cell.fill = PatternFill("solid", fgColor="FFF0F0" if override is not None else "EBF3FB")
        adj_cell.border = THIN_BORDER
        if override is not None:
            adj_cell.number_format = '#,##0.00 "Bs"'

        # Observations
        obs_cell = ws.cell(row=row_num, column=COL_OBSERVACIONES)
        obs_text = "; ".join(data.observations) if data.observations else ""
        obs_cell.value = obs_text if obs_text else None
        obs_cell.font = Font(name="Calibri", size=8, color="595959")
        obs_cell.alignment = Alignment(vertical="center", wrap_text=True)
        obs_cell.fill = base_fill
        obs_cell.border = THIN_BORDER

        ws.row_dimensions[row_num].height = 15

    # ------------------------------------------------------------------
    # Totals row
    # ------------------------------------------------------------------

    def _write_totals_row(
        self,
        ws,
        rows: list[PlanillaRow],
        totals_row: int,
        payment_overrides: dict[str, float],
    ) -> None:
        """Write the totals row at the bottom of all data rows."""
        if not rows:
            return

        # Model C totals
        total_hours = sum(r.payable_hours for r in rows)                    # total payable hours
        total_theory = sum(r.base_monthly_hours for r in rows)              # total assigned hours
        total_pract_int = sum(r.absent_hours for r in rows)                 # total deducted hours
        total_pract_ext = sum(r.total_practice_external_hours for r in rows)  # total attended (info)
        total_payment = self._calculate_total_payment(rows, payment_overrides)
        total_teachers = len({r.teacher_ci for r in rows})

        totals_fill = PatternFill("solid", fgColor=COLOR_TOTAL_ROW)
        totals_font = Font(name="Calibri", size=9, bold=True)
        totals_align = Alignment(horizontal="center", vertical="center")

        # Label
        ws.merge_cells(
            start_row=totals_row, start_column=1,
            end_row=totals_row, end_column=COL_BANCO
        )
        label_cell = ws.cell(row=totals_row, column=1)
        label_cell.value = f"TOTALES — {total_teachers} docente(s)"
        label_cell.font = totals_font
        label_cell.fill = totals_fill
        label_cell.alignment = Alignment(horizontal="right", vertical="center")
        label_cell.border = THIN_BORDER

        # Day columns — sum per day
        for day in range(1, 32):
            col = DAY_COL_START + (day - 1)
            day_total = sum(r.daily_hours.get(day, 0) for r in rows)
            cell = ws.cell(row=totals_row, column=col)
            cell.value = day_total if day_total > 0 else None
            cell.font = totals_font
            cell.alignment = totals_align
            cell.fill = totals_fill
            cell.border = THIN_BORDER

        # Summary totals
        def write_total(col: int, value, is_currency: bool = False) -> None:
            cell = ws.cell(row=totals_row, column=col)
            cell.value = value
            cell.font = totals_font
            cell.alignment = totals_align
            cell.fill = totals_fill
            cell.border = THIN_BORDER
            if is_currency:
                cell.number_format = '#,##0.00 "Bs"'

        write_total(COL_TOTAL_HORAS, total_hours)
        write_total(COL_GRUPO_RESUMEN, None)
        write_total(COL_MATERIA_RESUMEN, None)
        write_total(COL_PAGO_HORA, None)
        write_total(COL_HRS_TEORIA, total_theory)
        write_total(COL_HRS_PRACT_INT, total_pract_int)
        write_total(COL_HRS_PRACT_EXT, total_pract_ext)
        write_total(COL_TOTAL_HRS_CHECK, total_hours)
        write_total(COL_PAGO_CALCULADO, total_payment, is_currency=True)
        write_total(COL_PAGO_AJUSTADO, None)
        write_total(COL_OBSERVACIONES, None)

        ws.row_dimensions[totals_row].height = 18

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _apply_formatting(self, ws, last_row: int, month: int, year: int) -> None:
        """Apply freeze panes and print settings."""
        # Freeze panes: rows 1-6 (headers) and cols 1-3 (CI + name columns)
        ws.freeze_panes = ws.cell(row=DATA_ROW_START, column=COL_CI + 1)

        # Print settings
        ws.print_title_rows = f"1:{ROW_WEEKDAY}"
        ws.print_title_cols = f"A:{get_column_letter(COL_BANCO)}"
        ws.sheet_view.showGridLines = True

        # Auto-filter on column headers row
        if last_row >= DATA_ROW_START:
            ws.auto_filter.ref = (
                f"A{ROW_COL_HEADERS}:{get_column_letter(TOTAL_COLS)}{last_row}"
            )

    # ------------------------------------------------------------------
    # Detail sheet
    # ------------------------------------------------------------------

    def _write_detail_sheet(
        self,
        ws,
        detail_rows: list[DetailRow],
        month: int,
        year: int,
    ) -> None:
        """
        Write the Detalle sheet with granular class-slot data.

        Columns: CI | Docente | Fecha | Día | Materia | Grupo | Semestre |
                 Hora Inicio | Hora Fin | Hrs Académicas | Estado | Observación
        """
        month_name = MONTH_NAMES.get(month, str(month)).upper()
        total_detail_cols = 12

        # Title
        ws.merge_cells(f"A1:L1")
        title = ws.cell(row=1, column=1)
        title.value = f"DETALLE DE ASISTENCIA — {month_name} {year}"
        title.font = Font(name="Calibri", size=12, bold=True, color=COLOR_WHITE)
        title.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        title.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 22

        # Column headers
        detail_headers = [
            "CI", "Docente", "Fecha", "Día", "Materia", "Grupo",
            "Semestre", "Hora Inicio", "Hora Fin", "Hrs Académicas", "Estado", "Observación"
        ]
        header_widths = [10, 28, 12, 5, 28, 8, 10, 10, 10, 12, 12, 40]

        for col, (header, width) in enumerate(zip(detail_headers, header_widths), start=1):
            cell = ws.cell(row=2, column=col)
            cell.value = header
            cell.font = Font(name="Calibri", size=9, bold=True, color=COLOR_WHITE)
            cell.fill = PatternFill("solid", fgColor=COLOR_SECTION_BG)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = THIN_BORDER
            ws.column_dimensions[get_column_letter(col)].width = width

        ws.row_dimensions[2].height = 18
        ws.freeze_panes = ws.cell(row=3, column=1)

        # Status color mapping
        status_colors = {
            "ATTENDED": COLOR_DAY_CLASS,
            "LATE": COLOR_DAY_LATE,
            "ABSENT": COLOR_DAY_ABSENT,
            "NO_EXIT": "E6F0FF",   # Light blue
        }

        # Data rows
        for i, detail in enumerate(detail_rows):
            row_num = 3 + i
            is_even = i % 2 == 0
            bg = "FFFFFF" if is_even else "F5F8FA"

            status_upper = detail.status.upper()
            status_bg = status_colors.get(status_upper, bg)

            row_data = [
                detail.ci,
                detail.teacher_name,
                detail.date.strftime("%d/%m/%Y"),
                detail.day_letter,
                detail.subject,
                detail.group_code,
                detail.semester,
                detail.scheduled_start,
                detail.scheduled_end,
                detail.academic_hours,
                detail.status,
                detail.observation or "",
            ]

            for col, value in enumerate(row_data, start=1):
                cell = ws.cell(row=row_num, column=col)
                cell.value = value
                # Status column and hours get special coloring
                if col == 11:  # Estado
                    cell.fill = PatternFill("solid", fgColor=status_bg)
                    cell.font = Font(name="Calibri", size=9, bold=True)
                elif col == 10:  # Hrs Académicas
                    cell.font = Font(name="Calibri", size=9, bold=True)
                    cell.fill = PatternFill("solid", fgColor=bg)
                else:
                    cell.font = Font(name="Calibri", size=9)
                    cell.fill = PatternFill("solid", fgColor=bg)
                cell.alignment = Alignment(
                    horizontal="center" if col in (1, 3, 4, 7, 8, 9, 10, 11) else "left",
                    vertical="center",
                )
                cell.border = THIN_BORDER

            ws.row_dimensions[row_num].height = 14

        # Auto-filter
        if detail_rows:
            last_row = 2 + len(detail_rows)
            ws.auto_filter.ref = f"A2:L{last_row}"

        # Add summary at bottom
        if detail_rows:
            summary_row = 3 + len(detail_rows) + 1
            ws.cell(row=summary_row, column=1).value = "TOTAL REGISTROS:"
            ws.cell(row=summary_row, column=2).value = len(detail_rows)
            total_hrs_cell = ws.cell(row=summary_row, column=10)
            total_hrs_cell.value = sum(d.academic_hours for d in detail_rows)
            total_hrs_cell.font = Font(name="Calibri", size=9, bold=True)
            ws.cell(row=summary_row, column=1).font = Font(name="Calibri", size=9, bold=True)
            ws.cell(row=summary_row, column=2).font = Font(name="Calibri", size=9, bold=True)

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    def _persist_planilla_output(
        self,
        db: Session,
        month: int,
        year: int,
        file_path: str,
        total_teachers: int,
        total_hours: int,
        total_payment: float,
    ) -> Optional[PlanillaOutput]:
        """
        Create or update a PlanillaOutput record in the DB.
        Uses upsert logic: if one already exists for month/year, update it.
        """
        try:
            existing = (
                db.query(PlanillaOutput)
                .filter(
                    PlanillaOutput.month == month,
                    PlanillaOutput.year == year,
                )
                .first()
            )

            if existing:
                existing.file_path = file_path
                existing.total_teachers = total_teachers
                existing.total_hours = total_hours
                existing.total_payment = Decimal(str(total_payment))
                existing.generated_at = datetime.now()
                existing.status = "generated"
                db.flush()
                logger.info("Updated PlanillaOutput id=%d", existing.id)
                return existing
            else:
                output = PlanillaOutput(
                    month=month,
                    year=year,
                    file_path=file_path,
                    total_teachers=total_teachers,
                    total_hours=total_hours,
                    total_payment=Decimal(str(total_payment)),
                    status="generated",
                )
                db.add(output)
                db.flush()
                logger.info("Created PlanillaOutput id=%d", output.id)
                return output

        except Exception as exc:
            logger.exception("Failed to persist PlanillaOutput: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    def _style_section_header(self, cell) -> None:
        """Apply section header style (dark blue bg, white bold text, centered)."""
        cell.font = Font(name="Calibri", size=10, bold=True, color=COLOR_WHITE)
        cell.fill = PatternFill("solid", fgColor=COLOR_SECTION_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER

    def _style_col_header(
        self, cell, is_day: bool = False, wrap: bool = False
    ) -> None:
        """Apply column header style (light blue bg, dark bold text)."""
        cell.font = Font(name="Calibri", size=9, bold=True, color="1F3864")
        cell.fill = PatternFill("solid", fgColor=COLOR_COL_HEADER_BG)
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=wrap,
        )
        cell.border = THIN_BORDER

    def _get_row_override(
        self,
        row: PlanillaRow,
        payment_overrides: dict[str, float],
        all_rows: list[PlanillaRow],
    ) -> Optional[float]:
        """Resolve the display override for a specific row."""
        teacher_rows = [candidate for candidate in all_rows if candidate.teacher_ci == row.teacher_ci]
        allocations = self._get_teacher_override_allocations(teacher_rows, payment_overrides)
        if allocations is not None:
            return allocations.get(row.designation_id)

        return self._resolve_override(row.teacher_ci, row.designation_id, payment_overrides)

    def _resolve_override(
        self,
        teacher_ci: str,
        designation_id: int,
        overrides: dict[str, float],
    ) -> Optional[float]:
        """Resolve override precedence consistently across row and total calculations."""
        row_key = f"{teacher_ci}:{designation_id}"
        if row_key in overrides:
            return overrides[row_key]
        if teacher_ci in overrides:
            return overrides[teacher_ci]
        return None

    def _distribute_teacher_override(
        self,
        row: PlanillaRow,
        teacher_rows: list[PlanillaRow],
        teacher_override: float,
    ) -> float:
        """Distribute a teacher-level override proportionally by row hours."""
        total_hours = sum(candidate.total_hours for candidate in teacher_rows)
        if total_hours <= 0:
            return teacher_override / len(teacher_rows)
        return teacher_override * (row.total_hours / total_hours)

    def _get_teacher_override_allocations(
        self,
        teacher_rows: list[PlanillaRow],
        payment_overrides: dict[str, float],
    ) -> dict[int, float] | None:
        teacher_ci = teacher_rows[0].teacher_ci
        teacher_override = payment_overrides.get(teacher_ci)
        if teacher_override is None:
            return None

        allocations: dict[int, float] = {}
        row_override_total = 0.0
        rows_without_override: list[PlanillaRow] = []

        for row in teacher_rows:
            row_key = f"{row.teacher_ci}:{row.designation_id}"
            row_override = payment_overrides.get(row_key)
            if row_override is not None:
                allocations[row.designation_id] = row_override
                row_override_total += row_override
            else:
                rows_without_override.append(row)

        remaining_override = teacher_override - row_override_total
        if not rows_without_override:
            return allocations

        total_hours = sum(candidate.total_hours for candidate in rows_without_override)
        if total_hours <= 0:
            distributed_value = remaining_override / len(rows_without_override)
            for row in rows_without_override:
                allocations[row.designation_id] = distributed_value
            return allocations

        for row in rows_without_override:
            allocations[row.designation_id] = remaining_override * (row.total_hours / total_hours)

        return allocations

    def _calculate_total_payment(
        self,
        rows: list[PlanillaRow],
        payment_overrides: dict[str, float],
    ) -> float:
        """Apply override precedence consistently across the full planilla."""
        total_payment = 0.0

        rows_by_teacher: dict[str, list[PlanillaRow]] = {}
        for row in rows:
            rows_by_teacher.setdefault(row.teacher_ci, []).append(row)

        teacher_allocations: dict[str, dict[int, float]] = {}
        for teacher_ci, teacher_rows in rows_by_teacher.items():
            allocations = self._get_teacher_override_allocations(teacher_rows, payment_overrides)
            if allocations is not None:
                teacher_allocations[teacher_ci] = allocations

        for row in rows:
            allocation = teacher_allocations.get(row.teacher_ci, {}).get(row.designation_id)
            if allocation is not None:
                total_payment += allocation
            elif f"{row.teacher_ci}:{row.designation_id}" in payment_overrides:
                total_payment += payment_overrides[f"{row.teacher_ci}:{row.designation_id}"]
            else:
                total_payment += row.calculated_payment

        return total_payment


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


def _get_month_from_name(month_name: str) -> int:
    """Reverse lookup: month name → month number. Fallback = 1."""
    name_upper = month_name.upper()
    for num, name in MONTH_NAMES.items():
        if name.upper() == name_upper:
            return num
    return 1
