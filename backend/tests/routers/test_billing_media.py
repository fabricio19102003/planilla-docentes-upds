from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from app.models.billing_notification import BillingMediaToken, BillingNotificationBatch
from app.models.billing_publication import BillingPublication
from app.models.teacher import Teacher
from app.services.billing_pdf_service import BillingPdfService
from app.models.billing_notification import BillingNotificationJob


def _pdf_reader(payload: bytes) -> PdfReader:
    return PdfReader(BytesIO(payload))


def _extract_pdf_text(payload: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in _pdf_reader(payload).pages)


def _legacy_pdf_bytes() -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer, invariant=1)
    canvas.drawString(40, 760, "legacy technical billing artifact")
    canvas.save()
    return buffer.getvalue()


def _batch(db_session) -> BillingNotificationBatch:
    db_session.add(Teacher(ci="MEDIA-1", full_name="Media Teacher"))
    publication = BillingPublication(
        month=8,
        year=2026,
        planilla_type="regular",
        billing_snapshot={"teacher_details": [{"teacher_ci": "MEDIA-1", "net_payment": 123.45}]},
    )
    db_session.add(publication)
    db_session.flush()
    batch = BillingNotificationBatch(
        publication_id=publication.id,
        publication_version=publication.version,
        digest="a" * 64,
        readiness_snapshot={"ready": True},
        status="queued",
    )
    db_session.add(batch)
    db_session.commit()
    return batch


def _job(db_session, batch):
    job = BillingNotificationJob(batch_id=batch.id, teacher_ci="MEDIA-1", channel="whatsapp", status="queued")
    db_session.add(job)
    db_session.flush()
    return job


def test_billing_pdf_token_is_bound_deterministic_and_revocable(db_session, tmp_path):
    batch = _batch(db_session)
    service = BillingPdfService(db_session, storage_dir=tmp_path, now=lambda: datetime(2030, 1, 1))
    job = _job(db_session, batch)

    first = service.issue(batch, job, {"net_payment": 123.45})
    second = service.issue(batch, job, {"net_payment": 123.45})

    assert first.artifact_hash == second.artifact_hash
    assert first.filename == second.filename
    assert first.filename.endswith(".pdf")
    assert len(first.filename) <= 20
    assert Path(first.artifact_path).read_bytes().startswith(b"%PDF-")
    assert db_session.query(BillingMediaToken).count() == 2
    assert service.resolve(second.token) is not None

    row = db_session.query(BillingMediaToken).filter_by(token_hash=first.token_hash).one()
    row.revoked_at = datetime(2030, 1, 1)
    db_session.commit()
    assert service.resolve(first.token) is None


def test_billing_pdf_is_professional_deterministic_and_excludes_internal_metadata(tmp_path):
    snapshot = {
        "teacher_detail": {
            "teacher_name": "María José Núñez",
            "total_hours": 42,
            "gross_payment": 5184.5,
            "retention_rate": 0.13,
            "retention_amount": 673.99,
            "admin_adjustment": 25,
            "net_payment": 4535.51,
            "has_admin_override": True,
            "designations": [{
                "subject": "Ética y Gestión Pública",
                "semester": "Quinto",
                "group": "A-1",
                "payable_hours": 42,
                "gross": 5184.5,
                "retention": 673.99,
                "adjustment": 25,
                "net": 4535.51,
            }],
        },
        "document_context": {
            "month": 8,
            "year": 2026,
            "planilla_type": "regular",
            "start_date": "2026-08-01",
            "end_date": "2026-08-31",
            "rate_per_hour": 123.44,
        },
        "publication_revision_id": 91,
        "publication_version": 7,
        "billing_digest": "a" * 64,
    }
    first = BillingPdfService._pdf_bytes(37, "CI-77889911", snapshot)
    second = BillingPdfService._pdf_bytes(37, "CI-77889911", snapshot)
    reader = _pdf_reader(first)
    text = _extract_pdf_text(first)

    assert first.startswith(b"%PDF-")
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()
    assert b"sipad-billing-detail-v2" in first
    assert reader.metadata is not None
    assert reader.metadata.get("/Keywords") == "sipad-billing-detail-v2"
    assert "Universidad Privada Domingo Savio" in text.title()
    assert "Detalle de honorarios docentes" in text
    assert "María José Núñez" in text
    assert "Ética y Gestión Pública" in text
    assert "Agosto 2026" in text and "Regular" in text
    assert "Bs 5.184,50" in text and "Bs 4.535,51" in text
    assert "9911" in text and "CI-77889911" not in text
    assert "billing_digest" not in text
    assert "publication_revision_id" not in text
    assert "batch_id" not in text
    assert "a" * 64 not in text
    assert "teacher_detail" not in text


