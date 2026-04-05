"""
Service: Contract PDF Generator

Generates formal employment contract PDFs for teachers using ReportLab.
The contract follows the EXACT UPDS template text (plantilla_contrato_docente.txt).

Output: backend/data/contracts/Contrato_{TeacherName}_{date}.pdf
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether,
)
from reportlab.lib import colors
from reportlab.lib.colors import HexColor

if TYPE_CHECKING:
    from app.models.teacher import Teacher
    from app.models.designation import Designation

logger = logging.getLogger(__name__)

MONTH_NAMES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
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
        pagesize=A4,
        leftMargin=3.0 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    elements: list = []

    # ── Generation date ────────────────────────────────────────────────
    gen_day = str(now.day).zfill(2)
    gen_month = MONTH_NAMES.get(now.month, str(now.month))
    gen_year = str(now.year)
    generation_date = f"{gen_day} de {gen_month} de {gen_year}"

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
            "Cobija, representada legalmente en este acto por el señor Luis Michel Bravo Alencar "
            "con CI. N.º 1750986 Pando Boliviano, mayor de edad, hábil por ley, domiciliado en "
            "esta Ciudad Cobija, en virtud al Poder Especial, amplio y suficiente según consta en "
            "el Testimonio N. º1818/2024, de fecha 4 de septiembre de 2024, otorgado ante la "
            "Notaría de Fe Pública N.º 10, a cargo del Notario Jaime David Canedo Encinas, quien "
            'en adelante y para los efectos del presente contrato se denominará "COMITENTE".'
        ),
        (
            f'Por otra, el señor(a) <b>{teacher.full_name}</b> hábil por ley, con C.I. '
            f'<b>{teacher.ci} {department}</b>, con domicilio en la Ciudad de Cobija, a quien '
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

    # ── Subjects table — deduplicated by subject, hours summed ─────────
    subject_map: dict = defaultdict(lambda: {"semester": "", "total_hours": 0})
    for d in designations:
        key = d.subject
        subject_map[key]["semester"] = d.semester
        subject_map[key]["total_hours"] += (d.semester_hours or 0)

    subjects_list = sorted(subject_map.items())
    table_data = [["Nº", "Materia", "Semestre", "Total Horas"]]
    for idx, (subject, info) in enumerate(subjects_list, start=1):
        table_data.append([
            str(idx),
            subject,
            info["semester"],
            str(info["total_hours"]),
        ])

    # Page width minus margins: A4 = 21cm, left=3cm, right=2.5cm → usable = 15.5cm
    usable_width = A4[0] - 3.0 * cm - 2.5 * cm
    col_widths = [
        1.0 * cm,
        usable_width - 1.0 * cm - 3.0 * cm - 2.5 * cm,
        3.0 * cm,
        2.5 * cm,
    ]

    subjects_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    subjects_table.setStyle(TableStyle([
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
    elements.append(subjects_table)
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
        f"<b>Bs. {hourly_rate} ({hourly_rate_literal})</b>.<br/>"
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

    # ── DATE ───────────────────────────────────────────────────────────
    elements.append(Paragraph(
        f"Cobija, {generation_date}.",
        styles["normal"],
    ))

    # ── SIGNATURES — labels only, no names ─────────────────────────────
    elements.append(Spacer(1, 25 * mm))

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

    # Build PDF with page numbers
    doc.build(elements, onFirstPage=_page_number_canvas, onLaterPages=_page_number_canvas)

    logger.info("Generated contract PDF: %s", filename)
    return str(filepath)
