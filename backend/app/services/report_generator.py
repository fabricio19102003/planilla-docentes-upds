from __future__ import annotations

import logging
import calendar
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
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.models.report import Report
from app.services import app_settings_service
from app.services.practice_planilla_generator import PracticePlanillaGenerator
from app.services.monetary_snapshot import calculation_snapshot_rows

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

    @staticmethod
    def _load_planilla_exclusions(stored_planilla) -> list:
        if stored_planilla is None or not stored_planilla.excluded_days_json:
            return []
        from app.schemas.planilla import ExcludedDaySchema
        from app.services.planilla_generator import PayrollDataError

        try:
            return [
                ExcludedDaySchema.model_validate(item)
                for item in stored_planilla.excluded_days_json
            ]
        except Exception as exc:
            raise PayrollDataError(
                "La planilla almacenada contiene exclusiones inválidas; regenerala antes de crear reportes",
                code="invalid_stored_exclusions",
            ) from exc

    def _build_practice_planilla_rows(self, db: Session, month: int, year: int) -> tuple[list, PracticePlanillaOutput | None]:
        stored_po = (
            db.query(PracticePlanillaOutput)
            .filter(PracticePlanillaOutput.month == month, PracticePlanillaOutput.year == year)
            .order_by(PracticePlanillaOutput.generated_at.desc())
            .first()
        )
        dm = stored_po.discount_mode if stored_po else "attendance"
        sd = stored_po.start_date if stored_po else None
        ed = stored_po.end_date if stored_po else None
        practice_gen = PracticePlanillaGenerator()
        rows, _warnings = practice_gen._build_planilla_data(
            db, month=month, year=year, start_date=sd, end_date=ed, discount_mode=dm,
            excluded_days=self._load_planilla_exclusions(stored_po),
        )
        return rows, stored_po

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
            detail_data.append([
                _cell(r.teacher_name, cs["cell"]),
                _cell(r.subject, cs["cell"]),
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
                detail_data.append([
                    _cell(r.teacher_name, cs["cell"]),
                    _cell(f"{r.subject} (Prácticas)", cs["cell"]),
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

    # ── Attendance Report ────────────────────────────────────────────────────
    def generate_attendance_report(
        self,
        db: Session,
        month: int,
        year: int,
        teacher_ci: str | None = None,
        semester: str | None = None,
        group_code: str | None = None,
        generated_by: int | None = None,
        generated_by_name: str | None = None,
    ) -> Report:
        query = db.query(AttendanceRecord).filter(
            AttendanceRecord.month == month,
            AttendanceRecord.year == year,
        )
        if teacher_ci:
            query = query.filter(AttendanceRecord.teacher_ci == teacher_ci)

        records = query.order_by(AttendanceRecord.teacher_ci, AttendanceRecord.date).all()
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])

        practice_query = db.query(PracticeAttendanceLog).filter(
            PracticeAttendanceLog.date >= start,
            PracticeAttendanceLog.date <= end,
        )
        if teacher_ci:
            practice_query = practice_query.filter(PracticeAttendanceLog.teacher_ci == teacher_ci)
        practice_records = practice_query.order_by(PracticeAttendanceLog.teacher_ci, PracticeAttendanceLog.date).all()

        desig_map: dict[int, Designation] = {}
        desig_ids = set(r.designation_id for r in records) | set(r.designation_id for r in practice_records)
        if desig_ids:
            desig_map = {d.id: d for d in db.query(Designation).filter(Designation.id.in_(desig_ids)).all()}

        if semester or group_code:
            ok_ids: set[int] = set()
            for did, d in desig_map.items():
                if semester and d.semester.upper() != semester.upper():
                    continue
                if group_code and d.group_code != group_code:
                    continue
                ok_ids.add(did)
            records = [r for r in records if r.designation_id in ok_ids]
            practice_records = [r for r in practice_records if r.designation_id in ok_ids]

        teacher_cis = set(r.teacher_ci for r in records) | set(r.teacher_ci for r in practice_records)
        teachers: dict[str, Teacher] = {
            t.ci: t for t in db.query(Teacher).filter(Teacher.ci.in_(teacher_cis)).all()
        } if teacher_cis else {}

        filter_parts = [f"{MONTH_NAMES.get(month, str(month))} {year}"]
        if teacher_ci and teacher_ci in teachers:
            filter_parts.append(f"Docente: {teachers[teacher_ci].full_name}")
        if semester:
            filter_parts.append(f"Semestre: {semester}")
        if group_code:
            filter_parts.append(f"Grupo: {group_code}")

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
        attended = sum(1 for r in records if r.status == "ATTENDED") + sum(1 for r in practice_records if r.status.lower() in ("attended", "present", "justified"))
        late = sum(1 for r in records if r.status == "LATE") + sum(1 for r in practice_records if r.status.lower() == "late")
        absent = sum(1 for r in records if r.status == "ABSENT") + sum(1 for r in practice_records if r.status.lower() == "absent")
        no_exit = sum(1 for r in records if r.status == "NO_EXIT")
        total = len(records) + len(practice_records)
        # NO_EXIT counts as present (teacher was physically there, just forgot to clock out)
        rate = (attended + late + no_exit) / total * 100 if total > 0 else 0

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
            desig = desig_map.get(r.designation_id)
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
                _cell(desig.subject if desig else "", cs["cell"]),
                _cell(desig.group_code if desig else "", cs["cell_center"]),
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
            desig = desig_map.get(r.designation_id)
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
                _cell(desig.subject if desig else "", cs["cell"]),
                _cell(desig.group_code if desig else "", cs["cell_center"]),
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
            filters={"month": month, "year": year, "teacher_ci": teacher_ci, "semester": semester, "group_code": group_code},
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
        from app.services.planilla_generator import PlanillaGenerator

        months_query = db.query(
            AttendanceRecord.month,
        ).filter(AttendanceRecord.year == year).distinct().order_by(AttendanceRecord.month).all()
        months = {m[0] for m in months_query}
        practice_months = {
            r[0].month for r in db.query(PracticeAttendanceLog.date)
            .filter(PracticeAttendanceLog.date >= date(year, 1, 1), PracticeAttendanceLog.date <= date(year, 12, 31))
            .distinct().all()
        }
        practice_output_months = {
            r[0] for r in db.query(PracticePlanillaOutput.month)
            .filter(PracticePlanillaOutput.year == year)
            .distinct().all()
        }
        months.update(practice_months)
        months.update(practice_output_months)
        if not months:
            months = {datetime.now().month}

        gen = PlanillaGenerator()
        monthly_data = []
        for m in sorted(months):
            # Use stored discount_mode so PDF matches the approved planilla
            stored_m = (
                db.query(PlanillaOutput)
                .filter(PlanillaOutput.month == m, PlanillaOutput.year == year)
                .order_by(PlanillaOutput.generated_at.desc())
                .first()
            )
            m_dm = stored_m.discount_mode if stored_m else "attendance"
            m_sd = stored_m.start_date if stored_m else None
            m_ed = stored_m.end_date if stored_m else None
            rows, _, _ = gen._build_planilla_data(
                db,
                month=m,
                year=year,
                start_date=m_sd,
                end_date=m_ed,
                discount_mode=m_dm,
                excluded_days=self._load_planilla_exclusions(stored_m),
            )
            practice_rows, stored_practice_m = self._build_practice_planilla_rows(db, m, year)
            if teacher_ci:
                rows = [r for r in rows if r.teacher_ci == teacher_ci]
                practice_rows = [r for r in practice_rows if r.teacher_ci == teacher_ci]
            if not teacher_ci:
                month_total = 0.0
                month_total += float(stored_m.total_payment) if stored_m else sum(r.final_payment for r in rows)
                month_total += float(stored_practice_m.total_payment) if stored_practice_m else sum(r.final_payment for r in practice_rows)
            else:
                month_total = sum(r.final_payment for r in rows + practice_rows)  # net — after retention
            all_rows = rows + practice_rows

            monthly_data.append({
                "month": m,
                "month_name": MONTH_NAMES.get(m, str(m)),
                "teachers": len(set(r.teacher_ci for r in all_rows)),
                "base_hours": sum(r.base_monthly_hours for r in all_rows),
                "absent_hours": sum(r.absent_hours for r in all_rows),
                "payable_hours": sum(r.payable_hours for r in all_rows),
                "total_payment": month_total,
            })

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

        all_teacher_cis = {
            r[0] for r in db.query(Designation.teacher_ci)
            .filter(
                Designation.academic_period == app_settings_service.get_active_academic_period(db),
                Designation.designation_type != "practice",
            )
            .distinct().all()
        }
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
        from collections import defaultdict

        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])

        att_records = db.query(AttendanceRecord).filter(
            AttendanceRecord.month == month, AttendanceRecord.year == year,
        ).all()
        practice_records = db.query(PracticeAttendanceLog).filter(
            PracticeAttendanceLog.date >= start,
            PracticeAttendanceLog.date <= end,
        ).all()

        stored_planilla = db.query(PlanillaOutput).filter(
            PlanillaOutput.month == month, PlanillaOutput.year == year,
        ).order_by(PlanillaOutput.generated_at.desc()).first()
        exclusion_count = len(stored_planilla.excluded_days_json) if stored_planilla and stored_planilla.excluded_days_json else 0

        designations = db.query(Designation).filter(
            Designation.academic_period == app_settings_service.get_active_academic_period(db)
        ).all()

        teacher_cis = set(d.teacher_ci for d in designations)
        teacher_names = {t.ci: t.full_name for t in db.query(Teacher).filter(Teacher.ci.in_(teacher_cis)).all()}

        att_by_teacher: dict = defaultdict(list)
        for r in att_records:
            att_by_teacher[r.teacher_ci].append(r)

        practice_att_by_teacher: dict = defaultdict(list)
        for r in practice_records:
            practice_att_by_teacher[r.teacher_ci].append(r)

        desig_by_teacher: dict = defaultdict(list)
        for d in designations:
            desig_by_teacher[d.teacher_ci].append(d)

        discrepancies = []
        for ci in sorted(teacher_cis):
            if ci.startswith("TEMP-"):
                continue
            name = teacher_names.get(ci, ci)
            teacher_att = att_by_teacher.get(ci, [])
            teacher_practice_att = practice_att_by_teacher.get(ci, [])
            teacher_desigs = desig_by_teacher.get(ci, [])
            regular_desigs = [d for d in teacher_desigs if d.designation_type != "practice"]
            practice_desigs = [d for d in teacher_desigs if d.designation_type == "practice"]
            regular_expected = sum(d.monthly_hours or 0 for d in regular_desigs)
            practice_expected = sum(d.monthly_hours or 0 for d in practice_desigs)

            if regular_desigs and not teacher_att:
                discrepancies.append({
                    "teacher_name": name,
                    "source": "Regular",
                    "type": "Sin registro",
                    "description": "Sin registros de asistencia regular",
                    "expected_hours": regular_expected,
                    "actual_hours": 0,
                    "severity": "high",
                })

            if regular_desigs and teacher_att:
                absences = sum(1 for r in teacher_att if r.status == "ABSENT")
                total = len(teacher_att)
                absence_rate = absences / total if total > 0 else 0
                attended_hours = sum(r.academic_hours for r in teacher_att if r.status in ("ATTENDED", "LATE"))

                already_added = False
                if absence_rate > 0.3:
                    discrepancies.append({
                        "teacher_name": name,
                        "source": "Regular",
                        "type": "Alta ausencia",
                        "description": f"Tasa de ausencia regular: {absence_rate*100:.0f}% ({absences}/{total} clases)",
                        "expected_hours": regular_expected,
                        "actual_hours": attended_hours,
                        "severity": "high" if absence_rate > 0.5 else "medium",
                    })
                    already_added = True

                if regular_expected > 0 and attended_hours < regular_expected * 0.5 and not already_added:
                    discrepancies.append({
                        "teacher_name": name,
                        "source": "Regular",
                        "type": "Horas inconsistentes",
                        "description": f"Horas asistidas regulares ({attended_hours}h) < 50% de esperadas ({regular_expected}h)",
                        "expected_hours": regular_expected,
                        "actual_hours": attended_hours,
                        "severity": "medium",
                    })

            if practice_desigs and not teacher_practice_att:
                discrepancies.append({
                    "teacher_name": name,
                    "source": "Prácticas",
                    "type": "Sin registro",
                    "description": "Sin registros de asistencia de prácticas",
                    "expected_hours": practice_expected,
                    "actual_hours": 0,
                    "severity": "high",
                })

            if practice_desigs and teacher_practice_att:
                absences = sum(1 for r in teacher_practice_att if r.status.lower() == "absent")
                total = len(teacher_practice_att)
                absence_rate = absences / total if total > 0 else 0
                attended_hours = sum(
                    r.academic_hours for r in teacher_practice_att
                    if r.status.lower() in ("attended", "present", "justified", "late")
                )

                already_added = False
                if absence_rate > 0.3:
                    discrepancies.append({
                        "teacher_name": name,
                        "source": "Prácticas",
                        "type": "Alta ausencia",
                        "description": f"Tasa de ausencia en prácticas: {absence_rate*100:.0f}% ({absences}/{total} clases)",
                        "expected_hours": practice_expected,
                        "actual_hours": attended_hours,
                        "severity": "high" if absence_rate > 0.5 else "medium",
                    })
                    already_added = True

                if practice_expected > 0 and attended_hours < practice_expected * 0.5 and not already_added:
                    discrepancies.append({
                        "teacher_name": name,
                        "source": "Prácticas",
                        "type": "Horas inconsistentes",
                        "description": f"Horas asistidas en prácticas ({attended_hours}h) < 50% de esperadas ({practice_expected}h)",
                        "expected_hours": practice_expected,
                        "actual_hours": attended_hours,
                        "severity": "medium",
                    })

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
        high_count = sum(1 for d in discrepancies if d["severity"] == "high")
        medium_count = sum(1 for d in discrepancies if d["severity"] == "medium")
        regular_count = sum(1 for d in discrepancies if d["source"] == "Regular")
        practice_count = sum(1 for d in discrepancies if d["source"] == "Prácticas")

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

        # Count designations per teacher — scoped to the active academic period
        from collections import Counter
        desig_counts: Counter[str] = Counter()
        practice_counts: Counter[str] = Counter()
        desig_hours: Counter[str] = Counter()
        all_desigs = db.query(Designation).filter(
            Designation.academic_period == app_settings_service.get_active_academic_period(db)
        ).all()
        for d in all_desigs:
            if d.designation_type == "practice":
                practice_counts[d.teacher_ci] += 1
            else:
                desig_counts[d.teacher_ci] += 1
            desig_hours[d.teacher_ci] += (d.monthly_hours or 0)

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
            [_cell(h, cs["header"]) for h in ["Total Docentes", "Con NIT", "Con Retención", "Materias", "Hrs Mensuales"]],
            [_cell(v, cs["cell_center"]) for v in [
                str(len(teachers)),
                str(with_nit),
                str(with_retention),
                f"{sum(desig_counts.values())} ({sum(practice_counts.values())} prácticas)",
                f"{sum(desig_hours.values())}h",
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