def test_billing_pdf_supports_multiple_pages_and_repeats_table_header(tmp_path):
    designations = [{
        "subject": f"Materia de formación integral número {index} con nombre extenso",
        "semester": "Séptimo",
        "group": f"G-{index}",
        "payable_hours": 4,
        "gross": 400,
        "retention": 52,
        "net": 348,
    } for index in range(80)]
    payload = BillingPdfService._pdf_bytes(1, "DOC-12345678", {
        "teacher_name": "Ángela Pérez",
        "total_hours": 320,
        "gross_payment": 32000,
        "retention_amount": 4160,
        "net_payment": 27840,
        "designations": designations,
    })
    reader = _pdf_reader(payload)
    text = _extract_pdf_text(payload)

    assert len(reader.pages) > 1
    assert text.count("Materia") > 1
    assert "Ángela Pérez" in text


def test_billing_pdf_legacy_snapshot_is_safe_and_invalid_snapshot_fails_bounded(tmp_path):
    payload = BillingPdfService._pdf_bytes(1, "T", {"x": 1})
    text = _extract_pdf_text(payload)

    assert payload.startswith(b"%PDF-")
    assert "Docente" in text
    assert "No disponible" in text
    assert "Sin designaciones registradas" in text
    assert "\"x\"" not in text
    with pytest.raises(ValueError, match="invalid_billing_pdf_snapshot"):
        BillingPdfService._pdf_bytes(1, "T", {"designations": "not-a-list"})


def test_billing_pdf_rejects_extreme_decimal_with_bounded_error():
    with pytest.raises(ValueError, match="^invalid_billing_pdf_snapshot$"):
        BillingPdfService._pdf_bytes(1, "T", {"net_payment": "1e1000000"})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total_hours", 9),
        ("gross_payment", 999),
        ("retention_amount", 99),
        ("admin_adjustment", 9),
        ("net_payment", 999),
    ],
)
def test_billing_pdf_rejects_inconsistent_designation_aggregates(field, value):
    detail = {
        "total_hours": 10,
        "gross_payment": 1000,
        "retention_amount": 130,
        "admin_adjustment": 20,
        "net_payment": 890,
        "designations": [
            {"subject": "Materia A", "payable_hours": 4, "gross": 400, "retention": 52, "adjustment": 5, "net": 353},
            {"subject": "Materia B", "payable_hours": 6, "gross": 600, "retention": 78, "adjustment": 15, "net": 537},
        ],
    }
    detail[field] = value

    with pytest.raises(ValueError, match="^invalid_billing_pdf_snapshot$"):
        BillingPdfService._pdf_bytes(1, "DOC-12345678", detail)


def test_billing_pdf_allows_legacy_rows_missing_reconciliation_fields():
    payload = BillingPdfService._pdf_bytes(1, "DOC-12345678", {
        "total_hours": 10,
        "gross_payment": 1000,
        "retention_amount": 130,
        "net_payment": 870,
        "designations": [
            {"subject": "Materia completa", "payable_hours": 4, "gross": 400, "retention": 52, "net": 348},
            {"subject": "Materia legacy", "payment": 522},
        ],
    })

    text = _extract_pdf_text(payload)
    assert payload.startswith(b"%PDF-")
    assert "Materia legacy" in text
    assert text.count("—") >= 4
    assert "Bs 0,00" not in text


