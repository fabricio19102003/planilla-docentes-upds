from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER

logger = logging.getLogger(__name__)

# ── UPDS Colors ──────────────────────────────────────────────────────────────
NAVY = colors.HexColor('#003366')
BLUE = colors.HexColor('#0066CC')
SKY = colors.HexColor('#4DA8DA')
LIGHT_BLUE = colors.HexColor('#E8F4FD')
WHITE = colors.white

ASSETS_DIR = Path(__file__).resolve().parents[2] / "data" / "assets"
ISOLOGO_PATH = ASSETS_DIR / "isologo_upds.png"

# Subject color palette (UPDS-inspired)
SUBJECT_COLORS = [
    colors.HexColor('#003366'),  # Navy
    colors.HexColor('#0066CC'),  # Blue
    colors.HexColor('#4DA8DA'),  # Sky
    colors.HexColor('#16a34a'),  # Green
    colors.HexColor('#7c3aed'),  # Purple
    colors.HexColor('#dc2626'),  # Red
    colors.HexColor('#d97706'),  # Amber
    colors.HexColor('#0891b2'),  # Cyan
    colors.HexColor('#be185d'),  # Pink
    colors.HexColor('#4338ca'),  # Indigo
]

WEEKDAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

DAY_NORM: dict[str, str] = {
    'lunes': 'Lunes',
    'martes': 'Martes',
    'miércoles': 'Miércoles',
    'miercoles': 'Miércoles',
    'jueves': 'Jueves',
    'viernes': 'Viernes',
    'sábado': 'Sábado',
    'sabado': 'Sábado',
}


def _output_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "schedules"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_day(dia: str) -> str:
    return DAY_NORM.get(dia.lower(), dia.capitalize())


