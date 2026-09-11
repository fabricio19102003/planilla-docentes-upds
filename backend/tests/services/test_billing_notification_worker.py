from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app.models.activity_log import ActivityLog
from app.models.teacher import Teacher
from app.models.whatsapp_preference import WhatsAppConsentRevision, WhatsAppPreference
from app.models.billing_notification import (
    BillingMediaToken,
    BillingNotificationCapacityReservation,
    BillingNotificationCapacityWindow,
    BillingNotificationJob,
    BillingWhatsAppActivationTest,
    BillingWhatsAppDispatchAuthorization,
    WhatsAppEvent,
)
from app.workers.billing_notification_worker import BillingNotificationWorker


CLOCK = datetime(2026, 1, 1, 1, 1, 1)
READY = {"ready": True, "capacity": {"moving_recipient_limit": 10, "media_mps": 10, "window_seconds": 3600}}


def worker_session(tmp_path, name="worker"):
    engine = sa.create_engine(f"sqlite:///{tmp_path}/{name}.db")
    BillingNotificationJob.__table__.create(engine)
    BillingNotificationCapacityWindow.__table__.create(engine)
    BillingNotificationCapacityReservation.__table__.create(engine)
    BillingMediaToken.__table__.create(engine)
    BillingWhatsAppActivationTest.__table__.create(engine)
    BillingWhatsAppDispatchAuthorization.__table__.create(engine)
    Teacher.__table__.create(engine)
    WhatsAppPreference.__table__.create(engine)
    WhatsAppConsentRevision.__table__.create(engine)
    ActivityLog.__table__.create(engine)
    WhatsAppEvent.__table__.create(engine)
    return engine, sessionmaker(bind=engine)


def queued(session, *, teacher="x", batch=1, next_attempt_at=None, intent_type="ordinary"):
    if session.get(Teacher, teacher) is None:
        session.add(Teacher(ci=teacher, full_name=teacher))
    if session.get(WhatsAppPreference, teacher) is None:
        session.add(WhatsAppPreference(teacher_ci=teacher, phone_e164="+59170000000", is_verified=True, consent_evidence="test", consent_source="written_record", consented_at=CLOCK, consent_revision=1))
    session.add(
        BillingNotificationJob(
            batch_id=batch,
            teacher_ci=teacher,
            channel="whatsapp",
            intent_type=intent_type,
            status="queued",
            next_attempt_at=next_attempt_at,
        )
    )
    session.commit()


@pytest.mark.parametrize("intent, expected", [
    ("ordinary", "ordinary"), ("activation_test", None), (None, None),
])
def test_worker_claim_intent_is_one_cycle_authority(tmp_path, intent, expected):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, teacher="activation", batch=1, intent_type="activation_test")
    queued(session, teacher="ordinary", batch=2)
    worker = BillingNotificationWorker(
        session, lambda: READY, lambda _: SimpleNamespace(status="sent"),
        claim_intent=lambda: intent, now=lambda: CLOCK,
    )
    claimed = worker.claim_one()
    assert (claimed.intent_type if claimed else None) == expected


def test_missing_activation_authorization_is_not_claimable(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, teacher="activation", intent_type="activation_test")
    worker = BillingNotificationWorker(
        session, lambda: READY, lambda _: SimpleNamespace(status="sent"),
        claim_intent=lambda: "activation_test", now=lambda: CLOCK,
    )

    assert worker.claim_one() is None
    job = session.query(BillingNotificationJob).one()
    assert (job.status, job.lease_owner, job.lease_expires_at, job.attempts) == ("queued", None, None, 0)


