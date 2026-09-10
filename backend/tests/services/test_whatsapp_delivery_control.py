from datetime import datetime, timedelta

from app.models.app_setting import AppSetting
from app.models.billing_notification import BillingNotificationCapacityWindow
from app.services.whatsapp_delivery_control import (
    get_requested_enabled,
    mark_worker_heartbeat,
    status_from_readiness,
)


NOW = datetime(2026, 9, 8, 12, 0, 0)
READY = {"ready": True, "capacity": {"available": True, "remaining": 10}}


def test_delivery_control_is_disabled_by_default_and_reports_distinct_state(db_session):
    status = status_from_readiness(db_session, READY, now=NOW)

    assert status["requested_enabled"] is False
    assert status["effective_enabled"] is False
    assert status["can_enable"] is False
    assert status["blocking_reasons"] == ["worker_unavailable"]


def test_delivery_control_requires_recent_worker_heartbeat(db_session):
    db_session.add(AppSetting(key="BILLING_WHATSAPP_DELIVERY_ENABLED", value="true"))
    db_session.add(BillingNotificationCapacityWindow(id=1, revision=0, worker_heartbeat_at=NOW - timedelta(seconds=61)))
    db_session.commit()

    stale = status_from_readiness(db_session, READY, now=NOW)
    mark_worker_heartbeat(db_session, now=NOW)
    fresh = status_from_readiness(db_session, READY, now=NOW)

    assert stale["effective_enabled"] is False
    assert stale["blocking_reasons"] == ["worker_unavailable"]
    assert fresh["effective_enabled"] is True
    assert fresh["can_enable"] is True


def test_requested_enabled_is_an_uncached_database_read(db_session):
    row = AppSetting(key="BILLING_WHATSAPP_DELIVERY_ENABLED", value="false")
    db_session.add(row)
    db_session.commit()
    assert get_requested_enabled(db_session) is False

    row.value = "true"
    db_session.commit()
    assert get_requested_enabled(db_session) is True


def test_provider_readiness_reasons_remain_bounded(db_session):
    mark_worker_heartbeat(db_session, now=NOW)
    status = status_from_readiness(
        db_session,
        {"ready": False, "reason": "provider returned secret=unsafe", "capacity": {"available": False}},
        now=NOW,
    )

    assert status["can_enable"] is False
    assert status["effective_enabled"] is False
    assert status["blocking_reasons"] == ["provider_unavailable"]


def test_named_facts_and_bounded_reasons_are_independent_and_read_only(db_session):
    row = AppSetting(key="BILLING_WHATSAPP_DELIVERY_ENABLED", value="false")
    db_session.add(row)
    mark_worker_heartbeat(db_session, now=NOW)
    db_session.commit()

    status = status_from_readiness(
        db_session, READY, now=NOW,
        official_process_enabled=True, dispatch_process_enabled=True,
        activation_api_enabled=True, activation_dispatch_enabled=True,
        recipient_hmac_key="h" * 32,
    )

    assert set(("provider_configuration", "provider_live", "worker", "process_gates", "global_delivery", "activation")) <= status.keys()
    assert status["activation"]["capable"] is True
    assert status["global_delivery"] == {"requested": False, "effective": False}
    assert status["readiness"]["reason"] == "admin_disabled"
    assert db_session.get(AppSetting, row.key).value == "false"


def test_future_worker_heartbeat_is_unavailable(db_session):
    db_session.add(BillingNotificationCapacityWindow(
        id=1, revision=0, worker_heartbeat_at=NOW + timedelta(seconds=1),
    ))
    db_session.commit()

    status = status_from_readiness(db_session, READY, now=NOW)

    assert status["worker"] == {
        "ready": False, "reason": "worker_unavailable", "heartbeat_at": NOW + timedelta(seconds=1),
    }
    assert "worker_unavailable" in status["blocking_reasons"]


def test_persisted_request_needs_both_process_gates_and_disables_activation(db_session):
    row = AppSetting(key="BILLING_WHATSAPP_DELIVERY_ENABLED", value="true")
    db_session.add(row)
    mark_worker_heartbeat(db_session, now=NOW)
    db_session.commit()

    blocked = status_from_readiness(
        db_session, READY, now=NOW, official_process_enabled=True, dispatch_process_enabled=False,
        activation_api_enabled=True, activation_dispatch_enabled=True, recipient_hmac_key="h" * 32,
    )
    enabled = status_from_readiness(
        db_session, READY, now=NOW, official_process_enabled=True, dispatch_process_enabled=True,
        activation_api_enabled=True, activation_dispatch_enabled=True, recipient_hmac_key="h" * 32,
    )

    assert blocked["effective_enabled"] is False
    assert "process_gate_disabled" in blocked["blocking_reasons"]
    assert enabled["effective_enabled"] is True
    assert enabled["activation"]["capable"] is False
    assert "global_delivery_enabled" in enabled["activation"]["blocking_reasons"]
