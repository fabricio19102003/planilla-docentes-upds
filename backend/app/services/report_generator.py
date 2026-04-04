from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_RIGHT
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.report import Report

logger = logging.getLogger(__name__)

# UPDS Colors
NAVY = colors.HexColor('#003366')
BLUE = colors.HexColor('#0066CC')
SKY = colors.HexColor('#4DA8DA')
LIGHT_BLUE = colors.HexColor('#E8F4FD')
LIGHT_GRAY = colors.HexColor('#F5F5F5')

# Paths — parents[2] = backend/  (file is at backend/app/services/report_generator.py)
ASSETS_DIR = Path(__file__).resolve().parents[2] / "data" / "assets"
LOGO_PATH = ASSETS_DIR / "logo_upds.png"

MONTH_NAMES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


def _output_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _add_header(elements: list, styles: Any, title: str, subtitle: str = "") -> None:
    """Add UPDS branded header to the document."""
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=2.5 * inch, height=0.65 * inch)
        logo.hAlign = 'LEFT'
        elements.append(logo)
        elements.append(Spacer(1, 8))

    # Title
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Title'],
        fontSize=16, textColor=NAVY, spaceAfter=4
    )
    elements.append(Paragraph(title, title_style))

    if subtitle:
        sub_style = ParagraphStyle(
            'ReportSubtitle', parent=styles['Normal'],
            fontSize=10, textColor=BLUE, spaceAfter=12
        )
        elements.append(Paragraph(subtitle, sub_style))

    # Divider line
    elements.append(Spacer(1, 4))
    divider_table = Table([['']], colWidths=['100%'])
    divider_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, NAVY),
    ]))
    elements.append(divider_table)
    elements.append(Spacer(1, 12))


def _add_footer_info(elements: list, styles: Any) -> None:
    """Add generation timestamp footer."""
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=8, textColor=colors.gray, alignment=TA_RIGHT
    )
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — UPDS Sistema de Planilla Docentes",
        footer_style
    ))


