from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.billing_email_template import BillingEmailRow, render_billing_email_html, render_billing_email_text


def test_template_renders_static_sections_and_escapes_dynamic_values():
    html = render_billing_email_html(
        docente_name='Ana <script>alert("x")</script>',
        month_name="Marzo & Abril",
        year=2026,
        rows=[BillingEmailRow("Anatomía", Decimal("100.50"), "A", "1")],
    )

    assert "UNIVERSIDAD PRIVADA DOMINGO SAVIO" in html
    assert "Notificación de Honorarios Docentes" in html
    assert "Estimado(a) docente," in html
    assert "Ana &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
    assert "Marzo &amp; Abril 2026" in html
    assert "Gestión Humana: Lisseth, (+591) 69063028" in html
    assert "mensaje generado automáticamente" in html
    assert "<script>" not in html


def test_template_renders_fixed_headers_zebra_rows_and_exact_total():
    html = render_billing_email_html(
        docente_name="Docente UPDS",
        month_name="Mayo",
        year=2026,
        rows=[
            BillingEmailRow("Materia 1", Decimal("100.10"), "A", "1"),
            BillingEmailRow("Materia 2", "200.20", "B", "2"),
            BillingEmailRow("Materia 3", 300, "C", "3"),
        ],
    )

    assert "Materia" in html
    assert "Monto a facturar" in html
    assert "Grupo" in html
    assert "Semestre" in html
    assert html.count('<tr style="background: #ffffff;">') == 2
    assert html.count("background: #f9f9f9;") == 1
    assert "Materia 1" in html
    assert "Materia 2" in html
    assert "Materia 3" in html
    assert "background: #e8f0fe" in html
    assert "text-align: right; color: #003366;" in html
    assert "TOTAL:" in html
    assert html.count('colspan="2"') == 2
    assert "color: #d93025;\" colspan=\"2\">Bs 600.30</td>" in html


def test_template_rejects_invalid_amounts():
    with pytest.raises(ValueError, match="Invalid billing amount"):
        render_billing_email_html(
            docente_name="Docente UPDS",
            month_name="Mayo",
            year=2026,
            rows=[BillingEmailRow("Materia", "not-a-number", "A", "1")],
        )


def test_template_renders_context_sections_before_table():
    excluded_days = [
        {"date": "2026-04-30", "scope": "semester", "semester_id": "SEPTIMO", "reason": "Clase magistral de neurología"},
        {"date": "2026-05-08", "scope": "subject", "subject_id": "OFTALMOLOGÍA", "group_id": "M-3", "reason": "Clase magistral de oftalmología"},
        {"date": "2026-05-08", "scope": "subject", "subject_id": "OFTALMOLOGÍA", "group_id": "M-1", "reason": "Clase magistral de oftalmología"},
    ]

    html = render_billing_email_html(
        docente_name="Docente UPDS",
        month_name="Mayo",
        year=2026,
        rows=[BillingEmailRow("OFTALMOLOGÍA", Decimal("70"), "M-1", "SEPTIMO")],
        start_date="2026-04-21",
        end_date="2026-05-20",
        rate_per_hour=70.0,
        excluded_days=excluded_days,
    )
    text = render_billing_email_text(
        docente_name="Docente UPDS",
        month_name="Mayo",
        year=2026,
        rows=[BillingEmailRow("OFTALMOLOGÍA", Decimal("70"), "M-1", "SEPTIMO")],
        start_date="2026-04-21",
        end_date="2026-05-20",
        rate_per_hour=70.0,
        excluded_days=excluded_days,
    )

    assert html.index("odo de corte") < html.index("<table")
    assert "21/Abr/2026 al 20/May/2026" in html
    assert "Tarifa por hora" in html
    assert "Bs 70.00" in html
    assert "30/Abr/2026" in html
    assert "Clase magistral de neurolog" in html
    assert "08/May/2026" in html
    assert "Período de corte: 21/Abr/2026 al 20/May/2026" in text
    assert "Tarifa por hora académica: Bs 70.00" in text