def test_pending_activation_authorization_is_not_claimable_while_ordinary_queue_is(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, teacher="activation", batch=1, intent_type="activation_test")
    queued(session, teacher="ordinary", batch=2)
    activation, ordinary = session.query(BillingNotificationJob).order_by(BillingNotificationJob.id).all()
    session.add(BillingWhatsAppDispatchAuthorization(
        activation_id=1,
        job_id=activation.id,
        creator_user_id=1,
        state="pending",
        created_at=CLOCK,
        expires_at=CLOCK + timedelta(minutes=30),
    ))
    session.commit()

    activation_worker = BillingNotificationWorker(
        session, lambda: READY, lambda _: SimpleNamespace(status="sent"),
        claim_intent=lambda: "activation_test", now=lambda: CLOCK,
    )
    ordinary_worker = BillingNotificationWorker(
        session, lambda: READY, lambda _: SimpleNamespace(status="sent"),
        claim_intent=lambda: "ordinary", now=lambda: CLOCK,
    )

    assert activation_worker.claim_one() is None
    assert ordinary_worker.claim_one().id == ordinary.id
    session.expire_all()
    activation = session.get(BillingNotificationJob, activation.id)
    assert (activation.status, activation.lease_owner, activation.lease_expires_at, activation.attempts) == (
        "queued", None, None, 0,
    )


def activation_authorization(session, job, *, state="authorized", expires_at=CLOCK + timedelta(minutes=30), released=True, activation_status="queued", creator_matches=True):
    activation = BillingWhatsAppActivationTest(
        actor_user_id=1, actor_ci="creator", idempotency_key_hash=f"{job.id:064x}",
        request_digest=f"{job.id + 10:064x}", teacher_ci_at_creation=job.teacher_ci,
        recipient_hmac="c" * 64, recipient_masked="***", consent_revision=1,
        publication_id=1, publication_revision_id=1, publication_version=1,
        billing_digest="d" * 64, content_sid="HX" + "e" * 32,
        batch_id=job.batch_id, job_id=job.id, media_token_id=job.id,
        artifact_hash="f" * 64, artifact_size=1, status=activation_status,
        created_at=CLOCK,
    )
    session.add(activation)
    session.flush()
    release = {"attestation_code": "dispatch_reviewed_and_authorized_v1", "release_actor_user_id": 2,
               "release_key_hash": "g" * 64, "release_request_digest": "h" * 64,
               "released_at": CLOCK} if released else {}
    session.add(BillingWhatsAppDispatchAuthorization(
        activation_id=activation.id, job_id=job.id,
        creator_user_id=1 if creator_matches else 2, state=state,
        created_at=CLOCK - timedelta(seconds=1), expires_at=expires_at, **release,
    ))
    session.commit()


def test_activation_claim_requires_complete_bound_unexpired_authorization(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, teacher="valid", batch=1, intent_type="activation_test")
    queued(session, teacher="expired", batch=2, intent_type="activation_test")
    queued(session, teacher="unbound", batch=3, intent_type="activation_test")
    valid, expired, unbound = session.query(BillingNotificationJob).order_by(BillingNotificationJob.id).all()
    activation_authorization(session, valid)
    activation_authorization(session, expired, expires_at=CLOCK)
    activation_authorization(session, unbound, creator_matches=False)

    worker = BillingNotificationWorker(session, lambda: READY, lambda _: SimpleNamespace(status="sent"),
                                      claim_intent=lambda: "activation_test", now=lambda: CLOCK)
    assert worker.claim_one().id == valid.id
    session.expire_all()
    assert [(job.id, job.status) for job in session.query(BillingNotificationJob).order_by(BillingNotificationJob.id)] == [
        (valid.id, "leased"), (expired.id, "queued"), (unbound.id, "queued"),
    ]


