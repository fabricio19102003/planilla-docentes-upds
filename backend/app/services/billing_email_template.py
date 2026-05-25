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
            f"&#9654; <strong>Per&iacute;odo de corte:</strong> {escape(_format_date(start_date), quote=True)} al {escape(_format_date(end_date), quote=True)}"
        )
    if rate_per_hour is not None:
        lines.append(f"&#9654; <strong>Tarifa por hora acad&eacute;mica:</strong> {escape(_format_money(_to_decimal(rate_per_hour)), quote=True)}")

    excluded_items = _excluded_day_items(excluded_days)
    if excluded_items:
        items = "".join(f"<li style=\"margin: 4px 0;\">{escape(item, quote=True)}</li>" for item in excluded_items)
        lines.append(
            "&#9654; <strong>D&iacute;as no trabajados que aplican a sus materias:</strong>"
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
        lines.append(f"* Periodo de corte: {_format_date(start_date)} al {_format_date(end_date)}")
    if rate_per_hour is not None:
        lines.append(f"* Tarifa por hora academica: {_format_money(_to_decimal(rate_per_hour))}")

    excluded_items = _excluded_day_items(excluded_days)
    if excluded_items:
        lines.append("* Dias no trabajados que aplican a sus materias:")
        lines.extend(f"• {item}" for item in excluded_items)

    if lines:
        lines.append("")
    return lines


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