class ReportGenerator:

    def __init__(self) -> None:
        self.styles = getSampleStyleSheet()

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
    ) -> Report:
        """Generate a financial report PDF with payment breakdown by teacher/designation."""
        from app.services.planilla_generator import PlanillaGenerator

        gen = PlanillaGenerator()
        rows, _, warnings = gen._build_planilla_data(db, month=month, year=year)

        # Apply filters
        if teacher_ci:
            rows = [r for r in rows if r.teacher_ci == teacher_ci]
        if semester:
            rows = [r for r in rows if r.semester and r.semester.upper() == semester.upper()]
        if group_code:
            rows = [r for r in rows if r.group_code == group_code]
        if subject:
            rows = [r for r in rows if subject.lower() in r.subject.lower()]

        # Build title
        filter_parts = [f"{MONTH_NAMES.get(month, str(month))} {year}"]
        if teacher_ci:
            teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
            if teacher:
                filter_parts.append(f"Docente: {teacher.full_name}")
        if semester:
            filter_parts.append(f"Semestre: {semester}")
        if group_code:
            filter_parts.append(f"Grupo: {group_code}")
        if subject:
            filter_parts.append(f"Materia: {subject}")

        title = "Reporte Financiero"
        subtitle = " · ".join(filter_parts)

        # Generate PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_financiero_{timestamp}.pdf"
        filepath = _output_dir() / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=15*mm, rightMargin=15*mm,
            topMargin=15*mm, bottomMargin=15*mm
        )
        elements: list = []

        _add_header(elements, self.styles, title, subtitle)

        # Summary stats
        total_payment = sum(r.calculated_payment for r in rows)
        total_base = sum(r.base_monthly_hours for r in rows)
        total_absent = sum(r.absent_hours for r in rows)
        total_payable = sum(r.payable_hours for r in rows)
        unique_teachers = len(set(r.teacher_ci for r in rows))

        summary_data = [
            ['Docentes', 'Designaciones', 'Hrs Asignadas', 'Hrs Ausencia', 'Hrs a Pagar', 'Total (Bs)'],
            [str(unique_teachers), str(len(rows)), f'{total_base}h', f'{total_absent}h', f'{total_payable}h', f'{total_payment:,.2f}'],
        ]
        summary_table = Table(summary_data, colWidths=[70, 80, 80, 80, 80, 85])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        # Detail table
        detail_header = ['Docente', 'Materia', 'Grupo', 'Hrs Base', 'Ausencias', 'Hrs Pagar', 'Monto (Bs)']
        detail_data: list = [detail_header]
        for r in sorted(rows, key=lambda x: (-x.calculated_payment, x.teacher_name)):
            detail_data.append([
                r.teacher_name[:30],
                r.subject[:25],
                r.group_code,
                str(r.base_monthly_hours),
                str(r.absent_hours) if r.absent_hours > 0 else '0',
                str(r.payable_hours),
                f'{r.calculated_payment:,.2f}',
            ])

        col_widths = [110, 100, 40, 45, 50, 50, 70]
        detail_table = Table(detail_data, colWidths=col_widths, repeatRows=1)
        detail_style = [
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ]
        detail_table.setStyle(TableStyle(detail_style))
        elements.append(detail_table)

        _add_footer_info(elements, self.styles)
        doc.build(elements)

        # Save report record
        report = Report(
            report_type='financial',
            title=title,
            description=subtitle,
            filters={'month': month, 'year': year, 'teacher_ci': teacher_ci, 'semester': semester, 'group_code': group_code, 'subject': subject},
            file_path=str(filepath),
            file_size=filepath.stat().st_size,
            generated_by=generated_by,
            status='generated',
        )
        db.add(report)
        db.flush()

        logger.info("Generated financial report: %s (%d rows, %d bytes)", filename, len(rows), filepath.stat().st_size)
        return report

    def generate_attendance_report(
        self,
        db: Session,
        month: int,
        year: int,
        teacher_ci: str | None = None,
        semester: str | None = None,
        group_code: str | None = None,
        generated_by: int | None = None,
    ) -> Report:
        """Generate an attendance detail report PDF."""
        # Query attendance records
        query = db.query(AttendanceRecord).filter(
            AttendanceRecord.month == month,
            AttendanceRecord.year == year,
        )

        if teacher_ci:
            query = query.filter(AttendanceRecord.teacher_ci == teacher_ci)

        records = query.order_by(
            AttendanceRecord.teacher_ci,
            AttendanceRecord.date,
        ).all()

        # Load designations for context
        desig_map: dict[int, Designation] = {}
        desig_ids = set(r.designation_id for r in records)
        if desig_ids:
            desigs = db.query(Designation).filter(Designation.id.in_(desig_ids)).all()
            desig_map = {d.id: d for d in desigs}

        # Apply filters on designation
        if semester or group_code:
            filtered_desig_ids: set[int] = set()
            for did, d in desig_map.items():
                if semester and d.semester.upper() != semester.upper():
                    continue
                if group_code and d.group_code != group_code:
                    continue
                filtered_desig_ids.add(did)
            records = [r for r in records if r.designation_id in filtered_desig_ids]

        # Load teacher names
        teacher_cis = set(r.teacher_ci for r in records)
        teachers: dict[str, Teacher] = {
            t.ci: t for t in db.query(Teacher).filter(Teacher.ci.in_(teacher_cis)).all()
        } if teacher_cis else {}

        # Build title
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
            leftMargin=15*mm, rightMargin=15*mm,
            topMargin=15*mm, bottomMargin=15*mm
        )
        elements: list = []

        _add_header(elements, self.styles, title, subtitle)

        # Summary
        attended = sum(1 for r in records if r.status == 'ATTENDED')
        late = sum(1 for r in records if r.status == 'LATE')
        absent = sum(1 for r in records if r.status == 'ABSENT')
        total = len(records)
        rate = (attended + late) / total * 100 if total > 0 else 0

        summary_data = [
            ['Total Registros', 'Asistidos', 'Tardanzas', 'Ausencias', 'Tasa Asistencia'],
            [str(total), str(attended), str(late), str(absent), f'{rate:.1f}%'],
        ]
        summary_table = Table(summary_data, colWidths=[90, 80, 80, 80, 90])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, 1), LIGHT_BLUE),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        # Detail table — note: actual_entry/actual_exit are the real field names
        STATUS_LABELS = {'ATTENDED': 'Asistido', 'LATE': 'Tardanza', 'ABSENT': 'Ausente', 'NO_EXIT': 'Sin salida'}
        detail_header = ['Fecha', 'Docente', 'Materia', 'Grupo', 'Estado', 'Entrada', 'Salida', 'Hrs Acad.']
        detail_data: list = [detail_header]

        for r in records:
            desig = desig_map.get(r.designation_id)
            teacher = teachers.get(r.teacher_ci)
            detail_data.append([
                r.date.strftime('%d/%m') if r.date else '',
                (teacher.full_name if teacher else r.teacher_ci)[:25],
                (desig.subject if desig else '')[:20],
                desig.group_code if desig else '',
                STATUS_LABELS.get(r.status, r.status),
                r.actual_entry.strftime('%H:%M') if r.actual_entry else '—',
                r.actual_exit.strftime('%H:%M') if r.actual_exit else '—',
                str(r.academic_hours) if r.academic_hours else '0',
            ])

        col_widths = [40, 100, 90, 35, 55, 42, 42, 40]
        detail_table = Table(detail_data, colWidths=col_widths, repeatRows=1)

        # Color rows by status
        detail_style_list: list = [
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('ALIGN', (4, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]
        for i, r in enumerate(records):
            row_idx = i + 1
            if r.status == 'ABSENT':
                detail_style_list.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#FEE2E2')))
            elif r.status == 'LATE':
                detail_style_list.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#FEF3C7')))
            elif row_idx % 2 == 0:
                detail_style_list.append(('BACKGROUND', (0, row_idx), (-1, row_idx), LIGHT_GRAY))

        detail_table.setStyle(TableStyle(detail_style_list))
        elements.append(detail_table)

        _add_footer_info(elements, self.styles)
        doc.build(elements)

        report = Report(
            report_type='attendance',
            title=title,
            description=subtitle,
            filters={'month': month, 'year': year, 'teacher_ci': teacher_ci, 'semester': semester, 'group_code': group_code},
            file_path=str(filepath),
            file_size=filepath.stat().st_size,
            generated_by=generated_by,
            status='generated',
        )
        db.add(report)
        db.flush()

        logger.info("Generated attendance report: %s (%d records, %d bytes)", filename, len(records), filepath.stat().st_size)
        return report

    def generate_comparative_report(
        self,
        db: Session,
        year: int,
        teacher_ci: str | None = None,
        generated_by: int | None = None,
    ) -> Report:
        """Generate a month-by-month comparative report for a year."""
        from app.services.planilla_generator import PlanillaGenerator

        # Find which months have attendance data
        months_query = db.query(
            AttendanceRecord.month
        ).filter(AttendanceRecord.year == year).distinct().order_by(AttendanceRecord.month).all()
        months = [m[0] for m in months_query]

        if not months:
            months = [datetime.now().month]

        gen = PlanillaGenerator()

        monthly_data = []
        for m in months:
            rows, _, _ = gen._build_planilla_data(db, month=m, year=year)
            if teacher_ci:
                rows = [r for r in rows if r.teacher_ci == teacher_ci]

            total_payment = sum(r.calculated_payment for r in rows)
            total_base = sum(r.base_monthly_hours for r in rows)
            total_absent = sum(r.absent_hours for r in rows)
            total_payable = sum(r.payable_hours for r in rows)
            unique_teachers = len(set(r.teacher_ci for r in rows))

            monthly_data.append({
                'month': m,
                'month_name': MONTH_NAMES.get(m, str(m)),
                'teachers': unique_teachers,
                'base_hours': total_base,
                'absent_hours': total_absent,
                'payable_hours': total_payable,
                'total_payment': total_payment,
            })

        # Title
        filter_parts = [f"Año {year}"]
        if teacher_ci:
            teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
            if teacher:
                filter_parts.append(f"Docente: {teacher.full_name}")

        title = "Reporte Comparativo Mensual"
        subtitle = " · ".join(filter_parts)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_comparativo_{timestamp}.pdf"
        filepath = _output_dir() / filename

        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            leftMargin=15*mm, rightMargin=15*mm,
            topMargin=15*mm, bottomMargin=15*mm
        )
        elements: list = []

        _add_header(elements, self.styles, title, subtitle)

        # Comparative table
        comp_header = ['Mes', 'Docentes', 'Hrs Asignadas', 'Hrs Ausencia', 'Hrs a Pagar', 'Total (Bs)']
        comp_data: list = [comp_header]
        grand_total = 0.0
        for md in monthly_data:
            comp_data.append([
                md['month_name'],
                str(md['teachers']),
                f"{md['base_hours']}h",
                f"{md['absent_hours']}h",
                f"{md['payable_hours']}h",
                f"{md['total_payment']:,.2f}",
            ])
            grand_total += md['total_payment']

        # Total row
        comp_data.append([
            'TOTAL', '', '', '', '',
            f"{grand_total:,.2f}",
        ])

        comp_table = Table(comp_data, colWidths=[80, 65, 80, 80, 80, 85])
        comp_style: list = [
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, LIGHT_GRAY]),
            # Total row
            ('BACKGROUND', (0, -1), (-1, -1), NAVY),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]
        comp_table.setStyle(TableStyle(comp_style))
        elements.append(comp_table)

        _add_footer_info(elements, self.styles)
        doc.build(elements)

        report = Report(
            report_type='comparative',
            title=title,
            description=subtitle,
            filters={'year': year, 'teacher_ci': teacher_ci},
            file_path=str(filepath),
            file_size=filepath.stat().st_size,
            generated_by=generated_by,
            status='generated',
        )
        db.add(report)
        db.flush()

        logger.info("Generated comparative report: %s (%d months, %d bytes)", filename, len(monthly_data), filepath.stat().st_size)
        return report
