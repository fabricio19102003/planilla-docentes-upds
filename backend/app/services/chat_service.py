"""Shared inbox between docentes and Administración, with private attachments."""
from __future__ import annotations

import logging
import re
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote

from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.chat import ChatAttachment, ChatConversation, ChatMessage
from app.models.teacher import Teacher
from app.models.user import User
from app.services.activity_logger import log_activity
from app.schemas.chat import (
    ChatAttachmentResponse,
    ChatConversationResponse,
    ChatConversationSummary,
    ChatLastMessage,
    ChatMessageResponse,
)

logger = logging.getLogger(__name__)

MAX_BODY_LENGTH = 4000
MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
# Keeps a full multipart request under the 25 MB nginx client_max_body_size.
MAX_MESSAGE_ATTACHMENT_BYTES = 20 * 1024 * 1024
PREVIEW_LENGTH = 120
DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500
STAFF_NAME = "Administración"

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
INLINE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def attachments_dir() -> Path:
    directory = Path(settings.CHAT_ATTACHMENTS_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def detect_content_type(content: bytes) -> Optional[str]:
    """Identify the file by its magic bytes; the client-declared type is never trusted."""
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def sanitize_filename(name: Optional[str], content_type: str) -> str:
    """Reduce a client-supplied name to a harmless display name."""
    extension = ALLOWED_CONTENT_TYPES[content_type]
    base = re.split(r"[\\/]", unicodedata.normalize("NFC", name or ""))[-1]
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C")
    base = re.sub(r"[^\w .()-]", "_", base).strip(" .")
    base = re.sub(r"\.{2,}", ".", base)
    if not base or base.lower() == extension.lstrip("."):
        base = "adjunto" + extension
    if len(base) > 100:
        stem, dot, suffix = base.rpartition(".")
        base = (stem[: 100 - len(suffix) - 1] + dot + suffix) if dot else base[:100]
    return base


def content_disposition(filename: str, content_type: str) -> str:
    kind = "inline" if content_type in INLINE_CONTENT_TYPES else "attachment"
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^\w .()-]", "_", ascii_name) or "adjunto"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"


@dataclass
class PreparedAttachment:
    content: bytes
    content_type: str
    original_filename: str


def prepare_message(body: Optional[str], uploads: Iterable[UploadFile]) -> tuple[str, list[PreparedAttachment]]:
    """Validate text and files before anything is stored. Raises 4xx with Spanish details."""
    text = (body or "").strip()
    if len(text) > MAX_BODY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El mensaje no puede superar los {MAX_BODY_LENGTH} caracteres",
        )
    files = [upload for upload in uploads if upload.filename]
    if len(files) > MAX_ATTACHMENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Solo se permiten hasta {MAX_ATTACHMENTS} archivos por mensaje",
        )
    if not text and not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Escribe un mensaje o adjunta un archivo",
        )

    prepared: list[PreparedAttachment] = []
    total_bytes = 0
    for upload in files:
        content = upload.file.read(MAX_ATTACHMENT_BYTES + 1)
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo supera el máximo de {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB",
            )
        total_bytes += len(content)
        if total_bytes > MAX_MESSAGE_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "Los archivos de un mensaje no pueden superar "
                    f"{MAX_MESSAGE_ATTACHMENT_BYTES // (1024 * 1024)} MB en total"
                ),
            )
        detected = detect_content_type(content)
        declared = (upload.content_type or "").split(";")[0].strip().lower()
        if declared == "image/jpg":
            declared = "image/jpeg"
        if detected is None or declared != detected:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Solo se permiten archivos PDF, JPEG, PNG o WEBP válidos",
            )
        prepared.append(
            PreparedAttachment(
                content=content,
                content_type=detected,
                original_filename=sanitize_filename(upload.filename, detected),
            )
        )
    return text, prepared


def get_or_create_conversation(db: Session, teacher_ci: str) -> ChatConversation:
    conversation = db.query(ChatConversation).filter(ChatConversation.teacher_ci == teacher_ci).first()
    if conversation is not None:
        return conversation
    try:
        with db.begin_nested():
            conversation = ChatConversation(teacher_ci=teacher_ci)
            db.add(conversation)
            db.flush()
    except IntegrityError:
        # A concurrent request created it first.
        conversation = db.query(ChatConversation).filter(ChatConversation.teacher_ci == teacher_ci).one()
    db.commit()
    return conversation


