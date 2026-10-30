"""
Service: Contract PDF Generator

Generates formal employment contract PDFs for teachers using ReportLab.
The contract follows the EXACT UPDS template text (plantilla_contrato_docente.txt).

Output: backend/data/contracts/Contrato_{TeacherName}_{date}.pdf
"""
from __future__ import annotations

import logging
import io
from collections import defaultdict
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether,
)
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from app.models.teacher import Teacher
    from app.models.designation import Designation

logger = logging.getLogger(__name__)

CONTRACT_PAGE_SIZE = (8.5 * inch, 13 * inch)
_LEGACY_SUBJECT_TABLE_COLUMN_WEIGHTS = (1.0, 9.0, 3.0, 2.5)


class _InvariantContractCanvas(Canvas):
    """ReportLab canvas with reproducible metadata and document identifiers."""

    def __init__(self, *args, **kwargs):
        kwargs["invariant"] = 1
        super().__init__(*args, **kwargs)

def _output_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "contracts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _make_styles() -> dict:
    """Build and return all paragraph styles used in the contract."""
    base = getSampleStyleSheet()

    normal = ParagraphStyle(
        "CN", parent=base["Normal"],
        fontSize=10, leading=13, fontName="Times-Roman",
    )
    justify = ParagraphStyle(
        "CJ", parent=normal, alignment=TA_JUSTIFY, leading=14,
    )
    center = ParagraphStyle(
        "CC", parent=normal, alignment=TA_CENTER,
    )
    right = ParagraphStyle(
        "CR", parent=normal, alignment=TA_RIGHT,
    )
    bold = ParagraphStyle(
        "CB", parent=normal, fontName="Times-Bold",
    )
    bold_center = ParagraphStyle(
        "CBC", parent=bold, alignment=TA_CENTER,
    )
    bold_justify = ParagraphStyle(
        "CBJ", parent=bold, alignment=TA_JUSTIFY,
    )
    clause_title = ParagraphStyle(
        "CT", parent=bold,
        fontSize=10, fontName="Times-Bold",
        spaceBefore=6, spaceAfter=3,
        keepWithNext=1,
        alignment=TA_JUSTIFY,
    )
    title_main = ParagraphStyle(
        "CTM", parent=bold_center,
        fontSize=11, leading=15, spaceAfter=4,
    )
    # Bullet list item — indented
    bullet = ParagraphStyle(
        "CBL", parent=normal,
        alignment=TA_JUSTIFY,
        leftIndent=14, leading=14,
    )

    return {
        "normal": normal,
        "justify": justify,
        "center": center,
        "right": right,
        "bold": bold,
        "bold_center": bold_center,
        "bold_justify": bold_justify,
        "clause_title": clause_title,
        "title_main": title_main,
        "bullet": bullet,
    }


def _page_number_canvas(canvas, doc):
    """Draw page number footer on every page."""
    canvas.saveState()
    canvas.setFont("Times-Roman", 9)
    page_num = canvas.getPageNumber()
    text = f"Página {page_num}"
    canvas.drawCentredString(CONTRACT_PAGE_SIZE[0] / 2, 1.5 * cm, text)
    canvas.restoreState()


def _subject_table_column_widths() -> tuple[float, float, float, float]:
    """Scale the established subject-table proportions to the contract width."""
    usable_width = CONTRACT_PAGE_SIZE[0] - 3.0 * cm - 2.5 * cm
    total_weight = sum(_LEGACY_SUBJECT_TABLE_COLUMN_WEIGHTS)
    return tuple(
        usable_width * weight / total_weight
        for weight in _LEGACY_SUBJECT_TABLE_COLUMN_WEIGHTS
    )

def _contract_table(table_data: list, col_widths) -> Table:
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F2F2F2")),
    ]))
    return table


