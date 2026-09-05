from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services.billing_notification_service import (
    AttemptClaim,
    BillingNotificationService,
    NotificationAttempt,
    SqlAlchemyAttemptStore,
)
from app.services.email_service import EmailAttemptResult, EmailBatchResult, EmailRecipient
from app.services.twilio_whatsapp_transport import TwilioWhatsAppTransport
from app.services.whatsapp_service import WhatsAppSendResult, WhatsAppService


class MemoryStore:
    def __init__(self):
        self.rows = {}
        self.claims = []

    def claim(self, **values):
        key = values["idempotency_key"]
        self.claims.append(values)
        if key in self.rows:
            return AttemptClaim(owned=False, status=self.rows[key]["status"])
        self.rows[key] = {**values, "status": "pending"}
        return AttemptClaim(owned=True, status="pending")

    def finish(self, key, **values):
        self.rows[key].update(values)


class StubWhatsAppService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def send_billing_published(self, publication, user):
        self.calls.append((publication, user))
        return self.result


class StubEmailService:
    def __init__(self, *, status="sent"):
        self.status = status
        self.calls = []

    def send_billing_published(self, publication, users):
        self.calls.append((publication, users))
        user = users[0]
        recipient = EmailRecipient(
            user_id=user.id,
            name=user.full_name,
            email="redacted@example.invalid",
            teacher_ci=user.teacher_ci,
        )
        error = "provider response with private data" if self.status == "failed" else None
        return EmailBatchResult(
            eligible=1,
            sent=1 if self.status == "sent" else 0,
            failed=1 if self.status == "failed" else 0,
            attempts=(EmailAttemptResult(recipient=recipient, status=self.status, error=error),),
        )


def test_sandbox_sends_one_whatsapp_and_does_not_duplicate_with_email():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(WhatsAppSendResult(status="sent", provider_message_id="SM1"))
    email = StubEmailService()
    users = [_user(1), _user(2)]
    service = _service(store, whatsapp, email, enabled=True)

    result = service.send_billing_published(_publication(), users)

    assert result.sent == 1
    assert result.whatsapp_sent == 1
    assert result.email_sent == 0
    assert result.skipped == 1
    assert len(whatsapp.calls) == 1
    assert email.calls == []
    row = next(iter(store.rows.values()))
    assert row["status"] == "sent"
    assert row["provider_message_id"] == "SM1"
    assert "recipient" not in row


def test_sandbox_failure_falls_back_only_for_representative_and_sanitizes_audit():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(
        WhatsAppSendResult(status="failed", error_code="twilio_http_500")
    )
    email = StubEmailService(status="failed")
    users = [_user(1), _user(2), _user(3)]

    result = _service(store, whatsapp, email, enabled=True).send_billing_published(
        _publication(), users
    )

    assert result.failed == 1
    assert result.skipped == 2
    assert len(email.calls) == 1
    assert email.calls[0][1] == [users[0]]
    errors = {row.get("error_code") for row in store.rows.values()}
    assert errors == {"twilio_http_500", "email_provider_failed"}
    assert all("private" not in (error or "") for error in errors)


def test_completed_sandbox_claim_is_reused_without_second_provider_call():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(WhatsAppSendResult(status="sent", provider_message_id="SM1"))
    email = StubEmailService()
    service = _service(store, whatsapp, email, enabled=True)

    first = service.send_billing_published(_publication(), [_user(1)])
    second = service.send_billing_published(_publication(), [_user(1)])

    assert first.sent == 1
    assert second.sent == 0
    assert second.skipped == 1
    assert second.attempts[0].error_code == "already_sent"
    assert len(whatsapp.calls) == 1
    assert email.calls == []


def test_pending_sandbox_claim_is_not_retried_or_fallen_back():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(WhatsAppSendResult(status="sent"))
    email = StubEmailService()
    service = _service(store, whatsapp, email, enabled=True)
    publication = _publication()

    key = service._send_whatsapp(publication, _user(1))[0]
    assert key.status == "sent"
    stored_key = next(iter(store.rows))
    store.rows[stored_key]["status"] = "pending"
    whatsapp.calls.clear()

    result = service.send_billing_published(publication, [_user(1)])

    assert result.sent == 0
    assert result.skipped == 1
    assert result.attempts[0].error_code == "ambiguous_prior_attempt"
    assert whatsapp.calls == []
    assert email.calls == []


def test_whatsapp_disabled_preserves_resend_for_each_user_with_idempotency():
    store = MemoryStore()
    whatsapp = StubWhatsAppService(WhatsAppSendResult(status="sent"))
    email = StubEmailService()
    service = _service(store, whatsapp, email, enabled=False)
    users = [_user(1), _user(2)]

    first = service.send_billing_published(_publication(), users)
    second = service.send_billing_published(_publication(), users)

    assert first.sent == 2
    assert first.email_sent == 2
    assert second.sent == 0
    assert second.email_sent == 0
    assert second.skipped == 2
    assert {attempt.error_code for attempt in second.attempts} == {"already_sent"}
    assert len(email.calls) == 2
    assert whatsapp.calls == []