def generate_schedule_pdf(teacher, designations) -> str:
    """Generate a professional landscape PDF schedule for a teacher.

    Args:
        teacher: Teacher ORM model instance.
        designations: List of Designation ORM model instances.

    Returns:
        Absolute path string to the generated PDF file.
    """
    styles = getSampleStyleSheet()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"horario_{teacher.ci}_{timestamp}.pdf"
    filepath = _output_dir() / filename

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=15 * mm,
    )
    elements: list = []

    # ── Header ───────────────────────────────────────────────────────────────
    if ISOLOGO_PATH.exists():
        logo = Image(str(ISOLOGO_PATH), width=0.7 * inch, height=0.7 * inch)
        logo.hAlign = 'LEFT'
        elements.append(logo)
        elements.append(Spacer(1, 4))

    title_style = ParagraphStyle(
        'ScheduleTitle', parent=styles['Title'],
        fontSize=14, textColor=NAVY, spaceAfter=2,
    )
    elements.append(Paragraph('Horario Semanal de Clases', title_style))

    info_style = ParagraphStyle(
        'ScheduleInfo', parent=styles['Normal'],
        fontSize=10, textColor=BLUE, spaceAfter=4,
    )
    elements.append(Paragraph(f'Docente: {teacher.full_name}  |  CI: {teacher.ci}', info_style))

    total_weekly = sum(d.weekly_hours or 0 for d in designations)
    sub_info_style = ParagraphStyle(
        'ScheduleSubInfo', parent=styles['Normal'],
        fontSize=9, textColor=colors.gray, spaceAfter=8,
    )
    elements.append(Paragraph(
        f'{len(designations)} materia(s)  |  {total_weekly} horas/semana  |  Gestión {datetime.now().year}',
        sub_info_style,
    ))

    # Divider line
    div_table = Table([['']], colWidths=['100%'])
    div_table.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 2, NAVY)]))
    elements.append(div_table)
    elements.append(Spacer(1, 10))

    # ── Build flat slots + subject color map ─────────────────────────────────
    subject_color_map: dict[str, object] = {}
    color_idx = 0
    all_slots: list[dict] = []

    for d in designations:
        if d.subject not in subject_color_map:
            subject_color_map[d.subject] = SUBJECT_COLORS[color_idx % len(SUBJECT_COLORS)]
            color_idx += 1

        for slot in (d.schedule_json or []):
            all_slots.append({
                'dia': _normalize_day(slot.get('dia', '')),
                'hora_inicio': slot.get('hora_inicio', ''),
                'hora_fin': slot.get('hora_fin', ''),
                'horas_academicas': slot.get('horas_academicas', 0),
                'subject': d.subject,
                'group_code': d.group_code,
                'semester': d.semester,
            })

    # ── Weekly grid table ─────────────────────────────────────────────────────
    unique_times = sorted(set(s['hora_inicio'] for s in all_slots))

    cell_header = ParagraphStyle(
        'GridHeader', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=WHITE,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    cell_time = ParagraphStyle(
        'GridTime', parent=styles['Normal'],
        fontSize=8, leading=10, fontName='Helvetica-Bold',
        textColor=NAVY, alignment=TA_CENTER,
    )
    cell_subject = ParagraphStyle(
        'GridSubject', parent=styles['Normal'],
        fontSize=7, leading=8, textColor=WHITE,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    cell_empty = ParagraphStyle(
        'GridEmpty', parent=styles['Normal'],
        fontSize=7, alignment=TA_CENTER,
    )

    # Header row
    header_row = [Paragraph('Horario', cell_header)]
    for day in WEEKDAYS:
        header_row.append(Paragraph(day, cell_header))

    grid_data = [header_row]

    for start_time in unique_times:
        # Find an example slot to get hora_fin
        example = next((s for s in all_slots if s['hora_inicio'] == start_time), None)
        fin = example['hora_fin'] if example else ''
        time_label = f"{start_time}<br/>{fin}" if fin else start_time

        row = [Paragraph(time_label, cell_time)]
        for day in WEEKDAYS:
            matching = [
                s for s in all_slots
                if s['dia'] == day and s['hora_inicio'] == start_time
            ]
            if matching:
                s = matching[0]
                content = f"<b>{s['subject']}</b><br/>{s['group_code']}"
                row.append(Paragraph(content, cell_subject))
            else:
                row.append(Paragraph('', cell_empty))

        grid_data.append(row)

    # Column widths
    page_width = landscape(A4)[0] - 24 * mm
    time_col_w = 55
    day_col_w = int((page_width - time_col_w) / len(WEEKDAYS))
    col_widths = [time_col_w] + [day_col_w] * len(WEEKDAYS)

    grid_table = Table(grid_data, colWidths=col_widths, repeatRows=1)

    grid_style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 1), (0, -1), LIGHT_BLUE),  # time column
    ]

    # Color subject cells
    for row_idx, start_time in enumerate(unique_times, start=1):
        for col_idx, day in enumerate(WEEKDAYS, start=1):
            matching = [
                s for s in all_slots
                if s['dia'] == day and s['hora_inicio'] == start_time
            ]
            if matching:
                cell_color = subject_color_map.get(matching[0]['subject'], NAVY)
                grid_style_cmds.append(
                    ('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), cell_color)
                )

    grid_table.setStyle(TableStyle(grid_style_cmds))
    elements.append(grid_table)
    elements.append(Spacer(1, 12))

    # ── Legend ────────────────────────────────────────────────────────────────
    if subject_color_map:
        legend_title_style = ParagraphStyle(
            'LegendTitle', parent=styles['Normal'],
            fontSize=9, fontName='Helvetica-Bold',
            textColor=NAVY, spaceAfter=4,
        )
        elements.append(Paragraph('Referencias:', legend_title_style))

        legend_cell_style = ParagraphStyle(
            'LegendCell', parent=styles['Normal'],
            fontSize=7, leading=9, textColor=WHITE,
        )

        subjects_list = list(subject_color_map.keys())
        legend_rows: list[list] = []
        temp_row: list = []

        for i, subject in enumerate(subjects_list):
            desig = next((d for d in designations if d.subject == subject), None)
            group = desig.group_code if desig else ''
            hrs = desig.weekly_hours or 0 if desig else 0

            cell_text = f'<font color="white"><b>{subject}</b> ({group}) — {hrs}h/sem</font>'
            temp_row.append(Paragraph(cell_text, legend_cell_style))

            if len(temp_row) == 3 or i == len(subjects_list) - 1:
                while len(temp_row) < 3:
                    temp_row.append('')
                legend_rows.append(temp_row)
                temp_row = []

        legend_col_w = int(page_width / 3)
        legend_table = Table(legend_rows, colWidths=[legend_col_w] * 3)

        legend_style_cmds = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]
        # Color each legend cell
        flat_idx = 0
        for row_idx, row in enumerate(legend_rows):
            for col_idx, cell in enumerate(row):
                if cell and flat_idx < len(subjects_list):
                    color = subject_color_map[subjects_list[flat_idx]]
                    legend_style_cmds.append(
                        ('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), color)
                    )
                if cell:
                    flat_idx += 1

        legend_table.setStyle(TableStyle(legend_style_cmds))
        elements.append(legend_table)

    # ── Footer ────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 16))
    sep = Table([['']], colWidths=['100%'])
    sep.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.gray)]))
    elements.append(sep)
    elements.append(Spacer(1, 4))

    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7, textColor=colors.gray, alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")}  |  UPDS — Sistema de Planilla Docentes',
        footer_style,
    ))

    doc.build(elements)
    logger.info("Generated schedule PDF: %s", filename)
    return str(filepath)
