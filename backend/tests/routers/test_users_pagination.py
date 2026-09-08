from __future__ import annotations

from app.models.user import User


def _add_user(db_session, **overrides) -> User:
    values = {
        "ci": "USER-1",
        "full_name": "User One",
        "email": None,
        "password_hash": "unused",
        "role": "docente",
        "teacher_ci": None,
        "is_active": True,
    }
    values.update(overrides)
    user = User(**values)
    db_session.add(user)
    db_session.flush()
    return user


def test_list_users_paginates_filters_and_returns_global_summary(client, db_session):
    _add_user(db_session, ci="DOC-002", full_name="Zulu Docente", email="zulu@example.test")
    _add_user(db_session, ci="DOC-001", full_name="Alpha Docente", email="alpha@example.test", is_active=False)
    _add_user(db_session, ci="ADM-001", full_name="Beta Admin", role="admin")
    db_session.commit()

    response = client.get(
        "/api/users",
        params={"search": "docente", "role": "docente", "active": "true", "page": 1, "per_page": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["ci"] for item in payload["items"]] == ["DOC-002"]
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["per_page"] == 1
    # Includes the fixture admin and ignores filters/page.
    assert payload["summary"] == {"total": 4, "admins": 2, "docentes": 2, "active": 3}


def test_list_users_uses_stable_name_then_id_order(client, db_session):
    first = _add_user(db_session, ci="ORDER-1", full_name="Same Name")
    second = _add_user(db_session, ci="ORDER-2", full_name="Same Name")
    db_session.commit()

    response = client.get("/api/users", params={"search": "Same Name", "per_page": 10})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [first.id, second.id]


def test_list_users_rejects_invalid_filters(client):
    assert client.get("/api/users", params={"role": "owner"}).status_code == 422
    assert client.get("/api/users", params={"active": "sometimes"}).status_code == 422
