"""Atomic, digest-bound application of a designation bootstrap preview to one draft."""
from __future__ import annotations

import hmac
from datetime import date, time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.academic_management import (
    AcademicProgram,
    AcademicScheduleAssignment,
    AcademicScheduleBlock,
    AcademicScheduleDraft,
)
from app.models.activity_log import ActivityLog
from app.models.designation_bootstrap import DesignationBootstrapReceipt
from app.models.user import User
from app.services.designation_bootstrap_preview import (
    POLICY_VERSION,
    PlannedBlock,
    _build_designation_bootstrap_preview,
    _digest,
    _fold,
    _sha,
)


EFFECTIVE_DATE = date(2026, 8, 21)
RECEIPT_SCHEMA_VERSION = 1
POSTGRES_LOCK_TABLES = (
    # Canonical order follows the planner mutation order first, then catalogs,
    # immutable publication state, and finally this operation's receipt.
    "academic_programs",
    "academic_schedule_drafts",
    "academic_schedule_blocks",
    "academic_schedule_assignments",
    "teachers",
    "teacher_availability",
    "academic_subjects",
    "subject_offerings",
    "academic_groups",
    "classrooms",
    "academic_schedule_publications",
    "academic_schedule_published_blocks",
    "academic_schedule_published_assignments",
    "designation_bootstrap_receipts",
)


class DesignationBootstrapApplyError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _operation_key(
    official_content: bytes,
    salary_content: bytes,
    alias_content: bytes | None,
    academic_period: str,
    effective_date: date,
    program_id: int | None,
) -> str:
    return _digest({
        "policy": POLICY_VERSION,
        "official_sha256": _sha(official_content),
        "salary_sha256": _sha(salary_content),
        "alias_sha256": _sha(alias_content) if alias_content is not None else None,
        "academic_period": academic_period,
        "effective_date": effective_date.isoformat(),
        "program_id": program_id,
    })


def _scope_lock_key(academic_period: str, effective_date: date, program_id: int | None) -> str:
    return _digest({
        "operation": "designation_bootstrap_apply",
        "academic_period": academic_period,
        "effective_date": effective_date.isoformat(),
        "program_id": program_id,
    })


def _advisory_lock(db: Session, lock_identity: str) -> None:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        lock_key = int(lock_identity[:16], 16)
        if lock_key >= 2**63:
            lock_key -= 2**64
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})


def _lock_postgresql_tables(db: Session) -> None:
    """Freeze every relation that can change preview resolution or target state.

    SHARE ROW EXCLUSIVE conflicts with INSERT/UPDATE/DELETE table locks from
    other transactions while permitting this transaction's own draft writes.
    SQLite deliberately uses a no-op; its focused tests remain single-writer.
    """
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    for table_name in POSTGRES_LOCK_TABLES:
        db.execute(text(f'LOCK TABLE "{table_name}" IN SHARE ROW EXCLUSIVE MODE'))


def _source_plan(plan: tuple[PlannedBlock, ...]) -> list[dict[str, Any]]:
    ordered = sorted(plan, key=lambda item: (
        item.activity, item.subject_key, item.group_key, item.slot.weekday,
        item.slot.start, item.teacher_key, item.source.row,
    ))
    return [{
        "activity_type": item.activity,
        "teacher_ci": item.teacher_ci,
        "subject_id": item.subject_id,
        "offering_id": item.offering_id,
        "semester": item.semester,
        "group_id": item.group_id,
        "classroom_id": item.classroom_id,
        "weekday": item.slot.weekday,
        "start_time": item.slot.start.isoformat(),
        "end_time": item.slot.end.isoformat(),
        "source": {
            "workbook_sha256": item.source.workbook_sha256,
            "sheet": item.source.sheet,
            "row": item.source.row,
            "schedule_raw": item.slot.raw,
            "schedule_normalized": item.slot.normalized,
            "normalizations": list(item.slot.normalizations),
        },
    } for item in ordered]


