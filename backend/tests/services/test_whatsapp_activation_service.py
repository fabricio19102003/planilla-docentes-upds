import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.models.activity_log import ActivityLog
from app.models.billing_notification import (
    BillingNotificationJob, BillingWhatsAppActivationTest,
    BillingWhatsAppDispatchAuthorization,
)
from app.schemas.whatsapp_activation import (
    WhatsAppActivationCancel, WhatsAppActivationCreate, WhatsAppActivationProjection,
    WhatsAppActivationRelease,
)
from app.models.billing_notification import BillingMediaToken, BillingNotificationBatch, BillingWhatsAppActivationTest
from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.models.user import User
from app.models.whatsapp_preference import WhatsAppPreference
from app.services.billing_pdf_service import BillingPdfService
from app.services.whatsapp_activation_service import WhatsAppActivationError, WhatsAppActivationService, project_activation_status
from tests.routers.test_billing_publication_email import _seed_approved_planilla, _seed_docente


def _activation_setup(client, db_session, tmp_path, monkeypatch):
    import app.routers.billing_publication as publication_router

    _seed_approved_planilla(db_session)
    _seed_docente(db_session, ci="EMAIL-DOC-1", email="activation@example.com")
    monkeypatch.setattr(publication_router.EmailService, "send_billing_published", lambda *_: type("R", (), {"eligible": 0, "sent": 0, "failed": 0, "skipped": 0})())
    assert client.post("/api/billing/publish", json={"month": 5, "year": 2026}).status_code == 200
    preference = WhatsAppPreference(teacher_ci="EMAIL-DOC-1", phone_e164="+59170000000", is_verified=True, consent_evidence="record", consent_source="written_record", consented_at=__import__("datetime").datetime.utcnow(), consent_revision=1)
    db_session.add(preference); db_session.flush()
    revision = db_session.query(BillingPublicationRevision).one()
    actor = db_session.query(User).filter_by(ci="TEST_ADMIN_9999").one()
    request = WhatsAppActivationCreate(teacher_ci="EMAIL-DOC-1", recipient_e164="+59170000000", consent_revision=1, publication_revision_id=revision.id)
    return WhatsAppActivationService(db_session, recipient_hmac_key="k" * 32, pdf_service=BillingPdfService(db_session, storage_dir=tmp_path)), actor, request, revision


def _ready(sid):
    return {"activation": {"creation_capable": True, "dispatch_capable": True, "capable": True}, "global_delivery": {"requested": False, "effective": False}, "provider_configuration": {"ready": True}, "provider_live": {"ready": True}, "approved_content_sid": sid}


def test_activation_create_schema_requires_exact_canonical_recipient():
    request = WhatsAppActivationCreate(
        teacher_ci="teacher-1", recipient_e164="+59170000000",
        consent_revision=1, publication_revision_id=1,
    )
    assert request.recipient_e164 == "+59170000000"
    with pytest.raises(ValueError, match="canonical E.164"):
        WhatsAppActivationCreate(teacher_ci="teacher-1", recipient_e164=" +59170000000", consent_revision=1, publication_revision_id=1)


def test_activation_requires_exact_attestation_and_strict_projection():
    sid = "HX" + "a" * 32
    WhatsAppActivationService._require_readiness(_ready(sid), sid, sid)
    with pytest.raises(WhatsAppActivationError, match="activation_template_unapproved"):
        WhatsAppActivationService._require_readiness(_ready(sid), sid, "HX" + "b" * 32)
    global_on = _ready(sid); global_on["global_delivery"]["effective"] = True
    with pytest.raises(WhatsAppActivationError, match="activation_requires_global_delivery_disabled"):
        WhatsAppActivationService._require_readiness(global_on, sid, sid)
    with pytest.raises(ValueError):
        WhatsAppActivationProjection(id=1, status="queued", terminal_reason=None, teacher_ci_at_creation="T", recipient_masked="+591••••0000", consent_revision=1, publication_revision_id=1, publication_version=1, content_template_bound=True, pdf_bound=True, job_id=1, job_status="unknown", created_at=__import__("datetime").datetime.utcnow(), updated_at=__import__("datetime").datetime.utcnow())


def test_pdf_flush_cleanup_preserves_existing_artifact(tmp_path):
    db = type("DB", (), {"add": lambda *_: None, "flush": lambda *_: (_ for _ in ()).throw(RuntimeError("flush"))})()
    pdf = BillingPdfService(db, storage_dir=tmp_path); batch = type("B", (), {"id": 1})(); job = type("J", (), {"id": 1, "batch_id": 1, "teacher_ci": "T", "media_snapshot": None})()
    with pytest.raises(RuntimeError, match="flush"): pdf.issue(batch, job, {"x": 1}, commit=False)
    payload = pdf._pdf_bytes(1, "T", {"x": 1}); path = pdf._safe_path(f"b-{__import__('hashlib').sha256(payload).hexdigest()[:12]}.pdf"); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)
    with pytest.raises(RuntimeError, match="flush"): pdf.issue(batch, job, {"x": 1}, commit=False)
    assert path.exists()


