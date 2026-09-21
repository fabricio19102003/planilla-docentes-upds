from __future__ import annotations

import logging
import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from sqlalchemy.orm import Session, joinedload

from app.models.academic_management import AcademicSchedulePublishedAssignment
from app.models.attendance import AttendanceRecord
from app.models.planilla import PlanillaOutput
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.models.report import Report
from app.services.attendance_source_service import attendance_source_details
from app.services.practice_attendance_source_service import practice_attendance_source_details
from app.services.monetary_snapshot import calculation_snapshot_rows
from app.services import app_settings_service
from app.services.teacher_workload_service import active_period_effective_date, effective_workloads

logger = logging.getLogger(__name__)

# ── UPDS Colors ──────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#003366")
BLUE = colors.HexColor("#0066CC")
SKY = colors.HexColor("#4DA8DA")
LIGHT_BLUE = colors.HexColor("#E8F4FD")
LIGHT_GRAY = colors.HexColor("#F5F5F5")

# ── Paths ────────────────────────────────────────────────────────────────────
ASSETS_DIR = Path(__file__).resolve().parents[2] / "data" / "assets"
ISOLOGO_PATH = ASSETS_DIR / "isologo_upds.png"
LOGO_PATH = ASSETS_DIR / "logo_upds.png"

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


@dataclass(frozen=True)
class AttendanceReportDataset:
    regular_records: list[AttendanceRecord]
    practice_records: list[PracticeAttendanceLog]
    teachers: dict[str, Teacher]
    regular: dict[str, Any]
    practice: dict[str, Any]

    @property
    def total_records(self) -> int:
        return self.regular["total_records"] + self.practice["total_records"]

    @property
    def attended(self) -> int:
        return self.regular["attended"] + self.practice["attended"]

    @property
    def late(self) -> int:
        return self.regular["late"] + self.practice["late"]

    @property
    def absent(self) -> int:
        return self.regular["absent"] + self.practice["absent"]

    @property
    def no_exit(self) -> int:
        return self.regular["no_exit"] + self.practice["no_exit"]

    @property
    def attendance_rate(self) -> float:
        if not self.total_records:
            return 0
        return round((self.attended + self.late + self.no_exit) / self.total_records * 100, 1)

    def as_preview(self) -> dict[str, Any]:
        sample = [
            *_serialize_regular_attendance(self.regular_records),
            *_serialize_practice_attendance(self.practice_records),
        ][:50]
        return {
            "report_type": "attendance",
            "total_records": self.total_records,
            "attended": self.attended,
            "late": self.late,
            "absent": self.absent,
            "no_exit": self.no_exit,
            "attendance_rate": self.attendance_rate,
            "regular": self.regular,
            "practice": self.practice,
            "records_sample": sample,
        }


@dataclass(frozen=True)
class ReconciliationReportDataset:
    month: int
    year: int
    teacher_cis: set[str]
    discrepancies: list[dict[str, Any]]
    regular_exclusion_count: int
    practice_exclusion_count: int

    def as_preview(self) -> dict[str, Any]:
        regular_count = sum(1 for row in self.discrepancies if row["source"] == "Regular")
        practice_count = sum(1 for row in self.discrepancies if row["source"] == "Prácticas")
        return {
            "report_type": "reconciliation",
            "month": self.month,
            "year": self.year,
            "total_teachers": len(self.teacher_cis),
            "total_discrepancies": len(self.discrepancies),
            "high_severity": sum(1 for row in self.discrepancies if row["severity"] == "high"),
            "medium_severity": sum(1 for row in self.discrepancies if row["severity"] == "medium"),
            "regular_discrepancies": regular_count,
            "practice_discrepancies": practice_count,
            "regular_exclusion_count": self.regular_exclusion_count,
            "practice_exclusion_count": self.practice_exclusion_count,
            "exclusion_count": self.regular_exclusion_count + self.practice_exclusion_count,
            "discrepancies": self.discrepancies,
        }


def _serialize_regular_attendance(records: list[AttendanceRecord]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        source = attendance_source_details(record)
        rows.append({
            "date": record.date.isoformat() if record.date else None,
            "teacher_ci": record.teacher_ci,
            "record_kind": "regular",
            "source_kind": source.source_kind,
            "source_key": source.source_key,
            "designation_id": source.designation_id,
            "published_schedule_assignment_id": source.published_schedule_assignment_id,
            "subject": source.subject,
            "group_code": source.group_code,
            "semester": source.semester,
            "activity_type": source.activity_type,
            "status": record.status,
            "scheduled_start": record.scheduled_start.strftime("%H:%M"),
            "scheduled_end": record.scheduled_end.strftime("%H:%M"),
            "check_in": record.actual_entry.strftime("%H:%M") if record.actual_entry else None,
            "check_out": record.actual_exit.strftime("%H:%M") if record.actual_exit else None,
            "academic_hours": record.academic_hours,
        })
    return rows


def _serialize_practice_attendance(records: list[PracticeAttendanceLog]) -> list[dict[str, Any]]:
    rows = []
    status_map = {
        "attended": "ATTENDED",
        "present": "ATTENDED",
        "justified": "JUSTIFIED",
        "late": "LATE",
        "absent": "ABSENT",
    }
    for record in records:
        source = practice_attendance_source_details(record)
        rows.append({
            "date": record.date.isoformat() if record.date else None,
            "teacher_ci": record.teacher_ci,
            "record_kind": "practice",
            "source_kind": source.source_kind,
            "source_key": source.source_key,
            "designation_id": source.designation_id,
            "published_schedule_assignment_id": source.published_schedule_assignment_id,
            "subject": source.subject,
            "group_code": source.group_code,
            "semester": source.semester,
            "activity_type": source.activity_type,
            "status": status_map.get(record.status.lower(), record.status.upper()),
            "scheduled_start": record.scheduled_start.strftime("%H:%M"),
            "scheduled_end": record.scheduled_end.strftime("%H:%M"),
            "check_in": record.actual_start.strftime("%H:%M") if record.actual_start else None,
            "check_out": record.actual_end.strftime("%H:%M") if record.actual_end else None,
            "academic_hours": record.academic_hours,
        })
    return rows


def _output_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── Cell helper ──────────────────────────────────────────────────────────────
def _cell(text: str, style: ParagraphStyle) -> Paragraph:
    """Wrap text in a Paragraph so it wraps inside table cells instead of overflowing."""
    return Paragraph(text, style)


# ── Header / Footer ─────────────────────────────────────────────────────────
def _add_header(elements: list, styles: Any, title: str, subtitle: str = "") -> None:
    """Add UPDS branded header with isologo (4 letters) to the document."""
    # Use isologo (square UPDS letters) if available, fallback to horizontal logo
    logo_file = ISOLOGO_PATH if ISOLOGO_PATH.exists() else LOGO_PATH
    if logo_file.exists():
        logo = Image(str(logo_file), width=0.8 * inch, height=0.8 * inch)
        logo.hAlign = "LEFT"
        elements.append(logo)
        elements.append(Spacer(1, 6))

    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=16, textColor=NAVY, spaceAfter=4,
    )
    elements.append(Paragraph(title, title_style))

    if subtitle:
        sub_style = ParagraphStyle(
            "ReportSubtitle", parent=styles["Normal"],
            fontSize=10, textColor=BLUE, spaceAfter=12,
        )
        elements.append(Paragraph(subtitle, sub_style))

    # Divider line
    elements.append(Spacer(1, 4))
    divider_table = Table([[""]], colWidths=["100%"])
    divider_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 2, NAVY),
    ]))
    elements.append(divider_table)
    elements.append(Spacer(1, 12))


