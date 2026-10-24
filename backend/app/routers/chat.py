from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat import ChatAttachment, ChatConversation, ChatMessage
from app.models.user import User
from app.schemas.chat import (
    ChatConversationSummary,
    ChatMessageResponse,
    ChatThreadResponse,
    ChatUnreadCount,
)
from app.services import chat_service
from app.utils.auth import get_current_user, require_admin, require_docente

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _own_conversation(db: Session, user: User) -> ChatConversation:
    if not user.teacher_ci:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu cuenta de docente no tiene un docente vinculado",
        )
    return chat_service.get_or_create_conversation(db, user.teacher_ci)


def _thread(
    db: Session, conversation: ChatConversation, side: str, after: int, limit: int
) -> ChatThreadResponse:
    messages = chat_service.list_messages(db, conversation, after=after, limit=limit)
    return ChatThreadResponse(
        conversation=chat_service.serialize_conversation(db, conversation, side),
        messages=[chat_service.serialize_message(m, side) for m in messages],
    )


def _send(
    db: Session,
    request: Request,
    conversation: ChatConversation,
    user: User,
    side: str,
    body: Optional[str],
    files: list[UploadFile],
) -> ChatMessageResponse:
    text, prepared = chat_service.prepare_message(body, files)
    message = chat_service.send_message(db, conversation, user, side, text, prepared, request=request)
    return chat_service.serialize_message(message, side)


# ------------------------------------------------------------------
# Docente endpoints (own conversation only)
# ------------------------------------------------------------------


@router.get("/me", response_model=ChatThreadResponse)
def get_my_conversation(
    after: int = Query(0, ge=0, description="Devuelve solo mensajes con id mayor a este"),
    limit: int = Query(chat_service.DEFAULT_PAGE_SIZE, ge=1, le=chat_service.MAX_PAGE_SIZE),
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> ChatThreadResponse:
    conversation = _own_conversation(db, current_user)
    return _thread(db, conversation, "docente", after, limit)


@router.post("/me/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
def send_my_message(
    request: Request,
    body: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    conversation = _own_conversation(db, current_user)
    return _send(db, request, conversation, current_user, "docente", body, files)


@router.post("/me/read", response_model=ChatUnreadCount)
def mark_my_conversation_read(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> ChatUnreadCount:
    conversation = _own_conversation(db, current_user)
    return ChatUnreadCount(unread_count=chat_service.mark_read(db, conversation, "docente"))


@router.get("/me/unread-count", response_model=ChatUnreadCount)
def get_my_unread_count(
    current_user: User = Depends(require_docente),
    db: Session = Depends(get_db),
) -> ChatUnreadCount:
    conversation = _own_conversation(db, current_user)
    return ChatUnreadCount(unread_count=chat_service.unread_count(db, conversation, "docente"))


# ------------------------------------------------------------------
# Admin endpoints (shared inbox)
# ------------------------------------------------------------------


@router.get("/conversations", response_model=list[ChatConversationSummary])
def list_conversations(
    q: Optional[str] = Query(None, max_length=100, description="Busca por nombre o CI del docente"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ChatConversationSummary]:
    return chat_service.list_conversation_summaries(db, q)


@router.get("/unread-count", response_model=ChatUnreadCount)
def get_admin_unread_count(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ChatUnreadCount:
    return ChatUnreadCount(unread_count=chat_service.total_admin_unread(db))


@router.get("/conversations/{conversation_id}/messages", response_model=ChatThreadResponse)
def get_conversation_messages(
    conversation_id: int,
    after: int = Query(0, ge=0, description="Devuelve solo mensajes con id mayor a este"),
    limit: int = Query(chat_service.DEFAULT_PAGE_SIZE, ge=1, le=chat_service.MAX_PAGE_SIZE),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ChatThreadResponse:
    conversation = chat_service.get_conversation(db, conversation_id)
    return _thread(db, conversation, "admin", after, limit)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def reply_to_conversation(
    conversation_id: int,
    request: Request,
    body: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    conversation = chat_service.get_conversation(db, conversation_id)
    return _send(db, request, conversation, current_user, "admin", body, files)


@router.post("/conversations/{conversation_id}/read", response_model=ChatUnreadCount)
def mark_conversation_read(
    conversation_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ChatUnreadCount:
    conversation = chat_service.get_conversation(db, conversation_id)
    return ChatUnreadCount(unread_count=chat_service.mark_read(db, conversation, "admin"))


# ------------------------------------------------------------------
# Attachments (both roles, authorized per conversation)
# ------------------------------------------------------------------


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    not_found = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado")
    row = (
        db.query(ChatAttachment, ChatConversation.teacher_ci)
        .join(ChatMessage, ChatMessage.id == ChatAttachment.message_id)
        .join(ChatConversation, ChatConversation.id == ChatMessage.conversation_id)
        .filter(ChatAttachment.id == attachment_id)
        .first()
    )
    if row is None:
        raise not_found
    attachment, teacher_ci = row
    if current_user.role == "docente":
        if not current_user.teacher_ci or current_user.teacher_ci != teacher_ci:
            # Same answer as a missing file so other conversations are not probeable.
            raise not_found
    elif current_user.role != "admin":
        raise not_found
    path = chat_service.resolve_attachment_path(attachment)
    if path is None:
        logger.warning("Chat attachment %s is missing on disk", attachment.id)
        raise not_found
    return FileResponse(
        path,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": chat_service.content_disposition(
                attachment.original_filename, attachment.content_type
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