def _signature_elements(styles: dict) -> list:
    """Signature block — labels only, no names."""
    elements: list = [Spacer(1, 35 * mm)]

    sig_data = [
        [
            Paragraph("___________________________", styles["center"]),
            Paragraph("", styles["center"]),
            Paragraph("___________________________", styles["center"]),
        ],
        [
            Paragraph("<b>EL COMITENTE</b>", styles["bold_center"]),
            Paragraph("", styles["center"]),
            Paragraph("<b>EL CONTRATISTA</b>", styles["bold_center"]),
        ],
    ]

    sig_table = Table(sig_data, colWidths=[6.5 * cm, 3.0 * cm, 6.5 * cm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)
    return elements


def _legal_contract_elements(
    styles: dict,
    *,
    teacher_name: str,
    teacher_ci: str,
    department: str,
    subject_sections: list[tuple[str | None, list[tuple[str, str, str]]]],
    duration_text: str,
    start_date: str,
    end_date: str,
    rate_html: str,
    signature_date: str | None = None,
    comitente: dict[str, str] | None = None,
) -> list:
    """Build the UPDS contract clauses shared by every contract renderer."""
    comitente = _resolved_comitente(comitente)
    rep_name = escape(comitente["representative_name"])
    rep_ci = escape(comitente["representative_ci"])
    power_number = escape(comitente["power_number"])
    power_date = _format_power_date(comitente["power_date"])
    notary_office = escape(comitente["notary_office"])
    notary_name = escape(comitente["notary_name"])
    elements: list = []

    # ── TITLE ──────────────────────────────────────────────────────────
    elements.append(Paragraph(
        "CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES",
        styles["title_main"],
    ))
    elements.append(Spacer(1, 6 * mm))

    # ── INTRO PARAGRAPH ────────────────────────────────────────────────
    elements.append(Paragraph(
        "Conste por el presente documento, un CONTRATO PRIVADO DE PRESTACIÓN DE SERVICIOS "
        "PROFESIONALES, que con el solo reconocimiento de firmas tendrá la fuerza probatoria "
        "de un documento público como lo establece el artículo 1297 del Código Civil; y que "
        "estará sujeto al tenor de los artículos 450, 454, 519, 523, 732 y siguientes del "
        "Código Civil y a las siguientes cláusulas y condiciones siguientes:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── PRIMERA: (DE LAS PARTES) ───────────────────────────────────────
    elements.append(Paragraph(
        "<b>PRIMERA: (DE LAS PARTES). –</b><br/>"
        "Concurren a la celebración del presente contrato, las siguientes partes:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    # Numbered list for PRIMERA
    items_primera = [
        (
            "Por una parte, UNIPANDO S.R.L, registrada bajo la Matrícula de Comercio "
            "Nº 00207595, otorgada por el Registro de Comercio concesionario FUNDEMPRESA, "
            "con NIT 456850023, con Registro Obligatorio de Empleadores R.O.E. Nº456850023-1 "
            "domiciliada en la Avenida 16 de julio N° 128 Barrio Central de esta Ciudad de "
            f"Cobija, representada legalmente en este acto por el señor {rep_name} "
            f"con CI. N.º {rep_ci} Boliviano, mayor de edad, hábil por ley, domiciliado en "
            "esta Ciudad Cobija, en virtud al Poder Especial, amplio y suficiente según consta en "
            f"el Testimonio N. º{power_number}, de fecha {power_date}, otorgado ante la "
            f"Notaría de Fe Pública N.º {notary_office}, a cargo del Notario {notary_name}, quien "
            'en adelante y para los efectos del presente contrato se denominará "COMITENTE".'
        ),
        (
            f'Por otra, el señor(a) <b>{escape(teacher_name)}</b> hábil por ley, con C.I. '
            f'<b>{escape(teacher_ci)} {escape(department)}</b>, con domicilio en la Ciudad de Cobija, a quien '
            'se denominará en adelante para fines de este contrato como CONTRATISTA.'
        ),
        (
            'EL COMITENTE y EL CONTRATISTA podrán denominarse en conjunto "LAS PARTES".'
        ),
    ]
    for idx, text in enumerate(items_primera, start=1):
        elements.append(Paragraph(
            f"{idx}. {text}",
            styles["bullet"],
        ))
        elements.append(Spacer(1, 2 * mm))
    elements.append(Spacer(1, 3 * mm))

    # ── SEGUNDA: (OBJETO) ──────────────────────────────────────────────
    elements.append(Paragraph(
        "<b>SEGUNDA: (OBJETO).-</b><br/>"
        "El presente contrato tiene por objeto que el CONTRATISTA elabore y ejecute para el "
        "COMITENTE, un Proyecto Formativo de Aula orientado para cada una de las siguientes "
        "materias:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 3 * mm))

    # ── Subjects tables — one per activity when the contract is mixed ─
    col_widths = _subject_table_column_widths()
    for subtitle, rows in subject_sections:
        if subtitle:
            elements.append(Paragraph(f"<b>{escape(subtitle)}:</b>", styles["justify"]))
            elements.append(Spacer(1, 2 * mm))
        table_data = [["Nº", "Materia", "Semestre", "Total Horas"]]
        for idx, (subject, semester, total_hours) in enumerate(rows, start=1):
            table_data.append([str(idx), subject, semester, total_hours])
        elements.append(_contract_table(table_data, col_widths))
        elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        "Su ejecución, desarrollo y aplicación será realizado mediante el uso de Plataformas "
        "Virtuales, dirigido a estudiantes de la UNIVERSIDAD bajo el Modelo Educativo por "
        "Competencias, de acuerdo al número de Criterios establecidos en el Programa Analítico "
        "de la materia y Orientaciones Académicas que se entenderá son los términos de referencia "
        "sobre los que debe trabajar el CONTRATISTA para la elaboración del Proyecto Formativo de "
        "Aula y cumplimiento de este contrato.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── TERCERA: (ALCANCE) ─────────────────────────────────────────────
    elements.append(Paragraph(
        "<b>TERCERA: (ALCANCE DE LA PRESTACIÓN DE SERVICIOS).-</b><br/>"
        "Para cada materia EL CONTRATISTA, atendiendo a las Orientaciones Académicas que "
        "constituyen los términos de referencia de este contrato, deberá prestar los siguientes "
        "servicios en Coordinación con el jefe de Carreras y/o Asesoría Pedagógica:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    tercera_items = [
        "Elaboración del Proyecto Formativo, cargado a la Plataforma Moodle-UPDS.net u otra que "
        "indique oportunamente el COMITENTE.",
        "Elaboración de la planificación de la evaluación según requerimientos específicos "
        "señalados en las Orientaciones Académicas.",
        "Ejecución y desarrollo de las actividades sincrónicas y asincrónicas, de acuerdo con la "
        "Planificación de Evaluación, todo en interacción con los estudiantes registrados en la "
        "materia, mediante el uso de Plataformas.",
        "Presentación de informes mensuales y a la conclusión del proyecto, debe presentar la "
        "siguiente documentación: Informe de la Asignatura, guardado de calificaciones, "
        "centralizador impreso de calificaciones, mismo que debe presentar en formato físico al "
        "Departamento de Registro.",
        "Aquellas evidencias que no puedan ser verificadas en plataforma, se enviarán a un link "
        "de Jefaturas de Carrera.",
    ]
    for item in tercera_items:
        elements.append(Paragraph(f"• {item}", styles["bullet"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 3 * mm))

    # ── CUARTA: (CONTENIDO MÍNIMO) ─────────────────────────────────────
    elements.append(Paragraph(
        "<b>CUARTA: (CONTENIDO MÍNIMO DEL PROYECTO).-</b><br/>"
        "El Proyecto de cada materia deberá contener en forma enunciativa más no limitativa "
        "lo siguiente:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    cuarta_items = [
        "Fase de Direccionamiento",
        "Fase de Planeación",
        "Fase de Ejecución",
        "Fase de Comunicación",
    ]
    for item in cuarta_items:
        elements.append(Paragraph(f"• {item}", styles["bullet"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 3 * mm))

    # ── QUINTA: (OBLIGACIONES DEL CONTRATISTA) ─────────────────────────
    elements.append(Paragraph(
        "<b>QUINTA: (OBLIGACIONES DEL CONTRATISTA y PRODUCTOS REQUERIDOS).-</b><br/>"
        "Para cada materia se deberá desarrollar el proyecto mediante la Plataforma Virtual "
        "desde el espacio físico – geográfico determinado por el CONTRATISTA, conforme a lo "
        "siguiente:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "<b>Primer:</b> Ejecutará el Proyecto Formativo de Aula Virtual con una carga horaria "
        "mensual designada previamente elaborado por éste, que deberá ser cargado al entorno "
        "virtual hasta el quinto día de iniciado el contrato, sujeto al Programa Analítico y a "
        "las Orientaciones Académicas, entendidos éstos como los términos de referencia otorgados "
        "por la UNIVERSIDAD Preparará cada sesión con materiales técnicos y didácticos adecuados, "
        "aportados por él, haciéndoles conocer a los estudiantes la información básica para la "
        "coordinación e interacción con éstos.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "<b>Segundo:</b> De acuerdo con el calendario de actividades, evaluará continuamente a "
        "los estudiantes, empleando metodología que produzca claramente información probatoria de "
        "la evaluación de cada estudiante y ajustándose plenamente a los criterios de verificación "
        "de la materia que gestiona y que le ha proporcionado EL COMITENTE. Los resultados de las "
        "evaluaciones serán oportunamente puestos en conocimiento de los estudiantes y de la "
        "UNIVERSIDAD. El plazo para la entrega de las evaluaciones es de 72 horas luego de "
        "aplicadas las mismas.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "<b>Tercer:</b> Se obliga a presentar un informe final académico, que incluye la "
        "presentación de informe de la asignatura, guardado de calificaciones e impresión del "
        "centralizador de calificaciones que debe presentar en formato físico al Departamento "
        "de Registro.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "El informe final quedará evidenciado en la plataforma virtual.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "Igualmente se obliga a participar de cualquier reunión virtual o presencial convocada "
        "por EL COMITENTE, en el día y la hora que éste lo determine con la finalidad de ajustar "
        "el Proyecto Formativo de Aula Virtual.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "Así mismo, se obliga a abstenerse de realizar actos, por sí o por terceras personas, "
        "que perjudiquen el desarrollo de las actividades en las PLATAFORMAS VIRTUALES.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "Se obliga también a mantener la confidencialidad aún después de concluido el contrato "
        "sobre la información interna proporcionada por la Universidad; quedando terminantemente "
        "prohibido para EL CONTRATISTA realizar cualquier tipo de reproducción, publicación o "
        "divulgación por cualquier medio verbal, escrito o medios de comunicación privados o "
        "públicos. La omisión de esta obligación involucra la resolución del contrato, en "
        "aplicación del artículo 569 del Código Civil.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── SEXTA: (OBLIGACIONES DEL COMITENTE) ───────────────────────────
    elements.append(Paragraph(
        "<b>SEXTA: (OBLIGACIONES DEL COMITENTE).-</b><br/>"
        "EL COMITENTE se obliga a:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    sexta_items = [
        "Cumplir con todas y cada una de las cláusulas mencionadas en el presente Contrato.",
        "Comunicar clara y oportunamente, en forma escrita al CONTRATISTA, las acciones que "
        "deben realizar con la finalidad de ajustar los resultados esperados del cumplimiento "
        "de este contrato. Comunicaciones escritas que podrán realizarse por correo electrónico "
        "oficial u otro que indique la Universidad.",
        "Efectuar el pago del precio del contrato, una vez el CONTRATISTA, entregue los "
        "productos, documentos e informes que acrediten el cumplimiento de los términos de "
        "referencia del presente contrato.",
    ]
    for item in sexta_items:
        elements.append(Paragraph(f"• {item}", styles["bullet"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "EL COMITENTE, podrá mediante un aviso formal modificar las características de la "
        "prestación de servicios establecidos en la cláusula tercera, en cualquier momento de "
        "la vigencia del presente contrato, siempre tomando en cuenta el perfil profesional "
        "del CONTRATISTA.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "El presente contrato o sus partes integrantes también podrán ser modificadas y será "
        "factible realizar adiciones o complementaciones, siempre que exista entre las partes "
        "mutua voluntad y los acuerdos estén contenidos en adendas escritas.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── SÉPTIMA: (PERFIL DEL CONTRATISTA) ─────────────────────────────
    elements.append(Paragraph(
        "<b>SÉPTIMA: (PERFIL DEL CONTRATISTA).-</b><br/>"
        "El CONTRATISTA, mediante esta cláusula declara:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    septima_items = [
        "Ser profesional de formación universitaria con mayor o igual grado académico "
        "equivalente a la carrera para la cual elaborará y ejecutará el Proyecto Formativo.",
        "Contar con Diplomado en Educación Superior y dos años de experiencia en el ejercicio "
        "en el área de su profesión. En el caso de no contar con el Diplomado en Educación "
        "Superior, deberá demostrar como mínimo cinco años de experiencia en el ejercicio de "
        "su profesión.",
        "Contar con conocimientos sólidos de la materia para la cual elaborará y ejecutará el "
        "Proyecto Formativo.",
        "Contar con conocimientos de planificación, metodología y evaluación pedagógica de "
        "procesos formativos de Educación Superior y por Competencias.",
        "Poseer habilidades comunicativas, actitudes éticas y profesionales para la prestación "
        "del servicio en Plataforma Virtual que se requiere.",
        "Tener conocimiento y manejo de entornos virtuales, como el uso de plataformas virtuales "
        "sincrónicas y asincrónicas.",
    ]
    for item in septima_items:
        elements.append(Paragraph(f"• {item}", styles["bullet"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 4 * mm))

    # ── OCTAVA: (DURACIÓN, PRECIO, FORMA DE PAGO E IMPUESTOS) ─────────
    elements.append(Paragraph(
        "<b>OCTAVA: (DURACIÓN, PRECIO, FORMA DE PAGO E IMPUESTOS).-</b>",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        f"<b>8.1</b> Las partes de mutuo acuerdo establecen que el presente contrato tendrá "
        f"una duración de <b>{duration_text}</b> computables desde el <b>{start_date} al "
        f"{end_date}</b>, plazo durante el cual deberá ejecutar todos los proyectos conforme "
        "a lo estipulado en el presente contrato, en horarios administrados por el CONTRATISTA. "
        "Concluido el plazo, no opera la tácita reconducción del presente contrato.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        f"<b>8.2</b> El precio a ser cancelado de forma parcial conforme a las horas de trabajo "
        f"ejecutadas en cada mes, tomando en cuenta que el valor de la hora del servicio es de "
        f"{rate_html}.<br/>"
        "La forma de pago es la siguiente:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    octava_82_items = [
        "El CONTRATISTA debe presentar el último día hábil del mes un informe del trabajo "
        "ejecutado, indicando la cantidad de horas empleadas para cada proyecto a efectos de "
        "cálculo de su pago.",
        "Una vez aceptado el informe por el COMITENTE, el CONTRATISTA deberá presentar la "
        "correspondiente factura por sus servicios.",
        "El COMITENTE realizará el pago a favor del CONTRATISTA a los 30 días de presentada "
        "la correspondiente factura.",
    ]
    for item in octava_82_items:
        elements.append(Paragraph(f"• {item}", styles["bullet"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "<b>8.3</b> Queda establecido que el monto consignado incluye todos los elementos, "
        "sin excepción alguna, que sean necesarios para la realización y cumplimiento del "
        "servicio y es de exclusiva responsabilidad del CONTRATISTA, prestar el servicio por "
        "el monto establecido como costo del servicio, ya que no se reconocerán ni procederán "
        "pagos por servicios que hiciesen exceder dicho monto.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "Se aclara que correrá por cuenta del CONTRATISTA el pago de todos los impuestos "
        "vigentes en el país a la fecha de firma del presente contrato. En caso de que "
        "posteriormente, el Estado Plurinacional de Bolivia, implantará impuestos adicionales, "
        "disminuyera o incrementara los vigentes, mediante disposición legal expresa, el "
        "CONTRATISTA deberá acogerse a su cumplimiento desde la fecha de vigencia de dicha "
        "normativa.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "El COMITENTE podrá solicitar los respaldos de formularios, depósitos y constancias del "
        "cumplimiento de pago de Impuestos del CONTRATISTA para respaldar el debido cumplimiento "
        "de respaldo de las facturas emitidas.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "Por otra parte el CONTRATISTA se compromete a mantener indemne al COMITENTE de cualquier "
        "tipo de reclamo que le pudieran notificar y en caso de ser obligado por autoridad "
        "competente a realizar alguna retención o pago por cuenta de él se compromete a devolver "
        "al COMITENTE la suma de dinero reclamada más los gastos o costos administrados en que "
        "haya incurrido este último para el cumplimiento de la orden de pago o retención, siendo "
        "esta una suma de dinero exigible, sujeta al pago de intereses y mantenimiento de valor "
        "a la fecha de cumplimiento de pago.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── NOVENA: (GARANTÍA DE CALIDAD) ─────────────────────────────────
    elements.append(Paragraph(
        "<b>NOVENA: (GARANTÍA DE CALIDAD, DE CUMPLIMIENTO DE CONTRATO Y SANCIONES POR "
        "INCUMPLIMIENTO).-</b><br/>"
        "El CONTRATISTA garantiza que reúnen las cualidades prometidas y necesarias para brindar "
        "un servicio de calidad y para el buen cumplimiento del presente contrato. En caso de que "
        "no las reúna y/o no puedan cumplir con la carga horaria de las aulas virtuales se "
        "compromete a dotar por su propia cuenta y costo los recursos necesarios para su "
        "cumplimiento.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "A ese efecto, EL COMITENTE, podrá observar la calidad de los servicios en cualquier "
        "momento de la vigencia del contrato y exigir el cambio y modificación de los mismos; "
        "otorgándole un plazo prudencial, vencido ese plazo si no se efectuara el cambio, "
        "modificación o si no subsanara el incumplimiento, el COMITENTE podrá imponer multas "
        "por incumplimiento de contrato equivalente al 0,5% del valor del contrato por cada "
        "incumplimiento. Esta penalidad se aplicará salvo casos de fuerza mayor, caso fortuito "
        "u otras causas debidamente comprobadas por el COMITENTE debiendo ser comunicadas de "
        "manera inmediata al COMITENTE. Las multas serán cobradas por el COMITENTE mediante "
        "descuentos establecidos en la liquidación de pagos.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── DÉCIMA: (CAUSALES DE RESOLUCIÓN) ──────────────────────────────
    elements.append(Paragraph(
        "<b>DÉCIMA: (CAUSALES DE RESOLUCIÓN DEL CONTRATO).-</b><br/>"
        "Si el CONTRATISTA incumpliere cualquiera de las obligaciones asumidas en este contrato, "
        "EL COMITENTE a su elección podrá resolver y / o rescindir el contrato de pleno derecho, "
        "sin necesidad de intervención de ninguna naturaleza excepto la invocación de las "
        "cláusulas del presente contrato, en estos casos, el CONTRATISTA estará obligado al pago "
        "de todos los gastos, expensas, penas convencionales fijadas en este instrumento y demás "
        "costos ocasionados al COMITENTE por el incumplimiento de la obligación, incluyendo los "
        "relacionados y / o emergentes de la cobranza judicial y / o extrajudicial, honorarios, "
        "derechos, costas y otros, sin excepción. Aplicándose por tanto los Artículos 569, 746 y "
        "747 todos del Código Civil.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "Adicionalmente las causales de resolución del contrato, a decisión unilateral de la "
        "parte perjudicada por el incumplimiento de este contrato constituyen:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    decima_items = [
        "La transferencia, subrogación o cesión de las obligaciones derivadas de este contrato "
        "a favor de terceros, debido a que el cumplimiento de las obligaciones por parte de EL "
        "CONTRATISTA, son personalísimos.",
        "Por muerte, o por privación de libertad, Incapacidad total o parcial y permanente, "
        "del CONTRATISTA.",
        "Por asistir al cumplimiento de sus servicios en estado de ebriedad o bajo efectos de "
        "estupefacientes o cualquier sustancia controlada por la ley 1008 y/o su tenencia.",
        "Cuando el monto de la multa por incumplimiento en la prestación del servicio alcance "
        "el diez por ciento (10%) del monto total del contrato, la decisión del COMITENTE será "
        "optativa y en caso de que la multa llegue al veinte por ciento (20%) del monto total "
        "del contrato será de forma obligatoria.",
        "Por negligencia reiterada de 3 veces en el cumplimiento de los términos de referencia, "
        "u otras especificaciones, o instrucciones escritas por parte del COMITENTE.",
        "Transgresión por parte de EL CONTRATISTA a las normas de ética o comisión de conducta "
        "indebida, o por cometer conductas tipificadas como delitos penales dentro o fuera de "
        "las instalaciones de LA UNIVERSIDAD, en cuyo efecto opera resolución de pleno derecho "
        "(según el art. 569 del código civil) sin mediar previo aviso, ni necesidad de "
        "intervención judicial, con efectos de responsabilidad civil por el perjuicio ocasionado "
        "por dicha conducta anti ética y atrasos notorios en la ejecución de las obligaciones "
        "contractuales, quedando a salvo el derecho de pedir el resarcimiento del daño "
        "ocasionado, mediante lo determinado en lo previsto para Resolución de Conflictos.",
    ]
    for item in decima_items:
        elements.append(Paragraph(f"• {item}", styles["bullet"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 4 * mm))

    # ── DÉCIMA PRIMERA: (NATURALEZA) ───────────────────────────────────
    elements.append(Paragraph(
        "<b>DÉCIMA PRIMERA: (NATURALEZA DE LA RELACION CONTRACTUAL).-</b><br/>"
        "El presente contrato de servicios profesionales, se rige por los artículos 732 y "
        "siguientes del Código Civil, siendo su naturaleza jurídica estrictamente civil, no es "
        "un contrato de Trabajo Laboral, consiguientemente no corresponde ningún pago adicional "
        "por internet, electricidad y otros como beneficios sociales, etc., por cuanto EL "
        "CONTRATISTA, presta sus servicios en forma independiente, bajo su propia dirección, "
        "administrando sus propios recursos, entre ellos además su tiempo en su jornada diaria.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── DÉCIMA SEGUNDA: (PROHIBICIÓN) ─────────────────────────────────
    elements.append(Paragraph(
        "<b>DÉCIMA SEGUNDA: (PROHIBICIÓN).-</b><br/>"
        "El CONTRATISTA, no podrá ceder o subrogar la prestación del servicio bajo ninguna "
        "modalidad en favor de terceros, sin previa autorización expresa y escrita del "
        "COMITENTE, lo contrario a esa situación dará lugar a la resolución del contrato.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── DÉCIMA TERCERA: (SUPERVISIÓN) ─────────────────────────────────
    elements.append(Paragraph(
        "<b>DÉCIMA TERCERA: (SUPERVISIÓN Y EVALUACIONES).-</b><br/>"
        "El CONTRATISTA autoriza al COMITENTE a supervisiones y evaluaciones periódicas en "
        "cualquier momento de la vigencia de este contrato, debiendo absolver en forma escrita "
        "cualesquier duda u observación que EL COMITENTE lo requiera sobre el servicio contratado.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── DÉCIMA CUARTA: (SOLUCIÓN DE CONTROVERSIAS) ────────────────────
    elements.append(Paragraph(
        "<b>DÉCIMA CUARTA: (SOLUCION DE CONTROVERSIAS).-</b><br/>"
        "Las partes acuerdan que toda controversia o divergencia que pueda surgir con relación "
        "a la interpretación, aplicación, cumplimiento y ejecución del presente contrato, que "
        "no sea resuelta de mutuo acuerdo entre las partes dentro de los CINCO (05) días de "
        "haber sido notificado el conflicto a la otra parte, ésta será resuelta ante los "
        "tribunales de justicia de la ciudad de Cobija. La relación contractual entre las partes "
        "relativa al servicio se regirá de acuerdo a la legislación vigente en Estado "
        "Plurinacional de Bolivia.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── DÉCIMA QUINTA: (CONFIDENCIALIDAD) ─────────────────────────────
    elements.append(Paragraph(
        "<b>DÉCIMA QUINTA: (CONFIDENCIALIDAD).-</b> El CONTRATISTA acuerda que toda la "
        "información, documentos y datos a los que puedan acceder que sean confidenciales del "
        "COMITENTE serán mantenidas de manera confidencial y no serán entregados o revelados "
        "por éste a ningún tercero, salvo que cuente con el permiso escrito de la contraparte "
        "o el requerimiento de información emane de una orden judicial. Por otra parte, el "
        "CONTRATISTA se compromete a no utilizarla para realizar actos que puedan constituirse "
        "como competencia directa, indirecta y desvió de clientela, durante la ejecución del "
        "presente contrato y una vez finalizado o resuelto por incumplimiento de contrato de "
        "manera indefinida.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── DÉCIMA SEXTA: (ACUERDO TOTAL) ─────────────────────────────────
    elements.append(Paragraph(
        "<b>DÉCIMA SEXTA: (ACUERDO TOTAL).-</b><br/>"
        "LAS PARTES declaramos y exponemos de forma inequívoca e irrevocable que todos los "
        "compromisos establecidos en este instrumento constituyen un acuerdo de carácter global "
        "y de buena fe, solamente modificable en el futuro mediante otras adendas escritas y en "
        "razón a la voluntad uniforme de éstas.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph(
        "LAS PARTES declaramos también que este acuerdo total y definitivo asumirá, sustituirá "
        "o reemplazará cualquier otra comunicación, compromiso, pacto, obligación y derechos "
        "dispuestos de forma escrita o verbal con anterioridad por las PARTES, en cualquier "
        "escrito privado o público, ya sea de manera general y / o especial cuyo ámbito sea el "
        "del objeto de este contrato.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # ── DÉCIMA SÉPTIMA: (CONFORMIDAD) ─────────────────────────────────
    elements.append(Paragraph(
        "<b>DÉCIMA SÉPTIMA: (CONFORMIDAD).-</b><br/>"
        "Ambas PARTES como señal de conformidad y sin que medie ningún vicio del consentimiento, "
        "firmamos el presente contrato en doble ejemplar de un solo tenor y para un solo efecto.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 6 * mm))

    # ── DATE — right-aligned ─────────────────────────────────────────
    elements.append(Paragraph(
        f"{escape(comitente['city'])}, {signature_date or start_date}.",
        styles["right"],
    ))

    elements.extend(_signature_elements(styles))
    return elements


def generate_contract_pdf(
    teacher: "Teacher",
    designations: list["Designation"],
    department: str,
    duration_text: str,
    start_date: str,
    end_date: str,
    hourly_rate: str = "70,00",
    hourly_rate_literal: str = "Setenta bolivianos 00/100",
) -> str:
    """
    Generate a formal employment contract PDF for a single teacher.

    Args:
        teacher: Teacher ORM instance
        designations: List of Designation ORM instances for this teacher
        department: Department of Bolivia for the CI (e.g. "Pando", "La Paz")
        duration_text: Contract duration in text (e.g. "4 meses y 13 días")
        start_date: Contract start date in Spanish text (e.g. "05 de marzo de 2026")
        end_date: Contract end date in Spanish text (e.g. "18 de julio de 2026")
        hourly_rate: Hourly rate as string with comma separator (e.g. "70,00")
        hourly_rate_literal: Hourly rate in words (e.g. "Setenta bolivianos 00/100")

    Returns:
        Absolute path to the generated PDF file.
    """
    now = datetime.now()
    styles = _make_styles()

    safe_name = teacher.full_name.replace(" ", "_").replace("/", "-")
    date_str = now.strftime("%Y%m%d_%H%M%S")
    filename = f"Contrato_{safe_name}_{date_str}.pdf"
    filepath = _output_dir() / filename

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=CONTRACT_PAGE_SIZE,
        leftMargin=3.0 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    subject_map: dict = defaultdict(lambda: {"semester": "", "total_hours": 0})
    for d in designations:
        subject_map[d.subject]["semester"] = d.semester
        subject_map[d.subject]["total_hours"] += (d.semester_hours or 0)
    rows = [
        (subject, info["semester"], str(info["total_hours"]))
        for subject, info in sorted(subject_map.items())
    ]
    elements = _legal_contract_elements(
        styles,
        teacher_name=teacher.full_name,
        teacher_ci=teacher.ci,
        department=department,
        subject_sections=[(None, rows)],
        duration_text=duration_text,
        start_date=start_date,
        end_date=end_date,
        rate_html=f"<b>Bs. {hourly_rate} ({hourly_rate_literal})</b>",
    )

    # Build PDF with page numbers
    doc.build(elements, onFirstPage=_page_number_canvas, onLaterPages=_page_number_canvas)

    logger.info("Generated contract PDF: %s", filename)
    return str(filepath)


_MONTH_NAMES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

_ORDINAL_CLAUSES = (
    "PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA",
)

_ACTIVITY_SECTIONS = (
    ("theory", "Materias de teoría", "las materias de teoría"),
    ("practice", "Materias de práctica", "las materias de práctica"),
)

_CHANGE_LABELS = {"added": "Alta", "removed": "Retiro", "changed": "Cambio", "full": "Vigente"}


def _number_to_spanish(value: int) -> str:
    """Return a compact Spanish literal for integers from 0 to 10000."""
    if value < 0 or value > 10000:
        raise ValueError("Solo se soportan montos entre 0 y 10000")
    units = {
        0: "cero", 1: "un", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
        6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
        11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince",
        16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve",
        20: "veinte", 21: "veintiún", 22: "veintidós", 23: "veintitrés",
        24: "veinticuatro", 25: "veinticinco", 26: "veintiséis", 27: "veintisiete",
        28: "veintiocho", 29: "veintinueve",
    }
    tens = {
        30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta",
        70: "setenta", 80: "ochenta", 90: "noventa",
    }
    hundreds = {
        100: "cien", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos",
        500: "quinientos", 600: "seiscientos", 700: "setecientos", 800: "ochocientos",
        900: "novecientos",
    }
    if value < 30:
        return units[value]
    if value < 100:
        ten = (value // 10) * 10
        rest = value % 10
        return tens[ten] if rest == 0 else f"{tens[ten]} y {units[rest]}"
    if value < 1000:
        hundred = (value // 100) * 100
        rest = value % 100
        if rest == 0:
            return hundreds[hundred]
        prefix = "ciento" if hundred == 100 else hundreds[hundred]
        return f"{prefix} {_number_to_spanish(rest)}"
    if value == 1000:
        return "mil"
    if value < 10000:
        thousands = value // 1000
        rest = value % 1000
        prefix = "mil" if thousands == 1 else f"{_number_to_spanish(thousands)} mil"
        return prefix if rest == 0 else f"{prefix} {_number_to_spanish(rest)}"
    return "diez mil"


def _format_contract_rate(rate) -> tuple[str, str]:
    amount = Decimal(str(rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount < 0 or amount > Decimal("10000.00"):
        raise ValueError("La tarifa por hora debe estar entre 0 y 10000 Bs")
    integer_part = int(amount)
    cents = int((amount - Decimal(integer_part)) * 100)
    numeric = f"{integer_part},{cents:02d}"
    currency = "boliviano" if integer_part == 1 else "bolivianos"
    literal = f"{_number_to_spanish(integer_part).capitalize()} {currency} {cents:02d}/100"
    return numeric, literal


def _resolved_comitente(comitente: dict[str, str] | None) -> dict[str, str]:
    from app.services.app_settings_service import default_contract_comitente

    return {**default_contract_comitente(), **(comitente or {})}


def _format_power_date(value: str) -> str:
    """Power-of-attorney date as the template writes it: '4 de septiembre de 2024'."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return escape(value)
    return f"{parsed.day} de {_MONTH_NAMES[parsed.month]} de {parsed.year}"


def _format_spanish_date(value: date) -> str:
    return f"{value.day:02d} de {_MONTH_NAMES[value.month]} de {value.year}"


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _format_duration_text(start: date, end: date) -> str:
    if end < start:
        raise ValueError("La fecha de fin del contrato no puede ser anterior a la fecha de inicio")
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    days = (end - _add_months(start, months)).days
    parts: list[str] = []
    if months:
        parts.append(f"{months} mes{'es' if months != 1 else ''}")
    if days:
        parts.append(f"{days} día{'s' if days != 1 else ''}")
    return " y ".join(parts) if parts else "0 días"


def _hours_text(value) -> str:
    amount = Decimal(str(value)).normalize()
    return format(amount.quantize(Decimal(1)) if amount == amount.to_integral() else amount, "f")


def _line_term_hours(line: dict) -> Decimal:
    return Decimal(str(line.get("term_hours") or line["hours"]))


def _rate_html(lines: list[dict]) -> str:
    """Bold hourly-rate fragment; mixed contracts name each activity's rate."""
    parts = []
    for activity, _subtitle, scope in _ACTIVITY_SECTIONS:
        rates = {line["hourly_rate"] for line in lines if line["activity_kind"] == activity}
        if len(rates) > 1:
            raise ValueError(f"El contrato tiene más de una tarifa para {scope}.")
        if rates:
            numeric, literal = _format_contract_rate(rates.pop())
            parts.append((f"<b>Bs. {numeric} ({literal})</b>", scope))
    if len(parts) == 1:
        return parts[0][0]
    return " y de ".join(f"{amount} para {scope}" for amount, scope in parts)


def _activity_groups(lines: list[dict]) -> list[tuple[str | None, list[dict]]]:
    groups = [
        (subtitle, [line for line in lines if line["activity_kind"] == activity])
        for activity, subtitle, _scope in _ACTIVITY_SECTIONS
    ]
    groups = [(subtitle, items) for subtitle, items in groups if items]
    if len(groups) == 1:
        return [(None, groups[0][1])]
    return groups


def _subject_rows(lines: list[dict]) -> list[tuple[str, str, str]]:
    subject_map: dict = defaultdict(lambda: {"semester": "", "total_hours": Decimal(0)})
    for line in lines:
        info = subject_map[line["subject_label"]]
        info["semester"] = line["semester_label"]
        info["total_hours"] += _line_term_hours(line)
    return [
        (subject, info["semester"], _hours_text(info["total_hours"]))
        for subject, info in sorted(subject_map.items())
    ]


def _contract_term(lines: list[dict]) -> tuple[date, date]:
    start = min(date.fromisoformat(line.get("contract_from") or line["effective_from"]) for line in lines)
    end = max(date.fromisoformat(line.get("contract_to") or line["effective_to"]) for line in lines)
    return start, end


def _amendment_hours(line: dict) -> str:
    current = _hours_text(_line_term_hours(line))
    previous = line.get("previous_term_hours") or line.get("previous_hours")
    return current if previous is None else f"{_hours_text(previous)} → {current}"


def _amendment_elements(styles: dict, document: dict) -> list:
    teacher = document["teacher"]
    sequence = int(document["amendment_sequence"])
    effective = _format_spanish_date(date.fromisoformat(str(document["effective_date"])))
    lines = document["lines"]
    metadata_changes = document.get("metadata_changes", [])
    elements: list = [
        Paragraph(
            f"ADENDA N.º {sequence} AL CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES",
            styles["title_main"],
        ),
        Spacer(1, 6 * mm),
        Paragraph(
            f"Conste por el presente documento, la ADENDA N.º {sequence} al CONTRATO PRIVADO DE "
            "PRESTACIÓN DE SERVICIOS PROFESIONALES suscrito entre UNIPANDO S.R.L., en adelante el "
            f"COMITENTE, y el señor(a) <b>{escape(str(teacher['full_name']))}</b> con C.I. "
            f"<b>{escape(str(teacher['ci']))} {escape(str(document['department']))}</b>, en adelante "
            "el CONTRATISTA, conforme a la cláusula SEXTA del contrato, al tenor de las cláusulas "
            "siguientes:",
            styles["justify"],
        ),
        Spacer(1, 4 * mm),
    ]
    clauses = iter(_ORDINAL_CLAUSES)

    if lines:
        elements.append(Paragraph(
            f"<b>{next(clauses)}: (MODIFICACIÓN DE LA CARGA HORARIA).-</b><br/>"
            f"La presente adenda modifica, con efecto desde el {effective}, la carga horaria del "
            "contrato conforme al siguiente detalle:",
            styles["justify"],
        ))
        elements.append(Spacer(1, 3 * mm))
        usable_width = CONTRACT_PAGE_SIZE[0] - 3.0 * cm - 2.5 * cm
        col_widths = [usable_width * weight / 15.5 for weight in (1.0, 7.0, 2.5, 2.5, 2.5)]
        for subtitle, items in _activity_groups(lines):
            if subtitle:
                elements.append(Paragraph(f"<b>{escape(subtitle)}:</b>", styles["justify"]))
                elements.append(Spacer(1, 2 * mm))
            table_data = [["Nº", "Materia", "Semestre", "Modificación", "Total Horas"]]
            ordered = sorted(items, key=lambda line: (line["subject_label"], line["group_label"]))
            for idx, line in enumerate(ordered, start=1):
                table_data.append([
                    str(idx),
                    line["subject_label"],
                    line["semester_label"],
                    _CHANGE_LABELS[line["change_kind"]],
                    _amendment_hours(line),
                ])
            elements.append(_contract_table(table_data, col_widths))
            elements.append(Spacer(1, 3 * mm))
        elements.append(Paragraph(
            f"El valor de la hora del servicio aplicable es de {_rate_html(lines)}.",
            styles["justify"],
        ))
        elements.append(Spacer(1, 4 * mm))

    if metadata_changes:
        elements.append(Paragraph(
            f"<b>{next(clauses)}: (CORRECCIÓN DE DATOS).-</b><br/>"
            "La presente adenda corrige los datos de identificación del contrato conforme al "
            "siguiente detalle:",
            styles["justify"],
        ))
        elements.append(Spacer(1, 3 * mm))
        usable_width = CONTRACT_PAGE_SIZE[0] - 3.0 * cm - 2.5 * cm
        table_data = [["Dato", "Anterior", "Actual"]] + [
            [str(change["label"]), str(change["previous"]), str(change["current"])]
            for change in metadata_changes
        ]
        elements.append(_contract_table(table_data, [usable_width / 3] * 3))
        elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph(
        f"<b>{next(clauses)}: (VIGENCIA DEL CONTRATO).-</b> Todas las demás cláusulas del "
        "contrato original permanecen vigentes e inalteradas.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(
        f"<b>{next(clauses)}: (CONFORMIDAD).-</b> Ambas PARTES como señal de conformidad y sin "
        "que medie ningún vicio del consentimiento, firmamos la presente adenda en doble "
        "ejemplar de un solo tenor y para un solo efecto.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 6 * mm))
    city = escape(_resolved_comitente(document.get("comitente"))["city"])
    elements.append(Paragraph(f"{city}, {effective}.", styles["right"]))
    elements.extend(_signature_elements(styles))
    return elements


def render_contract_document_pdf(document: dict) -> bytes:
    """Render an immutable ledger DTO with the UPDS legal template.

    Originals and full re-issues carry the complete contract; other amendments
    render as a formal adenda. Ledger identifiers stay out of the body text.
    """
    styles = _make_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=CONTRACT_PAGE_SIZE,
        leftMargin=3.0 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=f"Contrato {document['public_id']}",
        author="UPDS",
        subject="Contrato docente inmutable",
    )
    lines = document["lines"]
    if document["document_kind"] == "original" or document.get("reissue"):
        teacher = document["teacher"]
        terms = document.get("contract_terms") or {}
        start, end = _contract_term(lines)
        start = date.fromisoformat(terms["start"]) if terms.get("start") else start
        end = date.fromisoformat(terms["end"]) if terms.get("end") else end
        signature = terms.get("signature")
        elements = _legal_contract_elements(
            styles,
            teacher_name=str(teacher["full_name"]),
            teacher_ci=str(teacher["ci"]),
            department=str(document["department"]),
            subject_sections=[
                (subtitle, _subject_rows(items)) for subtitle, items in _activity_groups(lines)
            ],
            duration_text=_format_duration_text(start, end),
            start_date=_format_spanish_date(start),
            end_date=_format_spanish_date(end),
            rate_html=_rate_html(lines),
            signature_date=_format_spanish_date(date.fromisoformat(signature)) if signature else None,
            comitente=document.get("comitente"),
        )
    else:
        elements = _amendment_elements(styles, document)
    doc.build(
        elements,
        onFirstPage=_page_number_canvas,
        onLaterPages=_page_number_canvas,
        canvasmaker=_InvariantContractCanvas,
    )
    return buffer.getvalue()