@pytest.mark.parametrize("mutate, code", [
    (lambda r: r.update(activation=[]), "activation_readiness_unavailable"),
    (lambda r: r["activation"].update(creation_capable=False), "activation_readiness_unavailable"),
    (lambda r: r["activation"].update(creation_capable=None), "activation_readiness_unavailable"),
    (lambda r: r["activation"].pop("creation_capable"), "activation_readiness_unavailable"),
    (lambda r: r.update(global_delivery=[]), "activation_requires_global_delivery_disabled"),
    (lambda r: r["global_delivery"].update(requested=True), "activation_requires_global_delivery_disabled"),
    (lambda r: r["global_delivery"].update(effective=True), "activation_requires_global_delivery_disabled"),
])
def test_activation_malformed_readiness_is_bounded_and_does_not_write(client, db_session, tmp_path, monkeypatch, mutate, code):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    readiness = _ready("HX" + "a" * 32); mutate(readiness); before = _graph_counts(db_session)
    with pytest.raises(WhatsAppActivationError, match=code):
        service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=readiness, configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    assert _graph_counts(db_session) == before


def test_activation_create_without_dispatch_readiness_creates_one_inert_pending_authorization(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    readiness = _ready("HX" + "a" * 32)
    readiness["activation"].update(dispatch_capable=False, capable=False)
    readiness.update(provider_configuration={"ready": False}, provider_live={"ready": False})

    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=readiness, configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    authorization = db_session.query(BillingWhatsAppDispatchAuthorization).one()

    assert (activation.status, db_session.get(BillingNotificationJob, result.job_id).status) == ("queued", "queued")
    assert (authorization.activation_id, authorization.job_id, authorization.creator_user_id, authorization.state) == (activation.id, activation.job_id, actor.id, "pending")
    assert authorization.expires_at - activation.created_at == __import__("datetime").timedelta(minutes=30)
    assert all(getattr(authorization, field) is None for field in ("released_at", "consumed_at", "revoked_at"))
    assert result.replayed is False
    assert result.model_dump(include={
        "authorization_state", "authorization_expires_at", "authorized_at", "consumed_at",
        "revoked_at", "attestation_code", "authorization_terminal_reason",
    }) == {
        "authorization_state": "pending", "authorization_expires_at": authorization.expires_at,
        "authorized_at": None, "consumed_at": None, "revoked_at": None,
        "attestation_code": None, "authorization_terminal_reason": None,
    }

    replay = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness={}, configured_content_sid=None, approved_content_sid=None)
    assert replay.id == result.id and replay.replayed is True
    assert replay.authorization_state == "pending"
    assert db_session.query(BillingWhatsAppDispatchAuthorization).count() == 1


def test_activation_creates_one_private_bound_graph_without_email(client, db_session, tmp_path, monkeypatch):
    service, actor, request, revision = _activation_setup(client, db_session, tmp_path, monkeypatch)
    detail = revision.billing_snapshot["teacher_details"][0]
    publication = db_session.get(BillingPublication, revision.publication_id)
    publication.billing_snapshot = {"mutable_snapshot": "must-not-bind"}; db_session.flush()
    monkeypatch.setattr("app.services.whatsapp_activation_service.validate_publication_revision", lambda _revision: ({}, {"teacher_details": [detail, {"teacher_ci": "UNRELATED-DETAIL"}]}))
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32, ip_address="127.0.0.1")
    activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    job = db_session.get(BillingNotificationJob, result.job_id)
    token = db_session.get(BillingMediaToken, activation.media_token_id)
    batch = db_session.get(BillingNotificationBatch, activation.batch_id)
    audit = db_session.query(ActivityLog).filter_by(action="whatsapp_activation_created").one()
    assert (db_session.query(BillingNotificationBatch).count(), db_session.query(BillingNotificationJob).count(), db_session.query(BillingMediaToken).count(), db_session.query(BillingWhatsAppActivationTest).count(), db_session.query(BillingWhatsAppDispatchAuthorization).count()) == (1, 1, 1, 1, 1)
    assert job.intent_type == "activation_test" and job.channel == "whatsapp" and job.content_sid == activation.content_sid
    assert token.batch_id == batch.id == activation.batch_id and token.job_id == job.id == activation.job_id
    assert token.teacher_ci == activation.teacher_ci_at_creation == request.teacher_ci
    content = Path(token.artifact_path).read_bytes()
    assert token.artifact_hash == activation.artifact_hash == __import__("hashlib").sha256(content).hexdigest()
    assert token.artifact_size == activation.artifact_size == len(content) == job.media_snapshot["artifact_size"]
    assert job.media_snapshot["token_id"] == token.id and job.media_snapshot["artifact_hash"] == token.artifact_hash
    assert activation.publication_revision_id == revision.id and activation.billing_digest == revision.billing_digest
    assert activation.recipient_hmac != request.recipient_e164 and request.recipient_e164 not in str((batch.__dict__, job.__dict__, token.__dict__, activation.__dict__, result, audit.details))
    assert audit.details == {"activation_id": activation.id, "teacher_ci_at_creation": request.teacher_ci, "consent_revision": 1, "publication_revision_id": revision.id, "publication_version": revision.version, "job_id": job.id, "content_template_bound": True, "pdf_bound": True}
    assert "activation@example.com" not in str(audit.details) and result.recipient_masked == "+591••••0000"
    assert f'"publication_revision_id":{revision.id}'.encode() in content
    assert f'"publication_version":{revision.version}'.encode() in content
    assert revision.billing_digest.encode() in content and detail["teacher_ci"].encode() in content
    assert b"must-not-bind" not in content and b"UNRELATED-DETAIL" not in content


def test_activation_storage_failure_leaves_rollback_clean_graph(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch); before = _graph_counts(db_session)
    monkeypatch.setattr(service.pdf_service, "issue_activation", lambda *_a, **_k: (_ for _ in ()).throw(OSError("storage")))
    with pytest.raises(OSError):
        service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    db_session.rollback()
    assert _graph_counts(db_session) == before and not list(tmp_path.glob("*.pdf"))


