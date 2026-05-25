"""Email service contracts and billing-publication send orchestration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Protocol

from app.config import settings as default_settings
from app.services.billing_email_template import (
    BillingEmailRow,
    render_billing_email_html,
    render_billing_email_text,
)

logger = logging.getLogger(__name__)

SendStatus = Literal["sent", "failed", "skipped"]


@dataclass(frozen=True)
class EmailRecipient:
    """A resolved recipient for an outbound email attempt."""

    user_id: int
    name: str
    email: str
    teacher_ci: str


@dataclass(frozen=True)
class EmailMessage:
    """Provider-agnostic email payload."""

    to: str
    subject: str
    html: str
    text: str


@dataclass(frozen=True)
class EmailSendResult:
    """Result for a single provider send attempt."""

    status: SendStatus
    error: str | None = None


@dataclass(frozen=True)
class EmailAttemptResult:
    """Operational result for one intended recipient."""

    recipient: EmailRecipient | None
    status: SendStatus
    error: str | None = None


@dataclass(frozen=True)
class EmailBatchResult:
    """Aggregated outcome for a billing-publication email batch."""

    eligible: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    attempts: tuple[EmailAttemptResult, ...] = field(default_factory=tuple)


class EmailTransport(Protocol):
    """Transport contract implemented by Resend or test doubles."""

    def send_email(self, message: EmailMessage) -> EmailSendResult:
        """Send one email and return a safe operational result."""


class EmailService:
    """Configuration-gated outbound email service for billing publication."""

    def __init__(
        self,
        *,
        settings: Any = default_settings,
        transport: EmailTransport | None = None,
        service_logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.logger = service_logger or logger

    def send_billing_published(self, publication: Any, docente_users: list[Any]) -> EmailBatchResult:
        """Send billing-published emails without raising provider/config failures."""

        if not getattr(self.settings, "EMAIL_ENABLED", False):
            result = EmailBatchResult(skipped=len(docente_users))
            self._log_batch_result(result, reason="email_disabled")
            return result

        if not self._has_provider_config():
            result = EmailBatchResult(skipped=len(docente_users))
            self._log_batch_result(result, reason="missing_provider_config")
            return result

        # ── Test mode: redirect ALL emails to a single test recipient ────
        test_mode = getattr(self.settings, "EMAIL_TEST_MODE", False)
        test_recipient_email = getattr(self.settings, "EMAIL_TEST_RECIPIENT", None) if test_mode else None
        if test_mode and not test_recipient_email:
            self.logger.warning("EMAIL_TEST_MODE is enabled but EMAIL_TEST_RECIPIENT is not set — skipping all emails")
            result = EmailBatchResult(skipped=len(docente_users))
            self._log_batch_result(result, reason="test_mode_no_recipient")
            return result

        if test_mode:
            self.logger.info(
                "EMAIL_TEST_MODE active — sending ONE test email to %s (simulating %d docentes)",
                test_recipient_email, len(docente_users),
            )

        transport = self._get_transport()
        snapshot_by_ci = self._snapshot_details_by_ci(publication)
        attempts: list[EmailAttemptResult] = []
        eligible = sent = failed = skipped = 0
        test_email_sent = False  # Only send one email in test mode

        for user in docente_users:
            recipient = self._resolve_recipient(user)
            if recipient is None:
                skipped += 1
                attempts.append(EmailAttemptResult(recipient=None, status="skipped", error="missing_recipient_email"))
                continue

            teacher_detail = snapshot_by_ci.get(recipient.teacher_ci)
            if not teacher_detail:
                skipped += 1
                attempts.append(EmailAttemptResult(recipient=recipient, status="skipped", error="missing_billing_snapshot"))
                continue

            try:
                rows = self._rows_from_snapshot(teacher_detail)
            except ValueError as exc:
                skipped += 1
                attempts.append(EmailAttemptResult(recipient=recipient, status="skipped", error=str(exc)))
                continue

            if not rows:
                skipped += 1
                attempts.append(EmailAttemptResult(recipient=recipient, status="skipped", error="missing_billing_rows"))
                continue

            eligible += 1

            # In test mode, send only ONE email to the test recipient
            if test_mode:
                if test_email_sent:
                    skipped += 1
                    attempts.append(EmailAttemptResult(recipient=recipient, status="skipped", error="test_mode_already_sent"))
                    continue
                # Override recipient email to test address
                recipient = EmailRecipient(
                    user_id=recipient.user_id,
                    name=f"[TEST] {recipient.name}",
                    email=test_recipient_email,
                    teacher_ci=recipient.teacher_ci,
                )

            message = self._build_billing_message(publication, recipient, rows, teacher_detail)
            try:
                send_result = transport.send_email(message)
            except Exception as exc:  # pragma: no cover - defensive boundary tested via behavior
                self.logger.exception("Billing email transport raised for user_id=%s: %s", recipient.user_id, exc)
                send_result = EmailSendResult(status="failed", error=str(exc))

            if test_mode:
                test_email_sent = True  # Stop after first attempt regardless of result

            if send_result.status == "sent":
                sent += 1
            elif send_result.status == "failed":
                failed += 1
            else:
                skipped += 1

            attempts.append(
                EmailAttemptResult(
                    recipient=recipient,
                    status=send_result.status,
                    error=send_result.error,
                )
            )

        result = EmailBatchResult(
            eligible=eligible,
            sent=sent,
            failed=failed,
            skipped=skipped,
            attempts=tuple(attempts),
        )
        self._log_batch_result(result)
        return result

    def _has_provider_config(self) -> bool:
        return bool(
            getattr(self.settings, "RESEND_API_KEY", None)
            and getattr(self.settings, "RESEND_FROM_EMAIL", None)
        )

    def _get_transport(self) -> EmailTransport:
        if self.transport is not None:
            return self.transport

        from app.services.resend_email_transport import ResendEmailTransport

        self.transport = ResendEmailTransport(
            api_key=getattr(self.settings, "RESEND_API_KEY"),
            from_email=getattr(self.settings, "RESEND_FROM_EMAIL"),
            api_url=getattr(self.settings, "RESEND_API_URL", "https://api.resend.com"),
            timeout_seconds=getattr(self.settings, "EMAIL_TIMEOUT_SECONDS", 3.0),
        )
        return self.transport

    def _resolve_recipient(self, user: Any) -> EmailRecipient | None:
        teacher = getattr(user, "teacher", None)
        raw_email = getattr(user, "email", None) or getattr(teacher, "email", None)
        email = _clean_email(raw_email)
        teacher_ci = getattr(user, "teacher_ci", None) or getattr(teacher, "ci", None)
        if not email or not teacher_ci:
            return None

        name = getattr(user, "full_name", None) or getattr(teacher, "full_name", None) or "Docente"
        return EmailRecipient(
            user_id=int(getattr(user, "id", 0) or 0),
            name=str(name),
            email=email,
            teacher_ci=str(teacher_ci),
        )

    def _snapshot_details_by_ci(self, publication: Any) -> dict[str, dict[str, Any]]:
        snapshot = getattr(publication, "billing_snapshot", None) or {}
        details = snapshot.get("teacher_details") if isinstance(snapshot, dict) else None
        if not isinstance(details, list):
            return {}
        return {
            str(detail.get("teacher_ci")): detail
            for detail in details
            if isinstance(detail, dict) and detail.get("teacher_ci") is not None
        }

    def _rows_from_snapshot(self, teacher_detail: dict[str, Any]) -> list[BillingEmailRow]:
        designations = teacher_detail.get("designations")
        if not isinstance(designations, list):
            return []

        rows: list[BillingEmailRow] = []
        for item in designations:
            if not isinstance(item, dict):
                continue
            try:
                amount = Decimal(str(item.get("payment", "0")))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError("invalid_billing_amount") from exc
            rows.append(
                BillingEmailRow(
                    subject=str(item.get("subject") or ""),
                    amount=amount,
                    group=str(item.get("group") or item.get("group_code") or ""),
                    semester=str(item.get("semester") or ""),
                )
            )
        return rows

    def _build_billing_message(
        self,
        publication: Any,
        recipient: EmailRecipient,
        rows: list[BillingEmailRow],
        teacher_detail: dict[str, Any],
    ) -> EmailMessage:
        month_name = _month_name(getattr(publication, "month", ""))
        year = getattr(publication, "year", "")
        subject = f"Detalle de honorarios docentes - {month_name} {year}"
        snapshot = getattr(publication, "billing_snapshot", None) or {}
        context = snapshot if isinstance(snapshot, dict) else {}
        excluded_days = context.get("excluded_days_json")
        filtered_excluded_days = self._filter_excluded_days_for_teacher(
            excluded_days if isinstance(excluded_days, list) else [],
            teacher_detail,
        )
        return EmailMessage(
            to=recipient.email,
            subject=subject,
            html=render_billing_email_html(
                docente_name=recipient.name,
                month_name=month_name,
                year=year,
                rows=rows,
                start_date=context.get("start_date"),
                end_date=context.get("end_date"),
                rate_per_hour=context.get("rate_per_hour"),
                excluded_days=filtered_excluded_days,
            ),
            text=render_billing_email_text(
                docente_name=recipient.name,
                month_name=month_name,
                year=year,
                rows=rows,
                start_date=context.get("start_date"),
                end_date=context.get("end_date"),
                rate_per_hour=context.get("rate_per_hour"),
                excluded_days=filtered_excluded_days,
            ),
        )

    def _filter_excluded_days_for_teacher(
        self,
        excluded_days: list[Any],
        teacher_detail: dict[str, Any],
    ) -> list[dict[str, Any]]:
        teacher_designations = teacher_detail.get("designations", [])
        if not isinstance(teacher_designations, list):
            teacher_designations = []

        teacher_semesters = {
            designation.get("semester")
            for designation in teacher_designations
            if isinstance(designation, dict) and designation.get("semester") is not None
        }
        teacher_subject_groups = {
            (designation.get("subject"), designation.get("group") or designation.get("group_code"))
            for designation in teacher_designations
            if isinstance(designation, dict) and designation.get("subject") is not None
        }

        filtered: list[dict[str, Any]] = []
        for excluded in excluded_days:
            if not isinstance(excluded, dict):
                continue
            scope = excluded.get("scope")
            if scope == "global":
                filtered.append(excluded)
            elif scope == "semester" and excluded.get("semester_id") in teacher_semesters:
                filtered.append(excluded)
            elif scope == "subject" and (excluded.get("subject_id"), excluded.get("group_id")) in teacher_subject_groups:
                filtered.append(excluded)
        return filtered

    def _log_batch_result(self, result: EmailBatchResult, *, reason: str | None = None) -> None:
        self.logger.info(
            "Billing email batch result eligible=%s sent=%s failed=%s skipped=%s%s",
            result.eligible,
            result.sent,
            result.failed,
            result.skipped,
            f" reason={reason}" if reason else "",
        )


def _clean_email(value: Any) -> str | None:
    if not value:
        return None
    email = str(value).strip()
    if not email or "@" not in email:
        return None
    return email


def _month_name(month: Any) -> str:
    names = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    }
    try:
        return names[int(month)]
    except (TypeError, ValueError, KeyError):
        return str(month)


__all__ = [
    "BillingEmailRow",
    "EmailAttemptResult",
    "EmailBatchResult",
    "EmailMessage",
    "EmailRecipient",
    "EmailSendResult",
    "EmailService",
    "EmailTransport",
]