def test_activation_claim_postgresql_locks_only_jobs(tmp_path):
    engine, Session = worker_session(tmp_path)
    worker = BillingNotificationWorker(Session(), lambda: READY, lambda _: SimpleNamespace(status="sent"),
                                      claim_intent=lambda: "activation_test", now=lambda: CLOCK)
    query = worker.db.query(BillingNotificationJob).filter(worker._activation_claimable(CLOCK)).with_for_update(
        of=BillingNotificationJob, skip_locked=True,
    )
    sql = str(query.statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF billing_notification_jobs SKIP LOCKED" in sql
    engine.dispose()


def test_activation_capacity_adapter_copies_only_live_provider_capacity_without_mutation(tmp_path):
    _, Session = worker_session(tmp_path)
    worker = BillingNotificationWorker(Session(), lambda: READY, lambda _: SimpleNamespace(status="sent"))
    facts = {"capacity": {"moving_recipient_limit": 99}, "provider_live": {"capacity": {
        "available": True, "moving_recipient_limit": 2, "media_mps": 3, "window_seconds": 60,
    }}}

    adapted = worker._activation_capacity_facts(facts)

    assert adapted == {"capacity": {"moving_recipient_limit": 2, "media_mps": 3, "window_seconds": 60}}
    assert facts == {"capacity": {"moving_recipient_limit": 99}, "provider_live": {"capacity": {
        "available": True, "moving_recipient_limit": 2, "media_mps": 3, "window_seconds": 60,
    }}}


@pytest.mark.parametrize("media_mps", [float("nan"), float("inf"), float("-inf")])
def test_activation_capacity_adapter_rejects_nonfinite_media_mps(tmp_path, media_mps):
    _, Session = worker_session(tmp_path)
    worker = BillingNotificationWorker(Session(), lambda: READY, lambda _: SimpleNamespace(status="sent"))
    facts = {"provider_live": {"capacity": {
        "available": True, "moving_recipient_limit": 2, "media_mps": media_mps, "window_seconds": 60,
    }}}

    assert worker._activation_capacity_facts(facts) is None


def test_worker_never_claims_or_transports_activation_before_pr9b(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, teacher="activation", batch=1, intent_type="activation_test")
    queued(session, teacher="ordinary", batch=2)
    for preference in session.query(WhatsAppPreference).all():
        preference.consent_source = "written_record"
        preference.consented_at = CLOCK
    session.commit()
    transport_calls = []
    worker = BillingNotificationWorker(
        session,
        lambda: READY,
        lambda job: transport_calls.append((job.id, job.intent_type)) or SimpleNamespace(status="sent", provider_message_id="SM" + "a" * 32),
        now=lambda: CLOCK,
    )

    assert worker.process_one() == "accepted"
    activation, ordinary = session.query(BillingNotificationJob).order_by(BillingNotificationJob.id).all()
    assert transport_calls == [(ordinary.id, "ordinary")]
    assert (activation.status, activation.lease_owner, activation.attempts) == ("queued", None, 0)


def test_activation_transport_runs_only_after_activation_authorizer_commits_sending(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session(); queued(session, teacher="activation", intent_type="activation_test")
    job = session.query(BillingNotificationJob).one(); activation_authorization(session, job)
    calls = []
    def authorize(job_id, _facts):
        leased = session.get(BillingNotificationJob, job_id)
        assert (leased.status, leased.lease_owner) == ("leased", "worker")
        leased.status = "sending"; session.commit()
        return leased
    worker = BillingNotificationWorker(
        session, lambda: {"activation": {"capable": True}, "provider_live": {"capacity": {
            "available": True, "moving_recipient_limit": 10, "media_mps": 10, "window_seconds": 60,
        }}}, lambda item: calls.append(item.status) or SimpleNamespace(status="sent", provider_message_id="SM" + "a" * 32),
        claim_intent=lambda: "activation_test", activation_authorize=authorize, now=lambda: CLOCK,
    )
    assert worker.process_one() == "accepted"
    assert calls == ["sending"]


def test_activation_authorizer_rejection_has_no_transport_or_ordinary_fallback(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session(); queued(session, teacher="activation", intent_type="activation_test")
    job = session.query(BillingNotificationJob).one(); activation_authorization(session, job)
    transports = []
    worker = BillingNotificationWorker(
        session, lambda: {"activation": {"capable": True}, "provider_live": {"capacity": {
            "available": True, "moving_recipient_limit": 10, "media_mps": 10, "window_seconds": 60,
        }}}, lambda item: transports.append(item), claim_intent=lambda: "activation_test",
        activation_authorize=lambda *_: None, now=lambda: CLOCK,
    )
    assert worker.process_one() == "cancelled"
    assert transports == []


def test_activation_ambiguous_result_keeps_consumed_authority_nonretryable(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session(); queued(session, teacher="activation", intent_type="activation_test")
    job = session.query(BillingNotificationJob).one(); activation_authorization(session, job)
    def authorize(job_id, _facts):
        row = session.get(BillingNotificationJob, job_id)
        authorization = session.query(BillingWhatsAppDispatchAuthorization).one()
        row.status = "sending"; authorization.state = "consumed"; authorization.consumed_at = CLOCK; session.commit()
        return row
    worker = BillingNotificationWorker(
        session, lambda: {"activation": {"capable": True}, "provider_live": {"capacity": {
            "available": True, "moving_recipient_limit": 10, "media_mps": 10, "window_seconds": 60,
        }}}, lambda _: SimpleNamespace(status="ambiguous"), claim_intent=lambda: "activation_test",
        activation_authorize=authorize, now=lambda: CLOCK,
    )
    assert worker.process_one() == "ambiguous" and worker.process_one() is None
    authorization = session.query(BillingWhatsAppDispatchAuthorization).one()
    assert authorization.state == "consumed" and authorization.revoked_at is not None


def test_worker_claims_once_and_keeps_ambiguous_without_retry(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session)
    calls = []
    worker = BillingNotificationWorker(
        session,
        lambda: READY,
        lambda job: calls.append(job.id) or SimpleNamespace(status="ambiguous", provider_message_id=None),
        now=lambda: CLOCK,
    )

    assert worker.process_one() == "ambiguous"
    assert worker.process_one() is None
    assert calls == [1]


def test_worker_commits_lease_before_readiness_or_transport(tmp_path):
    engine, Session = worker_session(tmp_path)
    session = Session()
    queued(session)
    observed = []

    def readiness():
        observer = Session()
        row = observer.query(BillingNotificationJob).one()
        observed.append((row.status, row.lease_owner, row.lease_expires_at))
        observer.close()
        return READY

    worker = BillingNotificationWorker(
        session,
        readiness,
        lambda _: SimpleNamespace(status="sent", provider_message_id="SM" + "a" * 32),
        owner="first",
        now=lambda: CLOCK,
    )
    assert worker.process_one() == "accepted"
    assert observed == [("leased", "first", CLOCK + timedelta(seconds=60))]
    engine.dispose()


def test_readiness_drift_backs_off_without_transport_or_email_fallback(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session)
    worker = BillingNotificationWorker(
        session,
        lambda: {"ready": False, "capacity": {"moving_recipient_limit": 10, "media_mps": 10}},
        lambda _: (_ for _ in ()).throw(AssertionError("transport must not run")),
        now=lambda: CLOCK,
    )
    assert worker.process_one() == "backoff"
    job = session.query(BillingNotificationJob).one()
    assert (job.status, job.next_attempt_at, job.lease_owner) == (
        "queued",
        CLOCK + timedelta(seconds=30),
        None,
    )


def test_worker_rechecks_admin_gate_at_final_provider_boundary(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session)
    gate = iter((True, False))
    worker = BillingNotificationWorker(
        session,
        lambda: READY,
        lambda _: (_ for _ in ()).throw(AssertionError("transport must not run")),
        now=lambda: CLOCK,
        dispatch_allowed=lambda: next(gate),
    )

    assert worker.process_one() == "cancelled"
    job = session.query(BillingNotificationJob).one()
    assert (job.status, job.next_attempt_at, job.lease_owner) == (
        "queued",
        CLOCK + timedelta(seconds=30),
        None,
    )
    assert job.last_error_code == "official_dispatch_disabled"


def test_future_retry_is_not_claimable_until_clock_reaches_it(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, next_attempt_at=CLOCK + timedelta(seconds=30))
    worker = BillingNotificationWorker(
        session, lambda: READY, lambda _: SimpleNamespace(status="sent", provider_message_id="SM" + "a" * 32), now=lambda: CLOCK
    )
    assert worker.process_one() is None


def test_expired_precreate_lease_is_reclaimed_once_and_sent(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    session.add(WhatsAppPreference(teacher_ci="x", phone_e164="+59170000000", is_verified=True, consent_evidence="test", consent_source="written_record", consented_at=CLOCK, consent_revision=1)); session.add(BillingNotificationJob(batch_id=1, teacher_ci="x", channel="whatsapp", status="leased", lease_expires_at=datetime(2000, 1, 1)))
    session.commit()
    calls = []
    worker = BillingNotificationWorker(
        session,
        lambda: READY,
        lambda job: calls.append(job.id) or SimpleNamespace(status="sent", provider_message_id="SM" + "a" * 32),
        now=lambda: CLOCK,
    )
    assert worker.process_one() == "accepted"
    assert calls == [1]


def test_failure_uses_deterministic_backoff_and_capacity_is_durable(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session)
    worker = BillingNotificationWorker(
        session, lambda: READY, lambda _: SimpleNamespace(status="failed", error_code="twilio_http_500"), now=lambda: CLOCK
    )
    assert worker.process_one() == "queued"
    assert session.query(BillingNotificationJob).one().next_attempt_at == CLOCK + timedelta(seconds=30)
    assert session.query(BillingNotificationCapacityReservation).count() == 1


def test_capacity_reservation_prevents_second_recipient_create(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, teacher="first")
    queued(session, teacher="second")
    calls = []
    worker = BillingNotificationWorker(
        session,
        lambda: {"ready": True, "capacity": {"moving_recipient_limit": 1, "media_mps": 10, "window_seconds": 3600}},
        lambda job: calls.append(job.teacher_ci) or SimpleNamespace(status="sent", provider_message_id="SM" + "a" * 32),
        now=lambda: CLOCK,
    )
    assert worker.process_one() == "accepted"
    assert worker.process_one() == "backoff"
    assert calls == ["first"]


def test_repeated_recipient_uses_one_moving_capacity_slot(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, teacher="same", batch=1)
    queued(session, teacher="same", batch=2)
    calls = []
    worker = BillingNotificationWorker(
        session,
        lambda: {"ready": True, "capacity": {"moving_recipient_limit": 1, "media_mps": 10, "window_seconds": 3600}},
        lambda job: calls.append(job.id) or SimpleNamespace(status="sent", provider_message_id="SM" + "a" * 32),
        now=lambda: CLOCK,
        sleeper=lambda _: None,
    )
    assert worker.process_one() == "accepted"
    assert worker.process_one() == "accepted"
    assert len(calls) == 2
    assert session.query(BillingNotificationCapacityReservation).count() == 2


def test_media_mps_throttle_uses_injected_sleeper_below_limit(tmp_path):
    _, Session = worker_session(tmp_path)
    session = Session()
    queued(session, teacher="first")
    queued(session, teacher="second")
    sleeps = []
    worker = BillingNotificationWorker(
        session,
        lambda: {"ready": True, "capacity": {"moving_recipient_limit": 10, "media_mps": 2, "window_seconds": 3600}},
        lambda _: SimpleNamespace(status="sent", provider_message_id="SM" + "a" * 32),
        now=lambda: CLOCK,
        sleeper=sleeps.append,
    )
    assert worker.process_one() == "accepted"
    assert worker.process_one() == "accepted"
    assert sleeps == [0.555556]


def test_stop_at_provider_barrier_uses_distinct_webhook_session(tmp_path):
    from app.services.whatsapp_webhook_service import WhatsAppWebhookService
    import base64, hashlib, hmac
    engine, Session = worker_session(tmp_path); worker_db = Session(); queued(worker_db, teacher="stop")
    stopped = []
    def stop_before_provider():
        webhook_db = Session()
        try:
            service = WhatsAppWebhookService(webhook_db, auth_token="token", status_url="https://x/status", inbound_url="https://x/inbound", now=lambda: CLOCK)
            fields = [("From", "whatsapp:+59170000000"), ("Body", "STOP")]
            sig = base64.b64encode(hmac.new(b"token", ("https://x/inbound" + "".join(k+v for k,v in sorted(fields))).encode(), hashlib.sha1).digest()).decode()
            stopped.append(service.process_inbound(fields, sig, ""))
        finally:
            webhook_db.close()
    calls=[]
    worker=BillingNotificationWorker(worker_db, lambda: READY, lambda _: calls.append(1), now=lambda: CLOCK, before_transport=stop_before_provider)
    assert worker.process_one() == "cancelled"
    assert stopped == ["opted_out"] and calls == []
    assert worker_db.query(BillingNotificationJob).one().status == "cancelled"
    assert worker.process_one() is None
    engine.dispose()
