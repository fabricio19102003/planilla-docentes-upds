"""UPDS billing-publication email template rendering."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html import escape
from typing import Iterable


@dataclass(frozen=True)
class BillingEmailRow:
    """A single consolidated billing item rendered in the email table."""

    subject: str
    amount: Decimal | int | float | str
    group: str
    semester: str


def render_billing_email_html(
    *,
    docente_name: str,
    month_name: str,
    year: int | str,
    rows: Iterable[BillingEmailRow],
    start_date: str | None = None,
    end_date: str | None = None,
    rate_per_hour: float | None = None,
    excluded_days: list[dict] | None = None,
) -> str:
    """Render the UPDS-branded billing email HTML.

    Dynamic values are HTML-escaped at the rendering boundary. Amount totals are
    presentation-only sums of the already consolidated snapshot row amounts.
    """

    row_list = list(rows)
    table_rows = []
    total = Decimal("0")

    for index, row in enumerate(row_list):
        amount = _to_decimal(row.amount)
        total += amount
        background = "#ffffff" if index % 2 == 0 else "#f9f9f9"
        table_rows.append(
            "<tr "
            f'style="background: {background};">'
            f"{_td(row.subject)}"
            f"{_td(_format_money(amount), align='right')}"
            f"{_td(row.group)}"
            f"{_td(row.semester)}"
            "</tr>"
        )

    safe_docente = escape(str(docente_name), quote=True)
    safe_month = escape(str(month_name), quote=True)
    safe_year = escape(str(year), quote=True)
    context_box = _render_context_box_html(
        start_date=start_date,
        end_date=end_date,
        rate_per_hour=rate_per_hour,
        excluded_days=excluded_days or [],
    )
    invoice_example = _render_invoice_example_html(row_list, month_name, year)

    return f"""<!doctype html>
<html lang="es">
  <body style="margin: 0; padding: 24px; background: #f3f4f6; font-family: Segoe UI, Arial, sans-serif; color: #1f2937;">
    <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border: 1px solid #d9e2ec; border-radius: 12px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08); overflow: hidden;">
      <header style="background: #003366; color: #ffffff; border-bottom: 5px solid #f4b400; padding: 24px; text-align: center;">
        <h1 style="margin: 0; font-size: 20px; letter-spacing: 0.4px;">UNIVERSIDAD PRIVADA DOMINGO SAVIO</h1>
        <p style="margin: 8px 0 0; font-size: 15px;">Notificación de Honorarios Docentes</p>
      </header>
      <main style="padding: 24px;">
        <p style="margin: 0 0 12px;">Estimado(a) docente,</p>
        <p style="margin: 0 0 16px;">
          <strong style="color: #003366;">{safe_docente}</strong>, le informamos que se publicó su detalle de honorarios correspondiente a {safe_month} {safe_year}.
        </p>
        {context_box}
        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; border-collapse: collapse; margin-top: 18px; font-size: 14px;">
          <thead>
            <tr style="background: #003366; color: #ffffff;">
              <th style="padding: 10px; border: 1px solid #d9e2ec; text-align: left;">Materia</th>
              <th style="padding: 10px; border: 1px solid #d9e2ec; text-align: right;">Monto a facturar</th>
              <th style="padding: 10px; border: 1px solid #d9e2ec; text-align: left;">Grupo</th>
              <th style="padding: 10px; border: 1px solid #d9e2ec; text-align: left;">Semestre</th>
            </tr>
          </thead>
          <tbody>
            {''.join(table_rows)}
            <tr style="background: #e8f0fe; font-weight: 700;">
              <td style="padding: 10px; border: 1px solid #d9e2ec; text-align: right; color: #003366;" colspan="2">TOTAL:</td>
              <td style="padding: 10px; border: 1px solid #d9e2ec; text-align: right; color: #d93025;" colspan="2">{_format_money(total)}</td>
            </tr>
          </tbody>
        </table>
        {invoice_example}
      </main>
      <footer style="padding: 18px 24px; background: #f8fafc; border-top: 1px solid #d9e2ec; font-size: 12px; color: #4b5563;">
        <p style="margin: 0 0 8px;">Este es un mensaje generado automáticamente. Por favor, no responda a este correo.</p>
        <p style="margin: 0;">Para consultas, comuníquese con Gestión Humana: Lisseth, (+591) 69063028.</p>
      </footer>
    </div>
  </body>
