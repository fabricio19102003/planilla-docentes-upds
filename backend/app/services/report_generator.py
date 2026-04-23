from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
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
from app.models.teacher import Teacher
from app.models.report import Report
from app.services import app_settings_service

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
        from app.services.planilla_generator import PlanillaGenerator

        gen = PlanillaGenerator()
        # Use stored discount_mode so PDF matches the approved planilla
        stored_po = (
            db.query(PlanillaOutput)
            .filter(PlanillaOutput.month == month, PlanillaOutput.year == year)
            .order_by(PlanillaOutput.generated_at.desc())
            .first()
        )
        dm = stored_po.discount_mode if stored_po else "attendance"
        sd = stored_po.start_date if stored_po else None
        ed = stored_po.end_date if stored_po else None
        rows, _, warnings = gen._build_planilla_data(db, month=month, year=year, start_date=sd, end_date=ed, discount_mode=dm)

        if teacher_ci:
            rows = [r for r in rows if r.teacher_ci == teacher_ci]
        if semester:
            rows = [r for r in rows if r.semester and r.semester.upper() == semester.upper()]
        if group_code:
            rows = [r for r in rows if r.group_code == group_code]
        if subject:
            rows = [r for r in rows if subject.lower() in r.subject.lower()]

        filter_parts = [f"{MONTH_NAMES.get(month, str(month))} {year}"]
        if teacher_ci:
            t = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
            if t:
                filter_parts.append(f"Docente: {t.full_name}")
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
        total_gross = sum(r.calculated_payment for r in rows)
        total_retention = sum(r.retention_amount for r in rows)
        # Prefer stored PlanillaOutput total (reflects admin overrides) over live sum
        stored_planilla = (
            db.query(PlanillaOutput)
            .filter(PlanillaOutput.month == month, PlanillaOutput.year == year)
            .order_by(PlanillaOutput.generated_at.desc())
            .first()
        )
        if stored_planilla and not teacher_ci and not semester and not group_code and not subject:
            total_payment = float(stored_planilla.total_payment)
        else:
            total_payment = sum(r.final_payment for r in rows)   # net — after retention
        total_base = sum(r.base_monthly_hours for r in rows)
        total_absent = sum(r.absent_hours for r in rows)
        total_payable = sum(r.payable_hours for r in rows)
        unique_teachers = len(set(r.teacher_ci for r in rows))

        summary_data = [
            [_cell(h, cs["header"]) for h in ["Docentes", "Designaciones", "Hrs Asignadas", "Hrs Ausencia", "Hrs a Pagar", "Bruto (Bs)", "Ret. 13% (Bs)", "Neto (Bs)"]],
            [_cell(v, cs["cell_center"]) for v in [
                str(unique_teachers), str(len(rows)), f"{total_base}h", f"{total_absent}h", f"{total_payable}h",
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
        logger.info("Generated financial report: %s (%d rows)", filename, len(rows))
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

        desig_map: dict[int, Designation] = {}
        desig_ids = set(r.designation_id for r in records)
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

        teacher_cis = set(r.teacher_ci for r in records)
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
        attended = sum(1 for r in records if r.status == "ATTENDED")
        late = sum(1 for r in records if r.status == "LATE")
        absent = sum(1 for r in records if r.status == "ABSENT")
        no_exit = sum(1 for r in records if r.status == "NO_EXIT")
        total = len(records)
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
        logger.info("Generated attendance report: %s (%d records)", filename, len(records))
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
        months = [m[0] for m in months_query]
        if not months:
            months = [datetime.now().month]

        gen = PlanillaGenerator()
        monthly_data = []
        for m in months:
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
            rows, _, _ = gen._build_planilla_data(db, month=m, year=year, start_date=m_sd, end_date=m_ed, discount_mode=m_dm)
            if teacher_ci:
                rows = [r for r in rows if r.teacher_ci == teacher_ci]
            if stored_m and not teacher_ci:
                month_total = float(stored_m.total_payment)
            else:
                month_total = sum(r.final_payment for r in rows)  # net — after retention

            monthly_data.append({
                "month": m,
                "month_name": MONTH_NAMES.get(m, str(m)),
                "teachers": len(set(r.teacher_ci for r in rows)),
                "base_hours": sum(r.base_monthly_hours for r in rows),
                "absent_hours": sum(r.absent_hours for r in rows),
                "payable_hours": sum(r.payable_hours for r in rows),
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

        bio_cis = {
            r[0] for r in db.query(BiometricRecord.teacher_ci)
            .join(BiometricUpload)
            .filter(BiometricUpload.month == month, BiometricUpload.year == year)
            .distinct().all()
        }

        all_teacher_cis = {
            r[0] for r in db.query(Designation.teacher_ci)
            .filter(Designation.academic_period == app_settings_service.get_active_academic_period(db))
            .distinct().all()
        }

        teachers_without_bio = all_teacher_cis - bio_cis
        teacher_names = {
            t.ci: t.full_name for t in db.query(Teacher).filter(Teacher.ci.in_(all_teacher_cis)).all()
        }

        teacher_stats: dict = defaultdict(lambda: {"absences": 0, "lates": 0, "late_minutes_total": 0, "total_slots": 0})
        for r in records:
            ts = teacher_stats[r.teacher_ci]
            ts["total_slots"] += 1
            if r.status == "ABSENT":
                ts["absences"] += 1
            elif r.status == "LATE":
                ts["lates"] += 1
                ts["late_minutes_total"] += r.late_minutes

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
                str(len(records)), str(total_absences), str(total_lates), str(len(without_bio_list)),
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

        att_records = db.query(AttendanceRecord).filter(
            AttendanceRecord.month == month, AttendanceRecord.year == year,
        ).all()

        designations = db.query(Designation).filter(
            Designation.academic_period == app_settings_service.get_active_academic_period(db)
        ).all()

        teacher_cis = set(d.teacher_ci for d in designations)
        teacher_names = {t.ci: t.full_name for t in db.query(Teacher).filter(Teacher.ci.in_(teacher_cis)).all()}

        att_by_teacher: dict = defaultdict(list)
        for r in att_records:
            att_by_teacher[r.teacher_ci].append(r)

        desig_by_teacher: dict = defaultdict(list)
        for d in designations:
            desig_by_teacher[d.teacher_ci].append(d)

        discrepancies = []
        for ci in sorted(teacher_cis):
            if ci.startswith("TEMP-"):
                continue
            name = teacher_names.get(ci, ci)
            teacher_att = att_by_teacher.get(ci, [])
            teacher_desigs = desig_by_teacher.get(ci, [])
            expected_monthly_hours = sum(d.monthly_hours or 0 for d in teacher_desigs)

            if not teacher_att:
                discrepancies.append({
                    "teacher_name": name,
                    "type": "Sin registro",
                    "description": "Sin registros de asistencia",
                    "expected_hours": expected_monthly_hours,
                    "actual_hours": 0,
                    "severity": "high",
                })
                continue

            absences = sum(1 for r in teacher_att if r.status == "ABSENT")
            total = len(teacher_att)
            absence_rate = absences / total if total > 0 else 0
            attended_hours = sum(r.academic_hours for r in teacher_att if r.status in ("ATTENDED", "LATE"))

            already_added = False
            if absence_rate > 0.3:
                discrepancies.append({
                    "teacher_name": name,
                    "type": "Alta ausencia",
                    "description": f"Tasa de ausencia: {absence_rate*100:.0f}% ({absences}/{total} clases)",
                    "expected_hours": expected_monthly_hours,
                    "actual_hours": attended_hours,
                    "severity": "high" if absence_rate > 0.5 else "medium",
                })
                already_added = True

            if expected_monthly_hours > 0 and attended_hours < expected_monthly_hours * 0.5:
                if not already_added:
                    discrepancies.append({
                        "teacher_name": name,
                        "type": "Horas inconsistentes",
                        "description": f"Horas asistidas ({attended_hours}h) < 50% de esperadas ({expected_monthly_hours}h)",
                        "expected_hours": expected_monthly_hours,
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

        summary_data = [
            [_cell(h, cs["header"]) for h in ["Total Docentes", "Discrepancias", "Severidad Alta", "Severidad Media"]],
            [_cell(v, cs["cell_center"]) for v in [
                str(len(teacher_cis)), str(len(discrepancies)), str(high_count), str(medium_count),
            ]],
        ]
        summary_table = Table(summary_data, colWidths=[110, 110, 110, 115])
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

        # ── Discrepancy table ─────────────────────────────────────────────
        if discrepancies:
            disc_header = [_cell(h, cs["header"]) for h in ["Nº", "Docente", "Tipo", "Descripción", "Hrs Esperadas", "Hrs Reales", "Severidad"]]
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

            disc_table = Table(disc_data, colWidths=[22, 110, 65, 155, 55, 50, 50], repeatRows=1)
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
        desig_hours: Counter[str] = Counter()
        all_desigs = db.query(Designation).filter(
            Designation.academic_period == app_settings_service.get_active_academic_period(db)
        ).all()
        for d in all_desigs:
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
                str(sum(desig_counts.values())),
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
        detail_header = [_cell(h, cs["header"]) for h in ["Nº", "Docente", "C.I.", "Teléfono", "Email", "Banco", "Cuenta", "NIT/Ret."]]
        detail_data: list = [detail_header]

        for idx, t in enumerate(teachers, start=1):
            nit_ret = "RET" if (t.invoice_retention or "").upper() == "RETENCION" else (t.nit or "—")
            detail_data.append([
                _cell(str(idx), cs["cell_center"]),
                _cell(t.full_name, cs["cell"]),
                _cell(t.ci, cs["cell_center"]),
                _cell(t.phone or "—", cs["cell_center"]),
                _cell(t.email or "—", cs["cell"]),
                _cell(t.bank or "—", cs["cell"]),
                _cell(t.account_number or "—", cs["cell"]),
                _cell(nit_ret, cs["cell_center"]),
            ])

        col_widths = [22, 110, 48, 55, 85, 50, 65, 45]
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