def _add_branded_header(elements: list, styles: Any, title: str, subtitle: str = "") -> None:
    """Branded header with UPDS isologo + navy title bar."""
    if ISOLOGO_PATH.exists():
        logo = Image(str(ISOLOGO_PATH), width=2 * cm, height=2 * cm)
        logo.hAlign = "LEFT"
        elements.append(logo)
        elements.append(Spacer(1, 3 * mm))

    # Navy title bar
    title_style = ParagraphStyle(
        "TitleBar", parent=styles["Normal"],
        fontSize=14, textColor=colors.white,
        fontName="Helvetica-Bold", leading=18,
        alignment=TA_LEFT,
    )
    title_table = Table(
        [[Paragraph(title, title_style)]],
        colWidths=["100%"],
    )
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 3 * mm))

    if subtitle:
        sub_style = ParagraphStyle(
            "SubLine", parent=styles["Normal"],
            fontSize=9, textColor=BLUE, spaceAfter=8,
        )
        elements.append(Paragraph(subtitle, sub_style))

    elements.append(Spacer(1, 4))


def _add_footer(
    elements: list,
    styles: Any,
    generated_by_name: str | None = None,
) -> None:
    """Add single-line audit footer with all fields separated by pipes."""
    now = datetime.now()
    parts: list[str] = []

    if generated_by_name:
        parts.append(f"Generado por: {generated_by_name}")
    parts.append(f"Fecha: {now.strftime('%d/%m/%Y %H:%M:%S')}")
    parts.append("SIPAD — Sistema Integrado de Pago Docente")

    footer_text = "  |  ".join(parts)

    elements.append(Spacer(1, 24))

    sep_table = Table([[""]], colWidths=["100%"])
    sep_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.gray),
    ]))
    elements.append(sep_table)
    elements.append(Spacer(1, 4))

    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=7, textColor=colors.gray, alignment=TA_CENTER,
        leading=10,
    )
    elements.append(Paragraph(footer_text, footer_style))


