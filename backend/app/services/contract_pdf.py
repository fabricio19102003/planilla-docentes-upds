"""
Service: Contract PDF Generator

Generates formal employment contract PDFs for teachers using ReportLab.
The contract follows the UPDS standard template with 17 clauses (full legal text).

Output: backend/data/contracts/Contrato_{TeacherName}_{date}.pdf
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)
from reportlab.lib import colors
from reportlab.lib.colors import HexColor

if TYPE_CHECKING:
    from app.models.teacher import Teacher
    from app.models.designation import Designation

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parents[2] / "data" / "assets"
ISOLOGO_PATH = ASSETS_DIR / "isologo_upds.png"

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


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
    )
    title_main = ParagraphStyle(
        "CTM", parent=bold_center,
        fontSize=12, leading=16, spaceAfter=4,
    )
    subtitle = ParagraphStyle(
        "CS", parent=center,
        fontSize=10, leading=13,
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
        "subtitle": subtitle,
    }


def _page_number_canvas(canvas, doc):
    """Draw page number footer on every page."""
    canvas.saveState()
    canvas.setFont("Times-Roman", 9)
    page_num = canvas.getPageNumber()
    text = f"Página {page_num}"
    canvas.drawCentredString(A4[0] / 2, 1.5 * cm, text)
    canvas.restoreState()


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
        department: Department of Bolivia (e.g. "Pando", "La Paz")
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
        pagesize=A4,
        leftMargin=3.0 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    elements: list = []

    # ── Generation date ────────────────────────────────────────────────
    gen_day = str(now.day)
    gen_month = MONTH_NAMES.get(now.month, str(now.month))
    gen_year = str(now.year)
    generation_date = f"{gen_day} de {gen_month} de {gen_year}"

    # ── HEADER ─────────────────────────────────────────────────────────
    elements.append(Paragraph(
        "UNIVERSIDAD PRIVADA DOMINGO SAVIO",
        styles["bold_center"],
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        f"CONTRATO DE PRESTACIÓN DE SERVICIOS PROFESIONALES",
        styles["title_main"],
    ))
    elements.append(Spacer(1, 1 * mm))
    elements.append(Paragraph(
        f"(Docente por hora — {department})",
        styles["subtitle"],
    ))
    elements.append(Spacer(1, 8 * mm))

    # ── PARTIES ────────────────────────────────────────────────────────
    elements.append(Paragraph(
        f"En la ciudad de Cobija, Departamento de {department}, a {generation_date}, entre:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph(
        "<b>PRIMERA PARTE (CONTRATANTE):</b>",
        styles["bold"],
    ))
    elements.append(Paragraph(
        "La <b>UNIVERSIDAD PRIVADA DOMINGO SAVIO — UNIPANDO S.R.L.</b>, representada legalmente "
        "por el Lic. Luis Michel Bravo Alencar, en calidad de Rector, con domicilio en la "
        f"ciudad de Cobija, Departamento de {department}, a quien en adelante se denominará "
        "<b>«LA UNIVERSIDAD»</b>.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph(
        "<b>SEGUNDA PARTE (DOCENTE):</b>",
        styles["bold"],
    ))
    elements.append(Paragraph(
        f"El/La profesional <b>{teacher.full_name}</b>, con C.I. N° <b>{teacher.ci}</b>, "
        "con domicilio en la ciudad de Cobija, quien en adelante se denominará "
        "<b>«EL/LA DOCENTE»</b>.",
        styles["justify"],
    ))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph(
        "Ambas partes suscriben el presente contrato de prestación de servicios profesionales "
        "de acuerdo a las siguientes cláusulas:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 6 * mm))

    # ── CLAUSE I — Antecedentes ────────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA PRIMERA. — ANTECEDENTES", styles["clause_title"]),
        Paragraph(
            "La Universidad Privada Domingo Savio — UNIPANDO S.R.L., es una institución de "
            "educación superior privada, autorizada y reconocida por el Estado Plurinacional de "
            "Bolivia mediante resolución correspondiente del Ministerio de Educación. En el "
            "ejercicio de sus funciones académicas y como parte de su Plan Académico Institucional, "
            "requiere contar con docentes idóneos para desarrollar actividades de enseñanza en sus "
            "distintas carreras y programas académicos.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE II — Objeto ─────────────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA SEGUNDA. — OBJETO DEL CONTRATO", styles["clause_title"]),
        Paragraph(
            f"El presente contrato tiene por objeto la prestación de servicios profesionales "
            f"docentes por parte de <b>{teacher.full_name}</b>, quien se compromete a ejercer "
            f"actividades de docencia en las asignaturas detalladas en la <b>Cláusula Tercera</b> "
            f"del presente instrumento, dentro del régimen académico de La Universidad.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE III — Materias ──────────────────────────────────────────
    elements.append(Paragraph("CLÁUSULA TERCERA. — ASIGNATURAS A CARGO", styles["clause_title"]))
    elements.append(Paragraph(
        f"El/La Docente se compromete a dictar las siguientes asignaturas durante la vigencia "
        f"del presente contrato:",
        styles["justify"],
    ))
    elements.append(Spacer(1, 3 * mm))

    # Subjects table
    table_data = [["N°", "Asignatura", "Semestre", "Hrs/Semana"]]
    for idx, d in enumerate(designations, start=1):
        weekly = d.weekly_hours or (d.monthly_hours // 4 if d.monthly_hours else 0)
        table_data.append([
            str(idx),
            d.subject,
            d.semester,
            f"{weekly}h",
        ])

    subjects_table = Table(
        table_data,
        colWidths=[1.0 * cm, 9.5 * cm, 3.5 * cm, 2.0 * cm],
        repeatRows=1,
    )
    subjects_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#EBF3FB")]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#B8B8B8")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(subjects_table)
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE IV — Vigencia ───────────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA CUARTA. — VIGENCIA", styles["clause_title"]),
        Paragraph(
            f"El presente contrato tendrá una vigencia de <b>{duration_text}</b>, "
            f"computados a partir del <b>{start_date}</b> al <b>{end_date}</b> de {gen_year}, "
            "pudiendo ser renovado por mutuo acuerdo de las partes mediante la suscripción de "
            "un nuevo contrato o adenda correspondiente.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE V — Honorarios ──────────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA QUINTA. — HONORARIOS PROFESIONALES", styles["clause_title"]),
        Paragraph(
            f"La Universidad reconocerá al/a la Docente honorarios profesionales de "
            f"<b>Bs. {hourly_rate}/- ({hourly_rate_literal})</b> por cada hora académica "
            "efectivamente dictada, de acuerdo al registro de asistencia y las horas consignadas "
            "en la planilla mensual de haberes. El pago se realizará mensualmente, previa "
            "presentación de la factura correspondiente o mediante retención RC-IVA, según "
            "corresponda a la situación impositiva del/de la Docente.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE VI — Obligaciones del Docente ──────────────────────────
    elements.append(Paragraph("CLÁUSULA SEXTA. — OBLIGACIONES DEL DOCENTE", styles["clause_title"]))
    obligations = [
        "Cumplir con el horario de clases establecido por La Universidad y asistir puntualmente a todas las sesiones programadas.",
        "Presentar el silabo o programa analítico de cada asignatura a su cargo, dentro de los plazos establecidos por el Vicerrectorado Académico.",
        "Evaluar a los estudiantes conforme al reglamento académico vigente y registrar las calificaciones en el sistema institucional dentro de los plazos establecidos.",
        "Guardar confidencialidad sobre la información académica y administrativa de La Universidad y de los estudiantes.",
        "Participar en las reuniones de colegiatura, actividades de capacitación y eventos institucionales convocados por La Universidad.",
        "Registrar su asistencia mediante el sistema biométrico institucional u otro medio oficial establecido por La Universidad.",
        "Comunicar con anticipación mínima de 24 horas cualquier inasistencia justificada, a fin de que La Universidad pueda adoptar las medidas pertinentes.",
        "No ceder, transferir ni subcontratar a terceros las obligaciones asumidas en el presente contrato.",
        "Respetar el Reglamento Interno de La Universidad, el Código de Ética Institucional y demás normativas vigentes.",
        "Entregar a La Universidad, al término del contrato, toda la documentación, materiales y recursos institucionales que hubiera recibido en custodia.",
    ]
    for i, ob in enumerate(obligations, start=1):
        elements.append(Paragraph(f"{i}. {ob}", styles["justify"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 3 * mm))

    # ── CLAUSE VII — Obligaciones de la Universidad ────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA SÉPTIMA. — OBLIGACIONES DE LA UNIVERSIDAD", styles["clause_title"]),
    ]))
    uni_obligations = [
        "Pagar oportunamente los honorarios profesionales pactados, en los plazos y condiciones establecidos en el presente contrato.",
        "Proporcionar al/a la Docente los recursos y medios necesarios (aulas, equipos, materiales didácticos) para el adecuado desarrollo de las actividades académicas.",
        "Informar al/a la Docente sobre las normativas, reglamentos y directrices académicas institucionales vigentes.",
        "Respetar la autonomía pedagógica del/de la Docente en el desarrollo de los contenidos de las asignaturas a su cargo, dentro del marco del silabo aprobado.",
    ]
    for i, ob in enumerate(uni_obligations, start=1):
        elements.append(Paragraph(f"{i}. {ob}", styles["justify"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 3 * mm))

    # ── CLAUSE VIII — Naturaleza del contrato ─────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA OCTAVA. — NATURALEZA JURÍDICA DEL CONTRATO", styles["clause_title"]),
        Paragraph(
            "Las partes expresamente declaran y reconocen que el presente contrato es de "
            "<b>prestación de servicios profesionales</b> de carácter civil, por lo que no crea "
            "relación laboral alguna entre El/La Docente y La Universidad. En consecuencia, no "
            "generará derecho a beneficios sociales, aportes a la seguridad social de largo plazo, "
            "ni ninguna otra prestación propia de los contratos de trabajo regulados por la "
            "legislación laboral boliviana.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE IX — Propiedad intelectual ─────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA NOVENA. — PROPIEDAD INTELECTUAL", styles["clause_title"]),
        Paragraph(
            "Los materiales didácticos, sílabos, apuntes, presentaciones y cualquier otro "
            "material elaborado específicamente para el desarrollo de las asignaturas objeto "
            "del presente contrato, podrán ser utilizados por La Universidad con fines "
            "académicos institucionales. El/La Docente conservará sus derechos morales de "
            "autoría sobre los mismos, conforme a la legislación boliviana sobre derechos de autor.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE X — Confidencialidad ───────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA DÉCIMA. — CONFIDENCIALIDAD", styles["clause_title"]),
        Paragraph(
            "El/La Docente se compromete a guardar estricta confidencialidad sobre toda "
            "información privilegiada, estratégica o sensible que llegue a su conocimiento "
            "con motivo de la ejecución del presente contrato, tanto durante la vigencia del "
            "mismo como con posterioridad a su conclusión. Esta obligación incluye, de manera "
            "enunciativa mas no limitativa, información financiera, datos de estudiantes, "
            "proyectos institucionales y procedimientos internos.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE XI — Causales de resolución ────────────────────────────
    elements.append(Paragraph("CLÁUSULA DÉCIMA PRIMERA. — CAUSALES DE RESOLUCIÓN", styles["clause_title"]))
    elements.append(Paragraph(
        "El presente contrato podrá resolverse por las siguientes causas:",
        styles["justify"],
    ))
    resolutions = [
        "Por acuerdo mutuo de las partes, mediante comunicación escrita con un mínimo de quince (15) días calendario de anticipación.",
        "Por incumplimiento grave o reiterado de las obligaciones asumidas por cualquiera de las partes.",
        "Por causas de fuerza mayor o caso fortuito debidamente comprobadas.",
        "Por vencimiento del plazo pactado, sin necesidad de aviso previo.",
        "Por fallecimiento o incapacidad física o mental permanente del/de la Docente.",
        "Por supresión o cierre de las asignaturas o programas académicos objeto del contrato, por decisión institucional debidamente justificada.",
    ]
    for i, r in enumerate(resolutions, start=1):
        elements.append(Paragraph(f"{i}. {r}", styles["justify"]))
        elements.append(Spacer(1, 1 * mm))
    elements.append(Spacer(1, 3 * mm))

    # ── CLAUSE XII — Penalidades ───────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA DÉCIMA SEGUNDA. — PENALIDADES", styles["clause_title"]),
        Paragraph(
            "En caso de incumplimiento imputable al/a la Docente, La Universidad podrá "
            "descontar de los honorarios pendientes de pago el monto equivalente a las "
            "horas no dictadas, sin perjuicio de las demás acciones legales que correspondan. "
            "Las inasistencias debidamente justificadas y comunicadas en los plazos previstos "
            "en la Cláusula Sexta no darán lugar a penalidad alguna.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE XIII — Aspectos tributarios ────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA DÉCIMA TERCERA. — ASPECTOS TRIBUTARIOS", styles["clause_title"]),
        Paragraph(
            "Los honorarios pactados en el presente contrato están sujetos al régimen "
            "tributario vigente. El/La Docente deberá emitir la factura correspondiente por "
            "los servicios prestados, o en su caso, solicitar por escrito la retención del "
            "impuesto RC-IVA del trece por ciento (13%) sobre sus honorarios, conforme a "
            "la normativa del Servicio de Impuestos Nacionales (SIN). La Universidad actuará "
            "como agente de retención en los casos en que corresponda.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE XIV — Modificaciones ───────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA DÉCIMA CUARTA. — MODIFICACIONES", styles["clause_title"]),
        Paragraph(
            "Cualquier modificación al presente contrato deberá efectuarse por escrito "
            "mediante adenda suscrita por ambas partes con las mismas formalidades del "
            "contrato original. Las modificaciones verbales o por cualquier otro medio "
            "informal no tendrán validez jurídica.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE XV — Domicilio ──────────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA DÉCIMA QUINTA. — DOMICILIO", styles["clause_title"]),
        Paragraph(
            f"Para todos los efectos del presente contrato, las partes fijan su domicilio "
            f"en la ciudad de Cobija, Departamento de {department}, Estado Plurinacional "
            "de Bolivia. Cualquier notificación, comunicación o requerimiento deberá "
            "efectuarse en los domicilios señalados.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE XVI — Solución de controversias ────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA DÉCIMA SEXTA. — SOLUCIÓN DE CONTROVERSIAS", styles["clause_title"]),
        Paragraph(
            "Cualquier controversia, disputa o diferencia que surja entre las partes "
            "con relación al presente contrato, su interpretación, cumplimiento o "
            "resolución, será resuelta en primera instancia mediante el diálogo y la "
            "negociación directa entre las partes. En caso de no llegarse a un acuerdo, "
            "las partes se someten a la jurisdicción y competencia de los Tribunales de "
            f"Justicia Ordinaria de la ciudad de Cobija, Departamento de {department}, "
            "renunciando expresamente a cualquier otro fuero que pudiera corresponderles.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 4 * mm))

    # ── CLAUSE XVII — Disposiciones finales ───────────────────────────
    elements.append(KeepTogether([
        Paragraph("CLÁUSULA DÉCIMA SÉPTIMA. — DISPOSICIONES FINALES", styles["clause_title"]),
        Paragraph(
            "El presente contrato se suscribe en dos (2) ejemplares originales de igual "
            "valor legal, quedando uno en poder de cada parte contratante. En señal de "
            "conformidad y plena aceptación con todas y cada una de las cláusulas del "
            "presente instrumento, las partes firman el presente contrato en la ciudad "
            f"de Cobija, Departamento de {department}, a {generation_date}.",
            styles["justify"],
        ),
    ]))
    elements.append(Spacer(1, 16 * mm))

    # ── SIGNATURES ─────────────────────────────────────────────────────
    sig_data = [
        [
            Paragraph("___________________________", styles["center"]),
            Paragraph("___________________________", styles["center"]),
        ],
        [
            Paragraph("<b>Lic. Luis Michel Bravo Alencar</b>", styles["bold_center"]),
            Paragraph(f"<b>{teacher.full_name}</b>", styles["bold_center"]),
        ],
        [
            Paragraph("Rector — UPDS UNIPANDO S.R.L.", styles["center"]),
            Paragraph(f"C.I. N° {teacher.ci}", styles["center"]),
        ],
        [
            Paragraph("C.I. _____________________", styles["center"]),
            Paragraph("El/La Docente", styles["center"]),
        ],
    ]

    sig_table = Table(sig_data, colWidths=[8.0 * cm, 8.0 * cm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(sig_table)

    # Build PDF with page numbers
    doc.build(elements, onFirstPage=_page_number_canvas, onLaterPages=_page_number_canvas)

    logger.info("Generated contract PDF: %s", filename)
    return str(filepath)
