from __future__ import annotations

from app.models.teacher import Teacher
from app.models.user import User
from app.routers.docente_portal import _filter_excluded_days_for_teacher
from app.services import app_settings_service, teacher_photo_service
from app.services.auth_service import auth_service


def _set_docente_token(client, db_session, teacher: Teacher) -> User:
    user = User(
        ci=f"USR-{teacher.ci}",
        full_name=teacher.full_name,
        email=teacher.email,
        password_hash=auth_service.hash_password("Testpass123"),
        role="docente",
        teacher_ci=teacher.ci,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    token = auth_service.create_access_token(data={"sub": str(user.id), "role": "docente"})
    client.headers["Authorization"] = f"Bearer {token}"
    return user


def _set_profile_permission(db_session, value: bool) -> None:
    app_settings_service.set_docente_can_edit_profile(db_session, value)
    db_session.commit()
    app_settings_service.invalidate_cache()


def _set_photo_permission(db_session, value: bool) -> None:
    app_settings_service.set_docente_can_edit_photo(db_session, value)
    db_session.commit()
    app_settings_service.invalidate_cache()


def test_admin_settings_expose_and_update_docente_permission_flags(client):
    app_settings_service.invalidate_cache()

    initial = client.get("/api/admin/settings")
    assert initial.status_code == 200
    assert initial.json()["docente_can_edit_profile"] is False
    assert initial.json()["docente_can_edit_photo"] is False

    updated = client.put(
        "/api/admin/settings",
        json={"docente_can_edit_profile": True, "docente_can_edit_photo": True},
    )
    assert updated.status_code == 200
    assert updated.json()["docente_can_edit_profile"] is True
    assert updated.json()["docente_can_edit_photo"] is True


def test_docente_profile_update_is_blocked_when_permission_disabled(client, db_session):
    teacher = Teacher(ci="PERM-PROFILE-1", full_name="Permiso Perfil", email="old@example.com")
    db_session.add(teacher)
    db_session.commit()
    _set_docente_token(client, db_session, teacher)
    _set_profile_permission(db_session, False)

    response = client.put("/api/portal/profile", json={"email": "new@example.com"})

    assert response.status_code == 403
    db_session.refresh(teacher)
    assert teacher.email == "old@example.com"


def test_docente_profile_update_is_allowed_when_permission_enabled(client, db_session):
    teacher = Teacher(ci="PERM-PROFILE-2", full_name="Permiso Perfil Dos", email="old2@example.com")
    db_session.add(teacher)
    db_session.commit()
    user = _set_docente_token(client, db_session, teacher)
    _set_profile_permission(db_session, True)

    response = client.put("/api/portal/profile", json={"email": "new2@example.com", "phone": " 777 "})

    assert response.status_code == 200
    db_session.refresh(teacher)
    db_session.refresh(user)
    assert teacher.email == "new2@example.com"
    assert user.email == "new2@example.com"
    assert teacher.phone == "777"


def test_docente_profile_response_includes_permissions_and_avatar_url(client, db_session):
    teacher = Teacher(
        ci="PERM-PROFILE-3",
        full_name="Avatar Docente",
        photo_filename="avatar-docente.png",
        photo_content_type="image/png",
    )
    db_session.add(teacher)
    db_session.commit()
    _set_docente_token(client, db_session, teacher)
    _set_profile_permission(db_session, True)
    _set_photo_permission(db_session, False)

    response = client.get("/api/portal/profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["avatar_url"] == "/uploads/teacher-photos/avatar-docente.png"
    assert payload["docente_can_edit_profile"] is True
    assert payload["docente_can_edit_photo"] is False


def test_docente_photo_mutations_are_blocked_when_permission_disabled(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    teacher = Teacher(ci="PERM-PHOTO-1", full_name="Permiso Foto")
    db_session.add(teacher)
    db_session.commit()
    _set_docente_token(client, db_session, teacher)
    _set_photo_permission(db_session, False)

    upload = client.put(
        "/api/portal/profile/photo",
        files={"file": ("avatar.png", b"image-bytes", "image/png")},
    )
    delete = client.delete("/api/portal/profile/photo")

    assert upload.status_code == 403
    assert delete.status_code == 403
    db_session.refresh(teacher)
    assert teacher.photo_filename is None
    assert not (tmp_path / "teacher-photos").exists()


def test_docente_photo_upload_replace_and_delete_when_permission_enabled(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    teacher = Teacher(ci="PERM-PHOTO-2", full_name="Permiso Foto Dos")
    db_session.add(teacher)
    db_session.commit()
    _set_docente_token(client, db_session, teacher)
    _set_photo_permission(db_session, True)

    upload = client.put(
        "/api/portal/profile/photo",
        files={"file": ("avatar.jpg", b"first", "image/jpeg")},
    )
    assert upload.status_code == 200
    first_url = upload.json()["avatar_url"]
    first_filename = first_url.rsplit("/", 1)[-1]
    assert (tmp_path / "teacher-photos" / first_filename).exists()

    replace = client.put(
        "/api/portal/profile/photo",
        files={"file": ("avatar.webp", b"second", "image/webp")},
    )
    assert replace.status_code == 200
    second_url = replace.json()["avatar_url"]
    second_filename = second_url.rsplit("/", 1)[-1]
    assert second_filename != first_filename
    assert (tmp_path / "teacher-photos" / second_filename).exists()
    assert not (tmp_path / "teacher-photos" / first_filename).exists()

    delete = client.delete("/api/portal/profile/photo")
    assert delete.status_code == 200
    assert delete.json()["avatar_url"] is None
    assert not (tmp_path / "teacher-photos" / second_filename).exists()


def test_auth_payloads_include_docente_avatar_url(client, db_session):
    teacher = Teacher(
        ci="PERM-AUTH-1",
        full_name="Auth Avatar",
        email="auth-avatar@example.com",
        photo_filename="auth-avatar.png",
        photo_content_type="image/png",
    )
    db_session.add(teacher)
    user = _set_docente_token(client, db_session, teacher)
    user.password_hash = auth_service.hash_password("Testpass123")
    user.ci = "PERM-AUTH-USER-1"
    db_session.commit()

    login = client.post("/api/auth/login", json={"ci": user.ci, "password": "Testpass123"})
    assert login.status_code == 200
    assert login.json()["user"]["avatar_url"] == "/uploads/teacher-photos/auth-avatar.png"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["avatar_url"] == "/uploads/teacher-photos/auth-avatar.png"


def test_docente_billing_excluded_days_are_filtered_and_deduplicated():
    teacher_detail = {
        "designations": [
            {"subject": "Anatomía", "group": "A", "semester": "1"},
        ]
    }
    excluded_days = [
        {"date": "2026-04-21", "scope": "global", "reason": "Feriado institucional"},
        {"date": "2026-04-30", "scope": "semester", "semester_id": "1", "reason": "Clase magistral"},
        {"date": "2026-04-30", "scope": "subject", "subject_id": "Anatomía", "group_id": "A", "reason": "Taller docente"},
        {"date": "2026-05-02", "scope": "semester", "semester_id": "9", "reason": "No aplica"},
        {"date": "2026-05-09", "scope": "subject", "subject_id": "Pediatría", "group_id": "B", "reason": "No aplica"},
    ]

    filtered = _filter_excluded_days_for_teacher(excluded_days, teacher_detail)

    assert [day.model_dump() for day in filtered] == [
        {"date": "2026-04-21", "reason": "Feriado institucional"},
        {"date": "2026-04-30", "reason": "Clase magistral; Taller docente"},
    ]
