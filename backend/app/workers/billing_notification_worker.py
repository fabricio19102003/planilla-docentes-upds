"""Durable worker for the official WhatsApp billing outbox.

A lease is committed before any readiness or provider call.  A job changes to
``sending`` in a second committed transaction immediately before create; this
makes a crash at the provider boundary ambiguous rather than retryable.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from math import isfinite
from time import sleep
from typing import Any, Callable

from sqlalchemy import and_, exists, func, or_
from sqlalchemy.orm import Session

from app.models.whatsapp_preference import WhatsAppPreference
from app.services.whatsapp_activation_service import project_activation_status
from app.models.billing_notification import (
    BillingNotificationCapacityReservation,
    BillingNotificationCapacityWindow,
    BillingNotificationJob,
    BillingWhatsAppActivationTest,
    BillingWhatsAppDispatchAuthorization,
)


class BillingNotificationWorker:
    def __init__(
        self,
        db: Session,
        readiness: Callable[[], dict[str, Any]],
        transport: Callable[[BillingNotificationJob], Any],
        *,
        owner: str = "worker",
        now: Callable[[], datetime] = datetime.utcnow,
        lease_seconds: int = 60,
        backoff_seconds: int = 30,
        sleeper: Callable[[float], None] = sleep,
        before_transport: Callable[[], None] | None = None,
        dispatch_allowed: Callable[[], bool] | None = None,
        claim_intent: Callable[[], str | None] | None = None,
        activation_authorize: Callable[[int, dict[str, Any]], Any | None] | None = None,
    ) -> None:
        self.db = db
        self.readiness = readiness
        self.transport = transport
        self.owner = owner
        self.now = now
        self.lease_seconds = lease_seconds
        self.backoff_seconds = backoff_seconds
        self.sleeper = sleeper
        self.before_transport = before_transport
        self.dispatch_allowed = dispatch_allowed or (lambda: True)
        self.claim_intent = claim_intent or (lambda: "ordinary")
        self.activation_authorize = activation_authorize

    def claim_one(self) -> BillingNotificationJob | None:
        """Atomically claim one due job for the single intent authorized this cycle."""
        intent = self.claim_intent()
        if intent not in {"ordinary", "activation_test"}:
            return None
        now = self.now()
        due = or_(
            and_(
                BillingNotificationJob.status == "queued",
                or_(
                    BillingNotificationJob.next_attempt_at.is_(None),
                    BillingNotificationJob.next_attempt_at <= now,
                ),
            ),
            and_(
                BillingNotificationJob.status == "leased",
                BillingNotificationJob.lease_expires_at < now,
            ),
        )
        query = (
            self.db.query(BillingNotificationJob)
            .filter(
                BillingNotificationJob.channel == "whatsapp",
                BillingNotificationJob.intent_type == intent,
                due,
            )
            .order_by(BillingNotificationJob.id)
        )
        if self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update(of=BillingNotificationJob, skip_locked=True)
        if intent == "activation_test":
            query = query.filter(self._activation_claimable(now))
        candidate = query.first()
        if candidate is None:
            self.db.rollback()
            return None

        expires = now + timedelta(seconds=self.lease_seconds)
        if self.db.bind.dialect.name == "sqlite":
            claimed = (
                self.db.query(BillingNotificationJob)
                .filter(
                    BillingNotificationJob.id == candidate.id,
                    BillingNotificationJob.intent_type == intent,
                    due,
                    *((self._activation_claimable(now),) if intent == "activation_test" else ()),
                )
                .update(
                    {
                        "status": "leased",
                        "lease_owner": self.owner,
                        "lease_expires_at": expires,
                        "attempts": BillingNotificationJob.attempts + 1,
                    },
                    synchronize_session=False,
                )
            )
            if not claimed:
                self.db.rollback()
                return None
        else:
            candidate.status = "leased"
            candidate.lease_owner = self.owner
            candidate.lease_expires_at = expires
            candidate.attempts += 1
        job_id = candidate.id
        self.db.expire_all()
        job = self.db.get(BillingNotificationJob, job_id)
        if job is not None:
            project_activation_status(self.db, job)
        self.db.commit()  # Never retain the claim lock across readiness or I/O.
        return self.db.get(BillingNotificationJob, job_id)

    def process_one(self) -> str | None:
        job = self.claim_one()
        if job is None:
            return None
        facts = self.readiness()
        activation = job.intent_type == "activation_test"
        ready = facts.get("activation", {}).get("capable") is True if activation else facts.get("ready") is True
        if not ready:
            if activation:
                self._cancel_activation(job.id, "activation_readiness_unavailable")
                return "cancelled"
            self._backoff(job.id, "official_readiness_unavailable")
            return "backoff"
        capacity_facts = self._activation_capacity_facts(facts) if activation else facts
        if capacity_facts is None:
            self._cancel_activation(job.id, "activation_readiness_unavailable")
            return "cancelled"
        reservation = self._reserve_capacity(job, capacity_facts)
        if reservation is None:
            if activation:
                self._cancel_activation(job.id, "activation_readiness_unavailable")
                return "cancelled"
            self._backoff(job.id, "official_capacity_exhausted")
            return "backoff"
        if reservation:
            self.sleeper(reservation)
        if not self._begin_send(job.id):
            return None
        if not activation and not self._can_dispatch(job.id):
            self._backoff(job.id, "official_dispatch_disabled", sending=True)
            return "cancelled"
        if self.before_transport:
            self.before_transport()
        if activation:
            dispatch = self.activation_authorize(job.id, facts) if self.activation_authorize else None
            if dispatch is None:
                return "cancelled"
        else:
            if not self._can_dispatch(job.id):
                self._backoff(job.id, "official_dispatch_disabled", sending=True)
                return "cancelled"
            dispatch = self.db.get(BillingNotificationJob, job.id)
        result = self.transport(dispatch)
        if result.status == "sent":
            self._finalize(job.id, "accepted", getattr(result, "provider_message_id", None))
            return "accepted"
        if result.status == "ambiguous":
            self._finalize(job.id, "ambiguous", None)
            return "ambiguous"
        if activation:
            self._cancel_activation(job.id, "activation_provider_failed")
            return "cancelled"
        self._backoff(job.id, getattr(result, "error_code", "provider_failed"), sending=True)
        return "queued"

    def _activation_claimable(self, now: datetime):
        """Return the authorization predicate repeated by SQLite's claim CAS."""
        authorization = BillingWhatsAppDispatchAuthorization
        activation = BillingWhatsAppActivationTest
        return exists().where(
            authorization.job_id == BillingNotificationJob.id,
            authorization.activation_id == activation.id,
            activation.job_id == BillingNotificationJob.id,
            authorization.creator_user_id == activation.actor_user_id,
            authorization.state == "authorized",
            authorization.expires_at > now,
            authorization.attestation_code == "dispatch_reviewed_and_authorized_v1",
            authorization.release_actor_user_id.is_not(None),
            authorization.release_key_hash.is_not(None),
            authorization.release_request_digest.is_not(None),
            authorization.released_at.is_not(None),
            authorization.consumed_at.is_(None),
            authorization.cancelled_at.is_(None),
            authorization.revoked_at.is_(None),
            activation.status == BillingNotificationJob.status,
        )

    @staticmethod
    def _activation_capacity_facts(facts: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
        """Copy a validated live capacity view without changing shared readiness facts."""
        provider_live = facts.get("provider_live")
        capacity = provider_live.get("capacity") if isinstance(provider_live, dict) else None
        if not isinstance(capacity, dict) or capacity.get("available") is not True:
            return None
        limit = capacity.get("moving_recipient_limit")
        mps = capacity.get("media_mps")
        window_seconds = capacity.get("window_seconds")
        if type(limit) is not int or limit < 1 or not isinstance(mps, (int, float)) or isinstance(mps, bool) or not isfinite(mps) or mps <= 0 or type(window_seconds) is not int or window_seconds < 1:
            return None
        return {"capacity": {
            "moving_recipient_limit": limit,
            "media_mps": mps,
            "window_seconds": window_seconds,
        }}

    def _cancel_activation(self, job_id: int, reason: str) -> None:
        """Activation failures are terminal and never re-enter ordinary fallback."""
        from app.models.billing_notification import BillingMediaToken, BillingWhatsAppActivationTest
        job = self.db.query(BillingNotificationJob).filter_by(id=job_id, intent_type="activation_test", lease_owner=self.owner).one_or_none()
        activation = self.db.query(BillingWhatsAppActivationTest).filter_by(job_id=job_id).one_or_none()
        if job is None or activation is None or job.status not in {"leased", "sending"}:
            self.db.rollback()
            return
        job.status, job.lease_owner, job.lease_expires_at, job.next_attempt_at, job.last_error_code = "cancelled", None, None, None, reason
        project_activation_status(self.db, job, reason)
        self.db.query(BillingMediaToken).filter_by(id=activation.media_token_id, revoked_at=None).update({"revoked_at": self.now()})
        self.db.commit()

    def _backoff(self, job_id: int, reason: str, *, sending: bool = False) -> None:
        now = self.now()
        status = "sending" if sending else "leased"
        updated = (
            self.db.query(BillingNotificationJob)
            .filter(
                BillingNotificationJob.id == job_id,
                BillingNotificationJob.status == status,
                BillingNotificationJob.lease_owner == self.owner,
            )
            .update(
                {
                    "status": "queued",
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "next_attempt_at": now + timedelta(seconds=self.backoff_seconds),
                    "last_error_code": reason,
                },
                synchronize_session=False,
            )
        )
        if updated:
            self.db.commit()
        else:
            self.db.rollback()

    def _begin_send(self, job_id: int) -> bool:
        updated = (
            self.db.query(BillingNotificationJob)
            .filter(
                BillingNotificationJob.id == job_id,
                BillingNotificationJob.status == "leased",
                BillingNotificationJob.lease_owner == self.owner,
            )
            .update({"status": "sending"}, synchronize_session=False)
        )
        if not updated:
            self.db.rollback()
            return False
        self.db.expire_all()
        job = self.db.get(BillingNotificationJob, job_id)
        if job is not None:
            project_activation_status(self.db, job)
        self.db.commit()
        return True

    def _can_dispatch(self, job_id: int) -> bool:
        # A different webhook session may have committed STOP after leasing.
        self.db.expire_all()
        job = self.db.get(BillingNotificationJob, job_id)
        preference = self.db.get(WhatsAppPreference, job.teacher_ci) if job else None
        return bool(
            self.dispatch_allowed()
            and job
            and job.status == "sending"
            and job.intent_type == "ordinary"
            and preference
            and preference.is_eligible_for_whatsapp
        )

    def _finalize(self, job_id: int, status: str, provider_sid: str | None) -> None:
        updated = (
            self.db.query(BillingNotificationJob)
            .filter(
                BillingNotificationJob.id == job_id,
                BillingNotificationJob.status == "sending",
                BillingNotificationJob.lease_owner == self.owner,
            )
            .update(
                {
                    "status": status,
                    "provider_sid": provider_sid,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "next_attempt_at": None,
                },
                synchronize_session=False,
            )
        )
        if updated:
            self.db.expire_all()
            job = self.db.get(BillingNotificationJob, job_id)
            if job is not None:
                project_activation_status(self.db, job)
            self.db.commit()
        else:
            self.db.rollback()

    def _reserve_capacity(self, job: BillingNotificationJob, facts: dict[str, Any]) -> float | None:
        """Reserve one distinct recipient and schedule safely below media MPS.

        The durable singleton is seeded by migration.  Its row lock serializes
        both moving-window recipient accounting and dispatch scheduling.
        """
        capacity = facts.get("capacity") or {}
        limit = capacity.get("moving_recipient_limit", capacity.get("recipient_limit"))
        mps = capacity.get("media_mps", capacity.get("dispatch_mps"))
        window_seconds = capacity.get("window_seconds", 86400)
        if (
            not isinstance(limit, int)
            or limit < 1
            or not isinstance(mps, (int, float))
            or mps <= 0
            or not isinstance(window_seconds, int)
        ):
            return None
        now = self.now()
        cutoff = now - timedelta(seconds=window_seconds)
        window_query = self.db.query(BillingNotificationCapacityWindow).filter_by(id=1)
        if self.db.bind.dialect.name == "postgresql":
            window_query = window_query.with_for_update()
        window = window_query.first()
        if window is None:  # SQLite fixtures/legacy recovery; migration seeds production.
            window = BillingNotificationCapacityWindow(id=1, revision=0)
            self.db.add(window)
            self.db.flush()
        existing_job = (
            self.db.query(BillingNotificationCapacityReservation)
            .filter(BillingNotificationCapacityReservation.job_id == job.id)
            .first()
        )
        recipient_seen = (
            self.db.query(BillingNotificationCapacityReservation.id)
            .filter(
                BillingNotificationCapacityReservation.recipient_key == job.teacher_ci,
                BillingNotificationCapacityReservation.reserved_at >= cutoff,
            )
            .first()
            is not None
        )
        used = (
            self.db.query(func.count(func.distinct(BillingNotificationCapacityReservation.recipient_key)))
            .filter(BillingNotificationCapacityReservation.reserved_at >= cutoff)
            .scalar()
        )
        if existing_job is None and not recipient_seen and used >= limit:
            self.db.rollback()
            return None
        if existing_job is None:
            self.db.add(BillingNotificationCapacityReservation(job_id=job.id, recipient_key=job.teacher_ci, reserved_at=now))

        # A 10% margin keeps actual sends below the observed provider MPS.
        interval = 1.0 / (float(mps) * 0.9)
        scheduled = max(now, window.next_dispatch_at or now)
        delay = max(0.0, (scheduled - now).total_seconds())
        window.next_dispatch_at = scheduled + timedelta(seconds=interval)
        window.revision += 1
        self.db.commit()
        return delay
