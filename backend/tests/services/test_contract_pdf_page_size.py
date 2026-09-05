from __future__ import annotations

import inspect
import re
from types import SimpleNamespace

import pytest
from reportlab.lib.units import cm

from app.services import contract_pdf


def test_generated_contract_uses_exact_8_5_by_13_inch_media_box(tmp_path, monkeypatch):
    monkeypatch.setattr(contract_pdf, "_output_dir", lambda: tmp_path)
    teacher = SimpleNamespace(full_name="Docente de Prueba", ci="1234567")
    designation = SimpleNamespace(
        subject="Materia de Prueba",
        semester="I",
        semester_hours=40,
    )

    output_path = contract_pdf.generate_contract_pdf(
        teacher=teacher,
        designations=[designation],
        department="Pando",
        duration_text="4 meses y 8 días",
        start_date="10 de agosto de 2026",
        end_date="18 de diciembre de 2026",
    )

    pdf_bytes = tmp_path.joinpath(output_path).read_bytes()
    media_boxes = re.findall(
        rb"/MediaBox\s*\[\s*0(?:\.0+)?\s+0(?:\.0+)?\s+"
        rb"([0-9.]+)\s+([0-9.]+)\s*\]",
        pdf_bytes,
    )
    page_count = len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))

    assert contract_pdf.CONTRACT_PAGE_SIZE == (612.0, 936.0)
    assert page_count > 1
    assert len(media_boxes) == page_count
    assert all(tuple(map(float, media_box)) == (612.0, 936.0) for media_box in media_boxes)
    assert all(float(width) < float(height) for width, height in media_boxes)


def test_contract_table_and_footer_use_canonical_page_width():
    col_widths = contract_pdf._subject_table_column_widths()
    expected_usable_width = contract_pdf.CONTRACT_PAGE_SIZE[0] - 3.0 * cm - 2.5 * cm
    legacy_proportions = (1.0, 9.0, 3.0, 2.5)
    legacy_total = sum(legacy_proportions)

    assert sum(col_widths) == pytest.approx(expected_usable_width, rel=1e-12, abs=1e-12)
    for width, legacy_width in zip(col_widths, legacy_proportions, strict=True):
        assert width / expected_usable_width == pytest.approx(
            legacy_width / legacy_total,
            rel=1e-12,
            abs=1e-12,
        )

    class RecordingCanvas:
        def saveState(self):
            pass

        def setFont(self, *_args):
            pass

        def getPageNumber(self):
            return 1

        def drawCentredString(self, x, y, text):
            self.footer = (x, y, text)

        def restoreState(self):
            pass

    canvas = RecordingCanvas()
    contract_pdf._page_number_canvas(canvas, None)

    footer_x, footer_y, footer_text = canvas.footer
    assert footer_x == pytest.approx(306.0, rel=0, abs=1e-12)
    assert footer_y == pytest.approx(1.5 * cm)
    assert footer_text == "Página 1"
    assert "A4" not in inspect.getsource(contract_pdf)
