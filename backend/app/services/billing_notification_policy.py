"""Pure planning primitives for official WhatsApp billing notifications.

These helpers deliberately do not perform provider I/O or database writes. Preview
and confirmation use the same deterministic input so a confirmation can reject a
plan whose consent, channel, template, or media identity has changed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Literal


Channel = Literal["whatsapp", "email", "blocked"]


@dataclass(frozen=True)
class BillingChannelDecision:
    channel: Channel
    reason: str


class BillingChannelPolicy:
    """Fail-closed channel selection for an individual billing recipient."""

    _TERMINAL_FAILURES = frozenset({"failed", "undelivered"})

    def consent_snapshot(self, preference: Any | None) -> dict[str, Any]:
        """Return the non-sensitive consent facts that bind a planned intent."""
        if preference is None:
            return {
                "teacher_ci": None,
                "consent_revision": 0,
                "eligible": False,
                "opted_out": False,
            }
        return {
            "teacher_ci": str(getattr(preference, "teacher_ci", "")),
            "consent_revision": int(getattr(preference, "consent_revision", 0) or 0),
            "eligible": bool(getattr(preference, "is_eligible_for_whatsapp", False)),
            "opted_out": bool(getattr(preference, "opted_out_at", None)),
        }

    def select(
        self,
        preference: Any | None,
        *,
        whatsapp_status: str | None = None,
        terminal_failure_verified: bool = False,
    ) -> BillingChannelDecision:
        """Choose the only permitted channel without treating ambiguity as failure."""
        snapshot = self.consent_snapshot(preference)
        if snapshot["opted_out"]:
            return BillingChannelDecision("blocked", "opted_out")
        if preference is None or not getattr(preference, "consent_evidence", None):
            return BillingChannelDecision("email", "absent_consent")
        if whatsapp_status in self._TERMINAL_FAILURES and terminal_failure_verified:
            return BillingChannelDecision("email", "definite_terminal_whatsapp_failure")
        if not snapshot["eligible"]:
            return BillingChannelDecision("email", "absent_eligible_consent")
        if whatsapp_status is not None:
            return BillingChannelDecision("blocked", f"whatsapp_{whatsapp_status}")
        return BillingChannelDecision("whatsapp", "evidenced_consent")


class BillingDigestPlanner:
    """Create SHA-256 digests over canonical, immutable billing-plan facts."""

    schema = "official-whatsapp-billing-notification/v1"

    def digest(
        self,
        *,
        publication_id: int,
        publication_version: int,
        billing_digest: str,
        recipients: list[dict[str, Any]],
    ) -> str:
        """Hash a canonical plan independent of caller recipient ordering."""
        plan = {
            "schema": self.schema,
            "publication": {
                "id": int(publication_id),
                "version": int(publication_version),
                "billing_digest": str(billing_digest),
            },
            "recipients": sorted(
                (self._recipient_snapshot(recipient) for recipient in recipients),
                key=lambda recipient: recipient["teacher_ci"],
            ),
        }
        encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _recipient_snapshot(recipient: dict[str, Any]) -> dict[str, Any]:
        required = (
            "teacher_ci",
            "consent_revision",
            "channel",
            "reason",
            "content_sid",
            "pdf_sha256",
            "pdf_size",
        )
        missing = [name for name in required if name not in recipient]
        if missing:
            raise ValueError(f"missing_digest_recipient_fields:{','.join(missing)}")
        return {
            "teacher_ci": str(recipient["teacher_ci"]),
            "consent_revision": int(recipient["consent_revision"]),
            "channel": str(recipient["channel"]),
            "reason": str(recipient["reason"]),
            "content_sid": None if recipient["content_sid"] is None else str(recipient["content_sid"]),
            "pdf_sha256": str(recipient["pdf_sha256"]),
            "pdf_size": int(recipient["pdf_size"]),
        }
