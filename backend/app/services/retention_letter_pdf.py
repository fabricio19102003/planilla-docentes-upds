from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

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
    titulo: str,
    matricula: str,
    materias: list[str],
    mes_cobro: int,
    anio_cobro: int,
    periodo: str,
) -> str:
    """Generate the retention letter PDF — all content on a single page."""
    now = datetime.now()
    styles = getSampleStyleSheet()

    # ── Styles ────────────────────────────────────────────────────────
    normal = ParagraphStyle('LN', parent=styles['Normal'], fontSize=11, leading=14, fontName='Times-Roman')
    normal_right = ParagraphStyle('LNR', parent=normal, alignment=TA_RIGHT)
    normal_justify = ParagraphStyle('LNJ', parent=normal, alignment=TA_JUSTIFY)
    normal_center = ParagraphStyle('LNC', parent=normal, alignment=TA_CENTER)
    bold_style = ParagraphStyle('LB', parent=normal, fontName='Times-Bold')
    ref_style = ParagraphStyle('LRef', parent=normal, alignment=TA_RIGHT, fontName='Times-Bold')

    timestamp = now.strftime("%Y%m%d_%H%M%S")
    safe_name = teacher_name.replace(' ', '_')
    filename = f"carta_retencion_{safe_name}_{timestamp}.pdf"
    filepath = _output_dir() / filename

    # Tight margins to fit everything on one page
    doc = SimpleDocTemplate(
        str(filepath), pagesize=A4,
        leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    elements: list = []

    # ── Logo — top left, large ────────────────────────────────────────
    if ISOLOGO_PATH.exists():
        logo = Image(str(ISOLOGO_PATH), width=3.5 * cm, height=3.5 * cm)
        logo.hAlign = 'LEFT'
        elements.append(logo)
        elements.append(Spacer(1, 2 * mm))

    # ── Date — right aligned, close to top ────────────────────────────
    dia = str(now.day)
    mes_name = MONTH_NAMES.get(now.month, str(now.month))
    anio = str(now.year)
    elements.append(Paragraph(f"Cobija, {dia} de {mes_name} de {anio}", normal_right))
    elements.append(Spacer(1, 8 * mm))

    # ── Addressee ─────────────────────────────────────────────────────
    elements.append(Paragraph("Lic. Luis Michel Bravo Alencar", normal))
    elements.append(Paragraph(
        "<b>RECTOR DE LA UNIVERSIDAD PRIVADA DOMINGO SAVIO – UNIPANDO S.R.L.</b>",
        bold_style,
    ))
    elements.append(Paragraph("PRESENTE.-", bold_style))
    elements.append(Spacer(1, 8 * mm))

    # ── Reference ─────────────────────────────────────────────────────
    elements.append(Paragraph(
        "<u><b>Ref.- SOLICITUD DE RETENCIÓN DE IMPUESTO RC-IVA 13%</b></u>",
        ref_style,
    ))
    elements.append(Spacer(1, 6 * mm))

    # ── Greeting ──────────────────────────────────────────────────────
    elements.append(Paragraph("De mi consideración:", normal))
    elements.append(Spacer(1, 4 * mm))

    # ── Body ──────────────────────────────────────────────────────────
    mes_cobro_name = MONTH_NAMES.get(mes_cobro, str(mes_cobro))
    body_text = (
        f"Por medio de la presente me dirijo a su autoridad con la finalidad de solicitarle "
        f"la retención de impuesto de mis honorarios de acuerdo al contrato del Periodo "
        f"{periodo} por concepto de docencia correspondiente al mes de "
        f"{mes_cobro_name} {anio_cobro}."
    )
    elements.append(Paragraph(body_text, normal_justify))
    elements.append(Spacer(1, 6 * mm))

    # ── Teacher data ──────────────────────────────────────────────────
    elements.append(Paragraph(f"{titulo}  {teacher_name}", normal))
    elements.append(Paragraph(f"Matrícula Profesional: {matricula}", normal))
    elements.append(Paragraph(f"Cédula de identidad: {teacher_ci}", normal))

    materias_text = ", ".join(materias) if materias else "—"
    elements.append(Paragraph(f"Materia(s): {materias_text}", normal))
    elements.append(Spacer(1, 6 * mm))

    # ── Farewell ──────────────────────────────────────────────────────
    farewell = (
        "Sin otro particular no dudando de su colaboración, aprovecho la oportunidad para saludar "
        "a Ud. con las consideraciones más distinguidas."
    )
    elements.append(Paragraph(farewell, normal_justify))
    elements.append(Spacer(1, 12 * mm))

    # ── Atte. ─────────────────────────────────────────────────────────
    elements.append(Paragraph("Atte.", normal))
    elements.append(Spacer(1, 18 * mm))

    # ── Signature ─────────────────────────────────────────────────────
    elements.append(Paragraph("___________________________", normal_center))
    elements.append(Paragraph(f"{titulo} {teacher_name}", normal_center))
    elements.append(Paragraph(f"C.I. {teacher_ci}", normal_center))

    doc.build(elements)
    logger.info("Generated retention letter PDF: %s", filename)
    return str(filepath)
