from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
)

logger = logging.getLogger(__name__)

# ── UPDS Colors ──────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#003366")
BLUE = colors.HexColor("#0066CC")
LIGHT_BLUE = colors.HexColor("#E8F4FD")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
GREEN_BG = colors.HexColor("#F0FFF4")
YELLOW_BG = colors.HexColor("#FFFBEB")
RED_BG = colors.HexColor("#FEF2F2")
GRAY_BG = colors.HexColor("#F9FAFB")

# ── Paths ────────────────────────────────────────────────────────────────────
ASSETS_DIR = Path(__file__).resolve().parents[2] / "data" / "assets"
ISOLOGO_PATH = ASSETS_DIR / "isologo_upds.png"

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

STATUS_LABELS = {
    "ATTENDED": "Asistido",
    "LATE": "Tardanza",
    "ABSENT": "Ausente",
    "NO_EXIT": "Sin salida",
}


def _output_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cell(text: str, style: ParagraphStyle) -> Paragraph:
    """Wrap text in a Paragraph for proper cell wrapping."""
    return Paragraph(str(text) if text is not None else "", style)


def _make_cell_styles(styles: Any) -> dict[str, ParagraphStyle]:
    return {
        "header": ParagraphStyle(
            "AuditCellHeader", parent=styles["Normal"],
            fontSize=7, textColor=colors.white,
            fontName="Helvetica-Bold", leading=9,
            alignment=TA_CENTER,
        ),
        "cell": ParagraphStyle(
            "AuditCellNormal", parent=styles["Normal"],
            fontSize=7, leading=9, textColor=colors.HexColor("#333333"),
        ),
        "cell_center": ParagraphStyle(
            "AuditCellCenter", parent=styles["Normal"],
            fontSize=7, leading=9, textColor=colors.HexColor("#333333"),
            alignment=TA_CENTER,
        ),
        "cell_right": ParagraphStyle(
            "AuditCellRight", parent=styles["Normal"],
            fontSize=7, leading=9, textColor=colors.HexColor("#333333"),
            alignment=TA_RIGHT,
        ),
        "cell_bold": ParagraphStyle(
            "AuditCellBold", parent=styles["Normal"],
            fontSize=7, leading=9, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#333333"),
        ),
        "cell_small": ParagraphStyle(
            "AuditCellSmall", parent=styles["Normal"],
            fontSize=6, leading=8, textColor=colors.HexColor("#555555"),
        ),
        "section": ParagraphStyle(
            "AuditSection", parent=styles["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=NAVY, spaceAfter=4,
        ),
    }


def _add_branded_header(
    elements: list,
    styles: Any,
    title: str,
    subtitle: str = "",
) -> None:
    """UPDS branded header: isologo + navy title bar."""
    if ISOLOGO_PATH.exists():
        logo = Image(str(ISOLOGO_PATH), width=2 * cm, height=2 * cm)
        logo.hAlign = "LEFT"
        elements.append(logo)
        elements.append(Spacer(1, 3 * mm))

    title_style = ParagraphStyle(
        "AuditTitleBar", parent=styles["Normal"],
        fontSize=13, textColor=colors.white,
        fontName="Helvetica-Bold", leading=17,
        alignment=TA_LEFT,
    )
    title_table = Table([[Paragraph(title, title_style)]], colWidths=["100%"])
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
            "AuditSubLine", parent=styles["Normal"],
            fontSize=9, textColor=BLUE, spaceAfter=6,
        )
        elements.append(Paragraph(subtitle, sub_style))

    elements.append(Spacer(1, 2 * mm))


def _add_footer(elements: list, styles: Any) -> None:
    """Single-line audit footer."""
    now = datetime.now()
    footer_text = (
        f"Generado: {now.strftime('%d/%m/%Y %H:%M:%S')}  |  "
        "SIPAD — Sistema Integrado de Pago Docente"
    )

    elements.append(Spacer(1, 16))

    sep = Table([[""]], colWidths=["100%"])
    sep.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.gray)]))
    elements.append(sep)
    elements.append(Spacer(1, 3))

    footer_style = ParagraphStyle(
        "AuditFooter", parent=styles["Normal"],
        fontSize=7, textColor=colors.gray, alignment=TA_CENTER, leading=9,
    )
    elements.append(Paragraph(footer_text, footer_style))