def _draft_graph(db: Session, draft_id: int) -> dict[str, Any] | None:
    draft = db.get(AcademicScheduleDraft, draft_id)
    if draft is None:
        return None
    blocks = db.query(AcademicScheduleBlock).filter_by(draft_id=draft_id).order_by(
        AcademicScheduleBlock.id
    ).all()
    graph_blocks = []
    for block in blocks:
        assignments = db.query(AcademicScheduleAssignment).filter_by(block_id=block.id).order_by(
            AcademicScheduleAssignment.id
        ).all()
        graph_blocks.append({
            "id": block.id,
            "offering_id": block.offering_id,
            "group_id": block.group_id,
            "classroom_id": block.classroom_id,
            "activity_type": block.activity_type,
            "weekday": block.weekday,
            "start_time": block.start_time.isoformat(),
            "end_time": block.end_time.isoformat(),
            "assignments": [{
                "id": assignment.id,
                "teacher_ci": assignment.teacher_ci,
                "effective_from": assignment.effective_from.isoformat(),
                "effective_to": assignment.effective_to.isoformat() if assignment.effective_to else None,
            } for assignment in assignments],
        })
    return {
        "draft": {
            "id": draft.id,
            "program_id": draft.program_id,
            "academic_period": draft.academic_period,
            "name": draft.name,
            "normalized_name": draft.normalized_name,
            "status": draft.status,
        },
        "blocks": graph_blocks,
    }


def _response(receipt: DesignationBootstrapReceipt, replayed: bool) -> dict[str, Any]:
    return {
        "status": "replayed" if replayed else "applied",
        "replayed": replayed,
        "draft_id": receipt.draft_id,
        "theory_block_count": receipt.theory_block_count,
        "practice_block_count": receipt.practice_block_count,
        "theory_assignment_count": receipt.theory_assignment_count,
        "practice_assignment_count": receipt.practice_assignment_count,
        "preview_digest": receipt.preview_digest,
    }


