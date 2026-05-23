"""UPDS billing-publication email template rendering."""
from __future__ import annotations

from dataclasses import dataclass
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
        "Materia | Monto a facturar | Grupo | Semestre",
    ]
    for row in row_list:
        amount = _to_decimal(row.amount)
        lines.append(f"{row.subject} | {_format_money(amount)} | {row.group} | {row.semester}")
    lines.extend(
        [
            f"TOTAL: {_format_money(total)}",
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


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid billing amount: {value!r}") from exc


def _format_money(value: Decimal) -> str:
    return f"Bs {value.quantize(Decimal('0.01'))}"
