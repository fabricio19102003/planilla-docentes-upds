from __future__ import annotations

from app.models.teacher import Teacher
from app.services import teacher_photo_service


def test_admin_upload_replace_and_delete_teacher_photo(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    teacher = Teacher(ci="PHOTO-1", full_name="Foto Docente")
    db_session.add(teacher)
    db_session.commit()

    upload_response = client.put(
        "/api/teachers/PHOTO-1/photo",
        files={"file": ("avatar.png", b"first-image", "image/png")},
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    first_url = upload_payload["avatar_url"]
    assert first_url.startswith("/uploads/teacher-photos/")
    first_filename = first_url.rsplit("/", 1)[-1]
    assert (tmp_path / "teacher-photos" / first_filename).exists()

    replace_response = client.put(
        "/api/teachers/PHOTO-1/photo",
        files={"file": ("avatar.webp", b"second-image", "image/webp")},
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
