from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatConversation(Base):
    """The single inbox thread between one docente and Administración."""

    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20), ForeignKey("teachers.ci", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Highest message id each side has read; unread = counterpart messages above it.
    admin_last_read_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    docente_last_read_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    teacher = relationship("Teacher", foreign_keys=[teacher_ci])

    def __repr__(self) -> str:
        return f"<ChatConversation id={self.id} teacher_ci={self.teacher_ci}>"


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("sender_role IN ('admin', 'docente')", name="ck_chat_message_sender_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sender_role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'admin' | 'docente'
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    sender = relationship("User", foreign_keys=[sender_user_id])
    attachments = relationship(
        "ChatAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="ChatAttachment.id",
    )

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} conversation_id={self.conversation_id}>"


class ChatAttachment(Base):
    __tablename__ = "chat_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Random server-generated name inside CHAT_ATTACHMENTS_DIR; never derived from user input.
    stored_filename: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    message = relationship("ChatMessage", back_populates="attachments")

    def __repr__(self) -> str:
        return f"<ChatAttachment id={self.id} message_id={self.message_id}>"