def test_twilio_timeout_is_audited_as_ambiguous_without_email_fallback():
    def timeout_after_dispatch(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private timeout details", request=request)

    store = MemoryStore()
    transport = TwilioWhatsAppTransport(
        account_sid="AC123",
        api_key_sid="SK123",
        api_key_secret="secret-value",
        from_number="+14155238886",
        client=httpx.Client(transport=httpx.MockTransport(timeout_after_dispatch)),
    )
    settings = SimpleNamespace(
        WHATSAPP_ENABLED=True,
        WHATSAPP_MODE="sandbox",
        TWILIO_WHATSAPP_SANDBOX_FROM="+14155238886",
        TWILIO_WHATSAPP_SANDBOX_TEST_RECIPIENT="+59170000000",
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_API_KEY_SID="SK123",
        TWILIO_API_KEY_SECRET="secret-value",
    )
    whatsapp = WhatsAppService(settings=settings, transport=transport)
    email = StubEmailService()
    service = BillingNotificationService(
        store=store,
        settings=settings,
        whatsapp_service=whatsapp,
        email_service=email,
    )

    first = service.send_billing_published(_publication(), [_user(1)])
    second = service.send_billing_published(_publication(), [_user(1)])

    assert first.sent == first.failed == 0
    assert first.skipped == 1
    assert first.attempts == (
        NotificationAttempt(
            channel="whatsapp",
            status="ambiguous",
            error_code="twilio_delivery_ambiguous",
        ),
    )
    row = next(iter(store.rows.values()))
    assert row["status"] == "ambiguous"
    assert row["error_code"] == "twilio_delivery_ambiguous"
    assert second.sent == second.failed == 0
    assert second.skipped == 1
    assert second.attempts[0].error_code == "ambiguous_prior_attempt"
    assert email.calls == []


def test_sqlalchemy_attempt_store_claim_is_atomic_under_concurrency(tmp_path):
    database_path = tmp_path / "outbound-attempt-concurrency.sqlite3"
    engine = sa.create_engine(
        f"sqlite:///{database_path}",
        connect_args={"timeout": 10},
    )
    from app.models.outbound_notification_attempt import OutboundNotificationAttempt

    OutboundNotificationAttempt.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = threading.Barrier(8)
    publication = _publication()

    def claim_once(_worker: int):
        session = sessions()
        try:
            barrier.wait(timeout=5)
            return SqlAlchemyAttemptStore(session).claim(
                idempotency_key="a" * 64,
                publication=publication,
                user_id=None,
                channel="whatsapp",
                provider="twilio",
                mode="sandbox",
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=8) as executor:
        claims = list(executor.map(claim_once, range(8)))

    assert sum(claim.owned for claim in claims) == 1
    assert {claim.status for claim in claims} == {"pending"}
    with sessions() as session:
        assert session.query(OutboundNotificationAttempt).count() == 1
    engine.dispose()


def _service(store, whatsapp, email, *, enabled):
    return BillingNotificationService(
        store=store,
        settings=SimpleNamespace(WHATSAPP_ENABLED=enabled),
        whatsapp_service=whatsapp,
        email_service=email,
    )


def _publication():
    return SimpleNamespace(id=9, version=3, month=8, year=2026, planilla_type="regular")


def _user(identifier):
    return SimpleNamespace(
        id=identifier,
        full_name=f"Docente {identifier}",
        teacher_ci=str(identifier),
    )


def test_whatsapp_preference_requires_canonical_verified_e164_and_evidence():
    from app.models.whatsapp_preference import WhatsAppPreference

    preference = WhatsAppPreference(
        teacher_ci="123",
        phone_e164="+59170000000",
        is_verified=True,
        consent_evidence="signed-admin-record",
        consent_revision=3,
    )

    assert preference.is_eligible_for_whatsapp is True
    assert WhatsAppPreference.canonical_e164(" +59170000000 ") == "+59170000000"
    assert WhatsAppPreference.canonical_e164("70000000") is None
    assert WhatsAppPreference.canonical_e164("+012345678") is None


def test_whatsapp_preference_requires_evidenced_consent_and_records_opt_out_revision():
    from app.models.whatsapp_preference import WhatsAppPreference

    preference = WhatsAppPreference(
        teacher_ci="123",
        phone_e164="+59170000000",
        is_verified=True,
        consent_evidence=None,
        consent_revision=1,
    )
    assert preference.is_eligible_for_whatsapp is False

    preference.record_consent("signed-admin-record")
    assert preference.is_eligible_for_whatsapp is True
    assert preference.consent_revision == 2

    preference.record_opt_out("twilio-stop-event")
    assert preference.is_eligible_for_whatsapp is False
    assert preference.opted_out_at is not None
    assert preference.opt_out_evidence == "twilio-stop-event"
    assert preference.consent_revision == 3


def test_billing_notification_persistence_has_durable_intent_constraints():
    from app.models.billing_notification import BillingNotificationBatch, BillingNotificationJob

    assert {constraint.name for constraint in BillingNotificationBatch.__table__.constraints} >= {
        "uq_billing_notification_batch_digest"
    }
    assert {constraint.name for constraint in BillingNotificationJob.__table__.constraints} >= {
        "uq_billing_notification_job_intent"
    }
    assert {index.name for index in BillingNotificationJob.__table__.indexes} >= {
        "ix_billing_notification_job_claim"
    }


def test_billing_notification_provider_sids_accept_message_and_media_shapes():
    from app.models.billing_notification import BillingNotificationJob, WhatsAppEvent

    assert BillingNotificationJob.is_provider_sid("SM" + "a" * 32)
    assert BillingNotificationJob.is_provider_sid("MM" + "b" * 32)
    assert WhatsAppEvent.is_provider_sid("SM" + "c" * 32)
    assert not BillingNotificationJob.is_provider_sid("SM" + "a" * 31)
    assert not BillingNotificationJob.is_provider_sid("XX" + "a" * 32)


def test_official_digest_is_canonical_and_binds_consent_channel_content_and_media():
    from app.services.billing_notification_policy import BillingDigestPlanner

    planner = BillingDigestPlanner()
    first = planner.digest(
        publication_id=9,
        publication_version=3,
        billing_digest="billing-v1",
        recipients=[
            {
                "teacher_ci": "200",
                "consent_revision": 4,
                "channel": "whatsapp",
                "reason": "evidenced_consent",
                "content_sid": "HX" + "a" * 32,
                "pdf_sha256": "b" * 64,
                "pdf_size": 1024,
            },
            {
                "teacher_ci": "100",
                "consent_revision": 0,
                "channel": "email",
                "reason": "absent_consent",
                "content_sid": None,
                "pdf_sha256": "c" * 64,
                "pdf_size": 2048,
            },
        ],
    )
    reordered = planner.digest(
        publication_id=9,
        publication_version=3,
        billing_digest="billing-v1",
        recipients=list(reversed([
            {
                "teacher_ci": "200", "consent_revision": 4, "channel": "whatsapp",
                "reason": "evidenced_consent", "content_sid": "HX" + "a" * 32,
                "pdf_sha256": "b" * 64, "pdf_size": 1024,
            },
            {
                "teacher_ci": "100", "consent_revision": 0, "channel": "email",
                "reason": "absent_consent", "content_sid": None,
                "pdf_sha256": "c" * 64, "pdf_size": 2048,
            },
        ])),
    )

    assert first == reordered
    assert len(first) == 64
    assert first != planner.digest(
        publication_id=9, publication_version=3, billing_digest="billing-v1",
        recipients=[{
            "teacher_ci": "100", "consent_revision": 0, "channel": "email",
            "reason": "absent_consent", "content_sid": None,
            "pdf_sha256": "c" * 64, "pdf_size": 2048,
        }, {
            "teacher_ci": "200", "consent_revision": 5, "channel": "whatsapp",
            "reason": "evidenced_consent", "content_sid": "HX" + "a" * 32,
            "pdf_sha256": "b" * 64, "pdf_size": 1024,
        }],
    )


def test_official_policy_snapshots_consent_and_allows_email_only_for_two_safe_cases():
    from app.services.billing_notification_policy import BillingChannelPolicy
    from app.models.whatsapp_preference import WhatsAppPreference

    policy = BillingChannelPolicy()
    consented = WhatsAppPreference(
        teacher_ci="123", phone_e164="+59170000000", is_verified=True,
        consent_evidence="signed", consent_revision=7,
    )
    snapshot = policy.consent_snapshot(consented)
    assert snapshot == {
        "teacher_ci": "123", "consent_revision": 7,
        "eligible": True, "opted_out": False,
    }
    assert policy.select(consented).channel == "whatsapp"
    assert policy.select(None).channel == "email"
    assert policy.select(consented, whatsapp_status="failed", terminal_failure_verified=True).channel == "email"

    for status in ("pending", "ambiguous", "undelivered", "blocked", "readiness_failed"):
        decision = policy.select(consented, whatsapp_status=status)
        assert decision.channel != "email"


def test_official_whatsapp_flags_default_to_disabled():
    from app.config import Settings

    settings = Settings(
        DATABASE_URL="sqlite:///policy-test.db",
        ASYNC_DATABASE_URL="sqlite+aiosqlite:///policy-test.db",
    )

    assert settings.OFFICIAL_WHATSAPP_ENABLED is False
    assert settings.WHATSAPP_DISPATCH_ENABLED is False