# ── Reusable table cell styles ───────────────────────────────────────────────
def _make_cell_styles(styles: Any) -> dict[str, ParagraphStyle]:
    """Create reusable ParagraphStyles for table cell wrapping."""
    return {
        "header": ParagraphStyle(
            "CellHeader", parent=styles["Normal"],
            fontSize=7, textColor=colors.white,
            fontName="Helvetica-Bold", leading=9,
            alignment=TA_CENTER,
        ),
        "cell": ParagraphStyle(
            "CellNormal", parent=styles["Normal"],
            fontSize=7, leading=9, textColor=colors.HexColor("#333333"),
        ),
        "cell_center": ParagraphStyle(
            "CellCenter", parent=styles["Normal"],
            fontSize=7, leading=9, textColor=colors.HexColor("#333333"),
            alignment=TA_CENTER,
        ),
        "cell_right": ParagraphStyle(
            "CellRight", parent=styles["Normal"],
            fontSize=7, leading=9, textColor=colors.HexColor("#333333"),
            alignment=TA_RIGHT,
        ),
        "cell_bold": ParagraphStyle(
            "CellBold", parent=styles["Normal"],
            fontSize=7, leading=9, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#333333"),
        ),
        "cell_bold_right": ParagraphStyle(
            "CellBoldRight", parent=styles["Normal"],
            fontSize=7, leading=9, fontName="Helvetica-Bold",
            textColor=NAVY, alignment=TA_RIGHT,
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
class ReportGenerator:

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()
        self.cs = _make_cell_styles(self.styles)

    def _filter_planilla_rows(
        self,
        rows: list,
        teacher_ci: str | None = None,
        semester: str | None = None,
        group_code: str | None = None,
        subject: str | None = None,
    ) -> list:
        if teacher_ci:
            rows = [r for r in rows if r.teacher_ci == teacher_ci]
        if semester:
            rows = [r for r in rows if r.semester and r.semester.upper() == semester.upper()]
        if group_code:
            rows = [r for r in rows if r.group_code == group_code]
        if subject:
            rows = [r for r in rows if subject.lower() in r.subject.lower()]
        return rows

    def build_financial_dataset(
        self,
        db: Session,
        month: int,
        year: int,
        teacher_ci: str | None = None,
        semester: str | None = None,
        group_code: str | None = None,
        subject: str | None = None,
    ) -> dict[str, Any]:
        stored = (
            db.query(PlanillaOutput)
            .filter(PlanillaOutput.month == month, PlanillaOutput.year == year)
            .order_by(PlanillaOutput.generated_at.desc()).first()
        )
        practice = (
            db.query(PracticePlanillaOutput)
            .filter(PracticePlanillaOutput.month == month, PracticePlanillaOutput.year == year)
            .order_by(PracticePlanillaOutput.generated_at.desc()).first()
        )
        outputs = [(output, kind) for output, kind in ((stored, "regular"), (practice, "practice")) if output]
        if not outputs:
            calculation_snapshot_rows(None, 0)
        rows = []
        for output, planilla_type in outputs:
            snapshot_rows = calculation_snapshot_rows(
                output.calculation_snapshot,
                output.total_payment,
            )
            for row in snapshot_rows:
                row.planilla_type = planilla_type
            rows.extend(snapshot_rows)
        rows = self._filter_planilla_rows(rows, teacher_ci, semester, group_code, subject)
        rows.sort(key=lambda row: (-row.final_payment, row.teacher_name, row.planilla_type))
        serialized = [{
            "teacher_ci": row.teacher_ci, "teacher_name": row.teacher_name,
            "subject": row.subject, "group_code": row.group_code, "semester": row.semester,
            "source_kind": row.source_kind, "source_id": row.source_id,
            "source_key": row.source_key, "designation_id": row.designation_id,
            "publication_id": row.publication_id,
            "published_block_id": row.published_block_id,
            "published_schedule_assignment_id": row.published_schedule_assignment_id,
            "activity_kind": row.activity_kind,
            "effective_from": row.effective_from, "effective_to": row.effective_to,
            "base_monthly_hours": row.base_monthly_hours, "absent_hours": row.absent_hours,
            "payable_hours": row.payable_hours, "calculated_payment": row.calculated_payment,
            "retention_amount": row.retention_amount, "final_payment": row.final_payment,
            "planilla_type": row.planilla_type,
        } for row in rows]
        return {
            "report_type": "financial", "total_teachers": len({row.teacher_ci for row in rows}),
            "total_designations": len(rows),
            "total_base_hours": sum(row.base_monthly_hours for row in rows),
            "total_absent_hours": sum(row.absent_hours for row in rows),
            "total_payable_hours": sum(row.payable_hours for row in rows),
            "total_gross_payment": sum((row.calculated_payment for row in rows), Decimal("0.00")),
            "total_retention": sum((row.retention_amount for row in rows), Decimal("0.00")),
            "total_payment": sum((row.final_payment for row in rows), Decimal("0.00")),
            "rows": serialized,
        }

    def build_comparative_dataset(
        self,
        db: Session,
        *,
        year: int,
        teacher_ci: str | None = None,
    ) -> dict[str, Any]:
        """Build monthly comparisons exclusively from immutable calculation snapshots."""
        regular_months = {
            month for (month,) in db.query(PlanillaOutput.month)
            .filter(PlanillaOutput.year == year).distinct().all()
        }
        practice_months = {
            month for (month,) in db.query(PracticePlanillaOutput.month)
            .filter(PracticePlanillaOutput.year == year).distinct().all()
        }
        months = sorted(regular_months | practice_months)
        if not months:
            calculation_snapshot_rows(None, 0)

        monthly_data = []
        for month in months:
            dataset = self.build_financial_dataset(
                db,
                month=month,
                year=year,
                teacher_ci=teacher_ci,
            )
            monthly_data.append({
                "month": month,
                "month_name": MONTH_NAMES.get(month, str(month)),
                "teachers": dataset["total_teachers"],
                "base_hours": dataset["total_base_hours"],
                "absent_hours": dataset["total_absent_hours"],
                "payable_hours": dataset["total_payable_hours"],
                "total_payment": dataset["total_payment"],
            })
        return {
            "report_type": "comparative",
            "year": year,
            "months": monthly_data,
            "grand_total": sum(
                (item["total_payment"] for item in monthly_data), Decimal("0.00")
            ),
        }

    # ── Financial Report ─────────────────────────────────────────────────────
    def generate_financial_report(
        self,
        db: Session,
        month: int,
        year: int,
        teacher_ci: str | None = None,
        semester: str | None = None,
        group_code: str | None = None,
        subject: str | None = None,
        generated_by: int | None = None,
        generated_by_name: str | None = None,
    ) -> Report:
        dataset = self.build_financial_dataset(
            db, month=month, year=year, teacher_ci=teacher_ci,
            semester=semester, group_code=group_code, subject=subject,
        )
        rows = [SimpleNamespace(**row) for row in dataset["rows"] if row["planilla_type"] == "regular"]
        practice_rows = [SimpleNamespace(**row) for row in dataset["rows"] if row["planilla_type"] == "practice"]
        all_rows = rows + practice_rows

        filter_parts = [f"{MONTH_NAMES.get(month, str(month))} {year}"]
        if teacher_ci:
            teacher_name = next((row.teacher_name for row in all_rows), teacher_ci)
            filter_parts.append(f"Docente: {teacher_name}")
        if semester:
            filter_parts.append(f"Semestre: {semester}")
        if group_code:
            filter_parts.append(f"Grupo: {group_code}")
        if subject:
            filter_parts.append(f"Materia: {subject}")

        title = "Reporte Financiero"
        subtitle = " · ".join(filter_parts)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_financiero_{timestamp}.pdf"
        filepath = _output_dir() / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=20 * mm,
        )
        elements: list = []
        cs = self.cs

        _add_branded_header(elements, self.styles, title, subtitle)

        # ── Summary ──────────────────────────────────────────────────────
        total_gross = dataset["total_gross_payment"]
        total_retention = dataset["total_retention"]
        total_payment = dataset["total_payment"]
        total_base = dataset["total_base_hours"]
        total_absent = dataset["total_absent_hours"]
        total_payable = dataset["total_payable_hours"]
        unique_teachers = dataset["total_teachers"]

        summary_data = [
            [_cell(h, cs["header"]) for h in ["Docentes", "Designaciones", "Hrs Asignadas", "Hrs Ausencia", "Hrs a Pagar", "Bruto (Bs)", "Ret. 13% (Bs)", "Neto (Bs)"]],
            [_cell(v, cs["cell_center"]) for v in [
                str(unique_teachers), str(len(all_rows)), f"{total_base}h", f"{total_absent}h", f"{total_payable}h",
                f"{total_gross:,.2f}", f"{total_retention:,.2f}", f"{total_payment:,.2f}",
            ]],
        ]
        summary_table = Table(summary_data, colWidths=[55, 65, 65, 65, 65, 72, 72, 72])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        # ── Detail table (Paragraph cells = auto-wrap) ───────────────────
        detail_header = [_cell(h, cs["header"]) for h in ["Docente", "Materia", "Grupo", "Hrs Base", "Ausencias", "Hrs Pagar", "Bruto (Bs)", "Ret. 13%", "Neto (Bs)"]]
        detail_data: list = [detail_header]
        for r in sorted(rows, key=lambda x: (-x.final_payment, x.teacher_name)):
            source_label = "Publicado" if r.source_kind == "published" else "Legado"
            detail_data.append([
                _cell(r.teacher_name, cs["cell"]),
                _cell(f"{r.subject}<br/><font size='6'>{source_label}</font>", cs["cell"]),
                _cell(r.group_code, cs["cell_center"]),
                _cell(str(r.base_monthly_hours), cs["cell_center"]),
                _cell(str(r.absent_hours) if r.absent_hours > 0 else "0", cs["cell_center"]),
                _cell(str(r.payable_hours), cs["cell_center"]),
                _cell(f"{r.calculated_payment:,.2f}", cs["cell_right"]),
                _cell(f"{r.retention_amount:,.2f}" if r.retention_amount > 0 else "—", cs["cell_center"]),
                _cell(f"{r.final_payment:,.2f}", cs["cell_bold_right"]),
            ])
        if practice_rows:
            detail_data.append([
                _cell("Prácticas Internas", cs["cell_bold"]), _cell("", cs["cell"]), _cell("", cs["cell_center"]),
                _cell("", cs["cell_center"]), _cell("", cs["cell_center"]), _cell("", cs["cell_center"]),
                _cell("", cs["cell_right"]), _cell("", cs["cell_center"]), _cell("", cs["cell_bold_right"]),
            ])
            for r in sorted(practice_rows, key=lambda x: (-x.final_payment, x.teacher_name)):
                source_label = "Publicado" if r.source_kind == "published" else "Legado"
                detail_data.append([
                    _cell(r.teacher_name, cs["cell"]),
                    _cell(f"{r.subject} (Prácticas)<br/><font size='6'>{source_label}</font>", cs["cell"]),
                    _cell(r.group_code, cs["cell_center"]),
                    _cell(str(r.base_monthly_hours), cs["cell_center"]),
                    _cell(str(r.absent_hours) if r.absent_hours > 0 else "0", cs["cell_center"]),
                    _cell(str(r.payable_hours), cs["cell_center"]),
                    _cell(f"{r.calculated_payment:,.2f}", cs["cell_right"]),
                    _cell(f"{r.retention_amount:,.2f}" if r.retention_amount > 0 else "—", cs["cell_center"]),
                    _cell(f"{r.final_payment:,.2f}", cs["cell_bold_right"]),
                ])

        col_widths = [100, 95, 33, 38, 44, 44, 60, 48, 60]
        detail_table = Table(detail_data, colWidths=col_widths, repeatRows=1)
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ]))
        elements.append(detail_table)

        _add_footer(elements, self.styles, generated_by_name)
        doc.build(elements)

        report = Report(
            report_type="financial", title=title, description=subtitle,
            filters={"month": month, "year": year, "teacher_ci": teacher_ci, "semester": semester, "group_code": group_code, "subject": subject},
            file_path=str(filepath), file_size=filepath.stat().st_size,
            generated_by=generated_by, status="generated",
        )
        db.add(report)
        db.flush()
        logger.info("Generated financial report: %s (%d rows)", filename, len(all_rows))
        return report

    def build_attendance_dataset(
        self,
        db: Session,
        *,
        month: int,
        year: int,
        teacher_ci: str | None = None,
        semester: str | None = None,
        group_code: str | None = None,
        subject: str | None = None,
    ) -> AttendanceReportDataset:
        regular_query = (
            db.query(AttendanceRecord)
            .options(
                joinedload(AttendanceRecord.designation),
                joinedload(AttendanceRecord.published_schedule_assignment).joinedload(
                    AcademicSchedulePublishedAssignment.block
                ),
            )
            .filter(AttendanceRecord.month == month, AttendanceRecord.year == year)
        )
        practice_query = db.query(PracticeAttendanceLog).options(
            joinedload(PracticeAttendanceLog.designation),
            joinedload(PracticeAttendanceLog.published_schedule_assignment).joinedload(
                AcademicSchedulePublishedAssignment.block
            ),
        ).filter(
            PracticeAttendanceLog.date >= date(year, month, 1),
            PracticeAttendanceLog.date <= date(year, month, calendar.monthrange(year, month)[1]),
        )
        if teacher_ci:
            regular_query = regular_query.filter(AttendanceRecord.teacher_ci == teacher_ci)
            practice_query = practice_query.filter(PracticeAttendanceLog.teacher_ci == teacher_ci)

        regular_records = regular_query.order_by(
            AttendanceRecord.teacher_ci, AttendanceRecord.date, AttendanceRecord.scheduled_start
        ).all()
        practice_records = practice_query.order_by(
            PracticeAttendanceLog.teacher_ci,
            PracticeAttendanceLog.date,
            PracticeAttendanceLog.scheduled_start,
        ).all()

        def matches(source: Any) -> bool:
            return (
                (not semester or source.semester.upper() == semester.upper())
                and (not group_code or source.group_code == group_code)
                and (not subject or source.subject.casefold() == subject.casefold())
            )

        regular_records = [
            record for record in regular_records if matches(attendance_source_details(record))
        ]
        practice_records = [
            record for record in practice_records
            if matches(practice_attendance_source_details(record))
        ]
        teacher_cis = {
            *(record.teacher_ci for record in regular_records),
            *(record.teacher_ci for record in practice_records),
        }
        teachers = {
            teacher.ci: teacher
            for teacher in db.query(Teacher).filter(Teacher.ci.in_(teacher_cis)).all()
        } if teacher_cis else {}

        regular = {
            "total_records": len(regular_records),
            "attended": sum(1 for record in regular_records if record.status == "ATTENDED"),
            "late": sum(1 for record in regular_records if record.status == "LATE"),
            "absent": sum(1 for record in regular_records if record.status == "ABSENT"),
            "no_exit": sum(1 for record in regular_records if record.status == "NO_EXIT"),
        }
        practice = {
            "total_records": len(practice_records),
            "attended": sum(
                1 for record in practice_records
                if record.status.lower() in ("attended", "present", "justified")
            ),
            "late": sum(1 for record in practice_records if record.status.lower() == "late"),
            "absent": sum(1 for record in practice_records if record.status.lower() == "absent"),
            "no_exit": 0,
        }
        for summary in (regular, practice):
            total = summary["total_records"]
            summary["attendance_rate"] = round(
                (summary["attended"] + summary["late"] + summary["no_exit"]) / total * 100,
                1,
            ) if total else 0
        return AttendanceReportDataset(
            regular_records=regular_records,
            practice_records=practice_records,
            teachers=teachers,
            regular=regular,
            practice=practice,
        )

    # ── Attendance Report ────────────────────────────────────────────────────
    def generate_attendance_report(
        self,
        db: Session,
        month: int,
        year: int,
        teacher_ci: str | None = None,
        semester: str | None = None,
        group_code: str | None = None,
        subject: str | None = None,
        generated_by: int | None = None,
        generated_by_name: str | None = None,
    ) -> Report:
        dataset = self.build_attendance_dataset(
            db,
            month=month,
            year=year,
            teacher_ci=teacher_ci,
            semester=semester,
            group_code=group_code,
            subject=subject,
        )
        records = dataset.regular_records
        practice_records = dataset.practice_records
        teachers = dataset.teachers

        filter_parts = [f"{MONTH_NAMES.get(month, str(month))} {year}"]
        if teacher_ci and teacher_ci in teachers:
            filter_parts.append(f"Docente: {teachers[teacher_ci].full_name}")
        if semester:
            filter_parts.append(f"Semestre: {semester}")
        if group_code:
            filter_parts.append(f"Grupo: {group_code}")
        if subject:
            filter_parts.append(f"Materia: {subject}")

        title = "Reporte de Asistencia"
        subtitle = " · ".join(filter_parts)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_asistencia_{timestamp}.pdf"
        filepath = _output_dir() / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=20 * mm,
        )
        elements: list = []
        cs = self.cs

        _add_branded_header(elements, self.styles, title, subtitle)

        # ── Summary ──────────────────────────────────────────────────────
        attended = dataset.attended
        late = dataset.late
        absent = dataset.absent
        no_exit = dataset.no_exit
        total = dataset.total_records
        rate = dataset.attendance_rate

        summary_data = [
            [_cell(h, cs["header"]) for h in ["Total Registros", "Asistidos", "Tardanzas", "Sin Salida", "Ausencias", "Tasa Asistencia"]],
            [_cell(v, cs["cell_center"]) for v in [str(total), str(attended), str(late), str(no_exit), str(absent), f"{rate:.1f}%"]],
        ]
        summary_table = Table(summary_data, colWidths=[80, 70, 70, 70, 70, 80])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        # ── Detail table ─────────────────────────────────────────────────
        STATUS_LABELS = {"ATTENDED": "Asistido", "LATE": "Tardanza", "ABSENT": "Ausente", "NO_EXIT": "Sin salida"}
        detail_header = [_cell(h, cs["header"]) for h in ["Fecha", "Docente", "Materia", "Grupo", "Estado", "Entrada", "Salida", "Hrs"]]
        detail_data: list = [detail_header]

        for r in records:
            source = attendance_source_details(r)
            teacher = teachers.get(r.teacher_ci)
            status_label = STATUS_LABELS.get(r.status, r.status)

            # Choose cell style for status column based on status
            if r.status == "ABSENT":
                status_style = ParagraphStyle("StatusAbsent", parent=cs["cell_center"], textColor=colors.HexColor("#DC2626"), fontName="Helvetica-Bold")
            elif r.status == "LATE":
                status_style = ParagraphStyle("StatusLate", parent=cs["cell_center"], textColor=colors.HexColor("#D97706"), fontName="Helvetica-Bold")
            else:
                status_style = cs["cell_center"]

            detail_data.append([
                _cell(r.date.strftime("%d/%m/%Y") if r.date else "", cs["cell_center"]),
                _cell(teacher.full_name if teacher else r.teacher_ci, cs["cell"]),
                _cell(source.subject, cs["cell"]),
                _cell(source.group_code, cs["cell_center"]),
                _cell(status_label, status_style),
                _cell(r.actual_entry.strftime("%H:%M") if r.actual_entry else "—", cs["cell_center"]),
                _cell(r.actual_exit.strftime("%H:%M") if r.actual_exit else "—", cs["cell_center"]),
                _cell(str(r.academic_hours) if r.academic_hours else "0", cs["cell_center"]),
            ])

        # Portrait A4 ~170mm usable width; 8 cols fitting ~482 points total
        col_widths = [42, 90, 80, 35, 50, 38, 38, 30]
        detail_table = Table(detail_data, colWidths=col_widths, repeatRows=1)

        detail_style_list: list = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, r in enumerate(records):
            row_idx = i + 1
            if r.status == "ABSENT":
                detail_style_list.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#FEE2E2")))
            elif r.status == "LATE":
                detail_style_list.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#FEF3C7")))
            elif row_idx % 2 == 0:
                detail_style_list.append(("BACKGROUND", (0, row_idx), (-1, row_idx), LIGHT_GRAY))

        detail_table.setStyle(TableStyle(detail_style_list))
        elements.append(detail_table)

        elements.append(Spacer(1, 16))
        section_style = ParagraphStyle(
            "PracticeSectionTitle", parent=self.styles["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=NAVY, spaceAfter=4,
        )
        elements.append(Paragraph("Prácticas Internas", section_style))

        practice_header = [_cell(h, cs["header"]) for h in ["Fecha", "Docente", "Materia", "Grupo", "Estado", "Entrada", "Salida", "Hrs"]]
        practice_data: list = [practice_header]
        practice_status_labels = {"attended": "Asistido", "present": "Asistido", "justified": "Justificado", "late": "Tardanza", "absent": "Ausente"}
        for r in practice_records:
            source = practice_attendance_source_details(r)
            teacher = teachers.get(r.teacher_ci)
            status = r.status.lower()
            if status == "absent":
                status_style = ParagraphStyle("PracticeStatusAbsent", parent=cs["cell_center"], textColor=colors.HexColor("#DC2626"), fontName="Helvetica-Bold")
            elif status == "late":
                status_style = ParagraphStyle("PracticeStatusLate", parent=cs["cell_center"], textColor=colors.HexColor("#D97706"), fontName="Helvetica-Bold")
            else:
                status_style = cs["cell_center"]

            practice_data.append([
                _cell(r.date.strftime("%d/%m/%Y") if r.date else "", cs["cell_center"]),
                _cell(teacher.full_name if teacher else r.teacher_ci, cs["cell"]),
                _cell(source.subject, cs["cell"]),
                _cell(source.group_code, cs["cell_center"]),
                _cell(practice_status_labels.get(status, r.status), status_style),
                _cell(r.actual_start.strftime("%H:%M") if r.actual_start else "—", cs["cell_center"]),
                _cell(r.actual_end.strftime("%H:%M") if r.actual_end else "—", cs["cell_center"]),
                _cell(str(r.academic_hours) if r.academic_hours else "0", cs["cell_center"]),
            ])

        practice_table = Table(practice_data, colWidths=col_widths, repeatRows=1)
        practice_style_list: list = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, r in enumerate(practice_records):
            row_idx = i + 1
            status = r.status.lower()
            if status == "absent":
                practice_style_list.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#FEE2E2")))
            elif status == "late":
                practice_style_list.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#FEF3C7")))
            elif row_idx % 2 == 0:
                practice_style_list.append(("BACKGROUND", (0, row_idx), (-1, row_idx), LIGHT_GRAY))
        practice_table.setStyle(TableStyle(practice_style_list))
        elements.append(practice_table)

        _add_footer(elements, self.styles, generated_by_name)
        doc.build(elements)

        report = Report(
            report_type="attendance", title=title, description=subtitle,
            filters={"month": month, "year": year, "teacher_ci": teacher_ci, "semester": semester, "group_code": group_code, "subject": subject},
            file_path=str(filepath), file_size=filepath.stat().st_size,
            generated_by=generated_by, status="generated",
        )
        db.add(report)
        db.flush()
        logger.info("Generated attendance report: %s (%d records)", filename, len(records) + len(practice_records))
        return report

    # ── Comparative Report ───────────────────────────────────────────────────
    def generate_comparative_report(
        self,
        db: Session,
        year: int,
        teacher_ci: str | None = None,
        generated_by: int | None = None,
        generated_by_name: str | None = None,
    ) -> Report:
        monthly_data = self.build_comparative_dataset(
            db,
            year=year,
            teacher_ci=teacher_ci,
        )["months"]

        filter_parts = [f"Año {year}"]
        if teacher_ci:
            t = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
            if t:
                filter_parts.append(f"Docente: {t.full_name}")

        title = "Reporte Comparativo Mensual"
        subtitle = " · ".join(filter_parts)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_comparativo_{timestamp}.pdf"
        filepath = _output_dir() / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=20 * mm,
        )
        elements: list = []
        cs = self.cs

        _add_branded_header(elements, self.styles, title, subtitle)

        comp_header = [_cell(h, cs["header"]) for h in ["Mes", "Docentes", "Hrs Asignadas", "Hrs Ausencia", "Hrs a Pagar", "Total (Bs)"]]
        comp_data: list = [comp_header]
        grand_total = 0.0
        for md in monthly_data:
            comp_data.append([
                _cell(md["month_name"], cs["cell_bold"]),
                _cell(str(md["teachers"]), cs["cell_center"]),
                _cell(f"{md['base_hours']}h", cs["cell_center"]),
                _cell(f"{md['absent_hours']}h", cs["cell_center"]),
                _cell(f"{md['payable_hours']}h", cs["cell_center"]),
                _cell(f"{md['total_payment']:,.2f}", cs["cell_bold_right"]),
            ])
            grand_total += md["total_payment"]

        # Total row
        total_style = ParagraphStyle("TotalCell", parent=cs["header"], fontSize=8)
        total_right = ParagraphStyle("TotalRight", parent=total_style, alignment=TA_RIGHT)
        comp_data.append([
            _cell("TOTAL", total_style), _cell("", total_style), _cell("", total_style),
            _cell("", total_style), _cell("", total_style),
            _cell(f"{grand_total:,.2f}", total_right),
        ])

        comp_table = Table(comp_data, colWidths=[80, 65, 80, 80, 80, 85])
        comp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
            ("BACKGROUND", (0, -1), (-1, -1), NAVY),
        ]))
        elements.append(comp_table)

        _add_footer(elements, self.styles, generated_by_name)
        doc.build(elements)

        report = Report(
            report_type="comparative", title=title, description=subtitle,
            filters={"year": year, "teacher_ci": teacher_ci},
            file_path=str(filepath), file_size=filepath.stat().st_size,
            generated_by=generated_by, status="generated",
        )
        db.add(report)
        db.flush()
        logger.info("Generated comparative report: %s (%d months)", filename, len(monthly_data))
        return report

    # ── Incidence Report ─────────────────────────────────────────────────────
    def generate_incidence_report(
        self,
        db: Session,
        month: int,
        year: int,
        generated_by: int | None = None,
        generated_by_name: str | None = None,
    ) -> Report:
        """Generate an incidence report PDF showing attendance problems."""
        from app.models.biometric import BiometricRecord, BiometricUpload
        from collections import defaultdict

        records = db.query(AttendanceRecord).filter(
            AttendanceRecord.month == month,
            AttendanceRecord.year == year,
        ).all()
        practice_records = db.query(PracticeAttendanceLog).filter(
            PracticeAttendanceLog.date >= date(year, month, 1),
            PracticeAttendanceLog.date <= date(year, month, calendar.monthrange(year, month)[1]),
        ).all()

        bio_cis = {
            r[0] for r in db.query(BiometricRecord.teacher_ci)
            .join(BiometricUpload)
            .filter(BiometricUpload.month == month, BiometricUpload.year == year)
            .distinct().all()
        }

        all_teacher_cis = {record.teacher_ci for record in records}
        practice_teacher_cis = {r.teacher_ci for r in practice_records}

        teachers_without_bio = all_teacher_cis - bio_cis
        teacher_names = {
            t.ci: t.full_name for t in db.query(Teacher).filter(Teacher.ci.in_(all_teacher_cis | practice_teacher_cis)).all()
        } if all_teacher_cis or practice_teacher_cis else {}

        teacher_stats: dict = defaultdict(lambda: {"absences": 0, "lates": 0, "late_minutes_total": 0, "total_slots": 0})
        for r in records:
            ts = teacher_stats[r.teacher_ci]
            ts["total_slots"] += 1
            if r.status == "ABSENT":
                ts["absences"] += 1
            elif r.status == "LATE":
                ts["lates"] += 1
                ts["late_minutes_total"] += r.late_minutes

        practice_stats: dict = defaultdict(lambda: {"absences": 0, "lates": 0, "total_slots": 0})
        for r in practice_records:
            status = r.status.lower()
            if status not in ("absent", "late"):
                continue
            ts = practice_stats[r.teacher_ci]
            ts["total_slots"] += 1
            if status == "absent":
                ts["absences"] += 1
            elif status == "late":
                ts["lates"] += 1

        top_absentees = sorted(
            [{"ci": ci, "name": teacher_names.get(ci, ci), **stats}
             for ci, stats in teacher_stats.items() if stats["absences"] > 0],
            key=lambda x: -x["absences"]
        )[:20]

        top_lates = sorted(
            [{"ci": ci, "name": teacher_names.get(ci, ci), **stats}
             for ci, stats in teacher_stats.items() if stats["lates"] > 0],
            key=lambda x: -x["lates"]
        )[:20]

        without_bio_list = [
            {"ci": ci, "name": teacher_names.get(ci, ci)}
            for ci in sorted(teachers_without_bio)
            if ci in teacher_names
        ]

        total_absences = sum(1 for r in records if r.status == "ABSENT")
        total_lates = sum(1 for r in records if r.status == "LATE")
        total_practice_absences = sum(1 for r in practice_records if r.status.lower() == "absent")
        total_practice_lates = sum(1 for r in practice_records if r.status.lower() == "late")
        practice_incidents = sorted(
            [{"ci": ci, "name": teacher_names.get(ci, ci), **stats}
             for ci, stats in practice_stats.items()],
            key=lambda x: (-(x["absences"] + x["lates"]), x["name"])
        )[:20]

        month_name = MONTH_NAMES.get(month, str(month))
        title = "Reporte de Incidencias"
        subtitle = f"{month_name} {year}"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_incidencias_{timestamp}.pdf"
        filepath = _output_dir() / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=20 * mm,
        )
        elements: list = []
        cs = self.cs

        _add_branded_header(elements, self.styles, title, subtitle)

        RED = colors.HexColor("#dc2626")
        ORANGE = colors.HexColor("#d97706")
        RED_LIGHT = colors.HexColor("#FEE2E2")
        ORANGE_LIGHT = colors.HexColor("#FEF3C7")

        # ── Summary ──────────────────────────────────────────────────────
        summary_data = [
            [_cell(h, cs["header"]) for h in ["Total Registros", "Ausencias", "Tardanzas", "Sin Biométrico"]],
            [_cell(v, cs["cell_center"]) for v in [
                str(len(records) + len(practice_records)),
                str(total_absences + total_practice_absences),
                str(total_lates + total_practice_lates),
                str(len(without_bio_list)),
            ]],
        ]
        summary_table = Table(summary_data, colWidths=[110, 110, 110, 115])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        # ── Top absentees table ───────────────────────────────────────────
        section_style = ParagraphStyle(
            "SectionTitle", parent=self.styles["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=NAVY, spaceAfter=4,
        )
        elements.append(Paragraph("Docentes con más ausencias", section_style))

        if top_absentees:
            abs_header = [_cell(h, cs["header"]) for h in ["Nº", "Docente", "Ausencias", "Total Clases", "% Ausencia"]]
            abs_data: list = [abs_header]
            for idx, row in enumerate(top_absentees, start=1):
                pct = row["absences"] / row["total_slots"] * 100 if row["total_slots"] > 0 else 0
                abs_data.append([
                    _cell(str(idx), cs["cell_center"]),
                    _cell(row["name"], cs["cell"]),
                    _cell(str(row["absences"]), cs["cell_center"]),
                    _cell(str(row["total_slots"]), cs["cell_center"]),
                    _cell(f"{pct:.1f}%", cs["cell_center"]),
                ])
            abs_table = Table(abs_data, colWidths=[25, 230, 70, 80, 70], repeatRows=1)
            abs_style_list: list = [
                ("BACKGROUND", (0, 0), (-1, 0), RED),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, RED_LIGHT]),
            ]
            abs_table.setStyle(TableStyle(abs_style_list))
            elements.append(abs_table)
        else:
            elements.append(Paragraph("Sin ausencias registradas en el período.", cs["cell"]))
        elements.append(Spacer(1, 12))

        # ── Top lates table ───────────────────────────────────────────────
        elements.append(Paragraph("Docentes con más tardanzas", section_style))

        if top_lates:
            late_header = [_cell(h, cs["header"]) for h in ["Nº", "Docente", "Tardanzas", "Min. Promedio"]]
            late_data: list = [late_header]
            for idx, row in enumerate(top_lates, start=1):
                avg_min = row["late_minutes_total"] // row["lates"] if row["lates"] > 0 else 0
                late_data.append([
                    _cell(str(idx), cs["cell_center"]),
                    _cell(row["name"], cs["cell"]),
                    _cell(str(row["lates"]), cs["cell_center"]),
                    _cell(str(avg_min), cs["cell_center"]),
                ])
            late_table = Table(late_data, colWidths=[25, 280, 70, 100], repeatRows=1)
            late_style_list: list = [
                ("BACKGROUND", (0, 0), (-1, 0), ORANGE),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ORANGE_LIGHT]),
            ]
            late_table.setStyle(TableStyle(late_style_list))
            elements.append(late_table)
        else:
            elements.append(Paragraph("Sin tardanzas registradas en el período.", cs["cell"]))
        elements.append(Spacer(1, 12))

        # ── Practice incidences table ─────────────────────────────────────
        elements.append(Paragraph("Incidencias en Prácticas", section_style))

        if practice_incidents:
            practice_header = [_cell(h, cs["header"]) for h in ["Nº", "Docente", "Ausencias", "Tardanzas", "Total Incidencias"]]
            practice_data: list = [practice_header]
            for idx, row in enumerate(practice_incidents, start=1):
                total_incidents = row["absences"] + row["lates"]
                practice_data.append([
                    _cell(str(idx), cs["cell_center"]),
                    _cell(row["name"], cs["cell"]),
                    _cell(str(row["absences"]), cs["cell_center"]),
                    _cell(str(row["lates"]), cs["cell_center"]),
                    _cell(str(total_incidents), cs["cell_center"]),
                ])
            practice_table = Table(practice_data, colWidths=[25, 230, 70, 70, 80], repeatRows=1)
            practice_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ]))
            elements.append(practice_table)
        else:
            elements.append(Paragraph("Sin incidencias de prácticas registradas en el período.", cs["cell"]))
        elements.append(Spacer(1, 12))

        # ── Without biometric table ───────────────────────────────────────
        elements.append(Paragraph("Docentes sin biométrico", section_style))

        if without_bio_list:
            bio_header = [_cell(h, cs["header"]) for h in ["Nº", "Docente", "CI"]]
            bio_data: list = [bio_header]
            for idx, row in enumerate(without_bio_list, start=1):
                bio_data.append([
                    _cell(str(idx), cs["cell_center"]),
                    _cell(row["name"], cs["cell"]),
                    _cell(row["ci"], cs["cell_center"]),
                ])
            bio_table = Table(bio_data, colWidths=[25, 330, 120], repeatRows=1)
            bio_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ]))
            elements.append(bio_table)
        else:
            elements.append(Paragraph("Todos los docentes tienen registro biométrico.", cs["cell"]))

        _add_footer(elements, self.styles, generated_by_name)
        doc.build(elements)

        report = Report(
            report_type="incidence", title=title, description=subtitle,
            filters={"month": month, "year": year},
            file_path=str(filepath), file_size=filepath.stat().st_size,
            generated_by=generated_by, status="generated",
        )
        db.add(report)
        db.flush()
        logger.info("Generated incidence report: %s", filename)
        return report

    def build_reconciliation_dataset(
        self,
        db: Session,
        *,
        month: int,
        year: int,
    ) -> ReconciliationReportDataset:
        attendance = self.build_attendance_dataset(db, month=month, year=year)
        financial_rows = self.build_financial_dataset(db, month=month, year=year)["rows"]
        teacher_cis = {row["teacher_ci"] for row in financial_rows}
        teacher_names = {
            teacher.ci: teacher.full_name
            for teacher in db.query(Teacher).filter(Teacher.ci.in_(teacher_cis)).all()
        } if teacher_cis else {}

        regular_attendance: dict[str, list[AttendanceRecord]] = defaultdict(list)
        for record in attendance.regular_records:
            regular_attendance[record.teacher_ci].append(record)
        practice_attendance: dict[str, list[PracticeAttendanceLog]] = defaultdict(list)
        for record in attendance.practice_records:
            practice_attendance[record.teacher_ci].append(record)
        workloads: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in financial_rows:
            workloads[row["teacher_ci"]].append(row)

        discrepancies: list[dict[str, Any]] = []

        def append_discrepancy(
            *,
            teacher_ci: str,
            teacher_name: str,
            source_label: str,
            expected_hours: int,
            source_keys: list[str],
            records: list[Any],
            practice: bool,
        ) -> None:
            if not source_keys:
                return
            if not records:
                discrepancies.append({
                    "teacher_ci": teacher_ci,
                    "teacher_name": teacher_name,
                    "source": source_label,
                    "type": "Sin registro",
                    "description": (
                        "Sin registros de asistencia de prácticas"
                        if practice else "Sin registros de asistencia regular"
                    ),
                    "expected_hours": expected_hours,
                    "actual_hours": 0,
                    "source_keys": source_keys,
                    "severity": "high",
                })
                return

            if practice:
                absences = sum(1 for record in records if record.status.lower() == "absent")
                attended_hours = sum(
                    record.academic_hours for record in records
                    if record.status.lower() in ("attended", "present", "justified", "late")
                )
            else:
                absences = sum(1 for record in records if record.status == "ABSENT")
                attended_hours = sum(
                    record.academic_hours for record in records
                    if record.status in ("ATTENDED", "LATE")
                )
            absence_rate = absences / len(records)
            if absence_rate > 0.3:
                discrepancies.append({
                    "teacher_ci": teacher_ci,
                    "teacher_name": teacher_name,
                    "source": source_label,
                    "type": "Alta ausencia",
                    "description": (
                        f"Tasa de ausencia en prácticas: {absence_rate*100:.0f}% ({absences}/{len(records)} clases)"
                        if practice
                        else f"Tasa de ausencia regular: {absence_rate*100:.0f}% ({absences}/{len(records)} clases)"
                    ),
                    "expected_hours": expected_hours,
                    "actual_hours": attended_hours,
                    "source_keys": source_keys,
                    "severity": "high" if absence_rate > 0.5 else "medium",
                })
                return
            if expected_hours > 0 and attended_hours < expected_hours * 0.5:
                discrepancies.append({
                    "teacher_ci": teacher_ci,
                    "teacher_name": teacher_name,
                    "source": source_label,
                    "type": "Horas inconsistentes",
                    "description": (
                        f"Horas asistidas en prácticas ({attended_hours}h) < 50% de esperadas ({expected_hours}h)"
                        if practice
                        else f"Horas asistidas regulares ({attended_hours}h) < 50% de esperadas ({expected_hours}h)"
                    ),
                    "expected_hours": expected_hours,
                    "actual_hours": attended_hours,
                    "source_keys": source_keys,
                    "severity": "medium",
                })

        for teacher_ci in sorted(teacher_cis):
            if teacher_ci.startswith("TEMP-"):
                continue
            teacher_rows = workloads.get(teacher_ci, [])
            regular_rows = [row for row in teacher_rows if row["planilla_type"] == "regular"]
            practice_rows = [row for row in teacher_rows if row["planilla_type"] == "practice"]
            teacher_name = teacher_names.get(teacher_ci, teacher_ci)
            append_discrepancy(
                teacher_ci=teacher_ci,
                teacher_name=teacher_name,
                source_label="Regular",
                expected_hours=sum(row["base_monthly_hours"] for row in regular_rows),
                source_keys=[row["source_key"] for row in regular_rows],
                records=regular_attendance.get(teacher_ci, []),
                practice=False,
            )
            append_discrepancy(
                teacher_ci=teacher_ci,
                teacher_name=teacher_name,
                source_label="Prácticas",
                expected_hours=sum(row["base_monthly_hours"] for row in practice_rows),
                source_keys=[row["source_key"] for row in practice_rows],
                records=practice_attendance.get(teacher_ci, []),
                practice=True,
            )

        regular_output = db.query(PlanillaOutput).filter(
            PlanillaOutput.month == month, PlanillaOutput.year == year,
        ).order_by(PlanillaOutput.generated_at.desc()).first()
        practice_output = db.query(PracticePlanillaOutput).filter(
            PracticePlanillaOutput.month == month, PracticePlanillaOutput.year == year,
        ).order_by(PracticePlanillaOutput.generated_at.desc()).first()
        return ReconciliationReportDataset(
            month=month,
            year=year,
            teacher_cis=teacher_cis,
            discrepancies=discrepancies,
            regular_exclusion_count=len(regular_output.excluded_days_json or []) if regular_output else 0,
            practice_exclusion_count=len(practice_output.excluded_days_json or []) if practice_output else 0,
        )

    # ── Reconciliation Report ─────────────────────────────────────────────────
    def generate_reconciliation_report(
        self,
        db: Session,
        month: int,
        year: int,
        generated_by: int | None = None,
        generated_by_name: str | None = None,
    ) -> Report:
        """Generate a reconciliation report comparing designation vs attendance."""
        dataset = self.build_reconciliation_dataset(db, month=month, year=year)
        preview = dataset.as_preview()
        teacher_cis = dataset.teacher_cis
        discrepancies = dataset.discrepancies
        exclusion_count = preview["exclusion_count"]

        month_name = MONTH_NAMES.get(month, str(month))
        title = "Reporte de Conciliación"
        subtitle = f"{month_name} {year}"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_conciliacion_{timestamp}.pdf"
        filepath = _output_dir() / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=20 * mm,
        )
        elements: list = []
        cs = self.cs

        _add_branded_header(elements, self.styles, title, subtitle)

        RED = colors.HexColor("#dc2626")
        ORANGE = colors.HexColor("#d97706")
        PURPLE = colors.HexColor("#7c3aed")

        # ── Summary ───────────────────────────────────────────────────────
        high_count = preview["high_severity"]
        medium_count = preview["medium_severity"]
        regular_count = preview["regular_discrepancies"]
        practice_count = preview["practice_discrepancies"]

        summary_data = [
            [_cell(h, cs["header"]) for h in ["Total Docentes", "Discrepancias Regular", "Discrepancias Prácticas", "Severidad Alta", "Severidad Media"]],
            [_cell(v, cs["cell_center"]) for v in [
                str(len(teacher_cis)), str(regular_count), str(practice_count), str(high_count), str(medium_count),
            ]],
        ]
        summary_table = Table(summary_data, colWidths=[85, 105, 105, 85, 85])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
            ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        if exclusion_count:
            note_style = ParagraphStyle(
                "ExclusionNote", parent=self.styles["Normal"],
                fontSize=8, textColor=colors.HexColor("#78350f"), leading=11,
            )
            note_table = Table(
                [[Paragraph(f"Nota: Esta planilla tiene {exclusion_count} días excluidos que pueden afectar las horas esperadas.", note_style)]],
                colWidths=[465],
            )
            note_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#F59E0B")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            elements.append(note_table)
            elements.append(Spacer(1, 12))

        # ── Discrepancy table ─────────────────────────────────────────────
        if discrepancies:
            disc_header = [_cell(h, cs["header"]) for h in ["Nº", "Docente", "Tipo", "Discrepancia", "Descripción", "Hrs Esperadas", "Hrs Reales", "Severidad"]]
            disc_data: list = [disc_header]

            for idx, row in enumerate(discrepancies, start=1):
                sev = row["severity"]
                if sev == "high":
                    sev_style = ParagraphStyle("SevHigh", parent=cs["cell_center"], textColor=RED, fontName="Helvetica-Bold")
                    sev_label = "Alta"
                else:
                    sev_style = ParagraphStyle("SevMed", parent=cs["cell_center"], textColor=ORANGE, fontName="Helvetica-Bold")
                    sev_label = "Media"

                disc_data.append([
                    _cell(str(idx), cs["cell_center"]),
                    _cell(row["teacher_name"], cs["cell"]),
                    _cell(row["source"], cs["cell_center"]),
                    _cell(row["type"], cs["cell"]),
                    _cell(row["description"], cs["cell"]),
                    _cell(f"{row['expected_hours']}h", cs["cell_center"]),
                    _cell(f"{row['actual_hours']}h", cs["cell_center"]),
                    _cell(sev_label, sev_style),
                ])

            disc_style_list: list = [
                ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
            # Row coloring by severity
            for i, row in enumerate(discrepancies, start=1):
                if row["severity"] == "high":
                    disc_style_list.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FEE2E2")))
                else:
                    disc_style_list.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FEF3C7")))

            disc_table = Table(disc_data, colWidths=[22, 92, 52, 68, 140, 52, 45, 45], repeatRows=1)
            disc_table.setStyle(TableStyle(disc_style_list))
            elements.append(disc_table)
        else:
            ok_style = ParagraphStyle("OkMsg", parent=self.styles["Normal"], fontSize=9, textColor=colors.HexColor("#16a34a"))
            elements.append(Paragraph("¡Sin discrepancias! Todos los docentes tienen registros de asistencia consistentes.", ok_style))

        _add_footer(elements, self.styles, generated_by_name)
        doc.build(elements)

        report = Report(
            report_type="reconciliation", title=title, description=subtitle,
            filters={"month": month, "year": year},
            file_path=str(filepath), file_size=filepath.stat().st_size,
            generated_by=generated_by, status="generated",
        )
        db.add(report)
        db.flush()
        logger.info("Generated reconciliation report: %s (%d discrepancies)", filename, len(discrepancies))
        return report

    # ── Roster Report ────────────────────────────────────────────────────────
    def generate_roster_report(
        self,
        db: Session,
        generated_by: int | None = None,
        generated_by_name: str | None = None,
    ) -> Report:
        """Generate a teacher roster report PDF with all registered teachers."""
        teachers = db.query(Teacher).filter(~Teacher.ci.startswith("TEMP-")).order_by(Teacher.full_name).all()

        # Count effective typed workloads for the configured academic period.
        from collections import Counter
        desig_counts: Counter[str] = Counter()
        practice_counts: Counter[str] = Counter()
        workload_hours: Counter[str] = Counter()
        academic_period = app_settings_service.get_active_academic_period(db)
        workloads = effective_workloads(
            db,
            academic_period=academic_period,
            target_date=active_period_effective_date(academic_period),
        )
        for workload in workloads:
            if workload.activity_kind == "practice":
                practice_counts[workload.teacher_ci] += 1
            else:
                desig_counts[workload.teacher_ci] += 1
            workload_hours[workload.teacher_ci] += workload.weekly_hours

        title = "Plantel Docente"
        subtitle = f"Total: {len(teachers)} docentes — Gestión {datetime.now().year}"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"plantel_docente_{timestamp}.pdf"
        filepath = _output_dir() / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=12 * mm, rightMargin=12 * mm,
            topMargin=15 * mm, bottomMargin=18 * mm,
        )
        elements: list = []
        cs = self.cs

        _add_branded_header(elements, self.styles, title, subtitle)

        # Summary stats
        with_retention = sum(1 for t in teachers if (t.invoice_retention or "").upper() == "RETENCION")
        with_nit = sum(1 for t in teachers if t.nit)

        summary_data = [
            [_cell(h, cs["header"]) for h in ["Total Docentes", "Con NIT", "Con Retención", "Cargas", "Hrs Semanales"]],
            [_cell(v, cs["cell_center"]) for v in [
                str(len(teachers)),
                str(with_nit),
                str(with_retention),
                f"{sum(desig_counts.values())} ({sum(practice_counts.values())} prácticas)",
                f"{sum(workload_hours.values())}h",
            ]],
        ]
        summary_table = Table(summary_data, colWidths=[85, 70, 80, 70, 80])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 12))

        # Detail table
        detail_header = [_cell(h, cs["header"]) for h in ["Nº", "Docente", "C.I.", "Designaciones", "Teléfono", "Banco", "Cuenta", "NIT/Ret."]]
        detail_data: list = [detail_header]

        for idx, t in enumerate(teachers, start=1):
            nit_ret = "RET" if (t.invoice_retention or "").upper() == "RETENCION" else (t.nit or "—")
            designation_label = f"{desig_counts[t.ci]} materias ({practice_counts[t.ci]} prácticas)"
            detail_data.append([
                _cell(str(idx), cs["cell_center"]),
                _cell(t.full_name, cs["cell"]),
                _cell(t.ci, cs["cell_center"]),
                _cell(designation_label, cs["cell_center"]),
                _cell(t.phone or "—", cs["cell_center"]),
                _cell(t.bank or "—", cs["cell"]),
                _cell(t.account_number or "—", cs["cell"]),
                _cell(nit_ret, cs["cell_center"]),
            ])

        col_widths = [22, 110, 48, 80, 55, 50, 65, 45]
        detail_table = Table(detail_data, colWidths=col_widths, repeatRows=1)
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ]))
        elements.append(detail_table)

        _add_footer(elements, self.styles, generated_by_name)
        doc.build(elements)

        report = Report(
            report_type="roster",
            title=title,
            description=subtitle,
            filters={},
            file_path=str(filepath),
            file_size=filepath.stat().st_size,
            generated_by=generated_by,
            status="generated",
        )
        db.add(report)
        db.flush()

        logger.info("Generated roster report: %s (%d teachers)", filename, len(teachers))
        return report