def start_conversation(db: Session, teacher_ci: str) -> ChatConversation:
    """The teacher's single conversation for an admin to open, created lazily."""
    if db.get(Teacher, teacher_ci) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Docente no encontrado")
    has_portal_user = (
        db.query(User.id).filter(User.role == "docente", User.teacher_ci == teacher_ci).first() is not None
    )
    if not has_portal_user:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Este docente no tiene una cuenta en el portal, por lo que no podría leer el mensaje",
        )
    return get_or_create_conversation(db, teacher_ci)


def get_conversation(db: Session, conversation_id: int) -> ChatConversation:
    conversation = db.get(ChatConversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada")
    return conversation


def send_message(
    db: Session,
    conversation: ChatConversation,
    sender: User,
    sender_role: str,
    body: str,
    attachments: list[PreparedAttachment],
    request: Optional[Request] = None,
) -> ChatMessage:
    """Store files, then the message and its audit entry; remove the files if the write fails."""
    directory = attachments_dir()
    written: list[Path] = []
    try:
        now = _utcnow()
        message = ChatMessage(
            conversation_id=conversation.id,
            sender_user_id=sender.id,
            sender_role=sender_role,
            body=body,
            created_at=now,
        )
        for item in attachments:
            stored = f"{secrets.token_hex(16)}{ALLOWED_CONTENT_TYPES[item.content_type]}"
            path = directory / stored
            with open(path, "xb") as handle:
                written.append(path)
                handle.write(item.content)
            message.attachments.append(
                ChatAttachment(
                    stored_filename=stored,
                    original_filename=item.original_filename,
                    content_type=item.content_type,
                    size_bytes=len(item.content),
                    created_at=now,
                )
            )
        db.add(message)
        conversation.last_message_at = now
        db.flush()
        log_activity(
            db,
            action="chat_message_sent",
            category="chat",
            description=f"Mensaje de chat enviado en la conversación {conversation.id}",
            user=sender,
            details={
                "conversation_id": conversation.id,
                "message_id": message.id,
                "teacher_ci": conversation.teacher_ci,
                "attachments": len(attachments),
            },
            request=request,
        )
        db.commit()
        return message
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise


def resolve_attachment_path(attachment: ChatAttachment) -> Optional[Path]:
    name = attachment.stored_filename
    if not name or Path(name).name != name:
        return None
    path = Path(settings.CHAT_ATTACHMENTS_DIR) / name
    return path if path.is_file() else None


# ── Reading ──────────────────────────────────────────────────────────────────


def _unread_filter(side: str):
    """Messages from the other side above this side's read marker."""
    if side == "admin":
        return (
            ChatMessage.sender_role == "docente",
            ChatMessage.id > func.coalesce(ChatConversation.admin_last_read_message_id, 0),
        )
    return (
        ChatMessage.sender_role == "admin",
        ChatMessage.id > func.coalesce(ChatConversation.docente_last_read_message_id, 0),
    )


def unread_count(db: Session, conversation: ChatConversation, side: str) -> int:
    return (
        db.query(func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
        .filter(ChatMessage.conversation_id == conversation.id, *_unread_filter(side))
        .scalar()
        or 0
    )


def total_admin_unread(db: Session) -> int:
    return (
        db.query(func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
        .filter(*_unread_filter("admin"))
        .scalar()
        or 0
    )


def mark_read(db: Session, conversation: ChatConversation, side: str) -> int:
    latest = db.query(func.max(ChatMessage.id)).filter(ChatMessage.conversation_id == conversation.id).scalar()
    column = "admin_last_read_message_id" if side == "admin" else "docente_last_read_message_id"
    current = getattr(conversation, column) or 0
    if latest is not None and latest > current:
        setattr(conversation, column, latest)
        db.commit()
    return unread_count(db, conversation, side)


def list_messages(
    db: Session,
    conversation: ChatConversation,
    after: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    before: Optional[int] = None,
) -> tuple[list[ChatMessage], bool]:
    """One page oldest first, plus whether older messages exist beyond it.

    `after` polls newer messages (never reports older ones); otherwise the latest page, or the
    page right before the `before` cursor.
    """
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    query = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id)
    if after > 0:
        return query.filter(ChatMessage.id > after).order_by(ChatMessage.id.asc()).limit(limit).all(), False
    if before is not None:
        query = query.filter(ChatMessage.id < before)
    # Fetch one extra row to learn whether anything older remains.
    rows = query.order_by(ChatMessage.id.desc()).limit(limit + 1).all()
    return list(reversed(rows[:limit])), len(rows) > limit


# ── Serialization ────────────────────────────────────────────────────────────


def serialize_message(message: ChatMessage, viewer_role: str) -> ChatMessageResponse:
    if message.sender_role == "admin":
        # Docentes talk to Administración, not to an individual admin.
        name = STAFF_NAME if viewer_role == "docente" or message.sender is None else message.sender.full_name
    else:
        name = message.sender.full_name if message.sender else None
    return ChatMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_user_id=message.sender_user_id,
        sender_role=message.sender_role,
        sender_name=name,
        body=message.body,
        created_at=message.created_at,
        attachments=[
            ChatAttachmentResponse(
                id=a.id, filename=a.original_filename, content_type=a.content_type, size_bytes=a.size_bytes
            )
            for a in message.attachments
        ],
    )


def serialize_conversation(db: Session, conversation: ChatConversation, side: str) -> ChatConversationResponse:
    teacher = db.get(Teacher, conversation.teacher_ci)
    return ChatConversationResponse(
        id=conversation.id,
        teacher_ci=conversation.teacher_ci,
        teacher_name=teacher.full_name if teacher else None,
        unread_count=unread_count(db, conversation, side),
        last_message_at=conversation.last_message_at,
    )


def _preview(message: ChatMessage) -> str:
    text = " ".join(message.body.split())
    if not text and message.attachments:
        text = "📎 " + message.attachments[0].original_filename
    return text if len(text) <= PREVIEW_LENGTH else text[: PREVIEW_LENGTH - 1] + "…"


def list_conversation_summaries(db: Session, q: Optional[str] = None) -> list[ChatConversationSummary]:
    """Conversations that have messages, most recently active first."""
    query = (
        db.query(ChatConversation, Teacher.full_name)
        .join(Teacher, Teacher.ci == ChatConversation.teacher_ci)
        .filter(ChatConversation.last_message_at.is_not(None))
    )
    term = (q or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(or_(Teacher.full_name.ilike(pattern), ChatConversation.teacher_ci.ilike(pattern)))
    rows = query.order_by(ChatConversation.last_message_at.desc(), ChatConversation.id.desc()).all()
    ids = [conversation.id for conversation, _ in rows]
    if not ids:
        return []
    # Two grouped queries instead of two per conversation: this list is polled.
    unread = dict(
        db.query(ChatMessage.conversation_id, func.count(ChatMessage.id))
        .select_from(ChatMessage)
        .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
        .filter(ChatMessage.conversation_id.in_(ids), *_unread_filter("admin"))
        .group_by(ChatMessage.conversation_id)
        .all()
    )
    latest_ids = (
        db.query(func.max(ChatMessage.id)).filter(ChatMessage.conversation_id.in_(ids)).group_by(ChatMessage.conversation_id)
    )
    last_by_conversation = {
        m.conversation_id: m for m in db.query(ChatMessage).filter(ChatMessage.id.in_(latest_ids)).all()
    }
    summaries = []
    for conversation, teacher_name in rows:
        last = last_by_conversation.get(conversation.id)
        summaries.append(
            ChatConversationSummary(
                id=conversation.id,
                teacher_ci=conversation.teacher_ci,
                teacher_name=teacher_name,
                unread_count=unread.get(conversation.id, 0),
                last_message_at=conversation.last_message_at,
                last_message=ChatLastMessage(
                    preview=_preview(last), sender_role=last.sender_role, created_at=last.created_at
                )
                if last
                else None,
            )
        )
    return summaries