def apply_designation_bootstrap(
    db: Session,
    *,
    official_content: bytes,
    salary_content: bytes,
    academic_period: str,
    effective_date: date,
    program_identity: str,
    confirmation_digest: str,
    actor: User,
    alias_content: bytes | None = None,
) -> dict[str, Any]:
    """Apply one verified preview. The caller owns commit and rollback."""
    if effective_date != EFFECTIVE_DATE:
        raise DesignationBootstrapApplyError("invalid_effective_date")
    if actor.id is None or actor.role != "admin" or not actor.is_active:
        raise DesignationBootstrapApplyError("invalid_actor")
    academic_period = " ".join(academic_period.split()).upper()
    program_identity = " ".join(program_identity.split())
    _lock_postgresql_tables(db)
    matching_programs = [
        item for item in db.query(AcademicProgram).filter(
            AcademicProgram.active.is_(True)
        ).order_by(AcademicProgram.id).all()
        if _fold(item.code) == _fold(program_identity) or _fold(item.name) == _fold(program_identity)
    ]
    resolved_program_id = matching_programs[0].id if len(matching_programs) == 1 else None
    _advisory_lock(db, _scope_lock_key(academic_period, effective_date, resolved_program_id))
    locked_actor = db.query(User).filter(User.id == actor.id).with_for_update().populate_existing().one_or_none()
    if locked_actor is None or locked_actor.role != "admin" or not locked_actor.is_active:
        raise DesignationBootstrapApplyError("invalid_actor")
    actor = locked_actor
    operation_key = _operation_key(
        official_content, salary_content, alias_content,
        academic_period, effective_date, resolved_program_id,
    )
    receipt = db.query(DesignationBootstrapReceipt).filter_by(
        operation_key=operation_key
    ).one_or_none()
    excluded_draft_id = receipt.draft_id if receipt is not None else None
    preview = _build_designation_bootstrap_preview(
        db, official_content=official_content, salary_content=salary_content,
        academic_period=academic_period, effective_date=effective_date,
        program_identity=program_identity, alias_content=alias_content,
        include_private=True, excluded_draft_id=excluded_draft_id,
    )
    if not hmac.compare_digest(preview["preview_digest"], confirmation_digest):
        raise DesignationBootstrapApplyError("preview_digest_drift")
    if not preview["can_apply"]:
        raise DesignationBootstrapApplyError("preview_blocked")
    if preview["_program_id"] != resolved_program_id:
        raise DesignationBootstrapApplyError("program_resolution_drift")

    source_plan = _source_plan(preview["_private_plan"])
    if not source_plan:
        raise DesignationBootstrapApplyError("empty_resolved_plan")
    if receipt is not None:
        bindings_match = (
            receipt.official_sha256 == preview["sources"]["official_sha256"]
            and receipt.salary_sha256 == preview["sources"]["salary_sha256"]
            and receipt.alias_sha256 == preview["sources"]["alias_sha256"]
            and receipt.database_state_fingerprint == preview["database_state_fingerprint"]
            and receipt.program_id == preview["_program_id"]
            and receipt.academic_period == academic_period
            and receipt.effective_date == effective_date
            and receipt.actor_id == actor.id
            and hmac.compare_digest(receipt.preview_digest, confirmation_digest)
        )
        snapshot = receipt.plan_snapshot
        if (
            not bindings_match
            or not hmac.compare_digest(receipt.content_digest, _digest(snapshot))
            or snapshot.get("schema_version") != RECEIPT_SCHEMA_VERSION
            or snapshot.get("source_plan") != source_plan
            or snapshot.get("graph") != _draft_graph(db, receipt.draft_id)
        ):
            raise DesignationBootstrapApplyError("replay_graph_drift")
        return _response(receipt, True)

    program_id = preview["_program_id"]
    if program_id is None or any(
        item[field] is None
        for item in source_plan
        for field in ("teacher_ci", "subject_id", "offering_id", "semester", "group_id", "classroom_id")
    ):
        raise DesignationBootstrapApplyError("incomplete_resolved_plan")
    draft_name = f"Designation bootstrap {academic_period} — {effective_date.isoformat()}"
    draft = AcademicScheduleDraft(
        program_id=program_id,
        academic_period=academic_period,
        name=draft_name,
        normalized_name=draft_name.casefold(),
        status="draft",
    )
    db.add(draft)
    db.flush()
    for item in source_plan:
        block = AcademicScheduleBlock(
            draft_id=draft.id,
            offering_id=item["offering_id"],
            group_id=item["group_id"],
            classroom_id=item["classroom_id"],
            activity_type=item["activity_type"],
            weekday=item["weekday"],
            start_time=time.fromisoformat(item["start_time"]),
            end_time=time.fromisoformat(item["end_time"]),
        )
        db.add(block)
        db.flush()
        db.add(AcademicScheduleAssignment(
            block_id=block.id,
            teacher_ci=item["teacher_ci"],
            effective_from=EFFECTIVE_DATE,
            effective_to=None,
        ))
    db.flush()
    graph = _draft_graph(db, draft.id)
    snapshot = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "source_plan": source_plan,
        "graph": graph,
    }
    counts = preview["planned"]
    receipt = DesignationBootstrapReceipt(
        operation_key=operation_key,
        preview_digest=preview["preview_digest"],
        official_sha256=preview["sources"]["official_sha256"],
        salary_sha256=preview["sources"]["salary_sha256"],
        alias_sha256=preview["sources"]["alias_sha256"],
        database_state_fingerprint=preview["database_state_fingerprint"],
        program_id=program_id,
        academic_period=academic_period,
        effective_date=effective_date,
        draft_id=draft.id,
        actor_id=actor.id,
        theory_block_count=counts["theory_block_count"],
        practice_block_count=counts["practice_block_count"],
        theory_assignment_count=counts["theory_assignment_count"],
        practice_assignment_count=counts["practice_assignment_count"],
        content_digest=_digest(snapshot),
        plan_snapshot=snapshot,
    )
    db.add(receipt)
    db.add(ActivityLog(
        user_id=actor.id,
        user_ci=None,
        user_name=None,
        user_role="admin",
        action="apply_designation_bootstrap",
        category="academic_schedule",
        description="Applied digest-bound designation bootstrap to a new schedule draft",
        details={
            "draft_id": draft.id,
            "preview_digest": preview["preview_digest"],
            "academic_period": academic_period,
            "effective_date": effective_date.isoformat(),
            "counts": counts,
        },
        status="success",
    ))
    db.flush()
    return _response(receipt, False)
