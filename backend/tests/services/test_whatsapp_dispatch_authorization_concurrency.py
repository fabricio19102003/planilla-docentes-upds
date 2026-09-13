"""PostgreSQL authorization races use independent sessions and bounded barriers."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.activity_log import ActivityLog
from app.models.billing_notification import BillingMediaToken, BillingNotificationCapacityWindow, BillingNotificationJob, BillingWhatsAppActivationTest, BillingWhatsAppDispatchAuthorization
from app.schemas.whatsapp_activation import WhatsAppActivationCancel, WhatsAppActivationRelease
from app.services.whatsapp_activation_service import WhatsAppActivationError, WhatsAppActivationService, project_activation_status
from app.workers.billing_notification_worker import BillingNotificationWorker
from app.workers.official_whatsapp_runner import _authorize_activation, expire_activation
from tests.services.test_billing_notification_worker import CLOCK, READY, activation_authorization, queued, worker_session
from tests.services.test_whatsapp_activation_service import _activation_setup, _ready
from tests.services.test_whatsapp_webhook_service import AUTH_TOKEN, SID, STATUS_URL, signature


RELEASE = WhatsAppActivationRelease(attestation="dispatch_reviewed_and_authorized_v1")
CANCEL = WhatsAppActivationCancel(reason="creator_cancelled")


@pytest.fixture(autouse=True)
def _postgresql_case_isolation(test_engine):
    """Reset the disposable PostgreSQL race database after direct commits."""
    if test_engine.dialect.name == "postgresql":
        tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
        with test_engine.begin() as connection:
            connection.exec_driver_sql(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
    yield


def _created_pending(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch)
    created = service.create(actor_user_id=actor.id, request=request, idempotency_key="c" * 16,
        readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32,
        approved_content_sid="HX" + "a" * 32)
    db_session.flush()
    db_session.connection().commit()
    return actor.id, created.id, created.job_id


def _race(factory, *operations):
    barrier = Barrier(len(operations), timeout=3)

    def run(operation):
        db = factory()
        try:
            barrier.wait()
            result = operation(db)
            db.commit()
            return result
        except Exception as exc:
            db.rollback()
            return exc
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        futures = [pool.submit(run, operation) for operation in operations]
        return [future.result(timeout=5) for future in futures]


def _release(actor_id, activation_id, key):
    return lambda db: WhatsAppActivationService(db, recipient_hmac_key="k" * 32).release(
        actor_user_id=actor_id, activation_id=activation_id, request=RELEASE,
        idempotency_key=key, readiness=_ready("HX" + "a" * 32))


def _cancel(actor_id, activation_id, key):
    return lambda db: WhatsAppActivationService(db, recipient_hmac_key="k" * 32).cancel(
        actor_user_id=actor_id, activation_id=activation_id, request=CANCEL, idempotency_key=key)


def _expire(job_id):
    return lambda db: expire_activation(db, job_id)


def _claim():
    return lambda db: BillingNotificationWorker(
        db, lambda: READY, lambda _job: None, claim_intent=lambda: "activation_test", now=lambda: CLOCK).claim_one()


def _boundary(job_id, owner="boundary"):
    return lambda db: _authorize_activation(db, job_id, {}, "k" * 32, owner=owner)


def _live_facts():
    return {"activation": {"dispatch_capable": True}, "global_delivery": {"requested": False, "effective": False},
        "provider_configuration": {"ready": True}, "provider_live": {"ready": True},
        "worker": {"ready": True}, "process_gates": {"official": True, "dispatch": True}}


def _leased(factory, job_id, owner="boundary"):
    db = factory()
    try:
        job = db.get(BillingNotificationJob, job_id)
        job.status, job.lease_owner = "leased", owner
        job.lease_expires_at = datetime.utcnow() + timedelta(minutes=1)
        db.query(BillingWhatsAppActivationTest).filter_by(job_id=job_id).one().status = "leased"
        db.commit()
    finally:
        db.close()


def _expire_now(factory, job_id):
    db = factory()
    try:
        db.query(BillingWhatsAppDispatchAuthorization).filter_by(job_id=job_id).one().expires_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def _graph(factory, job_id):
    db = factory()
    try:
        job = db.get(BillingNotificationJob, job_id)
        activation = db.query(BillingWhatsAppActivationTest).filter_by(job_id=job_id).one()
        authorization = db.query(BillingWhatsAppDispatchAuthorization).filter_by(job_id=job_id).one()
        token = db.query(BillingMediaToken).filter_by(job_id=job_id).one()
        return job, activation, authorization, token
    finally:
        db.close()


def _assert_terminal(factory, job_id, states):
    job, activation, authorization, token = _graph(factory, job_id)
    assert authorization.state in states
    assert (job.status, activation.status, authorization.revoked_at is not None, token.revoked_at is not None) == ("cancelled", "cancelled", True, True)


def test_sqlite_cas_fallback_allows_one_activation_claimer_only(tmp_path):
    """SQLite covers only its explicit CAS fallback, never row-lock behavior."""
    engine, Session = worker_session(tmp_path)
    first, second = Session(), Session()
    queued(first, teacher="activation", intent_type="activation_test")
    job = first.query(BillingNotificationJob).one()
    activation_authorization(first, job)
    first_worker = BillingNotificationWorker(first, lambda: READY, lambda _: None, claim_intent=lambda: "activation_test", now=lambda: CLOCK)
    second_worker = BillingNotificationWorker(second, lambda: READY, lambda _: None, claim_intent=lambda: "activation_test", now=lambda: CLOCK)
    assert first_worker.claim_one().id == job.id
    assert second_worker.claim_one() is None
    first.close(); second.close(); engine.dispose()


def test_postgresql_conflicting_release_has_one_winner_one_conflict_and_one_audit(test_engine, client, db_session, tmp_path, monkeypatch):
    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL transaction race requires TEST_DATABASE_URL=postgresql://...")
    actor_id, activation_id, job_id = _created_pending(client, db_session, tmp_path, monkeypatch)
    factory = sessionmaker(bind=test_engine, autoflush=False)
    results = _race(factory, _release(actor_id, activation_id, "r" * 16), _release(actor_id, activation_id, "s" * 16))
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, WhatsAppActivationError) for result in results) == 1
    job, activation, authorization, token = _graph(factory, job_id)
    assert (job.status, activation.status, authorization.state, token.revoked_at) == ("queued", "queued", "authorized", None)
    db = factory()
    try:
        assert db.query(ActivityLog).filter_by(action="whatsapp_activation_dispatch_authorized").count() == 1
    finally:
        db.close()


@pytest.mark.parametrize("race", ("release_expiry", "expiry_cancel"))
def test_postgresql_expiry_races_are_fully_terminal(race, test_engine, client, db_session, tmp_path, monkeypatch):
    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL transaction race requires TEST_DATABASE_URL=postgresql://...")
    actor_id, activation_id, job_id = _created_pending(client, db_session, tmp_path, monkeypatch)
    factory = sessionmaker(bind=test_engine, autoflush=False)
    _expire_now(factory, job_id)
    operations = (_release(actor_id, activation_id, "r" * 16), _expire(job_id)) if race == "release_expiry" else (_expire(job_id), _cancel(actor_id, activation_id, "x" * 16))
    results = _race(factory, *operations)
    assert sum(result is True for result in results) == 1
    assert sum(isinstance(result, WhatsAppActivationError) for result in results) == 1
    _assert_terminal(factory, job_id, {"expired"})


def test_postgresql_release_then_two_claimers_leases_exactly_one(test_engine, client, db_session, tmp_path, monkeypatch):
    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL transaction race requires TEST_DATABASE_URL=postgresql://...")
    actor_id, activation_id, job_id = _created_pending(client, db_session, tmp_path, monkeypatch)
    factory = sessionmaker(bind=test_engine, autoflush=False)
    assert not isinstance(_race(factory, _release(actor_id, activation_id, "r" * 16))[0], Exception)
    results = _race(factory, _claim(), _claim())
    assert not any(isinstance(result, Exception) for result in results)
    assert sum(result is not None for result in results) == 1
    job, activation, authorization, token = _graph(factory, job_id)
    assert (job.status, activation.status, authorization.state, token.revoked_at) == ("leased", "leased", "authorized", None)


def test_postgresql_claim_cancel_has_one_coherent_outcome(test_engine, client, db_session, tmp_path, monkeypatch):
    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL transaction race requires TEST_DATABASE_URL=postgresql://...")
    actor_id, activation_id, job_id = _created_pending(client, db_session, tmp_path, monkeypatch)
    factory = sessionmaker(bind=test_engine, autoflush=False)
    assert not isinstance(_race(factory, _release(actor_id, activation_id, "r" * 16))[0], Exception)
    claim, cancel = _race(factory, _claim(), _cancel(actor_id, activation_id, "x" * 16))
    assert not isinstance(cancel, Exception)
    assert claim is None or not isinstance(claim, Exception)
    job, activation, authorization, token = _graph(factory, job_id)
    assert (job.status, activation.status, authorization.state, token.revoked_at is not None) == (
        "cancelled", "cancelled", "cancelled", True)


def test_postgresql_expiry_during_actual_capacity_delay_never_authorizes_provider(test_engine, client, db_session, tmp_path, monkeypatch):
    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL capacity-delay race requires TEST_DATABASE_URL=postgresql://...")
    monkeypatch.setattr("app.workers.official_whatsapp_runner.current_delivery_status", lambda _db: _live_facts())
    actor_id, activation_id, job_id = _created_pending(client, db_session, tmp_path, monkeypatch)
    factory = sessionmaker(bind=test_engine, autoflush=False)
    assert not isinstance(_race(factory, _release(actor_id, activation_id, "r" * 16))[0], Exception)
    db = factory()
    try:
        window = db.get(BillingNotificationCapacityWindow, 1) or BillingNotificationCapacityWindow(id=1, revision=0)
        window.next_dispatch_at = CLOCK + timedelta(seconds=1)
        db.add(window)
        db.commit()
    finally:
        db.close()
    entered, release_delay = Barrier(2, timeout=3), Barrier(2, timeout=3)
    sent, worker_db = [], factory()
    facts = {"activation": {"capable": True}, "provider_live": {"capacity": {"available": True, "moving_recipient_limit": 1, "media_mps": 1, "window_seconds": 60}}}
    worker = BillingNotificationWorker(worker_db, lambda: facts, lambda dispatch: sent.append(dispatch), owner="capacity",
        claim_intent=lambda: "activation_test", now=lambda: CLOCK,
        sleeper=lambda _delay: (entered.wait(), release_delay.wait()),
        activation_authorize=lambda jid, _facts: _authorize_activation(worker_db, jid, _facts, "k" * 32, owner="capacity"))
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(worker.process_one)
            entered.wait()
            _expire_now(factory, job_id)
            expiry_db = factory()
            try:
                assert expire_activation(expiry_db, job_id) is True
            finally:
                expiry_db.close()
            release_delay.wait()
            assert result.result(timeout=5) == "cancelled"
    finally:
        worker_db.close()
    assert sent == []
    _assert_terminal(factory, job_id, {"expired"})


def test_postgresql_provider_boundary_consumes_once_and_crash_window_is_bounded(test_engine, client, db_session, tmp_path, monkeypatch):
    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL provider-boundary race requires TEST_DATABASE_URL=postgresql://...")
    monkeypatch.setattr("app.workers.official_whatsapp_runner.current_delivery_status", lambda _db: _live_facts())
    actor_id, activation_id, job_id = _created_pending(client, db_session, tmp_path, monkeypatch)
    factory = sessionmaker(bind=test_engine, autoflush=False)
    assert not isinstance(_race(factory, _release(actor_id, activation_id, "r" * 16))[0], Exception)
    _leased(factory, job_id)
    crashed = factory()
    try:
        crashed.commit = lambda: (_ for _ in ()).throw(RuntimeError("simulated pre-consume crash"))
        with pytest.raises(RuntimeError, match="pre-consume"):
            _authorize_activation(crashed, job_id, {}, "k" * 32, owner="boundary")
        crashed.rollback()
    finally:
        crashed.close()
    job, activation, authorization, _ = _graph(factory, job_id)
    assert (job.status, activation.status, authorization.state, authorization.consumed_at) == ("leased", "leased", "authorized", None)
    results = _race(factory, _boundary(job_id), _boundary(job_id))
    assert not any(isinstance(result, Exception) for result in results)
    assert sum(result is not None for result in results) == 1
    job, activation, authorization, _ = _graph(factory, job_id)
    assert (job.status, activation.status, authorization.state, authorization.consumed_at is not None) == ("sending", "sending", "consumed", True)
    assert _race(factory, _boundary(job_id))[0] is None


def test_postgresql_callback_reconciliation_is_monotonic_and_revokes_once(test_engine, client, db_session, tmp_path, monkeypatch):
    if test_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL callback/reconciliation race requires TEST_DATABASE_URL=postgresql://...")
    from app.services.whatsapp_webhook_service import WhatsAppWebhookService
    monkeypatch.setattr("app.workers.official_whatsapp_runner.current_delivery_status", lambda _db: _live_facts())
    actor_id, activation_id, job_id = _created_pending(client, db_session, tmp_path, monkeypatch)
    factory = sessionmaker(bind=test_engine, autoflush=False)
    assert not isinstance(_race(factory, _release(actor_id, activation_id, "r" * 16))[0], Exception)
    _leased(factory, job_id)
    assert _race(factory, _boundary(job_id))[0] is not None
    db = factory()
    try:
        job = db.get(BillingNotificationJob, job_id)
        job.provider_sid, job.status = SID, "accepted"
        project_activation_status(db, job)
        db.commit()
    finally:
        db.close()
    def callback(db):
        form = [("MessageSid", SID), ("MessageStatus", "read")]
        return WhatsAppWebhookService(db, auth_token=AUTH_TOKEN, status_url=STATUS_URL, inbound_url=None).process_status(form, signature(STATUS_URL, form), "")
    def reconcile(db):
        return WhatsAppWebhookService(db, auth_token=AUTH_TOKEN, status_url=STATUS_URL, inbound_url=None).reconcile(lambda _sid: "read")
    assert all(not isinstance(result, Exception) for result in _race(factory, callback, reconcile))
    job, activation, authorization, token = _graph(factory, job_id)
    assert (job.status, activation.status, authorization.state, authorization.consumed_at is not None, token.revoked_at is not None) == ("read", "read", "consumed", True, True)
