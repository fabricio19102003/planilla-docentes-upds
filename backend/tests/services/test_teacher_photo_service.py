from __future__ import annotations

import io

import pytest
from fastapi import HTTPException, UploadFile

from app.models.teacher import Teacher
from app.services import teacher_photo_service


def make_upload(filename: str, content_type: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content), headers={"content-type": content_type})


def test_save_upload_file_validates_and_uses_uuid_filename(monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    upload = make_upload("avatar.png", "image/png", b"png-bytes")

    filename, content_type = teacher_photo_service.save_upload_file(upload)

    assert filename.endswith(".png")
    assert filename != "avatar.png"
    assert content_type == "image/png"
    assert (tmp_path / "teacher-photos" / filename).read_bytes() == b"png-bytes"


def test_save_upload_file_rejects_invalid_content_type(monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    upload = make_upload("avatar.svg", "image/svg+xml", b"<svg></svg>")

    with pytest.raises(HTTPException) as exc_info:
        teacher_photo_service.save_upload_file(upload)

    assert exc_info.value.status_code == 400
    assert not (tmp_path / "teacher-photos").exists()


def test_save_upload_file_rejects_oversized_file(monkeypatch, tmp_path):
    monkeypatch.setattr(teacher_photo_service.settings, "UPLOAD_DIR", str(tmp_path))
    upload = make_upload("avatar.jpg", "image/jpeg", b"x" * (teacher_photo_service.MAX_PHOTO_BYTES + 1))

    with pytest.raises(HTTPException) as exc_info:
        teacher_photo_service.save_upload_file(upload)

    assert exc_info.value.status_code == 400


def test_apply_and_clear_photo_metadata():
    teacher = Teacher(ci="123", full_name="Docente", photo_filename="old.png")

    old_filename = teacher_photo_service.apply_photo_metadata(teacher, "new.webp", "image/webp")

    assert old_filename == "old.png"
    assert teacher.photo_filename == "new.webp"
    assert teacher.photo_content_type == "image/webp"
    assert teacher.photo_updated_at is not None
    assert teacher.avatar_url == "/uploads/teacher-photos/new.webp"

    cleared_filename = teacher_photo_service.clear_photo_metadata(teacher)

    assert cleared_filename == "new.webp"
    assert teacher.photo_filename is None
    assert teacher.photo_content_type is None
    assert teacher.photo_updated_at is None
    assert teacher.avatar_url is None
