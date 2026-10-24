from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatAttachmentResponse(BaseModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int


class ChatMessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_user_id: Optional[int] = None
    sender_role: Literal["admin", "docente"]
    sender_name: Optional[str] = None
    body: str
    created_at: datetime
    attachments: list[ChatAttachmentResponse] = []


class ChatConversationResponse(BaseModel):
    id: int
    teacher_ci: str
    teacher_name: Optional[str] = None
    unread_count: int = 0
    last_message_at: Optional[datetime] = None


class ChatThreadResponse(BaseModel):
    conversation: ChatConversationResponse
    messages: list[ChatMessageResponse]
    # True when messages older than the first one returned exist; always false for `after` polls.
    has_more: bool = False


class ChatStartRequest(BaseModel):
    teacher_ci: str = Field(min_length=1, max_length=20)


class ChatLastMessage(BaseModel):
    preview: str
    sender_role: Literal["admin", "docente"]
    created_at: datetime


class ChatConversationSummary(ChatConversationResponse):
    last_message: Optional[ChatLastMessage] = None


class ChatUnreadCount(BaseModel):
    unread_count: int
