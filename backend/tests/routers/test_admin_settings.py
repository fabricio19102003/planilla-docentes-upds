from __future__ import annotations

from app.models.app_setting import AppSetting
from app.services import app_settings_service
from app.services import whatsapp_delivery_control


def _seed_rate(db_session, key: str, value: str) -> None:
    setting = db_session.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    if setting is None:
        db_session.add(AppSetting(key=key, value=value, description="Test rate"))
    else:
        setting.value = value


def test_partial_active_period_update_preserves_both_hourly_rates(client, db_session):
    _seed_rate(db_session, app_settings_service.KEY_HOURLY_RATE, "70.0")
    _seed_rate(db_session, app_settings_service.KEY_PRACTICE_HOURLY_RATE, "50.0")
    _seed_rate(db_session, app_settings_service.KEY_ACTIVE_ACADEMIC_PERIOD, "I/2026")
    db_session.commit()
    response = client.put(
        "/api/admin/settings",
        json={"active_academic_period": "II/2026"},
    )

    assert response.status_code == 200
    assert response.json()["active_academic_period"] == "II/2026"
    assert response.json()["hourly_rate"] == 70.0
    assert response.json()["practice_hourly_rate"] == 50.0

    persisted = {
        row.key: row.value
        for row in db_session.query(AppSetting)
        .filter(
            AppSetting.key.in_(
                [
                    app_settings_service.KEY_HOURLY_RATE,
                    app_settings_service.KEY_PRACTICE_HOURLY_RATE,
                ]
            )
        )
        .all()
    }
    assert persisted == {
        app_settings_service.KEY_HOURLY_RATE: "70.0",
        app_settings_service.KEY_PRACTICE_HOURLY_RATE: "50.0",
    }


def test_admin_cannot_enable_whatsapp_when_effective_readiness_is_unavailable(client, db_session):
    response = client.put(
        "/api/admin/settings",
        json={"whatsapp_billing_requested_enabled": True},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "whatsapp_delivery_unavailable"
    assert db_session.get(
        AppSetting, app_settings_service.KEY_BILLING_WHATSAPP_DELIVERY_ENABLED
    ) is None


def test_admin_enables_ready_whatsapp_and_audits_state(client, db_session, monkeypatch):
    from app.models.activity_log import ActivityLog

    monkeypatch.setattr(
        whatsapp_delivery_control,
        "_provider_readiness",
        lambda: {"ready": True, "capacity": {"available": True, "remaining": 10}},
    )
    whatsapp_delivery_control.mark_worker_heartbeat(db_session)
    db_session.commit()

    response = client.put(
        "/api/admin/settings",
        json={"whatsapp_billing_requested_enabled": True},
    )

    assert response.status_code == 200
    status = response.json()["whatsapp_billing_delivery"]
    assert status["requested_enabled"] is True
    assert status["effective_enabled"] is True
    assert status["can_enable"] is True
    audit = db_session.query(ActivityLog).filter_by(action="update_settings").order_by(ActivityLog.id.desc()).first()
    assert audit.details["whatsapp_billing_requested_enabled"] == {
        "old": False,
        "new": True,
        "effective": True,
        "blocking_reasons": [],
    }


def test_admin_can_disable_whatsapp_when_provider_is_unavailable(client, db_session):
    db_session.add(AppSetting(
        key=app_settings_service.KEY_BILLING_WHATSAPP_DELIVERY_ENABLED,
        value="true",
    ))
    db_session.commit()

    response = client.put(
        "/api/admin/settings",
        json={"whatsapp_billing_requested_enabled": False},
    )

    assert response.status_code == 200
    status = response.json()["whatsapp_billing_delivery"]
    assert status["requested_enabled"] is False
    assert status["effective_enabled"] is False