def generate_audit_report_pdf(
    teacher: Any,
    month: int,
    year: int,
    designations: list,
    bio_records: list,
    att_records: list,
    db: Any,
) -> str:
    """
    Generate a professional PDF audit report for a teacher.

    Returns the absolute path to the generated PDF file.
    """
    from app.models.biometric import BiometricRecord

    styles = getSampleStyleSheet()
    cs = _make_cell_styles(styles)

    month_name = MONTH_NAMES.get(month, str(month))
    title = "Reporte de Auditoría de Asistencia"
    subtitle = f"Docente: {teacher.full_name} — CI: {teacher.ci} — {month_name} {year}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ci = teacher.ci.replace("/", "-")
    filename = f"auditoria_{safe_ci}_{month}_{year}_{timestamp}.pdf"
    filepath = _output_dir() / filename

    # ── Landscape A4 for wide detail table ───────────────────────────────────
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=18 * mm,
    )
    elements: list = []

    # ── SUMMARY STATS ─────────────────────────────────────────────────────────
    total_slots = len(att_records)
    attended = sum(1 for r in att_records if r.status == "ATTENDED")
    late = sum(1 for r in att_records if r.status == "LATE")
    absent = sum(1 for r in att_records if r.status == "ABSENT")
    no_exit = sum(1 for r in att_records if r.status == "NO_EXIT")
    rate = round((attended + late + no_exit) / total_slots * 100, 1) if total_slots else 0.0

    # ── SECTION 1: Header + Summary ──────────────────────────────────────────
    _add_branded_header(elements, styles, title, subtitle)

    # Summary table
    summary_data = [
        [_cell(h, cs["header"]) for h in [
            "Total Clases", "Asistidos", "Tardanzas", "Ausencias", "Sin Salida", "Tasa de Asistencia"
        ]],
        [_cell(v, cs["cell_center"]) for v in [
            str(total_slots), str(attended), str(late), str(absent), str(no_exit), f"{rate}%"
        ]],
    ]
    summary_table = Table(summary_data, colWidths=[90, 90, 90, 90, 90, 110])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 10 * mm))

    # ── SECTION 2: Schedule ───────────────────────────────────────────────────
    if designations:
        elements.append(Paragraph("Horario Asignado", cs["section"]))

        sched_header = [_cell(h, cs["header"]) for h in [
            "Materia", "Grupo", "Semestre", "Hrs Mensuales", "Hrs Semanales", "Horarios"
        ]]
        sched_data: list = [sched_header]

        for d in designations:
            slots = d.schedule_json or []
            slots_text = ", ".join(
                f"{s.get('dia', '')} {s.get('hora_inicio', '')}–{s.get('hora_fin', '')}"
                for s in slots
            ) if slots else "—"
            sched_data.append([
                _cell(d.subject, cs["cell"]),
                _cell(d.group_code or "—", cs["cell_center"]),
                _cell(str(d.semester) if d.semester else "—", cs["cell_center"]),
                _cell(f"{d.monthly_hours or 0}h", cs["cell_center"]),
                _cell(f"{d.weekly_hours or 0}h", cs["cell_center"]),
                _cell(slots_text, cs["cell_small"]),
            ])

        sched_table = Table(sched_data, colWidths=[160, 55, 60, 70, 70, 145])
        sched_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ]))
        elements.append(sched_table)
        elements.append(Spacer(1, 8 * mm))

    # ── SECTION 3: Attendance Detail Table ───────────────────────────────────
    elements.append(Paragraph("Detalle de Auditoría de Asistencia", cs["section"]))

    # Build designation lookup
    desig_map = {d.id: d for d in designations}

    # Build biometric lookup per record
    bio_by_id: dict[int, Any] = {}
    if att_records:
        bio_ids = [r.biometric_record_id for r in att_records if r.biometric_record_id]
        if bio_ids:
            bios = db.query(BiometricRecord).filter(BiometricRecord.id.in_(bio_ids)).all()
            bio_by_id = {b.id: b for b in bios}

    WEEKDAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    detail_header = [_cell(h, cs["header"]) for h in [
        "Fecha", "Día", "Materia", "Grupo", "Horario Prog.", "Entrada Real",
        "Salida Real", "Estado", "Retraso", "Hrs Acad.", "Explicación",
    ]]
    detail_data: list = [detail_header]
    row_colors: list[tuple] = []

    for idx, rec in enumerate(att_records):
        desig = desig_map.get(rec.designation_id)
        row_num = idx + 1  # +1 for header row

        date_str = rec.date.strftime("%d/%m/%Y") if rec.date else "—"
        day_name = WEEKDAY_NAMES[rec.date.weekday()] if rec.date else "—"
        subject = desig.subject if desig else "—"
        group = desig.group_code if desig else "—"
        sched_time = (
            f"{rec.scheduled_start.strftime('%H:%M')}–{rec.scheduled_end.strftime('%H:%M')}"
            if rec.scheduled_start and rec.scheduled_end else "—"
        )
        entry_str = rec.actual_entry.strftime("%H:%M") if rec.actual_entry else "—"
        exit_str = rec.actual_exit.strftime("%H:%M") if rec.actual_exit else "—"
        status_label = STATUS_LABELS.get(rec.status, rec.status)
        late_str = f"{rec.late_minutes} min" if rec.late_minutes and rec.late_minutes > 0 else "—"
        acad_hrs = f"{rec.academic_hours}h" if rec.academic_hours is not None else "0h"

        # Build explanation
        if rec.status == "ABSENT":
            explanation = "No se encontró registro biométrico para este horario programado"
        elif rec.status == "LATE":
            explanation = (
                f"Entrada registrada {rec.late_minutes} min después del horario "
                f"({rec.scheduled_start.strftime('%H:%M') if rec.scheduled_start else ''})"
            )
        elif rec.status == "ATTENDED":
            explanation = "Entrada registrada dentro del margen de tolerancia"
        elif rec.status == "NO_EXIT":
            explanation = "Se registró entrada pero no se registró salida"
        else:
            explanation = rec.status

        # Row background by status
        if rec.status == "ABSENT":
            row_colors.append(("BACKGROUND", (0, row_num), (-1, row_num), RED_BG))
        elif rec.status == "LATE":
            row_colors.append(("BACKGROUND", (0, row_num), (-1, row_num), YELLOW_BG))
        elif rec.status == "ATTENDED":
            if row_num % 2 == 0:
                row_colors.append(("BACKGROUND", (0, row_num), (-1, row_num), GREEN_BG))
        else:
            if row_num % 2 == 0:
                row_colors.append(("BACKGROUND", (0, row_num), (-1, row_num), GRAY_BG))

        detail_data.append([
            _cell(date_str, cs["cell_center"]),
            _cell(day_name, cs["cell_center"]),
            _cell(subject, cs["cell"]),
            _cell(group, cs["cell_center"]),
            _cell(sched_time, cs["cell_center"]),
            _cell(entry_str, cs["cell_center"]),
            _cell(exit_str, cs["cell_center"]),
            _cell(status_label, cs["cell_center"]),
            _cell(late_str, cs["cell_center"]),
            _cell(acad_hrs, cs["cell_center"]),
            _cell(explanation, cs["cell_small"]),
        ])

    # Landscape A4 usable width ≈ 267mm → ~757pt (after margins)
    # Columns: 42+42+110+38+60+48+48+48+42+42+155 = 675
    col_widths = [42, 42, 110, 38, 60, 48, 48, 48, 42, 42, 155]
    detail_table = Table(detail_data, colWidths=col_widths, repeatRows=1)

    detail_style_list: list = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ] + row_colors

    detail_table.setStyle(TableStyle(detail_style_list))
    elements.append(detail_table)
    elements.append(Spacer(1, 8 * mm))

    # ── SECTION 4: Raw Biometric Data ─────────────────────────────────────────
    elements.append(Paragraph("Registros Biométricos Originales", cs["section"]))

    if bio_records:
        bio_header = [_cell(h, cs["header"]) for h in [
            "Fecha", "Entrada", "Salida", "Minutos Trabajados"
        ]]
        bio_data: list = [bio_header]
        for b in bio_records:
            bio_data.append([
                _cell(b.date.strftime("%d/%m/%Y") if b.date else "—", cs["cell_center"]),
                _cell(b.entry_time.strftime("%H:%M") if b.entry_time else "—", cs["cell_center"]),
                _cell(b.exit_time.strftime("%H:%M") if b.exit_time else "—", cs["cell_center"]),
                _cell(f"{b.worked_minutes} min" if b.worked_minutes is not None else "—", cs["cell_center"]),
            ])

        bio_table = Table(bio_data, colWidths=[90, 90, 90, 110])
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
        elements.append(Paragraph(
            "Sin registros biométricos para este período.",
            cs["cell"],
        ))

    _add_footer(elements, styles)
    doc.build(elements)

    logger.info("Generated audit report PDF: %s", filename)
    return str(filepath)
