from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.models.whatsapp_preference import WhatsAppPreference
from app.models.billing_notification import (
    BillingNotificationCapacityReservation,
    BillingNotificationCapacityWindow,
    BillingNotificationJob,
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
    WhatsAppPreference.__table__.create(engine)
    WhatsAppEvent.__table__.create(engine)
    return engine, sessionmaker(bind=engine)


def queued(session, *, teacher="x", batch=1, next_attempt_at=None):
    if session.get(WhatsAppPreference, teacher) is None:
        session.add(WhatsAppPreference(teacher_ci=teacher, phone_e164="+59170000000", is_verified=True, consent_evidence="test", consent_revision=1))
    session.add(
        BillingNotificationJob(
            batch_id=batch,
            teacher_ci=teacher,
            channel="whatsapp",
            status="queued",
            next_attempt_at=next_attempt_at,
        )
    )
    session.commit()


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
    session.add(WhatsAppPreference(teacher_ci="x", phone_e164="+59170000000", is_verified=True, consent_evidence="test", consent_revision=1)); session.add(BillingNotificationJob(batch_id=1, teacher_ci="x", channel="whatsapp", status="leased", lease_expires_at=datetime(2000, 1, 1)))
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