@pytest.mark.parametrize("drift", ["global", "provider", "worker", "process", "preference", "recipient", "consent", "content", "token", "artifact", "revision", "link", "status", "capacity_delay_expiry", "channel", "batch_publication", "batch_version"])
def test_activation_final_authorization_cancels_every_drift(client, db_session, tmp_path, monkeypatch, drift):
    from app.workers.official_whatsapp_runner import _authorize_activation
    service, actor, request, revision = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="z" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    service.release(actor_user_id=actor.id, activation_id=result.id, request=WhatsAppActivationRelease(attestation="dispatch_reviewed_and_authorized_v1"), idempotency_key="d" * 16, readiness=_ready("HX" + "a" * 32))
    activation = db_session.get(BillingWhatsAppActivationTest, result.id); job = db_session.get(BillingNotificationJob, result.job_id)
    token = db_session.get(BillingMediaToken, activation.media_token_id); preference = db_session.get(WhatsAppPreference, job.teacher_ci)
    authorization = db_session.query(BillingWhatsAppDispatchAuthorization).one()
    job.status, job.lease_owner, job.lease_expires_at, activation.status = "leased", "worker", __import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(minutes=1), "leased"
    facts = {"activation": {"capable": True}, "global_delivery": {"requested": False}}
    fresh = {"activation": {"capable": True}, "global_delivery": {"requested": False, "effective": False}, "provider_configuration": {"ready": True}, "provider_live": {"ready": True}, "worker": {"ready": True}, "process_gates": {"official": True, "dispatch": True}}
    monkeypatch.setattr("app.workers.official_whatsapp_runner.current_delivery_status", lambda _: fresh)
    if drift == "global": fresh["global_delivery"]["requested"] = True
    elif drift == "provider": fresh["provider_live"]["ready"] = False
    elif drift == "worker": fresh["worker"]["ready"] = False
    elif drift == "process": fresh["process_gates"]["dispatch"] = False
    elif drift == "preference": preference.opted_out_at = __import__("datetime").datetime.utcnow()
    elif drift == "recipient": preference.phone_e164 = "+59171111111"
    elif drift == "consent": preference.consent_revision += 1
    elif drift == "content": job.content_sid = "HX" + "b" * 32
    elif drift == "token": token.revoked_at = __import__("datetime").datetime.utcnow()
    elif drift == "artifact": Path(token.artifact_path).write_bytes(b"drift")
    elif drift == "link": activation.batch_id += 99
    elif drift == "status": activation.status = "queued"
    elif drift == "capacity_delay_expiry": authorization.expires_at = __import__("datetime").datetime.utcnow()
    elif drift == "channel": job.channel = "email"
    elif drift == "batch_publication": db_session.get(BillingNotificationBatch, job.batch_id).publication_id += 1
    elif drift == "batch_version": db_session.get(BillingNotificationBatch, job.batch_id).publication_version += 1
    else: revision.version += 1
    db_session.flush()
    assert _authorize_activation(db_session, job.id, facts, "k" * 32) is None
    assert (job.status, job.lease_owner, job.next_attempt_at, activation.status, token.revoked_at is not None) == ("cancelled", None, None, "cancelled", True)


def test_activation_final_authorization_consumes_leased_authority_before_transport(client, db_session, tmp_path, monkeypatch):
    from app.workers.official_whatsapp_runner import _authorize_activation
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="y" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    service.release(actor_user_id=actor.id, activation_id=result.id, request=WhatsAppActivationRelease(attestation="dispatch_reviewed_and_authorized_v1"), idempotency_key="r" * 16, readiness=_ready("HX" + "a" * 32))
    job = db_session.get(BillingNotificationJob, result.job_id); activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    job.status, job.lease_owner, job.lease_expires_at, activation.status = "leased", "worker", __import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(minutes=1), "leased"; db_session.flush()
    monkeypatch.setattr("app.workers.official_whatsapp_runner.current_delivery_status", lambda _: {"activation": {"capable": True}, "global_delivery": {"requested": False, "effective": False}, "provider_configuration": {"ready": True}, "provider_live": {"ready": True}, "worker": {"ready": True}, "process_gates": {"official": True, "dispatch": True}})
    dispatch = _authorize_activation(db_session, job.id, {}, "k" * 32)
    authorization = db_session.query(BillingWhatsAppDispatchAuthorization).one()
    assert dispatch is not None and dispatch.recipient == "+59170000000" and dispatch.media_token
    assert (job.status, activation.status, authorization.state, authorization.consumed_at is not None) == ("sending", "sending", "consumed", True)
    assert _authorize_activation(db_session, job.id, {}, "k" * 32) is None


def test_activation_preprovider_rejection_never_calls_transport(client, db_session, tmp_path, monkeypatch):
    from app.workers.official_whatsapp_runner import _authorize_activation
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="s" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    service.release(actor_user_id=actor.id, activation_id=result.id, request=WhatsAppActivationRelease(attestation="dispatch_reviewed_and_authorized_v1"), idempotency_key="r" * 16, readiness=_ready("HX" + "a" * 32))
    job = db_session.get(BillingNotificationJob, result.job_id); activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    job.status, job.lease_owner, job.lease_expires_at, job.channel, activation.status = "leased", "worker", __import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(minutes=1), "email", "leased"; db_session.commit()
    monkeypatch.setattr("app.workers.official_whatsapp_runner.current_delivery_status", lambda _: {"activation": {"capable": True}, "global_delivery": {"requested": False, "effective": False}, "provider_configuration": {"ready": True}, "provider_live": {"ready": True}, "worker": {"ready": True}, "process_gates": {"official": True, "dispatch": True}})
    calls = []
    dispatch = _authorize_activation(db_session, job.id, {}, "k" * 32)
    if dispatch is not None:
        calls.append(dispatch)
    assert calls == [] and db_session.get(BillingNotificationJob, job.id).status == "cancelled"


