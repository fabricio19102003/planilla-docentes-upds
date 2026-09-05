"""Durable worker for the official WhatsApp billing outbox.

A lease is committed before any readiness or provider call.  A job changes to
``sending`` in a second committed transaction immediately before create; this
makes a crash at the provider boundary ambiguous rather than retryable.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from time import sleep
from typing import Any, Callable

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.whatsapp_preference import WhatsAppPreference
from app.models.billing_notification import (
    BillingNotificationCapacityReservation,
    BillingNotificationCapacityWindow,
    BillingNotificationJob,
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

    def claim_one(self) -> BillingNotificationJob | None:
        """Atomically claim one *due* job and commit its durable lease."""
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
            .filter(BillingNotificationJob.channel == "whatsapp", due)
            .order_by(BillingNotificationJob.id)
        )
        if self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        candidate = query.first()
        if candidate is None:
            self.db.rollback()
            return None

        expires = now + timedelta(seconds=self.lease_seconds)
        if self.db.bind.dialect.name == "sqlite":
            claimed = (
                self.db.query(BillingNotificationJob)
                .filter(BillingNotificationJob.id == candidate.id, due)
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
        self.db.commit()  # Never retain the claim lock across readiness or I/O.
        return self.db.get(BillingNotificationJob, job_id)

    def process_one(self) -> str | None:
        job = self.claim_one()
        if job is None:
            return None
        facts = self.readiness()
        if not facts.get("ready"):
            self._backoff(job.id, "official_readiness_unavailable")
            return "backoff"
        reservation = self._reserve_capacity(job, facts)
        if reservation is None:
            self._backoff(job.id, "official_capacity_exhausted")
            return "backoff"
        if reservation:
            self.sleeper(reservation)
        if not self._begin_send(job.id):
            return None

        # STOP may cancel a committed sending job before this final provider boundary.
        if not self._can_dispatch(job.id):
            return "cancelled"
        if self.before_transport:
            self.before_transport()
        if not self._can_dispatch(job.id):
            return "cancelled"
        result = self.transport(self.db.get(BillingNotificationJob, job.id))
        if result.status == "sent":
            self._finalize(job.id, "accepted", getattr(result, "provider_message_id", None))
            return "accepted"
        if result.status == "ambiguous":
            self._finalize(job.id, "ambiguous", None)
            return "ambiguous"
        self._backoff(job.id, getattr(result, "error_code", "provider_failed"), sending=True)
        return "queued"

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
        self.db.commit()
        return True

    def _can_dispatch(self, job_id: int) -> bool:
        # A different webhook session may have committed STOP after leasing.
        self.db.expire_all()
        job = self.db.get(BillingNotificationJob, job_id)
        preference = self.db.get(WhatsAppPreference, job.teacher_ci) if job else None
        return bool(job and job.status == "sending" and preference and preference.is_eligible_for_whatsapp)

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
