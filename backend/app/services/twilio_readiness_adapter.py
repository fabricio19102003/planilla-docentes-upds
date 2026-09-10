"""Bounded provider-readiness facts, separate from delivery authorization."""
from typing import Any


class TwilioReadinessAdapter:
    def evaluate(self, facts: dict[str, Any]) -> dict[str, Any]:
        capacity = facts.get("capacity")
        capacity_available = isinstance(capacity, dict) and bool(capacity.get("available"))
        if facts.get("provider_available") is False:
            reason = "provider_unavailable"
        elif facts.get("sender_status") != "ONLINE":
            reason = "sender_unavailable"
        elif not facts.get("templates_approved"):
            reason = "template_unapproved"
        elif not capacity_available:
            reason = "capacity_unavailable"
        else:
            reason = None
        return {
            "ready": reason is None,
            "capacity": capacity if capacity_available else {"available": False},
            "reason": reason,
        }
