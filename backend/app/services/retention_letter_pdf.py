from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parents[2] / "data" / "assets"
ISOLOGO_PATH = ASSETS_DIR / "isologo_upds.png"

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def _output_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "retention_letters"
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_retention_letter(
    teacher_name: str,
    teacher_ci: str,
    titulo: str,          # "Dr.", "Lic.", "Ing.", etc.
    matricula: str,       # Professional license number
    materias: list[str],  # List of subject names
    mes_cobro: int,       # Month number (1-12)
    anio_cobro: int,      # Year
    periodo: str,         # e.g. "I/2026"
) -> str:
    """Generate the retention letter PDF and return the file path."""
    now = datetime.now()

    styles = getSampleStyleSheet()

    # Custom styles
    normal = ParagraphStyle(
        'LetterNormal', parent=styles['Normal'],
        fontSize=11, leading=15, fontName='Times-Roman',
    )
    normal_right = ParagraphStyle('LetterRight', parent=normal, alignment=TA_RIGHT)
    normal_justify = ParagraphStyle('LetterJustify', parent=normal, alignment=TA_JUSTIFY)
    normal_center = ParagraphStyle('LetterCenter', parent=normal, alignment=TA_CENTER)
    bold = ParagraphStyle('LetterBold', parent=normal, fontName='Times-Bold')
    bold_upper = ParagraphStyle('LetterBoldUpper', parent=bold)
    ref_style = ParagraphStyle(
        'LetterRef', parent=normal,
        alignment=TA_RIGHT, fontName='Times-Bold',
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = teacher_name.replace(' ', '_')
    filename = f"carta_retencion_{safe_name}_{timestamp}.pdf"
    filepath = _output_dir() / filename

    doc = SimpleDocTemplate(
        str(filepath), pagesize=A4,
        leftMargin=3 * cm, rightMargin=3 * cm,
        topMargin=2.5 * cm, bottomMargin=2.5 * cm,
    )
    elements = []

    # Logo — large, top-left
    if ISOLOGO_PATH.exists():
        logo = Image(str(ISOLOGO_PATH), width=4 * cm, height=4 * cm)
        logo.hAlign = 'LEFT'
        elements.append(logo)
        elements.append(Spacer(1, 6 * mm))

    # Date — right aligned
    dia = str(now.day)
    mes_name = MONTH_NAMES.get(now.month, str(now.month))
    anio = str(now.year)
    elements.append(Paragraph(f"Cobija, {dia} de {mes_name} de {anio}", normal_right))
    elements.append(Spacer(1, 15 * mm))

    # Addressee
    elements.append(Paragraph("Lic. Luis Michel Bravo Alencar", normal))
    elements.append(Paragraph(
        "<b>RECTOR DE LA UNIVERSIDAD PRIVADA DOMINGO SAVIO – UNIPANDO S.R.L.</b>",
        bold_upper,
    ))
    elements.append(Paragraph("PRESENTE.-", bold_upper))
    elements.append(Spacer(1, 12 * mm))

    # Reference — right, bold, underlined
    elements.append(Paragraph(
        "<u><b>Ref.- SOLICITUD DE RETENCIÓN DE IMPUESTO RC-IVA 13%</b></u>",
        ref_style,
    ))
    elements.append(Spacer(1, 10 * mm))

    # Greeting
    elements.append(Paragraph("De mi consideración:", normal))
    elements.append(Spacer(1, 5 * mm))

    # Body — justified
    mes_cobro_name = MONTH_NAMES.get(mes_cobro, str(mes_cobro))
    body_text = (
        f"Por medio de la presente me dirijo a su autoridad con la finalidad de solicitarle "
        f"la retención de impuesto de mis honorarios de acuerdo al contrato del Periodo "
        f"{periodo} por concepto de docencia correspondiente al mes de "
        f"{mes_cobro_name} {anio_cobro}."
    )
    elements.append(Paragraph(body_text, normal_justify))
    elements.append(Spacer(1, 8 * mm))

    # Teacher data
    elements.append(Paragraph(f"{titulo}  {teacher_name}", normal))
    elements.append(Paragraph(f"Matrícula Profesional: {matricula}", normal))
    elements.append(Paragraph(f"Cédula de identidad: {teacher_ci}", normal))

    # Materias — list all
    materias_text = ", ".join(materias) if materias else "—"
    elements.append(Paragraph(f"Materia(s): {materias_text}", normal))
    elements.append(Spacer(1, 10 * mm))

    # Farewell — justified
    farewell = (
        "Sin otro particular no dudando de su colaboración, aprovecho la oportunidad para saludar "
        "a Ud. con las consideraciones más distinguidas."
    )
    elements.append(Paragraph(farewell, normal_justify))
    elements.append(Spacer(1, 20 * mm))

    # Atte.
    elements.append(Paragraph("Atte.", normal))
    elements.append(Spacer(1, 25 * mm))

    # Signature — centered
    elements.append(Paragraph("___________________________", normal_center))
    elements.append(Paragraph(f"{titulo} {teacher_name}", normal_center))
    elements.append(Paragraph(f"C.I. {teacher_ci}", normal_center))

    doc.build(elements)
    logger.info("Generated retention letter PDF: %s", filename)
    return str(filepath)
