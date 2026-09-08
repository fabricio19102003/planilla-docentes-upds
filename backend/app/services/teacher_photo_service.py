from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status

from app.config import settings
from app.models.teacher import Teacher

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}
MAX_PHOTO_BYTES = 2 * 1024 * 1024
TEACHER_PHOTOS_DIR_NAME = "teacher-photos"
TEACHER_PHOTOS_URL_PREFIX = "/uploads/teacher-photos"


def get_teacher_photos_dir() -> Path:
    return Path(settings.UPLOAD_DIR) / TEACHER_PHOTOS_DIR_NAME


def ensure_teacher_photos_dir() -> Path:
    directory = get_teacher_photos_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_avatar_url(filename: str | None) -> str | None:
    if not filename:
        return None
    return f"{TEACHER_PHOTOS_URL_PREFIX}/{filename}"


def _validate_upload_metadata(file: UploadFile) -> tuple[str, str]:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    content_type = file.content_type or ""

    if content_type not in ALLOWED_CONTENT_TYPES or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de imagen no permitido. Use JPG, PNG o WebP.",
        )

    return extension, content_type


def _read_limited(file_obj: BinaryIO) -> bytes:
    content = file_obj.read(MAX_PHOTO_BYTES + 1)
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen supera el tamaño máximo permitido de 2 MiB.",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La imagen está vacía.")
    return content


def _detect_image_content_type(content: bytes) -> str | None:
    if len(content) >= 24 and content.startswith(b"\x89PNG\r\n\x1a\n") and content[12:16] == b"IHDR":
        return "image/png"
    if len(content) >= 4 and content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9"):
        return "image/jpeg"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def save_upload_file(file: UploadFile) -> tuple[str, str]:
    extension, content_type = _validate_upload_metadata(file)
    content = _read_limited(file.file)
    detected_content_type = _detect_image_content_type(content)
    if (
        detected_content_type != content_type
        or extension not in CONTENT_TYPE_EXTENSIONS.get(detected_content_type or "", set())
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contenido del archivo no coincide con un formato de imagen permitido.",
        )

    directory = ensure_teacher_photos_dir()
    filename = f"{uuid.uuid4().hex}{extension}"
    destination = directory / filename
    destination.write_bytes(content)
    return filename, content_type


def resolve_teacher_photo_path(filename: str | None) -> Path | None:
    """Resolve only a stored basename inside the configured teacher-photo directory."""
    if (
        not filename
        or Path(filename).name != filename
        or "\\" in filename
        or Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS
    ):
        return None
    directory = get_teacher_photos_dir().resolve()
    candidate = (directory / filename).resolve()
    if candidate.parent != directory or not candidate.is_file():
        return None
    return candidate


def apply_photo_metadata(teacher: Teacher, filename: str, content_type: str) -> str | None:
    old_filename = teacher.photo_filename
    teacher.photo_filename = filename
    teacher.photo_content_type = content_type
    teacher.photo_updated_at = datetime.utcnow()
    return old_filename


def clear_photo_metadata(teacher: Teacher) -> str | None:
    old_filename = teacher.photo_filename
    teacher.photo_filename = None
    teacher.photo_content_type = None
    teacher.photo_updated_at = None
    return old_filename


def delete_photo_file(filename: str | None) -> None:
    if not filename:
        return
    try:
        path = get_teacher_photos_dir() / filename
        if path.exists() and path.is_file():
            path.unlink()
    except Exception as exc:  # pragma: no cover - best-effort cleanup must not break API success
        logger.warning("Could not delete teacher photo %s: %s", filename, exc)