</html>"""


def render_billing_email_text(
    *,
    docente_name: str,
    month_name: str,
    year: int | str,
    rows: Iterable[BillingEmailRow],
    start_date: str | None = None,
    end_date: str | None = None,
    rate_per_hour: float | None = None,
    excluded_days: list[dict] | None = None,
) -> str:
    """Render a plain-text fallback for the billing email."""

    row_list = list(rows)
    total = sum((_to_decimal(row.amount) for row in row_list), Decimal("0"))
    lines = [
        "UNIVERSIDAD PRIVADA DOMINGO SAVIO",
        "Notificación de Honorarios Docentes",
        "",
        "Estimado(a) docente,",
        f"{docente_name}, se publicó su detalle de honorarios correspondiente a {month_name} {year}.",
        "",
    ]
    lines.extend(_render_context_lines_text(
        start_date=start_date,
        end_date=end_date,
        rate_per_hour=rate_per_hour,
        excluded_days=excluded_days or [],
    ))
    lines.append("Materia | Monto a facturar | Grupo | Semestre")
    for row in row_list:
        amount = _to_decimal(row.amount)
        lines.append(f"{row.subject} | {_format_money(amount)} | {row.group} | {row.semester}")
    lines.extend(
        [
            f"TOTAL: {_format_money(total)}",
            "",
            *_render_invoice_example_text(row_list, month_name, year),
            "",
            "Este es un mensaje generado automáticamente.",
            "Gestión Humana: Lisseth, (+591) 69063028.",
        ]
    )
    return "\n".join(lines)


def _td(value: object, *, align: str = "left") -> str:
    return (
        f'<td style="padding: 10px; border: 1px solid #d9e2ec; text-align: {align};">'
        f"{escape(str(value), quote=True)}</td>"
    )


def _render_context_box_html(
    *,
    start_date: str | None,
    end_date: str | None,
    rate_per_hour: float | None,
    excluded_days: list[dict],
) -> str:
    lines: list[str] = []
    if start_date and end_date:
        lines.append(
            f"&#128197; <strong>Per&iacute;odo de corte:</strong> {escape(_format_date(start_date), quote=True)} al {escape(_format_date(end_date), quote=True)}"
        )
    if rate_per_hour is not None:
        lines.append(f"&#128176; <strong>Tarifa por hora acad&eacute;mica:</strong> {escape(_format_money(_to_decimal(rate_per_hour)), quote=True)}")

    excluded_items = _excluded_day_items(excluded_days)
    if excluded_items:
        items = "".join(f"<li style=\"margin: 4px 0;\">{escape(item, quote=True)}</li>" for item in excluded_items)
        lines.append(
            "&#128203; <strong>D&iacute;as no trabajados que aplican a sus materias:</strong>"
            f"<ul style=\"margin: 8px 0 0 18px; padding: 0;\">{items}</ul>"
        )

    if not lines:
        return ""

    content = "".join(f"<div style=\"margin: 6px 0;\">{line}</div>" for line in lines)
    return (
        '<div style="margin: 18px 0; padding: 14px 16px; background: #f8fafc; '
        'border: 1px solid #d9e2ec; border-left: 4px solid #f4b400; border-radius: 8px; font-size: 14px;">'
        f"{content}</div>"
    )


def _render_context_lines_text(
    *,
    start_date: str | None,
    end_date: str | None,
    rate_per_hour: float | None,
    excluded_days: list[dict],
) -> list[str]:
    lines: list[str] = []
    if start_date and end_date:
        lines.append(f"* Período de corte: {_format_date(start_date)} al {_format_date(end_date)}")
    if rate_per_hour is not None:
        lines.append(f"* Tarifa por hora académica: {_format_money(_to_decimal(rate_per_hour))}")

    excluded_items = _excluded_day_items(excluded_days)
    if excluded_items:
        lines.append("* Días no trabajados que aplican a sus materias:")
        lines.extend(f"• {item}" for item in excluded_items)

    if lines:
        lines.append("")
    return lines


def _render_invoice_example_html(rows: list[BillingEmailRow], month_name: str, year: int | str) -> str:
    total = sum((_to_decimal(row.amount) for row in rows), Decimal("0"))
    safe_month = escape(str(month_name).upper(), quote=True)
    safe_year = escape(str(year), quote=True)
    safe_date = escape(date.today().strftime("%d/%m/%Y"), quote=True)
    invoice_rows: list[str] = []

    for index, row in enumerate(rows, start=66):
        amount = _to_decimal(row.amount)
        safe_subject = escape(str(row.subject).upper(), quote=True)
        description = (
            "SERVICIOS PROFESIONALES DE DOCENCIA EN LA MATERIA DE "
            f"{safe_subject} CORRESPONDIENTE AL MES DE {safe_month} DE {safe_year}"
        )
        invoice_rows.append(
            "<tr>"
            f"{_invoice_td(f'P{index}')}"
            f"{_invoice_td('1.00', align='right')}"
            f"{_invoice_td('Unidad (Servicios)')}"
            f"{_invoice_td_html(description)}"
            f"{_invoice_td(_format_invoice_amount(amount), align='right', monospace=True)}"
            f"{_invoice_td('0.00', align='right', monospace=True)}"
            f"{_invoice_td(_format_invoice_amount(amount), align='right', monospace=True)}"
            "</tr>"
        )

    total_amount = _format_invoice_amount(total)
    total_words = escape(_number_to_spanish_words(int(total)).upper(), quote=True)
    cents = int((total.quantize(Decimal("0.01")) * 100) % 100)

    return f"""
        <div style="margin-top: 24px; padding-top: 18px; border-top: 1px solid #d9e2ec;">
          <p style="margin: 0 0 6px; font-size: 16px; font-weight: 700; color: #003366;">Ejemplo de facturaci&oacute;n</p>
          <p style="margin: 0 0 12px; font-size: 13px; color: #4b5563;">A continuaci&oacute;n se muestra un ejemplo de c&oacute;mo debe realizar su factura. Este es un ejemplo orientativo.</p>
          <div style="max-width: 100%; overflow-x: auto;">
            <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; border-collapse: collapse; border: 1px solid #333; font-family: 'Courier New', Courier, monospace; font-size: 11px; color: #111; background: #ffffff;">
              <tbody>
                <tr>
                  <td style="padding: 14px 12px 8px; border: 1px solid #333; text-align: center;" colspan="7">
                    <div style="font-size: 16px; font-weight: 700; letter-spacing: 0.4px;">FACTURA DE VENTA DE ZONA FRANCA</div>
                    <div style="font-size: 12px; margin-top: 3px;">(Sin Derecho a Cr&eacute;dito Fiscal)</div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 10px 12px; border: 1px solid #333;" colspan="7">
                    <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; border-collapse: collapse; font-family: 'Courier New', Courier, monospace; font-size: 11px;">
                      <tr>
                        <td style="padding: 2px 0; width: 58%;"><strong>Fecha:</strong> {safe_date}</td>
                        <td style="padding: 2px 0;"><strong>NIT/CI/CEX:</strong> 456850023</td>
                      </tr>
                      <tr>
                        <td style="padding: 2px 0;"><strong>Nombre/Raz&oacute;n Social:</strong> UNIPANDO S.R.L.</td>
                        <td style="padding: 2px 0;"><strong>Cod. Cliente:</strong> 456850023</td>
                      </tr>
                      <tr>
                        <td style="padding: 2px 0;">&nbsp;</td>
                        <td style="padding: 2px 0;"><strong>Nro. Parte Recepci&oacute;n:</strong> ---</td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr style="background: #333; color: #ffffff;">
                  <th style="padding: 7px 6px; border: 1px solid #333; text-align: left;">C&Oacute;DIGO PRODUCTO</th>
                  <th style="padding: 7px 6px; border: 1px solid #333; text-align: right;">CANTIDAD</th>
                  <th style="padding: 7px 6px; border: 1px solid #333; text-align: left;">UNIDAD DE MEDIDA</th>
                  <th style="padding: 7px 6px; border: 1px solid #333; text-align: left;">DESCRIPCI&Oacute;N</th>
                  <th style="padding: 7px 6px; border: 1px solid #333; text-align: right;">PRECIO UNITARIO</th>
                  <th style="padding: 7px 6px; border: 1px solid #333; text-align: right;">DESCUENTO</th>
                  <th style="padding: 7px 6px; border: 1px solid #333; text-align: right;">SUBTOTAL</th>
                </tr>
                {''.join(invoice_rows)}
                {_invoice_total_row('SUBTOTAL Bs', total_amount)}
                {_invoice_total_row('DESCUENTO Bs', '0.00')}
                {_invoice_total_row('TOTAL Bs', total_amount, bold=True)}
                {_invoice_total_row('MONTO GIFT CARD Bs', '0.00')}
                {_invoice_total_row('MONTO A PAGAR Bs', total_amount, bold=True)}
                <tr>
                  <td style="padding: 10px 6px; border: 1px solid #ddd;" colspan="7"><strong>Son:</strong> {total_words} {cents:02d}/100 Bolivianos</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>"""


def _render_invoice_example_text(rows: list[BillingEmailRow], month_name: str, year: int | str) -> list[str]:
    total = sum((_to_decimal(row.amount) for row in rows), Decimal("0"))
    total_amount = _format_invoice_amount(total)
    cents = int((total.quantize(Decimal("0.01")) * 100) % 100)
    lines = [
        "Ejemplo de facturación",
        "Este es un ejemplo orientativo de cómo debe realizar su factura.",
        "FACTURA DE VENTA DE ZONA FRANCA",
        "(Sin Derecho a Crédito Fiscal)",
        f"Fecha: {date.today().strftime('%d/%m/%Y')}",
        "Nombre/Razón Social: UNIPANDO S.R.L. | NIT/CI/CEX: 456850023",
        "Cod. Cliente: 456850023 | Nro. Parte Recepción: ---",
        "CÓDIGO PRODUCTO | CANTIDAD | UNIDAD DE MEDIDA | DESCRIPCIÓN | PRECIO UNITARIO | DESCUENTO | SUBTOTAL",
    ]

    for index, row in enumerate(rows, start=66):
        amount = _to_decimal(row.amount)
        description = (
            "SERVICIOS PROFESIONALES DE DOCENCIA EN LA MATERIA DE "
            f"{str(row.subject).upper()} CORRESPONDIENTE AL MES DE {str(month_name).upper()} DE {year}"
        )
        lines.append(
            f"P{index} | 1.00 | Unidad (Servicios) | {description} | "
            f"{_format_invoice_amount(amount)} | 0.00 | {_format_invoice_amount(amount)}"
        )

    lines.extend(
        [
            f"SUBTOTAL Bs {total_amount}",
            "DESCUENTO Bs 0.00",
            f"TOTAL Bs {total_amount}",
            "MONTO GIFT CARD Bs 0.00",
            f"MONTO A PAGAR Bs {total_amount}",
            f"Son: {_number_to_spanish_words(int(total)).upper()} {cents:02d}/100 Bolivianos",
        ]
    )
    return lines


def _invoice_td(value: object, *, align: str = "left", monospace: bool = False) -> str:
    font = " font-family: 'Courier New', Courier, monospace;" if monospace else ""
    return (
        f'<td style="padding: 7px 6px; border: 1px solid #ddd; text-align: {align};{font}">'
        f"{escape(str(value), quote=True)}</td>"
    )


def _invoice_td_html(value: str) -> str:
    return f'<td style="padding: 7px 6px; border: 1px solid #ddd; text-align: left; line-height: 1.35;">{value}</td>'


def _invoice_total_row(label: str, amount: str, *, bold: bool = False) -> str:
    weight = "700" if bold else "400"
    cells = "".join('<td style="padding: 5px 6px; border: 1px solid #ddd;"></td>' for _ in range(5))
    return (
        "<tr>"
        f"{cells}"
        f'<td style="padding: 5px 6px; border: 1px solid #ddd; text-align: right; font-weight: {weight};">{escape(label, quote=True)}</td>'
        f'<td style="padding: 5px 6px; border: 1px solid #ddd; text-align: right; font-family: \'Courier New\', Courier, monospace; font-weight: {weight};">{escape(amount, quote=True)}</td>'
        "</tr>"
    )


def _format_invoice_amount(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _number_to_spanish_words(value: int) -> str:
    if value == 0:
        return "cero"
    if value < 0:
        return f"menos {_number_to_spanish_words(abs(value))}"

    units = [
        "", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
        "diez", "once", "doce", "trece", "catorce", "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve",
    ]
    tens = {20: "veinte", 30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}
    hundreds = {100: "cien", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos", 500: "quinientos", 600: "seiscientos", 700: "setecientos", 800: "ochocientos", 900: "novecientos"}

    if value < 20:
        return units[value]
    if value < 30:
        return "veinti" + units[value - 20]
    if value < 100:
        ten = value // 10 * 10
        unit = value % 10
        return tens[ten] if unit == 0 else f"{tens[ten]} y {units[unit]}"
    if value < 1000:
        hundred = value // 100 * 100
        rest = value % 100
        if rest == 0:
            return hundreds[hundred]
        prefix = "ciento" if hundred == 100 else hundreds[hundred]
        return f"{prefix} {_number_to_spanish_words(rest)}"
    if value < 1_000_000:
        thousands = value // 1000
        rest = value % 1000
        prefix = "mil" if thousands == 1 else f"{_number_to_spanish_words(thousands)} mil"
        return prefix if rest == 0 else f"{prefix} {_number_to_spanish_words(rest)}"

    millions = value // 1_000_000
    rest = value % 1_000_000
    prefix = "un millon" if millions == 1 else f"{_number_to_spanish_words(millions)} millones"
    return prefix if rest == 0 else f"{prefix} {_number_to_spanish_words(rest)}"


def _excluded_day_items(excluded_days: list[dict]) -> list[str]:
    grouped_subjects: dict[tuple[str, str, str], set[str]] = {}
    items: list[str] = []

    for excluded in excluded_days:
        if not isinstance(excluded, dict):
            continue
        scope = str(excluded.get("scope") or "")
        date_label = _format_date(str(excluded.get("date") or ""))
        reason = str(excluded.get("reason") or "Sin motivo")

        if scope == "subject":
            subject = str(excluded.get("subject_id") or "")
            group = str(excluded.get("group_id") or "")
            grouped_subjects.setdefault((date_label, reason, subject), set()).add(group)
            continue

        if scope == "semester":
            semester = str(excluded.get("semester_id") or "")
            items.append(f"{date_label} — {reason} (Semestre: {semester})")
        else:
            items.append(f"{date_label} — {reason} (Global)")

    for (date_label, reason, subject), groups in grouped_subjects.items():
        group_list = ", ".join(sorted(group for group in groups if group))
        items.append(f"{date_label} — {reason} (Materia: {subject}, Grupos: {group_list})")

    return items


def _format_date(value: str) -> str:
    month_names = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
    }
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{parsed.day:02d}/{month_names[parsed.month]}/{parsed.year}"


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid billing amount: {value!r}") from exc


def _format_money(value: Decimal) -> str:
    return f"Bs {value.quantize(Decimal('0.01'))}"
