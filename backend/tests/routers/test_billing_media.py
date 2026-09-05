from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.models.billing_notification import BillingMediaToken, BillingNotificationBatch
from app.models.billing_publication import BillingPublication
from app.models.teacher import Teacher
from app.services.billing_pdf_service import BillingPdfService
from app.models.billing_notification import BillingNotificationJob


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


def test_public_media_rejects_unbound_expired_revoked_and_oversized_artifacts(client, db_session, tmp_path, monkeypatch):
    from app.routers import billing_media

    monkeypatch.setattr(billing_media, "_service", lambda db: BillingPdfService(db, storage_dir=tmp_path, now=lambda: datetime(2030, 1, 1)))
    batch = _batch(db_session)
    service = BillingPdfService(db_session, storage_dir=tmp_path, now=lambda: datetime(2030, 1, 1))
    job = _job(db_session, batch)
    issued = service.issue(batch, job, {"net_payment": 123.45})

    head = client.head(f"/api/public/billing-media/{issued.token}")
    get = client.get(f"/api/public/billing-media/{issued.token}")
    repeated = client.get(f"/api/public/billing-media/{issued.token}")
    assert [response.status_code for response in (head, get, repeated)] == [200, 200, 200]
    assert head.headers["content-type"] == "application/pdf"
    assert head.headers["content-length"] == str(len(get.content))
    assert get.headers["cache-control"] == "no-store"
    assert get.headers["content-disposition"].startswith("inline; filename=")
    assert get.content == repeated.content

    row = db_session.query(BillingMediaToken).filter_by(token_hash=issued.token_hash).one()
    row.expires_at = datetime(2029, 12, 31)
    db_session.commit()
    assert client.get(f"/api/public/billing-media/{issued.token}").status_code == 404

    revoked = service.issue(batch, job, {"net_payment": 123.45, "revision": 1})
    revoked_row = db_session.query(BillingMediaToken).filter_by(token_hash=revoked.token_hash).one()
    revoked_row.revoked_at = datetime(2030, 1, 1)
    db_session.commit()
    assert client.get(f"/api/public/billing-media/{revoked.token}").status_code == 404

    assert client.get("/api/public/billing-media/not-a-real-token").status_code == 404

    replacement = service.issue(batch, job, {"net_payment": 123.45, "revision": 2})
    replacement_row = db_session.query(BillingMediaToken).filter_by(token_hash=replacement.token_hash).one()
    Path(replacement_row.artifact_path).write_bytes(b"%PDF-" + b"x" * 15_000_000)
    assert client.get(f"/api/public/billing-media/{replacement.token}").status_code == 404


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

    assert client.get(f"/api/public/billing-media/{issued.token}").status_code == 404


def test_confirm_issues_media_from_immutable_teacher_snapshot(db_session, tmp_path, monkeypatch):
    from app.models.whatsapp_preference import WhatsAppPreference
    from app.services import billing_pdf_service
    from app.services.billing_notification_preview import BillingNotificationPreviewService

    monkeypatch.setattr(billing_pdf_service.default_settings, "BILLING_MEDIA_DIR", str(tmp_path))
    batch_source = _batch(db_session)
    publication = db_session.get(BillingPublication, batch_source.publication_id)
    db_session.add(WhatsAppPreference(teacher_ci="MEDIA-1", phone_e164="+59170000000", is_verified=True, consent_evidence="test", consent_revision=1))
    db_session.commit()
    service = BillingNotificationPreviewService(db_session, readiness={"ready": True, "capacity": {"available": True, "remaining": 1}})
    plan = service.preview(publication, ["MEDIA-1"])
    batch = service.confirm(publication, ["MEDIA-1"], plan.digest)
    db_session.commit()

    job = db_session.query(BillingNotificationJob).filter_by(batch_id=batch.id).one()
    token = db_session.query(BillingMediaToken).filter_by(job_id=job.id).one()
    assert job.media_snapshot == {"token_id": token.id, "artifact_hash": token.artifact_hash, "artifact_size": token.artifact_size}