def test_activation_authorizer_commits_before_transport_and_never_retries_after_transport_error(client, db_session, tmp_path, monkeypatch):
    from app.workers.official_whatsapp_runner import _authorize_activation
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="t" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    service.release(actor_user_id=actor.id, activation_id=result.id, request=WhatsAppActivationRelease(attestation="dispatch_reviewed_and_authorized_v1"), idempotency_key="u" * 16, readiness=_ready("HX" + "a" * 32))
    job = db_session.get(BillingNotificationJob, result.job_id); activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    job.status, job.lease_owner, job.lease_expires_at, activation.status = "leased", "worker", __import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(minutes=1), "leased"; db_session.commit()
    monkeypatch.setattr("app.workers.official_whatsapp_runner.current_delivery_status", lambda _: {"activation": {"capable": True}, "global_delivery": {"requested": False, "effective": False}, "provider_configuration": {"ready": True}, "provider_live": {"ready": True}, "worker": {"ready": True}, "process_gates": {"official": True, "dispatch": True}})
    dispatch = _authorize_activation(db_session, job.id, {}, "k" * 32)
    authorization = db_session.query(BillingWhatsAppDispatchAuthorization).one()
    calls = []
    def transport(_dispatch):
        calls.append(_dispatch)
        assert (db_session.get(BillingNotificationJob, job.id).status, authorization.state, authorization.consumed_at is not None) == ("sending", "consumed", True)
        raise RuntimeError("transport interrupted")
    with pytest.raises(RuntimeError, match="transport interrupted"):
        transport(dispatch)
    assert calls == [dispatch] and _authorize_activation(db_session, job.id, {}, "k" * 32) is None


def test_activation_authorizer_rolls_back_foreign_or_missing_job_without_downstream_locks(client, db_session, tmp_path, monkeypatch):
    from app.workers.official_whatsapp_runner import _authorize_activation
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="v" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    job = db_session.get(BillingNotificationJob, result.job_id); job.status, job.lease_owner = "leased", "other"; db_session.commit()
    original_query, original_rollback, locked, rollbacks = db_session.query, db_session.rollback, [], []
    def query(model, *args, **kwargs):
        locked.append(model)
        return original_query(model, *args, **kwargs)
    def rollback():
        rollbacks.append(True)
        original_rollback()
    monkeypatch.setattr(db_session, "query", query)
    monkeypatch.setattr(db_session, "rollback", rollback)
    assert _authorize_activation(db_session, job.id, {}, "k" * 32) is None
    assert _authorize_activation(db_session, job.id + 1, {}, "k" * 32) is None
    assert (locked, rollbacks) == ([BillingNotificationJob, BillingNotificationJob], [True, True])


def test_activation_final_authorization_rejects_other_worker_lease(client, db_session, tmp_path, monkeypatch):
    from app.workers.official_whatsapp_runner import _authorize_activation
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="w" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    job = db_session.get(BillingNotificationJob, result.job_id); activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    job.status, job.lease_owner, activation.status = "leased", "other", "leased"; db_session.commit()
    assert _authorize_activation(db_session, result.job_id, {}, "k" * 32, owner="worker") is None
    job = db_session.get(BillingNotificationJob, result.job_id); activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    assert (job.status, job.lease_owner, activation.status) == ("leased", "other", "leased")


def test_activation_kill_switch_cancels_only_unleased_activation(client, db_session, tmp_path, monkeypatch):
    from app.workers.official_whatsapp_runner import rollback_unleased_activation
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="q" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    activation = db_session.get(BillingWhatsAppActivationTest, result.id); job = db_session.get(BillingNotificationJob, result.job_id)
    ordinary_batch = BillingNotificationBatch(publication_id=activation.publication_id, publication_version=activation.publication_version, digest="f" * 64, readiness_snapshot={}, status="queued")
    db_session.add(ordinary_batch); db_session.flush()
    ordinary = BillingNotificationJob(batch_id=ordinary_batch.id, teacher_ci=job.teacher_ci, channel="whatsapp", intent_type="ordinary", status="queued")
    leased_batch = BillingNotificationBatch(publication_id=activation.publication_id, publication_version=activation.publication_version, digest="e" * 64, readiness_snapshot={}, status="queued")
    db_session.add(leased_batch); db_session.flush()
    leased = BillingNotificationJob(batch_id=leased_batch.id, teacher_ci=job.teacher_ci, channel="whatsapp", intent_type="activation_test", status="leased", lease_owner="other")
    db_session.add(leased); db_session.add(ordinary); db_session.flush()
    assert rollback_unleased_activation(db_session) == 1
    token = db_session.get(BillingMediaToken, activation.media_token_id)
    assert (job.status, activation.status, ordinary.status, leased.status, token.revoked_at is not None) == ("cancelled", "cancelled", "queued", "leased", True)


