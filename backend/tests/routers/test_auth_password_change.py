from __future__ import annotations

from app.models.user import User
from app.services.auth_service import auth_service


CURRENT_PASSWORD = "CurrentPass1"
NEW_PASSWORD = "DifferentPass2"


def _prepare_forced_change(client, db_session) -> User:
    user = db_session.query(User).filter(User.ci == "TEST_ADMIN_9999").one()
    user.password_hash = auth_service.hash_password(CURRENT_PASSWORD)
    user.must_change_password = True
    db_session.commit()
    return user


def test_change_password_rejects_current_password_reuse(client, db_session):
    user = _prepare_forced_change(client, db_session)
    previous_hash = user.password_hash

    response = client.put(
        "/api/auth/change-password",
        json={"current_password": CURRENT_PASSWORD, "new_password": CURRENT_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "La nueva contraseña debe ser diferente de la contraseña actual"
    db_session.refresh(user)
    assert user.password_hash == previous_hash
    assert user.must_change_password is True


def test_change_password_accepts_strong_distinct_password_and_clears_forced_flag(client, db_session):
    user = _prepare_forced_change(client, db_session)

    response = client.put(
        "/api/auth/change-password",
        json={"current_password": CURRENT_PASSWORD, "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["must_change_password"] is False
    db_session.refresh(user)
    assert auth_service.verify_password(NEW_PASSWORD, user.password_hash)
    assert not auth_service.verify_password(CURRENT_PASSWORD, user.password_hash)
    assert user.must_change_password is False