def test_billing_pdf_partial_legacy_snapshot_does_not_invent_summary_zeros():
    payload = BillingPdfService._pdf_bytes(1, "DOC-12345678", {
        "teacher_name": "Docente Legacy",
        "designations": [{"subject": "Materia parcial", "payment": 522}],
    })
    text = _extract_pdf_text(payload)
    summary_text = text.split("Detalle por materia", 1)[0]

    assert "Materia parcial" in text
    assert "Neto final" in summary_text and "Bs 522,00" in summary_text
    assert "Horas" not in summary_text and "Bruto" not in summary_text and "Retención" not in summary_text
    assert "Bs 0,00" not in text


def test_billing_pdf_rejects_invalid_row_financial_equation():
    detail = {
        "designations": [{
            "subject": "Materia inconsistente",
            "gross": 100,
            "retention": 13,
            "adjustment": 0,
            "net": 90,
        }],
    }

    with pytest.raises(ValueError, match="^invalid_billing_pdf_snapshot$"):
        BillingPdfService._pdf_bytes(1, "DOC-12345678", detail)


def test_billing_pdf_rejects_invalid_summary_financial_equation():
    detail = {
        "gross_payment": 100,
        "retention_amount": 13,
        "admin_adjustment": 0,
        "net_payment": 90,
        "designations": [{"subject": "Materia legacy"}],
    }

    with pytest.raises(ValueError, match="^invalid_billing_pdf_snapshot$"):
        BillingPdfService._pdf_bytes(1, "DOC-12345678", detail)


def test_billing_pdf_accepts_complete_valid_financial_equations():
    detail = {
        "total_hours": 10,
        "gross_payment": 1000,
        "retention_amount": 130,
        "admin_adjustment": 20,
        "net_payment": 890,
        "has_admin_override": True,
        "designations": [
            {"subject": "Materia A", "payable_hours": 4, "gross": 400, "retention": 52, "adjustment": 5, "net": 353, "has_admin_override": True},
            {"subject": "Materia B", "payable_hours": 6, "gross": 600, "retention": 78, "adjustment": 15, "net": 537, "has_admin_override": True},
        ],
    }

    payload = BillingPdfService._pdf_bytes(1, "DOC-12345678", detail)
    assert payload.startswith(b"%PDF-")
    assert "Neto final" in _extract_pdf_text(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("total_hours", -1),
        ("gross_payment", -1),
        ("retention_amount", -1),
        ("net_payment", -1),
    ],
)
def test_billing_pdf_rejects_negative_summary_values(field, value):
    with pytest.raises(ValueError, match="^invalid_billing_pdf_snapshot$"):
        BillingPdfService._pdf_bytes(1, "DOC-12345678", {field: value})


@pytest.mark.parametrize(
    "field",
    ["payable_hours", "gross", "retention", "net"],
)
def test_billing_pdf_rejects_negative_designation_values(field):
    with pytest.raises(ValueError, match="^invalid_billing_pdf_snapshot$"):
        BillingPdfService._pdf_bytes(1, "DOC-12345678", {
            "designations": [{"subject": "Materia inválida", field: -1}],
        })


@pytest.mark.parametrize("retention_rate", [-0.01, 1.01, 13, 101])
def test_billing_pdf_rejects_retention_rate_outside_fractional_range(retention_rate):
    with pytest.raises(ValueError, match="^invalid_billing_pdf_snapshot$"):
        BillingPdfService._pdf_bytes(1, "DOC-12345678", {
            "retention_rate": retention_rate,
        })


def test_billing_pdf_rejects_negative_hourly_rate():
    with pytest.raises(ValueError, match="^invalid_billing_pdf_snapshot$"):
        BillingPdfService._pdf_bytes(1, "DOC-12345678", {
            "teacher_detail": {},
            "document_context": {"rate_per_hour": -1},
        })