def test_activation_terminal_reason_is_bounded_and_first_terminal_wins(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="r" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    job = db_session.get(BillingNotificationJob, result.job_id)
    job.status = "cancelled"
    project_activation_status(db_session, job, "provider payload +59170000000")
    assert (activation.status, activation.terminal_reason) == ("cancelled", None)


def test_revoked_or_expired_activation_media_never_mutates_delivery_status(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="m" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    activation = db_session.get(BillingWhatsAppActivationTest, result.id)
    job = db_session.get(BillingNotificationJob, result.job_id)
    token = db_session.get(BillingMediaToken, activation.media_token_id)
    job.status = activation.status = "delivered"
    token.token_hash = __import__("hashlib").sha256(b"opaque").hexdigest()
    token.revoked_at = __import__("datetime").datetime.utcnow()
    db_session.commit()
    assert BillingPdfService(db_session, storage_dir=tmp_path).resolve("opaque") is None
    assert (job.status, activation.status) == ("delivered", "delivered")
    token.revoked_at = None
    token.expires_at = __import__("datetime").datetime.utcnow()
    db_session.commit()
    assert BillingPdfService(db_session, storage_dir=tmp_path).resolve("opaque") is None
    assert (job.status, activation.status) == ("delivered", "delivered")


def _graph_counts(db):
    return tuple(db.query(model).count() for model in (BillingNotificationBatch, BillingNotificationJob, BillingMediaToken, BillingWhatsAppActivationTest, BillingWhatsAppDispatchAuthorization, ActivityLog))


@pytest.mark.parametrize("change, code", [
    ("missing_revision", "activation_publication_not_current"),
    ("draft_revision", "activation_publication_not_current"),
    ("stale_publication", "activation_publication_not_current"),
    ("corrupt_revision", "activation_publication_corrupt"),
    ("missing_teacher", "teacher_not_found"),
    ("recipient", "activation_recipient_mismatch"),
    ("consent_revision", "activation_consent_revision_mismatch"),
    ("opted_out", "activation_consent_ineligible"),
    ("unverified", "activation_consent_ineligible"),
    ("missing_detail", "activation_teacher_not_in_revision"),
    ("duplicate_detail", "activation_teacher_not_in_revision"),
])
def test_activation_rejects_invalid_bound_facts_without_writes(client, db_session, tmp_path, monkeypatch, change, code):
    service, actor, request, revision = _activation_setup(client, db_session, tmp_path, monkeypatch)
    preference = db_session.query(WhatsAppPreference).one()
    if change == "missing_revision":
        request = request.model_copy(update={"publication_revision_id": revision.id + 999})
    elif change == "draft_revision":
        revision.status = "draft"
    elif change == "stale_publication":
        revision.version += 1
    elif change == "corrupt_revision":
        revision.billing_digest = "0" * 64
    elif change == "missing_teacher":
        request = request.model_copy(update={"teacher_ci": "ABSENT"})
    elif change == "recipient":
        request = request.model_copy(update={"recipient_e164": "+59171111111"})
    elif change == "consent_revision":
        request = request.model_copy(update={"consent_revision": 2})
    elif change == "opted_out":
        preference.opted_out_at = __import__("datetime").datetime.utcnow()
    elif change == "unverified":
        preference.is_verified = False
    elif change in {"missing_detail", "duplicate_detail"}:
        detail = revision.billing_snapshot["teacher_details"][0]
        details = [] if change == "missing_detail" else [detail, detail]
        monkeypatch.setattr("app.services.whatsapp_activation_service.validate_publication_revision", lambda _revision: ({}, {"teacher_details": details}))
    db_session.flush(); before = _graph_counts(db_session)
    with pytest.raises(WhatsAppActivationError, match=code):
        service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    assert _graph_counts(db_session) == before


@pytest.mark.parametrize("readiness, configured_sid, approved_sid, code", [
    ({}, "HX" + "a" * 32, "HX" + "a" * 32, "activation_requires_global_delivery_disabled"),
    (_ready("HX" + "a" * 32), None, "HX" + "a" * 32, "activation_template_unapproved"),
    (_ready("HX" + "a" * 32), "HX" + "b" * 32, "HX" + "a" * 32, "activation_template_unapproved"),
])
def test_activation_readiness_and_sid_rejections_do_not_write(client, db_session, tmp_path, monkeypatch, readiness, configured_sid, approved_sid, code):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch); before = _graph_counts(db_session)
    with pytest.raises(WhatsAppActivationError, match=code):
        service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=readiness, configured_content_sid=configured_sid, approved_content_sid=approved_sid)
    assert _graph_counts(db_session) == before


@pytest.mark.parametrize("configured_sid, approved_sid, readiness_sid", [
    ("not-a-sid", "not-a-sid", "not-a-sid"),
    ("HX" + "a" * 33, "HX" + "a" * 33, "HX" + "a" * 33),
    ("HX" + "a" * 32, "HX" + "b" * 32, "HX" + "a" * 32),
    ("HX" + "a" * 32, "HX" + "a" * 32, "HX" + "b" * 32),
    ("HX" + "b" * 32, "HX" + "a" * 32, "HX" + "a" * 32),
])
def test_activation_sid_rejections_are_bounded_and_do_not_write(client, db_session, tmp_path, monkeypatch, configured_sid, approved_sid, readiness_sid):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch); before = _graph_counts(db_session)
    with pytest.raises(WhatsAppActivationError, match="activation_template_unapproved"):
        service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready(readiness_sid), configured_content_sid=configured_sid, approved_content_sid=approved_sid)
    assert _graph_counts(db_session) == before


