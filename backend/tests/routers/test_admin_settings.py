from __future__ import annotations

from app.models.app_setting import AppSetting
from app.services import app_settings_service


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
    app_settings_service.invalidate_cache()

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
