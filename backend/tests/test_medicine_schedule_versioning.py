from app.database import Base
from app.main import app
from app.routers.medicine_schedules import router
from app.services import app_settings_service


MEDICINE_TABLES = {
    "medicine_schedule_versions", "medicine_offerings", "medicine_meetings",
    "medicine_import_issues", "medicine_corrections", "medicine_version_events",
    "medicine_simulations",
}


def test_medicine_models_are_registered_and_isolated():
    assert MEDICINE_TABLES <= set(Base.metadata.tables)
    foreign_tables = {
        foreign_key.column.table.name
        for name in MEDICINE_TABLES
        for foreign_key in Base.metadata.tables[name].foreign_keys
    }
    assert foreign_tables <= MEDICINE_TABLES | {"users"}


def test_feature_is_default_disabled_and_registered(client, db_session):
    app_settings_service.invalidate_cache()
    assert app_settings_service.get_medicine_schedule_assistant_enabled(db_session) is False
    assert router.prefix == "/api/medicine-schedules"
    assert any(route.path == "/api/medicine-schedules/status" for route in app.routes)
    assert client.get("/api/medicine-schedules/status").status_code == 404
    settings = client.get("/api/admin/settings")
    assert settings.status_code == 200
    assert settings.json()["medicine_schedule_assistant_enabled"] is False
    assert client.put("/api/admin/settings", json={"medicine_schedule_assistant_enabled": True}).json()["medicine_schedule_assistant_enabled"] is True
    assert client.get("/api/medicine-schedules/status").json() == {"enabled": True}