def test_billing_pdf_accepts_signed_negative_adjustment():
    detail = {
        "gross_payment": 100,
        "retention_amount": 13,
        "admin_adjustment": -5,
        "net_payment": 82,
        "has_admin_override": True,
        "designations": [{
            "subject": "Materia con descuento",
            "gross": 100,
            "retention": 13,
            "adjustment": -5,
            "net": 82,
            "has_admin_override": True,
        }],
    }

    payload = BillingPdfService._pdf_bytes(1, "DOC-12345678", detail)
    assert "-Bs 5,00" in _extract_pdf_text(payload)


def test_resolve_accepts_v2_and_rejects_legacy_pdf_with_matching_binding(db_session, tmp_path):
    batch = _batch(db_session)
    service = BillingPdfService(db_session, storage_dir=tmp_path, now=lambda: datetime(2030, 1, 1))
    job = _job(db_session, batch)
    issued = service.issue(batch, job, {"net_payment": 123.45})
    row = db_session.query(BillingMediaToken).filter_by(token_hash=issued.token_hash).one()
    assert b"sipad-billing-detail-v2" in Path(row.artifact_path).read_bytes()
    assert service.resolve(issued.token) is not None

    legacy = _legacy_pdf_bytes()
    legacy_hash = hashlib.sha256(legacy).hexdigest()
    Path(row.artifact_path).write_bytes(legacy)
    row.artifact_hash = legacy_hash
    row.artifact_size = len(legacy)
    job.media_snapshot = {
        "token_id": row.id,
        "artifact_hash": legacy_hash,
        "artifact_size": len(legacy),
    }
    db_session.commit()

    assert _pdf_reader(legacy).pages[0].extract_text()
    assert b"sipad-billing-detail-v2" not in legacy
    assert service.resolve(issued.token) is None


def test_public_media_rejects_unbound_expired_revoked_and_oversized_artifacts(client, db_session, tmp_path, monkeypatch):
    from app.routers import billing_media

    monkeypatch.setattr(billing_media, "_service", lambda db: BillingPdfService(db, storage_dir=tmp_path, now=lambda: datetime(2030, 1, 1)))
    batch = _batch(db_session)
    service = BillingPdfService(db_session, storage_dir=tmp_path, now=lambda: datetime(2030, 1, 1))
    job = _job(db_session, batch)
    issued = service.issue(batch, job, {"net_payment": 123.45})

    head = client.head(f"/api/public/billing-media/{issued.token}.pdf")
    get = client.get(f"/api/public/billing-media/{issued.token}.pdf")
    repeated = client.get(f"/api/public/billing-media/{issued.token}.pdf")
    assert [response.status_code for response in (head, get, repeated)] == [200, 200, 200]
    assert client.get(f"/api/public/billing-media/{issued.token}").status_code == 404
    assert head.headers["content-type"] == "application/pdf"
    assert head.headers["content-length"] == str(len(get.content))
    assert get.headers["cache-control"] == "no-store"
    assert get.headers["content-disposition"].startswith("inline; filename=")
    assert get.content == repeated.content

    row = db_session.query(BillingMediaToken).filter_by(token_hash=issued.token_hash).one()
    row.expires_at = datetime(2029, 12, 31)
    db_session.commit()
    expired = client.get(f"/api/public/billing-media/{issued.token}.pdf")
    assert (expired.status_code, expired.headers["cache-control"]) == (404, "no-store")

    revoked = service.issue(batch, job, {"net_payment": 123.45, "revision": 1})
    revoked_row = db_session.query(BillingMediaToken).filter_by(token_hash=revoked.token_hash).one()
    revoked_row.revoked_at = datetime(2030, 1, 1)
    db_session.commit()
    denied = client.get(f"/api/public/billing-media/{revoked.token}.pdf")
    missing = client.get("/api/public/billing-media/not-a-real-token.pdf")
    assert (denied.status_code, denied.headers["cache-control"]) == (404, "no-store")
    assert (missing.status_code, missing.headers["cache-control"]) == (404, "no-store")

    replacement = service.issue(batch, job, {"net_payment": 123.45, "revision": 2})
    replacement_row = db_session.query(BillingMediaToken).filter_by(token_hash=replacement.token_hash).one()
    Path(replacement_row.artifact_path).write_bytes(b"%PDF-" + b"x" * 15_000_000)
    assert client.get(f"/api/public/billing-media/{replacement.token}.pdf").status_code == 404


