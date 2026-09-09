from datetime import datetime
import re

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


CONSENT_SOURCES = (
    "written_record",
    "verbal_record",
    "other_documented",
)


class WhatsAppPreference(Base):
    __tablename__ = "whatsapp_preferences"

    teacher_ci: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("teachers.ci", ondelete="CASCADE"),
        primary_key=True,
    )
    phone_e164: Mapped[str] = mapped_column(String(16), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_evidence: Mapped[str | None] = mapped_column(Text)
    consent_source: Mapped[str | None] = mapped_column(String(32))
    consented_at: Mapped[datetime | None] = mapped_column(DateTime)
    consent_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    opt_out_evidence: Mapped[str | None] = mapped_column(Text)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime)

    @staticmethod
    def canonical_e164(value):
        value = value.strip() if isinstance(value, str) else ""
        return value if re.fullmatch(r"\+[1-9]\d{7,14}", value) else None

    @property
    def is_eligible_for_whatsapp(self):
        return bool(
            self.canonical_e164(self.phone_e164)
            and self.is_verified
            and self.consent_evidence
            and self.consent_source in CONSENT_SOURCES
            and self.consented_at
            and self.consent_revision >= 1
            and not self.opted_out_at
        )

    def record_consent(self, evidence):
        self.consent_evidence = evidence
        self.opted_out_at = None
        self.consent_revision += 1

    def record_opt_out(self, evidence):
        self.opt_out_evidence = evidence
        self.opted_out_at = datetime.utcnow()
        self.consent_revision += 1


class WhatsAppConsentRevision(Base):
    __tablename__ = "whatsapp_consent_revisions"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_whatsapp_consent_revision_positive"),
        UniqueConstraint("teacher_ci", "revision", name="uq_whatsapp_consent_teacher_revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_ci: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("teachers.ci", ondelete="CASCADE"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(16), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_evidence: Mapped[str | None] = mapped_column(Text)
    consent_source: Mapped[str | None] = mapped_column(String(32))
    consented_at: Mapped[datetime | None] = mapped_column(DateTime)
    opt_out_evidence: Mapped[str | None] = mapped_column(Text)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime)
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
