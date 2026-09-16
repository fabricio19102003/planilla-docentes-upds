"""Private, deterministic billing PDFs and opaque media tokens."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException, ROUND_HALF_UP
import hashlib
from io import BytesIO
from pathlib import Path
import re
import secrets
import unicodedata
from typing import Any, Callable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.config import settings as default_settings
from app.models.billing_notification import BillingMediaToken, BillingNotificationBatch, BillingNotificationJob
from app.models.billing_publication import BillingPublication

MAX_BILLING_PDF_BYTES = 15_000_000
_SAFE_FILENAME = re.compile(r"[A-Za-z0-9._-]{1,20}\.pdf\Z")
_MAX_DESIGNATIONS = 500
_MONEY_QUANTUM = Decimal("0.01")
_HOURS_TOLERANCE = Decimal("0.000001")
_PDF_FORMAT_MARKER = "sipad-billing-detail-v2"
_UPDS_BLUE = colors.HexColor("#123A63")
_UPDS_GOLD = colors.HexColor("#D6A62E")
_TEXT = colors.HexColor("#263442")
_MUTED = colors.HexColor("#607080")
_BORDER = colors.HexColor("#D8E0E8")
_ROW_ALT = colors.HexColor("#F4F7FA")
_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


@dataclass(frozen=True)
class BillingMediaIssue:
    token: str
    token_hash: str
    artifact_hash: str
    artifact_path: str
    filename: str
    artifact_size: int
    token_id: int
    artifact_created: bool = False


class BillingPdfService:
    """Creates snapshot-derived PDF artifacts and validates opaque token access."""

    def __init__(
        self,
        db: Session,
        *,
        storage_dir: str | Path | None = None,
        now: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        self.db = db
        self.storage_dir = Path(storage_dir or default_settings.BILLING_MEDIA_DIR).resolve()
        self.now = now

    def issue(
        self,
        batch: BillingNotificationBatch,
        job: BillingNotificationJob,
        snapshot: dict[str, Any],
        *,
        expires_in: timedelta = timedelta(hours=24),
        commit: bool = True,
    ) -> BillingMediaIssue:
        if job.batch_id != batch.id or not job.teacher_ci or not isinstance(snapshot, dict) or expires_in.total_seconds() <= 0:
            raise ValueError("invalid_billing_media_binding")
        rendered_snapshot = snapshot if "teacher_detail" in snapshot else {
            "teacher_detail": snapshot,
            "document_context": self._document_context_for_batch(batch),
        }
        payload = self._pdf_bytes(batch.id, job.teacher_ci, rendered_snapshot)
        if len(payload) > MAX_BILLING_PDF_BYTES:
            raise ValueError("billing_pdf_too_large")
        artifact_hash = hashlib.sha256(payload).hexdigest()
        filename = f"b-{artifact_hash[:12]}.pdf"
        path = self._safe_path(filename)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        artifact_created = not path.exists()
        if artifact_created:
            path.write_bytes(payload)
        if path.read_bytes() != payload:
            raise ValueError("billing_pdf_storage_conflict")

        try:
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
            self.db.add(BillingMediaToken(
                batch_id=batch.id, teacher_ci=job.teacher_ci, job_id=job.id,
                token_hash=token_hash, artifact_hash=artifact_hash, artifact_path=str(path),
                artifact_size=len(payload), expires_at=self.now() + expires_in,
            ))
            self.db.flush()
            row = self.db.query(BillingMediaToken).filter_by(token_hash=token_hash).one()
            job.media_snapshot = {"token_id": row.id, "artifact_hash": artifact_hash, "artifact_size": len(payload)}
            self.db.flush()
            if commit:
                self.db.commit()
            return BillingMediaIssue(token, token_hash, artifact_hash, str(path), filename, len(payload), row.id, artifact_created)
        except Exception:
            if artifact_created:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

    def issue_activation(
        self,
        batch: BillingNotificationBatch,
        job: BillingNotificationJob,
        teacher_detail: dict[str, Any],
        *,
        publication_revision_id: int,
        publication_version: int,
        billing_digest: str,
        document_context: dict[str, Any] | None = None,
        expires_in: timedelta = timedelta(hours=24),
    ) -> BillingMediaIssue:
        """Issue an activation PDF from one validated immutable revision detail only."""
        if (
            not isinstance(teacher_detail, dict)
            or publication_revision_id < 1
            or publication_version < 1
            or not re.fullmatch(r"[0-9a-f]{64}", billing_digest)
        ):
            raise ValueError("invalid_activation_pdf_binding")
        snapshot = {
            "teacher_detail": teacher_detail,
            "publication_revision_id": publication_revision_id,
            "publication_version": publication_version,
            "billing_digest": billing_digest,
            "document_context": document_context or {},
        }
        return self.issue(batch, job, snapshot, expires_in=expires_in, commit=False)

    def _document_context_for_batch(self, batch: BillingNotificationBatch) -> dict[str, Any]:
        publication_id = getattr(batch, "publication_id", None)
        if not isinstance(publication_id, int):
            return {}
        publication = self.db.get(BillingPublication, publication_id)
        if publication is None:
            return {}
        snapshot = publication.billing_snapshot if isinstance(publication.billing_snapshot, dict) else {}
        return {
            "month": publication.month,
            "year": publication.year,
            "planilla_type": publication.planilla_type,
            "start_date": snapshot.get("start_date"),
            "end_date": snapshot.get("end_date"),
            "rate_per_hour": snapshot.get("rate_per_hour"),
        }

    def resolve(self, token: str) -> tuple[Path, str] | None:
        if not isinstance(token, str) or not token or len(token) > 255:
            return None
        row = self.db.query(BillingMediaToken).filter_by(
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest()
        ).one_or_none()
        if row is None or row.revoked_at is not None or row.expires_at <= self.now():
            return None
        job = self.db.get(BillingNotificationJob, row.job_id)
        media = getattr(job, "media_snapshot", None) if job else None
        if not job or job.batch_id != row.batch_id or job.teacher_ci != row.teacher_ci or not isinstance(media, dict) or media.get("token_id") != row.id or media.get("artifact_hash") != row.artifact_hash or media.get("artifact_size") != row.artifact_size:
            return None
        try:
            path = Path(row.artifact_path).resolve()
            if path.parent != self.storage_dir or not _SAFE_FILENAME.fullmatch(path.name):
                return None
            content = path.read_bytes()
        except OSError:
            return None
        if len(content) != row.artifact_size or len(content) > MAX_BILLING_PDF_BYTES:
            return None
        if (
            not content.startswith(b"%PDF-")
            or _PDF_FORMAT_MARKER.encode("ascii") not in content
            or hashlib.sha256(content).hexdigest() != row.artifact_hash
        ):
            return None
        return path, path.name

    def _safe_path(self, filename: str) -> Path:
        if not _SAFE_FILENAME.fullmatch(filename):
            raise ValueError("invalid_billing_media_filename")
        path = (self.storage_dir / filename).resolve()
        if path.parent != self.storage_dir:
            raise ValueError("invalid_billing_media_path")
        return path

    @staticmethod
    def _pdf_bytes(batch_id: int, teacher_ci: str, snapshot: dict[str, Any]) -> bytes:
        del batch_id  # Binding remains in BillingMediaToken; internal identifiers never enter the document.
        if not isinstance(snapshot, dict):
            raise ValueError("invalid_billing_pdf_snapshot")
        wrapped = "teacher_detail" in snapshot
        detail = snapshot.get("teacher_detail") if wrapped else snapshot
        context = snapshot.get("document_context", {}) if wrapped else {}
        if not isinstance(detail, dict) or not isinstance(context, dict):
            raise ValueError("invalid_billing_pdf_snapshot")
        return _render_billing_pdf(detail, context, teacher_ci)


def _render_billing_pdf(detail: dict[str, Any], context: dict[str, Any], teacher_ci: str) -> bytes:
    designations = detail.get("designations", [])
    if designations is None:
        designations = []
    if not isinstance(designations, list) or len(designations) > _MAX_DESIGNATIONS:
        raise ValueError("invalid_billing_pdf_snapshot")
    if any(not isinstance(item, dict) for item in designations):
        raise ValueError("invalid_billing_pdf_snapshot")

    teacher_name = _safe_text(
        detail.get("teacher_name") or detail.get("docente_name") or "Docente",
        200,
        redact=teacher_ci,
    ).strip(" -–—·") or "Docente"
    rows = [_designation_values(item, teacher_ci) for item in designations]
    summary = {
        "hours": _summary_value(detail, rows, ("total_hours", "hours"), "hours"),
        "gross": _summary_value(detail, rows, ("gross_payment", "gross"), "gross"),
        "retention": _summary_value(detail, rows, ("retention_amount", "retention"), "retention"),
        "adjustment": _summary_value(detail, rows, ("admin_adjustment", "adjustment"), "adjustment"),
        "net": _summary_value(
            detail,
            rows,
            ("net_payment", "final_payment", "total_payment", "payment"),
            "net",
        ),
    }
    has_adjustment = (
        bool(detail.get("has_admin_override"))
        or any(row["has_adjustment"] for row in rows)
        or (summary["adjustment"] is not None and summary["adjustment"] != 0)
    )
    _require_valid_financial_equation(
        summary["gross"],
        summary["retention"],
        summary["adjustment"],
        summary["net"],
        has_override=has_adjustment,
    )
    _require_reconciled_detail(
        detail,
        designations,
        rows,
        summary=summary,
    )
    retention_rate = _optional_decimal(
        detail.get("retention_rate"),
        minimum=Decimal("0"),
        maximum=Decimal("1"),
    )
    normalized_context = _normalize_context(context)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title="Detalle de honorarios docentes",
        author="Universidad Privada Domingo Savio",
        subject="Documento informativo de honorarios docentes",
        creator="SIPAD",
        keywords=_PDF_FORMAT_MARKER,
    )
    styles = _styles()
    story: list[Any] = [
        Paragraph("UNIVERSIDAD PRIVADA DOMINGO SAVIO", styles["institution"]),
        Spacer(1, 2 * mm),
        Paragraph("Detalle de honorarios docentes", styles["title"]),
        Spacer(1, 5 * mm),
    ]
    identity_data = [
        [Paragraph("Docente", styles["label"]), Paragraph(teacher_name, styles["value"])],
        [Paragraph("CI", styles["label"]), Paragraph(_mask_ci(teacher_ci), styles["value"])],
    ]
    period = _period_label(normalized_context)
    if period:
        identity_data.append([Paragraph("Planilla", styles["label"]), Paragraph(period, styles["value"])])
    date_range = _date_range(normalized_context)
    if date_range:
        identity_data.append([Paragraph("Período", styles["label"]), Paragraph(date_range, styles["value"])])
    if normalized_context.get("rate_per_hour") is not None:
        identity_data.append([
            Paragraph("Tarifa por hora", styles["label"]),
            Paragraph(_format_money(normalized_context["rate_per_hour"]), styles["value"]),
        ])
    identity = Table(identity_data, colWidths=[30 * mm, 145 * mm], hAlign="LEFT")
    identity.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF3F8")),
        ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([identity, Spacer(1, 5 * mm), Paragraph("Resumen", styles["section"])])

    summary_rows = []
    if summary["hours"] is not None:
        summary_rows.append(("Horas", _format_hours(summary["hours"])))
    if summary["gross"] is not None:
        summary_rows.append(("Bruto", _format_money(summary["gross"])))
    if summary["retention"] is not None:
        summary_rows.append((f"Retención{_format_rate(retention_rate)}", _format_money(summary["retention"])))
    if has_adjustment and summary["adjustment"] is not None:
        summary_rows.append(("Ajuste", _format_money(summary["adjustment"])))
    if summary["net"] is not None:
        summary_rows.append(("Neto final", _format_money(summary["net"])))
    if summary_rows:
        summary_table = Table(
            [[Paragraph(label, styles["summary_label"]), Paragraph(value, styles["summary_value"])] for label, value in summary_rows],
            colWidths=[87.5 * mm, 87.5 * mm],
        )
        summary_commands = [
            ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, _BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]
        if summary["net"] is not None:
            summary_commands.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8F0F7")))
        summary_table.setStyle(TableStyle(summary_commands))
        story.append(summary_table)
    else:
        story.append(Paragraph("Información financiera no disponible", styles["empty"]))
    story.extend([Spacer(1, 6 * mm), Paragraph("Detalle por materia", styles["section"])])
    story.append(_detail_table(rows, has_adjustment, styles))

    def canvas_factory(filename: Any, **kwargs: Any) -> Canvas:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 0
        return Canvas(filename, **kwargs)

    footer_period = _footer_period(normalized_context)
    doc.build(
        story,
        onFirstPage=lambda canvas, current_doc: _draw_page(canvas, current_doc, footer_period),
        onLaterPages=lambda canvas, current_doc: _draw_page(canvas, current_doc, footer_period),
        canvasmaker=canvas_factory,
    )
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    return {
        "institution": ParagraphStyle("Institution", parent=base, fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=_UPDS_BLUE, alignment=TA_CENTER, spaceAfter=0),
        "title": ParagraphStyle("DocumentTitle", parent=base, fontName="Helvetica-Bold", fontSize=19, leading=22, textColor=_TEXT, alignment=TA_CENTER),
        "section": ParagraphStyle("Section", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=_UPDS_BLUE, spaceAfter=5),
        "label": ParagraphStyle("Label", parent=base, fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=_UPDS_BLUE),
        "value": ParagraphStyle("Value", parent=base, fontName="Helvetica", fontSize=8.5, leading=11, textColor=_TEXT),
        "summary_label": ParagraphStyle("SummaryLabel", parent=base, fontName="Helvetica", fontSize=8.5, leading=11, textColor=_MUTED),
        "summary_value": ParagraphStyle("SummaryValue", parent=base, fontName="Helvetica-Bold", fontSize=9, leading=11, textColor=_TEXT, alignment=TA_RIGHT),
        "th": ParagraphStyle("TableHeader", parent=base, fontName="Helvetica-Bold", fontSize=6.6, leading=8, textColor=colors.white, alignment=TA_CENTER),
        "cell": ParagraphStyle("TableCell", parent=base, fontName="Helvetica", fontSize=6.8, leading=8.5, textColor=_TEXT, alignment=TA_LEFT, splitLongWords=True),
        "number": ParagraphStyle("TableNumber", parent=base, fontName="Helvetica", fontSize=6.8, leading=8.5, textColor=_TEXT, alignment=TA_RIGHT),
        "empty": ParagraphStyle("Empty", parent=base, fontName="Helvetica-Oblique", fontSize=8, leading=11, textColor=_MUTED, alignment=TA_CENTER),
    }


def _detail_table(rows: list[dict[str, Any]], has_adjustment: bool, styles: dict[str, ParagraphStyle]) -> LongTable:
    headers = ["Materia", "Semestre", "Grupo", "Horas", "Bruto", "Retención"]
    widths = ([42, 17, 13, 13, 24, 24] if has_adjustment else [57, 18, 14, 14, 25, 25])
    if has_adjustment:
        headers.append("Ajuste")
        widths.append(23)
    headers.append("Neto")
    widths.append(25 if has_adjustment else 28)
    widths = [width * mm for width in widths]
    data: list[list[Any]] = [[Paragraph(header, styles["th"]) for header in headers]]
    if not rows:
        data.append([Paragraph("Sin designaciones registradas", styles["empty"])] + [""] * (len(headers) - 1))
    for row in rows:
        cells: list[Any] = [
            Paragraph(row["subject"], styles["cell"]),
            Paragraph(row["semester"], styles["cell"]),
            Paragraph(row["group"], styles["cell"]),
            Paragraph(_format_optional_hours(row["hours"]), styles["number"]),
            Paragraph(_format_optional_money(row["gross"]), styles["number"]),
            Paragraph(_format_optional_money(row["retention"]), styles["number"]),
        ]
        if has_adjustment:
            cells.append(Paragraph(_format_optional_money(row["adjustment"]), styles["number"]))
        cells.append(Paragraph(_format_optional_money(row["net"]), styles["number"]))
        data.append(cells)
    table = LongTable(data, colWidths=widths, repeatRows=1, splitByRow=1, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), _UPDS_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if not rows:
        commands.append(("SPAN", (0, 1), (-1, 1)))
    else:
        for index in range(2, len(data), 2):
            commands.append(("BACKGROUND", (0, index), (-1, index), _ROW_ALT))
    table.setStyle(TableStyle(commands))
    return table


def _draw_page(canvas: Canvas, doc: SimpleDocTemplate, period: str) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(_UPDS_GOLD)
    canvas.setLineWidth(1.4)
    canvas.line(doc.leftMargin, A4[1] - 11 * mm, width - doc.rightMargin, A4[1] - 11 * mm)
    canvas.setStrokeColor(_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 15 * mm, width - doc.rightMargin, 15 * mm)
    canvas.setFillColor(_MUTED)
    canvas.setFont("Helvetica", 7)
    footer = "Documento informativo · Gestión Humana +59169063028"
    if period:
        footer += f" · {period}"
    canvas.drawString(doc.leftMargin, 10.5 * mm, footer)
    page = f"Página {doc.page}"
    canvas.drawRightString(width - doc.rightMargin, 10.5 * mm, page)
    canvas.restoreState()


def _designation_values(item: dict[str, Any], teacher_ci: str) -> dict[str, Any]:
    gross = _optional_number(item, ("gross", "gross_payment"), minimum=Decimal("0"))
    retention = _optional_number(item, ("retention", "retention_amount"), minimum=Decimal("0"))
    adjustment = _optional_number(item, ("adjustment", "admin_adjustment"))
    net = _optional_number(item, ("net", "net_payment", "payment"), minimum=Decimal("0"))
    has_override = bool(item.get("has_admin_override"))
    _require_valid_financial_equation(
        gross,
        retention,
        adjustment,
        net,
        has_override=has_override,
    )
    return {
        "subject": _safe_text(item.get("subject") or "Sin materia", 180, redact=teacher_ci),
        "semester": _safe_text(item.get("semester") or "—", 40, redact=teacher_ci),
        "group": _safe_text(item.get("group") or item.get("group_code") or "—", 30, redact=teacher_ci),
        "hours": _optional_number(item, ("payable_hours", "hours"), minimum=Decimal("0")),
        "gross": gross,
        "retention": retention,
        "adjustment": adjustment,
        "net": net,
        "has_adjustment": has_override or (adjustment is not None and adjustment != 0),
    }


def _summary_value(
    detail: dict[str, Any],
    rows: list[dict[str, Any]],
    summary_keys: tuple[str, ...],
    row_key: str,
) -> Decimal | None:
    minimum = None if row_key == "adjustment" else Decimal("0")
    value = _optional_number(detail, summary_keys, minimum=minimum)
    if value is not None:
        return value
    if rows and all(row[row_key] is not None for row in rows):
        return sum((row[row_key] for row in rows), Decimal("0"))
    return None


def _require_valid_financial_equation(
    gross: Decimal | None,
    retention: Decimal | None,
    adjustment: Decimal | None,
    net: Decimal | None,
    *,
    has_override: bool,
) -> None:
    if gross is None or retention is None or net is None:
        return
    if adjustment is None:
        if has_override:
            return
        adjustment = Decimal("0")
    expected = _money_value(gross) - _money_value(retention) + _money_value(adjustment)
    if _money_value(net) != expected:
        raise ValueError("invalid_billing_pdf_snapshot")


def _require_reconciled_detail(
    detail: dict[str, Any],
    designations: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    summary: dict[str, Decimal | None],
) -> None:
    if not designations:
        return
    checks = (
        ("hours", ("total_hours", "hours"), ("payable_hours", "hours"), False),
        ("gross", ("gross_payment", "gross"), ("gross", "gross_payment"), True),
        ("retention", ("retention_amount", "retention"), ("retention", "retention_amount"), True),
        ("adjustment", ("admin_adjustment", "adjustment"), ("adjustment", "admin_adjustment"), True),
        ("net", ("net_payment", "final_payment", "total_payment", "payment"), ("net", "net_payment", "payment"), True),
    )
    for row_key, summary_keys, row_keys, is_money in checks:
        summary_value = summary[row_key]
        if summary_value is None or not _has_value(detail, summary_keys) or not all(_has_value(item, row_keys) for item in designations):
            continue
        if is_money:
            row_total = sum((_money_value(row[row_key]) for row in rows), Decimal("0"))
            matches = _money_value(summary_value) == row_total
        else:
            row_total = sum((row[row_key] for row in rows), Decimal("0"))
            matches = abs(summary_value - row_total) <= _HOURS_TOLERANCE
        if not matches:
            raise ValueError("invalid_billing_pdf_snapshot")


def _has_value(data: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(key in data and data[key] is not None for key in keys)


def _optional_number(
    data: dict[str, Any],
    keys: tuple[str, ...],
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal | None:
    if not _has_value(data, keys):
        return None
    return _number(data, keys, minimum=minimum, maximum=maximum)


def _money_value(value: Decimal) -> Decimal:
    try:
        return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    except DecimalException as exc:
        raise ValueError("invalid_billing_pdf_snapshot") from exc


def _number(
    data: dict[str, Any],
    keys: tuple[str, ...],
    *,
    default: Decimal | int | float = 0,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal:
    value: Any = default
    for key in keys:
        if key in data and data[key] is not None:
            value = data[key]
            break
    try:
        number = Decimal(str(value))
    except (DecimalException, OverflowError, ValueError, TypeError) as exc:
        raise ValueError("invalid_billing_pdf_snapshot") from exc
    try:
        if (
            not number.is_finite()
            or abs(number) > Decimal("1000000000")
            or (minimum is not None and number < minimum)
            or (maximum is not None and number > maximum)
        ):
            raise ValueError("invalid_billing_pdf_snapshot")
    except DecimalException as exc:
        raise ValueError("invalid_billing_pdf_snapshot") from exc
    return number


def _optional_decimal(
    value: Any,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal | None:
    if value is None:
        return None
    return _number(
        {"value": value},
        ("value",),
        minimum=minimum,
        maximum=maximum,
    )


def _safe_text(value: Any, limit: int, *, redact: str | None = None) -> str:
    if not isinstance(value, (str, int, float, Decimal)) or isinstance(value, bool):
        raise ValueError("invalid_billing_pdf_snapshot")
    text = unicodedata.normalize("NFC", str(value))
    text = "".join(" " if unicodedata.category(char).startswith("C") else char for char in text)
    if redact:
        text = re.sub(re.escape(redact), "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "—"
    return escape(text[:limit])


def _normalize_context(context: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    month = context.get("month")
    year = context.get("year")
    if month is not None:
        try:
            month = int(month)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_billing_pdf_snapshot") from exc
        if month not in _MONTHS:
            raise ValueError("invalid_billing_pdf_snapshot")
        result["month"] = month
    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_billing_pdf_snapshot") from exc
        if not 2000 <= year <= 2100:
            raise ValueError("invalid_billing_pdf_snapshot")
        result["year"] = year
    planilla_type = context.get("planilla_type")
    if planilla_type is not None:
        result["planilla_type"] = "Prácticas" if str(planilla_type).lower() in {"practice", "practicas", "prácticas"} else "Regular"
    for key in ("start_date", "end_date"):
        if context.get(key):
            value = str(context[key])
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("invalid_billing_pdf_snapshot")
            result[key] = value
    if context.get("rate_per_hour") is not None:
        result["rate_per_hour"] = _number(
            context,
            ("rate_per_hour",),
            minimum=Decimal("0"),
        )
    return result


def _mask_ci(value: Any) -> str:
    if not isinstance(value, str):
        return "No disponible"
    compact = re.sub(r"\s+", "", value)
    return f"•••• {escape(compact[-4:])}" if len(compact) > 4 else "No disponible"


def _format_money(value: Decimal) -> str:
    quantized = value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    whole, fraction = f"{abs(quantized):.2f}".split(".")
    grouped = f"{int(whole):,}".replace(",", ".")
    return f"{sign}Bs {grouped},{fraction}"


def _format_optional_money(value: Decimal | None) -> str:
    return _format_money(value) if value is not None else "—"


def _format_hours(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):f}".rstrip("0").rstrip(".").replace(".", ",")


def _format_optional_hours(value: Decimal | None) -> str:
    return _format_hours(value) if value is not None else "—"


def _format_rate(value: Decimal | None) -> str:
    if value is None:
        return ""
    rate = value * 100 if abs(value) <= 1 else value
    rendered = _format_hours(rate)
    return f" ({rendered} %)"


def _period_label(context: dict[str, Any]) -> str:
    parts = []
    if context.get("planilla_type"):
        parts.append(str(context["planilla_type"]))
    if context.get("month") and context.get("year"):
        parts.append(f"{_MONTHS[context['month']].capitalize()} {context['year']}")
    return " · ".join(parts)


def _date_range(context: dict[str, Any]) -> str:
    start, end = context.get("start_date"), context.get("end_date")
    if start and end:
        return f"{start} al {end}"
    return str(start or end or "")


def _footer_period(context: dict[str, Any]) -> str:
    if context.get("month") and context.get("year"):
        return f"{_MONTHS[context['month']].capitalize()} {context['year']}"
    return _date_range(context)