def test_public_media_rejects_durable_token_with_mismatched_job_artifact(client, db_session, tmp_path, monkeypatch):
    from app.routers import billing_media
    monkeypatch.setattr(billing_media, "_service", lambda db: BillingPdfService(db, storage_dir=tmp_path, now=lambda: datetime(2030, 1, 1)))
    batch = _batch(db_session)
    job = BillingNotificationJob(batch_id=batch.id, teacher_ci="MEDIA-1", channel="whatsapp", status="queued")
    db_session.add(job)
    db_session.flush()
    issued = BillingPdfService(db_session, storage_dir=tmp_path, now=lambda: datetime(2030, 1, 1)).issue(
        batch, job, {"net_payment": 123.45}
    )
    job.media_snapshot = {"token_id": issued.token_id, "artifact_hash": "0" * 64, "artifact_size": issued.artifact_size}
    db_session.commit()

    assert client.get(f"/api/public/billing-media/{issued.token}.pdf").status_code == 404


def test_rollback_cancels_only_unleased_jobs_and_revokes_their_media_tokens(db_session, tmp_path):
    from app.workers.official_whatsapp_runner import rollback_unleased

    batch = _batch(db_session)
    queued = _job(db_session, batch)
    db_session.add(Teacher(ci="MEDIA-2", full_name="Leased Teacher"))
    leased = BillingNotificationJob(batch_id=batch.id, teacher_ci="MEDIA-2", channel="whatsapp", status="leased", lease_owner="worker")
    db_session.add(leased)
    leased.lease_owner = "worker"; leased.status = "leased"
    service = BillingPdfService(db_session, storage_dir=tmp_path)
    issued = service.issue(batch, queued, {"net_payment": 123.45})
    db_session.commit()

    assert rollback_unleased(db_session, now=datetime(2030, 1, 1)) == 1
    assert queued.status == "cancelled" and leased.status == "leased"
    assert db_session.query(BillingMediaToken).filter_by(token_hash=issued.token_hash).one().revoked_at == datetime(2030, 1, 1)


def test_confirm_issues_media_from_immutable_teacher_snapshot(db_session, tmp_path, monkeypatch):
    from app.models.whatsapp_preference import WhatsAppPreference
    from app.services import billing_pdf_service
    from app.services.billing_notification_preview import BillingNotificationPreviewService

    monkeypatch.setattr(billing_pdf_service.default_settings, "BILLING_MEDIA_DIR", str(tmp_path))
    batch_source = _batch(db_session)
    publication = db_session.get(BillingPublication, batch_source.publication_id)
    db_session.add(WhatsAppPreference(teacher_ci="MEDIA-1", phone_e164="+59170000000", is_verified=True, consent_evidence="test", consent_source="written_record", consented_at=datetime(2026, 8, 1), consent_revision=1))
    db_session.commit()
    service = BillingNotificationPreviewService(db_session, readiness={"ready": True, "capacity": {"available": True, "remaining": 1}})
    plan = service.preview(publication, ["MEDIA-1"])
    batch = service.confirm(publication, ["MEDIA-1"], plan.digest)
    db_session.commit()

    job = db_session.query(BillingNotificationJob).filter_by(batch_id=batch.id).one()
    token = db_session.query(BillingMediaToken).filter_by(job_id=job.id).one()
    assert job.media_snapshot == {"token_id": token.id, "artifact_hash": token.artifact_hash, "artifact_size": token.artifact_size}
