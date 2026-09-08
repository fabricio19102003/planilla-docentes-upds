from __future__ import annotations

from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service
from app.services import teacher_photo_service


PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 16
WEBP_BYTES = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 8


def test_admin_upload_replace_and_delete_teacher_photo(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    teacher = Teacher(ci="PHOTO-1", full_name="Foto Docente")
    db_session.add(teacher)
    db_session.commit()

    upload_response = client.put(
        "/api/teachers/PHOTO-1/photo",
        files={"file": ("avatar.png", PNG_BYTES, "image/png")},
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    first_url = upload_payload["avatar_url"]
    assert first_url.startswith("/uploads/teacher-photos/")
    first_filename = first_url.rsplit("/", 1)[-1]
    assert (tmp_path / "teacher-photos" / first_filename).exists()

    replace_response = client.put(
        "/api/teachers/PHOTO-1/photo",
        files={"file": ("avatar.webp", WEBP_BYTES, "image/webp")},
    )

    assert replace_response.status_code == 200
    second_url = replace_response.json()["avatar_url"]
    second_filename = second_url.rsplit("/", 1)[-1]
    assert second_filename.endswith(".webp")
    assert second_filename != first_filename
    assert (tmp_path / "teacher-photos" / second_filename).exists()
    assert not (tmp_path / "teacher-photos" / first_filename).exists()

    delete_response = client.delete("/api/teachers/PHOTO-1/photo")

    assert delete_response.status_code == 200
    assert delete_response.json()["avatar_url"] is None
    assert not (tmp_path / "teacher-photos" / second_filename).exists()


def test_admin_photo_upload_rejects_invalid_type_without_mutating(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    teacher = Teacher(ci="PHOTO-2", full_name="Foto Dos")
    db_session.add(teacher)
    db_session.commit()

    response = client.put(
        "/api/teachers/PHOTO-2/photo",
        files={"file": ("avatar.gif", b"gif-bytes", "image/gif")},
    )

    assert response.status_code == 400
    db_session.refresh(teacher)
    assert teacher.photo_filename is None


def test_admin_download_teacher_photo_returns_stored_file(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    photo_dir = tmp_path / "teacher-photos"
    photo_dir.mkdir()
    (photo_dir / "stored.png").write_bytes(PNG_BYTES)
    teacher = Teacher(
        ci="PHOTO-DOWNLOAD",
        full_name="Foto Descargable",
        photo_filename="stored.png",
        photo_content_type="image/png",
    )
    db_session.add(teacher)
    db_session.commit()

    response = client.get("/api/teachers/PHOTO-DOWNLOAD/photo/download")

    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["content-type"].startswith("image/png")
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_admin_download_teacher_photo_rejects_non_basename(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    teacher = Teacher(
        ci="PHOTO-PATH",
        full_name="Foto Path",
        photo_filename="../secret.png",
        photo_content_type="image/png",
    )
    db_session.add(teacher)
    db_session.commit()

    response = client.get("/api/teachers/PHOTO-PATH/photo/download")

    assert response.status_code == 404


def test_teacher_cannot_use_admin_photo_download(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    photo_dir = tmp_path / "teacher-photos"
    photo_dir.mkdir()
    (photo_dir / "stored.png").write_bytes(PNG_BYTES)
    teacher = Teacher(ci="PHOTO-PRIVATE", full_name="Private Photo", photo_filename="stored.png")
    user = User(
        ci="PHOTO-PRIVATE",
        full_name="Private Photo",
        password_hash="unused",
        role="docente",
        teacher_ci=teacher.ci,
        is_active=True,
    )
    db_session.add_all([teacher, user])
    db_session.commit()
    token = auth_service.create_access_token({"sub": str(user.id), "role": "docente"})

    response = client.get(
        "/api/teachers/PHOTO-PRIVATE/photo/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_admin_photo_upload_rejects_oversized_without_mutating(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    teacher = Teacher(ci="PHOTO-3", full_name="Foto Tres")
    db_session.add(teacher)
    db_session.commit()

    response = client.put(
        "/api/teachers/PHOTO-3/photo",
        files={"file": ("avatar.jpg", b"x" * (teacher_photo_service.MAX_PHOTO_BYTES + 1), "image/jpeg")},
    )

    assert response.status_code == 400
    db_session.refresh(teacher)
    assert teacher.photo_filename is None
