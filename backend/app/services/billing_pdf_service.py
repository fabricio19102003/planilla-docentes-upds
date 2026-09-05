"""Private, deterministic billing PDFs and opaque media tokens."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import secrets
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import settings as default_settings
from app.models.billing_notification import BillingMediaToken, BillingNotificationBatch, BillingNotificationJob

MAX_BILLING_PDF_BYTES = 15_000_000
_SAFE_FILENAME = re.compile(r"[A-Za-z0-9._-]{1,20}\.pdf\Z")


@dataclass(frozen=True)
class BillingMediaIssue:
    token: str
    token_hash: str
    artifact_hash: str
    artifact_path: str
    filename: str
    artifact_size: int
    token_id: int


class BillingPdfService:
    """Creates snapshot-derived PDF artifacts and validates opaque token access."""

    def __init__(
        self,
        db: Session,
        *,
        storage_dir: str | Path | None = None,
        now: Callable[[], datetime] = datetime.utcnow,
    ) -> None:
        self.db = db
        self.storage_dir = Path(storage_dir or default_settings.BILLING_MEDIA_DIR).resolve()
        self.now = now

    def issue(
        self,
        batch: BillingNotificationBatch,
        job: BillingNotificationJob,
        snapshot: dict[str, Any],
        *,
        expires_in: timedelta = timedelta(hours=24),
        commit: bool = True,
    ) -> BillingMediaIssue:
        if job.batch_id != batch.id or not job.teacher_ci or not isinstance(snapshot, dict) or expires_in.total_seconds() <= 0:
            raise ValueError("invalid_billing_media_binding")
        payload = self._pdf_bytes(batch.id, job.teacher_ci, snapshot)
        if len(payload) > MAX_BILLING_PDF_BYTES:
            raise ValueError("billing_pdf_too_large")
        artifact_hash = hashlib.sha256(payload).hexdigest()
        filename = f"b-{artifact_hash[:12]}.pdf"
        path = self._safe_path(filename)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(payload)
        if path.read_bytes() != payload:
            raise ValueError("billing_pdf_storage_conflict")

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        self.db.add(BillingMediaToken(
            batch_id=batch.id,
            teacher_ci=job.teacher_ci,
            job_id=job.id,
            token_hash=token_hash,
            artifact_hash=artifact_hash,
            artifact_path=str(path),
            artifact_size=len(payload),
            expires_at=self.now() + expires_in,
        ))
        self.db.flush()
        row = self.db.query(BillingMediaToken).filter_by(token_hash=token_hash).one()
        job.media_snapshot = {"token_id": row.id, "artifact_hash": artifact_hash, "artifact_size": len(payload)}
        self.db.flush()
        if commit:
            self.db.commit()
        return BillingMediaIssue(token, token_hash, artifact_hash, str(path), filename, len(payload), row.id)

    def resolve(self, token: str) -> tuple[Path, str] | None:
        if not isinstance(token, str) or not token or len(token) > 255:
            return None
        row = self.db.query(BillingMediaToken).filter_by(
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest()
        ).one_or_none()
        if row is None or row.revoked_at is not None or row.expires_at <= self.now():
            return None
        job = self.db.get(BillingNotificationJob, row.job_id)
        media = getattr(job, "media_snapshot", None) if job else None
        if not job or job.batch_id != row.batch_id or job.teacher_ci != row.teacher_ci or not isinstance(media, dict) or media.get("token_id") != row.id or media.get("artifact_hash") != row.artifact_hash or media.get("artifact_size") != row.artifact_size:
            return None
        try:
            path = Path(row.artifact_path).resolve()
            if path.parent != self.storage_dir or not _SAFE_FILENAME.fullmatch(path.name):
                return None
            content = path.read_bytes()
        except OSError:
            return None
        if len(content) != row.artifact_size or len(content) > MAX_BILLING_PDF_BYTES:
            return None
        if not content.startswith(b"%PDF-") or hashlib.sha256(content).hexdigest() != row.artifact_hash:
            return None
        return path, path.name

    def _safe_path(self, filename: str) -> Path:
        if not _SAFE_FILENAME.fullmatch(filename):
            raise ValueError("invalid_billing_media_filename")
        path = (self.storage_dir / filename).resolve()
        if path.parent != self.storage_dir:
            raise ValueError("invalid_billing_media_path")
        return path

    @staticmethod
    def _pdf_bytes(batch_id: int, teacher_ci: str, snapshot: dict[str, Any]) -> bytes:
        facts = json.dumps(
            {"batch_id": batch_id, "teacher_ci": teacher_ci, "snapshot": snapshot},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 9 Tf 40 760 Td ({facts}) Tj ET".encode("ascii")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        result = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, body in enumerate(objects, start=1):
            offsets.append(len(result))
            result.extend(f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
        xref = len(result)
        result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
        result.extend(b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]))
        result.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
        return bytes(result)
