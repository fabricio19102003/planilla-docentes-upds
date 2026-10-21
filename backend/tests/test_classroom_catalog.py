from __future__ import annotations

from app.models.activity_log import ActivityLog
from app.models.academic_management import Classroom

URL = "/api/admin/academic-management/classroom-catalog"


def _rooms(db):
    db.expire_all()
    return {
        room.code: (room.name, room.campus, room.capacity, room.classroom_type, room.active)
        for room in db.query(Classroom).all()
    }


def test_preview_lists_the_official_catalog_and_writes_nothing(client, db_session):
    response = client.post(f"{URL}/preview")

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["create"]) == 31
    assert data["update"] == []
    assert data["unchanged"] == 0
    assert data["conflicts"] == []
    by_code = {item["code"]: item for item in data["create"]}
    assert by_code["COB-ANTIGUO-P1-A1"] == {
        "code": "COB-ANTIGUO-P1-A1", "name": "Antiguo / Piso 1 / Aula 1",
        "building": "ANTIGUO", "floor": 1, "room": "1", "capacity": 54,
    }
    assert by_code["COB-ANTIGUO-P2-A10"]["capacity"] == 54
    assert by_code["COB-ANTIGUO-P1-AA"]["capacity"] == 20
    assert by_code["COB-ANTIGUO-P1-AB"]["name"] == "Antiguo / Piso 1 / Aula B"
    assert by_code["COB-NUEVO-P2-A17"]["capacity"] == 20
    assert by_code["COB-NUEVO-P3-A20"]["capacity"] == 52
    assert by_code["COB-NUEVO-P4-A29"]["capacity"] == 45
    assert _rooms(db_session) == {}


def test_apply_creates_missing_rooms_updates_capacity_and_reports_other_codes(client, db_session):
    db_session.add_all([
        Classroom(code="COB-NUEVO-P3-A19", name="Nuevo / Piso 3 / Aula 19", campus="Cobija",
                  capacity=40, classroom_type="classroom", resources=[], active=True),
        Classroom(code="COB-NUEVO-P2-A12", name="Nuevo / Piso 2 / Aula 12", campus="Cobija",
                  capacity=50, classroom_type="classroom", resources=["proyector"], active=True),
        # Same room number with another building/floor: reported, never changed.
        Classroom(code="COB-ANTIGUO-P3-A20", name="Antiguo / Piso 3 / Aula 20", campus="Cobija",
                  capacity=52, classroom_type="classroom", resources=[], active=True),
        Classroom(code="FIELD", name="Sin aula / campo asistencial", campus="Cobija",
                  capacity=None, classroom_type="other", resources=[], active=True),
    ])
    db_session.flush()

    preview = client.post(f"{URL}/preview").json()
    assert len(preview["create"]) == 29
    assert preview["update"] == [{
        "code": "COB-NUEVO-P3-A19", "changes": {"capacity": [40, 51]},
    }]
    assert preview["unchanged"] == 1
    assert preview["conflicts"] == [{
        "code": "COB-ANTIGUO-P3-A20", "room": "20", "catalog_code": "COB-NUEVO-P3-A20",
    }]

    applied = client.post(f"{URL}/apply")
    assert applied.status_code == 200, applied.text
    assert applied.json() == preview
    rooms = _rooms(db_session)
    assert len(rooms) == 33
    assert rooms["COB-NUEVO-P3-A19"] == ("Nuevo / Piso 3 / Aula 19", "Cobija", 51, "classroom", True)
    assert rooms["COB-NUEVO-P2-A12"][2] == 50
    assert db_session.query(Classroom).filter_by(code="COB-NUEVO-P2-A12").one().resources == ["proyector"]
    assert rooms["COB-ANTIGUO-P3-A20"] == ("Antiguo / Piso 3 / Aula 20", "Cobija", 52, "classroom", True)
    assert rooms["FIELD"][3] == "other"
    assert rooms["COB-ANTIGUO-P1-AA"] == ("Antiguo / Piso 1 / Aula A", "Cobija", 20, "classroom", True)
    log = db_session.query(ActivityLog).filter_by(action="classroom_catalog_sync").one()
    assert log.details["created"] == 29 and log.details["updated"] == ["COB-NUEVO-P3-A19"]

    again = client.post(f"{URL}/preview").json()
    assert again["create"] == [] and again["update"] == [] and again["unchanged"] == 31


def test_apply_reactivates_an_inactive_catalog_room(client, db_session):
    db_session.add(Classroom(code="COB-NUEVO-P4-A24", name="Nuevo / Piso 4 / Aula 24", campus="Cobija",
                             capacity=47, classroom_type="classroom", resources=[], active=False))
    db_session.flush()

    preview = client.post(f"{URL}/preview").json()
    assert preview["update"] == [{"code": "COB-NUEVO-P4-A24", "changes": {"active": [False, True]}}]
    client.post(f"{URL}/apply")
    assert _rooms(db_session)["COB-NUEVO-P4-A24"][4] is True