def test_activation_replay_conflict_and_different_actor_are_actor_scoped(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    first = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    other = User(ci="OTHER-ACTOR", full_name="Other Actor", password_hash="x", role="admin")
    db_session.add(other); db_session.flush()
    independent = service.create(actor_user_id=other.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    assert independent.id != first.id
    db_session.query(WhatsAppPreference).one().opted_out_at = __import__("datetime").datetime.utcnow()
    replay = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness={}, configured_content_sid=None, approved_content_sid=None)
    assert replay.id == first.id and replay.replayed is True
    with pytest.raises(WhatsAppActivationError, match="activation_idempotency_conflict"):
        service.create(actor_user_id=actor.id, request=request.model_copy(update={"consent_revision": 2}), idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    assert db_session.query(BillingWhatsAppActivationTest).count() == 2


def test_activation_persistence_rejects_duplicate_actor_idempotency_only(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    result = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    original = db_session.get(BillingWhatsAppActivationTest, result.id)
    batch = BillingNotificationBatch(publication_id=original.publication_id, publication_version=original.publication_version, digest="b" * 64, readiness_snapshot={}, status="queued")
    db_session.add(batch); db_session.flush()
    job = BillingNotificationJob(batch_id=batch.id, teacher_ci=request.teacher_ci, channel="whatsapp", intent_type="activation_test", content_sid=original.content_sid, status="queued")
    db_session.add(job); db_session.flush()
    token = BillingMediaToken(batch_id=batch.id, job_id=job.id, teacher_ci=request.teacher_ci, token_hash="c" * 64, artifact_hash=original.artifact_hash, artifact_path=db_session.get(BillingMediaToken, original.media_token_id).artifact_path, artifact_size=original.artifact_size, expires_at=db_session.get(BillingMediaToken, original.media_token_id).expires_at)
    db_session.add(token); db_session.flush(); job.media_snapshot = {"token_id": token.id, "artifact_hash": token.artifact_hash, "artifact_size": token.artifact_size}
    facts = {column.name: getattr(original, column.name) for column in BillingWhatsAppActivationTest.__table__.columns if column.name != "id"}
    facts.update(batch_id=batch.id, job_id=job.id, media_token_id=token.id)
    db_session.add(BillingWhatsAppActivationTest(**facts))
    with pytest.raises(sa.exc.IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_mutation_uses_job_first_lock_order(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    created = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    original_scalar, locks = db_session.scalar, []
    def locked_scalar(statement, *args, **kwargs):
        entity = statement.column_descriptions[0].get("entity")
        locks.append((entity, statement._for_update_arg is not None))
        return original_scalar(statement, *args, **kwargs)
    monkeypatch.setattr(db_session, "scalar", locked_scalar)
    service._lock_graph(created.id)
    assert locks == [
        (BillingWhatsAppActivationTest, False), (BillingNotificationJob, True),
        (BillingWhatsAppActivationTest, True), (BillingWhatsAppDispatchAuthorization, True),
        (BillingMediaToken, True),
    ]


def test_activation_audit_failure_and_outer_rollback_remove_only_new_artifact(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    before = _graph_counts(db_session)
    original_flush, calls = db_session.flush, {"count": 0}
    def fail_audit_flush():
        calls["count"] += 1
        if calls["count"] == 6:
            raise RuntimeError("audit flush")
        original_flush()
    monkeypatch.setattr(db_session, "flush", fail_audit_flush)
    with pytest.raises(RuntimeError, match="audit flush"):
        service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    db_session.rollback()
    assert _graph_counts(db_session) == before and not list(tmp_path.glob("*.pdf"))


def test_activation_outer_failure_preserves_preexisting_artifact(client, db_session, tmp_path, monkeypatch):
    service, actor, request, revision = _activation_setup(client, db_session, tmp_path, monkeypatch); before = _graph_counts(db_session)
    detail = revision.billing_snapshot["teacher_details"][0]
    payload = service.pdf_service._pdf_bytes(1, request.teacher_ci, {"teacher_detail": detail, "publication_revision_id": revision.id, "publication_version": revision.version, "billing_digest": revision.billing_digest})
    path = service.pdf_service._safe_path(f"b-{__import__('hashlib').sha256(payload).hexdigest()[:12]}.pdf")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)
    original_flush, calls = db_session.flush, {"count": 0}
    def fail_audit_flush():
        calls["count"] += 1
        if calls["count"] == 6: raise RuntimeError("audit flush")
        original_flush()
    monkeypatch.setattr(db_session, "flush", fail_audit_flush)
    with pytest.raises(RuntimeError, match="audit flush"):
        service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    db_session.rollback()
    assert _graph_counts(db_session) == before and path.read_bytes() == payload


ACTIVATION_MIGRATION = "a2c4e6f8b002"
PREVIOUS_MIGRATION = "a2c4e6f8b001"


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[2]
    url = f"sqlite:///{tmp_path / name}"
    engine = sa.create_engine(url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return engine, config


def _migration_module():
    path = Path(__file__).parents[2] / "alembic/versions/a2c4e6f8b002_add_whatsapp_activation_tests.py"
    spec = importlib.util.spec_from_file_location("activation_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_activation_persistence_declares_bounded_and_private_binding():
    table = BillingWhatsAppActivationTest.__table__
    assert BillingWhatsAppActivationTest.__tablename__ == "billing_whatsapp_activation_tests"
    assert "recipient_e164" not in table.c
    assert {"recipient_hmac", "recipient_masked"}.issubset(table.c.keys())
    assert BillingNotificationJob.__table__.c.intent_type.default.arg == "ordinary"
    checks = {constraint.name: str(constraint.sqltext) for constraint in table.constraints if isinstance(constraint, sa.CheckConstraint)}
    assert "consent_revision > 0" in checks["ck_whatsapp_activation_consent_revision_positive"]
    assert "artifact_size > 0" in checks["ck_whatsapp_activation_artifact_size_positive"]
    assert "'cancelled'" in checks["ck_whatsapp_activation_status"]
    unique = {constraint.name for constraint in table.constraints if isinstance(constraint, sa.UniqueConstraint)}
    assert {"uq_whatsapp_activation_actor_key", "uq_whatsapp_activation_batch", "uq_whatsapp_activation_job", "uq_whatsapp_activation_media_token"}.issubset(unique)


def test_activation_migration_fresh_upgrade_creates_constrained_schema(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-fresh.sqlite3")
    command.upgrade(config, ACTIVATION_MIGRATION)
    inspector = sa.inspect(engine)
    assert inspector.has_table("billing_whatsapp_activation_tests")
    assert {"intent_type", "recipient_hmac", "recipient_masked"}.issubset(
        {column["name"] for column in inspector.get_columns("billing_notification_jobs")}
        | {column["name"] for column in inspector.get_columns("billing_whatsapp_activation_tests")}
    )
    assert {"uq_whatsapp_activation_actor_key", "uq_whatsapp_activation_batch", "uq_whatsapp_activation_job", "uq_whatsapp_activation_media_token"}.issubset(
        {item["name"] for item in inspector.get_unique_constraints("billing_whatsapp_activation_tests")}
    )
    assert ("intent_type", "status", "lease_expires_at") in {
        tuple(item["column_names"]) for item in inspector.get_indexes("billing_notification_jobs")
    }
    engine.dispose()


def test_activation_migration_backfills_legacy_jobs_and_refuses_destructive_downgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-legacy.sqlite3")
    command.upgrade(config, PREVIOUS_MIGRATION)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO billing_notification_jobs (batch_id, teacher_ci, channel, status, attempts, created_at, updated_at) VALUES (1, 'legacy', 'whatsapp', 'queued', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
    command.upgrade(config, ACTIVATION_MIGRATION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT intent_type FROM billing_notification_jobs WHERE id = 1")) == "ordinary"
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREVIOUS_MIGRATION)
    assert sa.inspect(engine).has_table("billing_whatsapp_activation_tests")
    engine.dispose()


def test_activation_migration_rejects_incompatible_preexisting_adoption(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-adoption.sqlite3")
    command.upgrade(config, PREVIOUS_MIGRATION)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE billing_whatsapp_activation_tests (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing billing_whatsapp_activation_tests columns"):
        command.upgrade(config, ACTIVATION_MIGRATION)
    engine.dispose()


class _PostgreSQLActivationInspector:
    def __init__(self):
        self.bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()
        table = BillingWhatsAppActivationTest.__table__
        self.columns = [{"name": column.name, "type": column.type, "nullable": column.nullable} for column in table.columns]
        self.pk = {"constrained_columns": ["id"]}
        self.foreign_keys = [{"constrained_columns": [item.parent.name], "referred_table": item.column.table.name, "referred_columns": [item.column.name], "options": {"ondelete": item.ondelete}} for foreign_key in table.foreign_key_constraints for item in foreign_key.elements]
        self.indexes = [{"name": "ix_whatsapp_activation_status", "column_names": ["status"]}]

    def get_columns(self, _table): return self.columns
    def get_pk_constraint(self, _table): return self.pk
    def get_unique_constraints(self, _table): return [{"name": item.name, "column_names": [column.name for column in item.columns]} for item in BillingWhatsAppActivationTest.__table__.constraints if isinstance(item, sa.UniqueConstraint)]
    def get_check_constraints(self, _table): return [{"name": item.name, "sqltext": str(item.sqltext)} for item in BillingWhatsAppActivationTest.__table__.constraints if isinstance(item, sa.CheckConstraint)]
    def get_foreign_keys(self, _table): return self.foreign_keys
    def get_indexes(self, _table): return self.indexes


def test_release_and_creator_cancel_state_machine_is_idempotent_and_sanitized(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    created = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    release = WhatsAppActivationRelease(attestation="dispatch_reviewed_and_authorized_v1")
    cancel = WhatsAppActivationCancel(reason="creator_cancelled")
    released = service.release(actor_user_id=actor.id, activation_id=created.id, request=release, idempotency_key="r" * 16, readiness=_ready("HX" + "a" * 32), ip_address="127.0.0.1")
    authorization = db_session.query(BillingWhatsAppDispatchAuthorization).one()
    assert (released.authorization_state, released.replayed, authorization.release_actor_user_id) == ("authorized", False, actor.id)
    assert db_session.query(ActivityLog).filter_by(action="whatsapp_activation_dispatch_authorized").count() == 1
    db_session.get(BillingNotificationJob, created.job_id).status = "leased"
    replay = service.release(actor_user_id=actor.id, activation_id=created.id, request=release, idempotency_key="r" * 16, readiness={})
    assert replay.replayed is True and replay.job_status == "leased"
    other = User(ci="RELEASE-OTHER", full_name="Other", password_hash="x", role="admin")
    db_session.add(other); db_session.flush()
    with pytest.raises(WhatsAppActivationError, match="dispatch_authorization_idempotency_conflict"):
        service.release(actor_user_id=other.id, activation_id=created.id, request=release, idempotency_key="r" * 16, readiness=_ready("HX" + "a" * 32))
    with pytest.raises(WhatsAppActivationError, match="activation_cancel_forbidden"):
        service.cancel(actor_user_id=other.id, activation_id=created.id, request=cancel, idempotency_key="c" * 16)
    cancelled = service.cancel(actor_user_id=actor.id, activation_id=created.id, request=cancel, idempotency_key="c" * 16)
    token = db_session.get(BillingMediaToken, db_session.get(BillingWhatsAppActivationTest, created.id).media_token_id)
    assert (cancelled.authorization_state, cancelled.replayed, token.revoked_at is not None) == ("cancelled", False, True)
    assert db_session.get(BillingNotificationJob, created.job_id).status == "cancelled"
    assert db_session.query(ActivityLog).filter_by(action="whatsapp_activation_cancelled").count() == 1
    assert service.cancel(actor_user_id=actor.id, activation_id=created.id, request=cancel, idempotency_key="c" * 16).replayed
    expired = service.create(actor_user_id=actor.id, request=request, idempotency_key="e" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    db_session.query(BillingWhatsAppDispatchAuthorization).filter_by(activation_id=expired.id).update({"expires_at": __import__("datetime").datetime.utcnow()})
    with pytest.raises(WhatsAppActivationError, match="dispatch_authorization_already_decided"):
        service.release(actor_user_id=actor.id, activation_id=expired.id, request=release, idempotency_key="x" * 16, readiness=_ready("HX" + "a" * 32))
    with pytest.raises(WhatsAppActivationError, match="activation_cancel_already_decided"):
        service.cancel(actor_user_id=actor.id, activation_id=expired.id, request=cancel, idempotency_key="y" * 16)



@pytest.mark.parametrize("method, state, code", [
    (method, state, f"{'dispatch_authorization' if method == 'release' else 'activation_cancel'}_already_decided")
    for method in ("release", "cancel") for state in ("cancelled", "consumed", "revoked")
])
def test_release_and_cancel_reject_terminal_authorizations_without_mutation_or_audit(client, db_session, tmp_path, monkeypatch, method, state, code):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    created = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    authorization = db_session.query(BillingWhatsAppDispatchAuthorization).one(); now = __import__("datetime").datetime.utcnow()
    facts = {
        "cancelled": {"cancelled_at": now, "revoked_at": now, "cancel_key_hash": "c" * 64, "cancel_request_digest": "d" * 64},
        "consumed": {"released_at": now, "consumed_at": now, "attestation_code": "dispatch_reviewed_and_authorized_v1", "release_actor_user_id": actor.id, "release_key_hash": "r" * 64, "release_request_digest": "d" * 64},
        "revoked": {"revoked_at": now},
    }[state]
    authorization.state = state
    for field, value in facts.items(): setattr(authorization, field, value)
    db_session.commit(); before = (authorization.state, authorization.released_at, authorization.consumed_at, authorization.cancelled_at, authorization.revoked_at, db_session.query(ActivityLog).count())
    action = WhatsAppActivationRelease(attestation="dispatch_reviewed_and_authorized_v1") if method == "release" else WhatsAppActivationCancel(reason="creator_cancelled")
    with pytest.raises(WhatsAppActivationError, match=code):
        getattr(service, method)(actor_user_id=actor.id, activation_id=created.id, request=action, idempotency_key="x" * 16, **({"readiness": _ready("HX" + "a" * 32)} if method == "release" else {}))
    assert (authorization.state, authorization.released_at, authorization.consumed_at, authorization.cancelled_at, authorization.revoked_at, db_session.query(ActivityLog).count()) == before


def test_release_audit_flush_rollback_restores_pending_authorization(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    created = service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    db_session.commit(); monkeypatch.setattr(db_session, "flush", lambda: (_ for _ in ()).throw(RuntimeError("audit flush")))
    with pytest.raises(RuntimeError, match="audit flush"):
        service.release(actor_user_id=actor.id, activation_id=created.id, request=WhatsAppActivationRelease(attestation="dispatch_reviewed_and_authorized_v1"), idempotency_key="r" * 16, readiness=_ready("HX" + "a" * 32))
    db_session.rollback()
    assert db_session.query(BillingWhatsAppDispatchAuthorization).one().state == "pending"
    assert db_session.query(ActivityLog).filter_by(action="whatsapp_activation_dispatch_authorized").count() == 0


def test_release_and_cancel_contracts_are_strict_and_bounded():
    for contract, valid, invalid in (
        (WhatsAppActivationRelease, {"attestation": "dispatch_reviewed_and_authorized_v1"}, {"attestation": "other"}),
        (WhatsAppActivationCancel, {"reason": "creator_cancelled"}, {"reason": "other"}),
    ):
        assert contract(**valid)
        for payload in ({}, invalid, {**valid, "extra": True}):
            with pytest.raises(ValueError):
                contract(**payload)
    with pytest.raises(WhatsAppActivationError, match="invalid_idempotency_key"):
        WhatsAppActivationService._key_hash(" " * 16)


def test_activation_adoption_requires_exact_postgresql_pk_fks_and_indexes():
    module = _migration_module()
    inspector = _PostgreSQLActivationInspector()
    module._validate_activation_table(inspector)
    for attribute, bad, message in (
        ("pk", {"constrained_columns": ["actor_user_id"]}, "primary key"),
        ("indexes", [], "index"),
    ):
        setattr(inspector, attribute, bad)
        with pytest.raises(RuntimeError, match=message):
            module._validate_activation_table(inspector)
        setattr(inspector, attribute, _PostgreSQLActivationInspector().__dict__[attribute])
    for target, action in (("wrong_table", "RESTRICT"), ("users", "CASCADE")):
        bad = [dict(item, options=dict(item["options"])) for item in inspector.foreign_keys]
        bad[0].update(referred_table=target, options={"ondelete": action})
        inspector.foreign_keys = bad
        with pytest.raises(RuntimeError, match="foreign keys"):
            module._validate_activation_table(inspector)
        inspector.foreign_keys = _PostgreSQLActivationInspector().foreign_keys
