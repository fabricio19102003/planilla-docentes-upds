from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date, timedelta
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.academic_management import (
    AcademicScheduleAssignment,
    AcademicScheduleBlock,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
    SubjectOffering,
)
from app.models.attendance import AttendanceRecord
from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.services import academic_management_service as academic


OPERATIONAL_WARNINGS = [
    "Las asignaciones teóricas publicadas alimentan la asistencia regular y conservan su procedencia inmutable.",
    "Los bloques de práctica, planillas, contratos y facturación continúan usando únicamente las designaciones heredadas.",
]


def _publication_query(db: Session):
    return db.query(AcademicSchedulePublication).options(
        joinedload(AcademicSchedulePublication.program),
        joinedload(AcademicSchedulePublication.blocks)
        .joinedload(AcademicSchedulePublishedBlock.assignments),
    )


def _draft_graph(db: Session, draft_id: int, lock: bool) -> AcademicScheduleDraft:
    if lock:
        draft = academic._lock_schedule_draft(db, draft_id)
    else:
        draft = db.query(AcademicScheduleDraft).filter(
            AcademicScheduleDraft.id == draft_id
        ).first()
    if draft is None:
        raise HTTPException(404, detail="No se encontró el borrador de horario solicitado.")
    if lock:
        db.query(AcademicScheduleBlock.id).filter(
            AcademicScheduleBlock.draft_id == draft.id
        ).order_by(AcademicScheduleBlock.id).with_for_update().all()
        db.query(AcademicScheduleAssignment.id).join(AcademicScheduleBlock).filter(
            AcademicScheduleBlock.draft_id == draft.id
        ).order_by(AcademicScheduleAssignment.id).with_for_update().all()
    draft.blocks = academic._schedule_block_query(db).options(
        joinedload(AcademicScheduleBlock.assignments).joinedload(
            AcademicScheduleAssignment.teacher
        )
    ).filter(AcademicScheduleBlock.draft_id == draft.id).all()
    return draft


def _next_sequence(db: Session, draft: AcademicScheduleDraft, effective_from: date) -> int:
    current = db.query(func.max(AcademicSchedulePublication.sequence)).filter(
        AcademicSchedulePublication.program_id == draft.program_id,
        AcademicSchedulePublication.academic_period == draft.academic_period,
        AcademicSchedulePublication.effective_from == effective_from,
    ).scalar()
    return int(current or 0) + 1


def _relevant_assignments(
    block: AcademicScheduleBlock, effective_from: date
) -> list[AcademicScheduleAssignment]:
    return sorted(
        [
            item for item in block.assignments
            if item.effective_to is None or item.effective_to >= effective_from
        ],
        key=lambda item: (item.effective_from, item.id),
    )


def _canonical_block(block: AcademicScheduleBlock, effective_from: date) -> dict[str, Any]:
    return {
        "offering_id": block.offering_id,
        "subject_id": block.offering.subject_id,
        "subject_code": block.offering.subject.code,
        "subject_name": block.offering.subject.name,
        "group_id": block.group_id,
        "group_code": block.group.code,
        "semester": block.group.semester,
        "classroom_id": block.classroom_id,
        "classroom_code": block.classroom.code,
        "classroom_name": block.classroom.name,
        "activity_type": block.activity_type,
        "weekday": block.weekday,
        "start_time": block.start_time.isoformat(),
        "end_time": block.end_time.isoformat(),
        "notes": None,
        "assignments": [
            {
                "teacher_ci": item.teacher_ci,
                "teacher_name": item.teacher.full_name,
                "effective_from": item.effective_from.isoformat(),
                "effective_to": item.effective_to.isoformat() if item.effective_to else None,
            }
            for item in _relevant_assignments(block, effective_from)
        ],
    }


def _canonical_content(
    draft: AcademicScheduleDraft, effective_from: date, sequence: int
) -> dict[str, Any]:
    blocks = [_canonical_block(block, effective_from) for block in draft.blocks]
    blocks.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    return {
        "program_id": draft.program_id,
        "academic_period": draft.academic_period,
        "effective_from": effective_from.isoformat(),
        "sequence": sequence,
        "blocks": blocks,
    }


def _digest(content: dict[str, Any]) -> str:
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _coverage_error(
    assignments: list[AcademicScheduleAssignment], effective_from: date
) -> str | None:
    active = [
        item for item in assignments
        if item.effective_from <= effective_from
        and (item.effective_to is None or item.effective_to >= effective_from)
    ]
    if len(active) != 1:
        return "teacher_coverage_start"
    current = active[0]
    future = [item for item in assignments if item.effective_from > effective_from]
    future.sort(key=lambda item: (item.effective_from, item.id))
    for following in future:
        if current.effective_to is None:
            return "teacher_coverage_overlap"
        if following.effective_from != current.effective_to + timedelta(days=1):
            return "teacher_coverage_gap"
        current = following
    if current.effective_to is not None:
        return "teacher_coverage_not_open_ended"
    return None


def _month_end(month: int, year: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _output_affects(row: Any, effective_from: date) -> bool:
    end = getattr(row, "end_date", None) or _month_end(row.month, row.year)
    return end >= effective_from


def _retroactive_blockers(
    db: Session, draft: AcademicScheduleDraft, effective_from: date
) -> list[dict[str, Any]]:
    if effective_from >= date.today():
        return []
    represented = {
        (block.offering.subject.name.casefold().strip(), block.group.code.casefold().strip())
        for block in draft.blocks
    }
    legacy_attendance_rows = db.query(AttendanceRecord).join(Designation).filter(
        Designation.academic_period == draft.academic_period,
        AttendanceRecord.date >= effective_from,
    ).all()
    attendance_count = sum(
        1 for row in legacy_attendance_rows
        if (row.designation.subject.casefold().strip(), row.designation.group_code.casefold().strip())
        in represented
    )
    published_attendance_rows = (
        db.query(AttendanceRecord)
        .join(AcademicSchedulePublishedAssignment)
        .join(AcademicSchedulePublishedBlock)
        .join(AcademicSchedulePublication)
        .filter(
            AcademicSchedulePublication.program_id == draft.program_id,
            AcademicSchedulePublication.academic_period == draft.academic_period,
            AttendanceRecord.date >= effective_from,
        )
        .all()
    )
    attendance_count += sum(
        1 for row in published_attendance_rows
        if (
            row.published_schedule_assignment.block.subject_name.casefold().strip(),
            row.published_schedule_assignment.block.group_code.casefold().strip(),
        ) in represented
    )
    practice_rows = db.query(PracticeAttendanceLog).join(Designation).filter(
        Designation.academic_period == draft.academic_period,
        PracticeAttendanceLog.date >= effective_from,
    ).all()
    practice_count = sum(
        1 for row in practice_rows
        if (row.designation.subject.casefold().strip(), row.designation.group_code.casefold().strip())
        in represented
    )
    published_practice_rows = (
        db.query(PracticeAttendanceLog)
        .join(AcademicSchedulePublishedAssignment)
        .join(AcademicSchedulePublishedBlock)
        .join(AcademicSchedulePublication)
        .filter(
            AcademicSchedulePublication.program_id == draft.program_id,
            AcademicSchedulePublication.academic_period == draft.academic_period,
            PracticeAttendanceLog.date >= effective_from,
        )
        .all()
    )
    practice_count += sum(
        1 for row in published_practice_rows
        if (
            row.published_schedule_assignment.block.subject_name.casefold().strip(),
            row.published_schedule_assignment.block.group_code.casefold().strip(),
        ) in represented
    )
    regular_planillas = sum(
        _output_affects(row, effective_from) for row in db.query(PlanillaOutput).all()
    )
    practice_planillas = sum(
        _output_affects(row, effective_from) for row in db.query(PracticePlanillaOutput).all()
    )
    publications = [
        row for row in db.query(BillingPublication).all()
        if _month_end(row.month, row.year) >= effective_from
    ]
    publication_ids = [row.id for row in publications]
    revision_count = 0
    if publication_ids:
        revision_count = db.query(BillingPublicationRevision.id).filter(
            BillingPublicationRevision.publication_id.in_(publication_ids)
        ).count()
    counts = {
        "regular_attendance": attendance_count,
        "practice_attendance": practice_count,
        "regular_planilla": regular_planillas,
        "practice_planilla": practice_planillas,
        "billing_publication": len(publications),
        "billing_revision": revision_count,
    }
    labels = {
        "regular_attendance": "asistencias regulares",
        "practice_attendance": "asistencias de práctica",
        "regular_planilla": "planillas regulares",
        "practice_planilla": "planillas de práctica",
        "billing_publication": "publicaciones de facturación",
        "billing_revision": "revisiones de facturación",
    }
    return [
        {
            "category": category,
            "count": count,
            "message": f"Existen {count} registros de {labels[category]} en el rango afectado.",
        }
        for category, count in counts.items() if count
    ]


def _effective_publication(
    db: Session, program_id: int, academic_period: str, target_date: date
) -> AcademicSchedulePublication | None:
    return _publication_query(db).filter(
        AcademicSchedulePublication.program_id == program_id,
        AcademicSchedulePublication.academic_period == academic_period,
        AcademicSchedulePublication.effective_from <= target_date,
    ).order_by(
        AcademicSchedulePublication.effective_from.desc(),
        AcademicSchedulePublication.sequence.desc(),
        AcademicSchedulePublication.id.desc(),
    ).first()


def _block_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        item["subject_code"].casefold(), item["group_code"].casefold(), item["semester"],
        item["activity_type"], item["weekday"], item["start_time"], item["end_time"],
    )


def _publication_block_dict(block: AcademicSchedulePublishedBlock) -> dict[str, Any]:
    return {
        "offering_id": block.source_offering_id,
        "subject_id": block.source_subject_id,
        "subject_code": block.subject_code,
        "subject_name": block.subject_name,
        "group_id": block.source_group_id,
        "group_code": block.group_code,
        "semester": block.semester,
        "classroom_id": block.source_classroom_id,
        "classroom_code": block.classroom_code,
        "classroom_name": block.classroom_name,
        "activity_type": block.activity_type,
        "weekday": block.weekday,
        "start_time": block.start_time.isoformat(),
        "end_time": block.end_time.isoformat(),
        "notes": block.notes,
        "assignments": [
            {
                "teacher_ci": item.teacher_ci,
                "teacher_name": item.teacher_name,
                "effective_from": item.effective_from.isoformat(),
                "effective_to": item.effective_to.isoformat() if item.effective_to else None,
            }
            for item in sorted(block.assignments, key=lambda row: (row.effective_from, row.id))
        ],
    }


def _workload(blocks: list[dict[str, Any]], reference_date: date) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for block in blocks:
        assignment = next((
            item for item in block["assignments"]
            if date.fromisoformat(item["effective_from"]) <= reference_date
            and (item["effective_to"] is None or date.fromisoformat(item["effective_to"]) >= reference_date)
        ), None)
        if assignment is None:
            continue
        item = totals.setdefault(assignment["teacher_ci"], {
            "teacher_ci": assignment["teacher_ci"], "teacher_name": assignment["teacher_name"],
            "theory_minutes_week": 0, "practice_minutes_week": 0, "total_minutes_week": 0,
        })
        start_hour, start_minute, *_ = map(int, block["start_time"].split(":"))
        end_hour, end_minute, *_ = map(int, block["end_time"].split(":"))
        minutes = end_hour * 60 + end_minute - start_hour * 60 - start_minute
        item[f"{block['activity_type']}_minutes_week"] += minutes
        item["total_minutes_week"] += minutes
    return totals


def _diff(
    db: Session, draft: AcademicScheduleDraft, effective_from: date, current: list[dict[str, Any]]
) -> dict[str, Any]:
    previous = _effective_publication(db, draft.program_id, draft.academic_period, effective_from)
    old = [_publication_block_dict(block) for block in previous.blocks] if previous else []
    new_by_key = {_block_key(item): item for item in current}
    old_by_key = {_block_key(item): item for item in old}
    common = set(new_by_key) & set(old_by_key)
    changed = sum(
        {key: value for key, value in new_by_key[key].items() if key != "assignments"}
        != {key: value for key, value in old_by_key[key].items() if key != "assignments"}
        for key in common
    )
    teacher_replacements = sum(
        new_by_key[key]["assignments"] != old_by_key[key]["assignments"] for key in common
    )
    new_workload = _workload(current, effective_from)
    old_workload = _workload(old, effective_from)
    workload_changes = []
    for teacher_ci in sorted(set(new_workload) | set(old_workload)):
        new_item = new_workload.get(teacher_ci, {})
        old_item = old_workload.get(teacher_ci, {})
        delta = {
            "teacher_ci": teacher_ci,
            "teacher_name": new_item.get("teacher_name") or old_item.get("teacher_name") or teacher_ci,
            "theory_minutes_week": new_item.get("theory_minutes_week", 0) - old_item.get("theory_minutes_week", 0),
            "practice_minutes_week": new_item.get("practice_minutes_week", 0) - old_item.get("practice_minutes_week", 0),
            "total_minutes_week": new_item.get("total_minutes_week", 0) - old_item.get("total_minutes_week", 0),
        }
        if delta["total_minutes_week"] or delta["theory_minutes_week"] or delta["practice_minutes_week"]:
            workload_changes.append(delta)
    return {
        "added_blocks": len(set(new_by_key) - set(old_by_key)),
        "removed_blocks": len(set(old_by_key) - set(new_by_key)),
        "changed_blocks": changed,
        "teacher_replacements": teacher_replacements,
        "workload_changes": workload_changes,
    }


def preview_publication(
    db: Session, draft_id: int, effective_from: date, lock: bool = False
) -> dict[str, Any]:
    draft = _draft_graph(db, draft_id, lock)
    sequence = _next_sequence(db, draft, effective_from)
    blockers: list[dict[str, Any]] = []
    if draft.status != "draft":
        blockers.append({
            "category": "draft_state", "count": 1,
            "message": "Solo un borrador editable puede publicarse.",
        })
    if not draft.blocks:
        blockers.append({
            "category": "empty_draft", "count": 1,
            "message": "El borrador debe contener al menos un bloque.",
        })
    validation_counts: dict[str, int] = {}
    for block in draft.blocks:
        values = {
            "offering_id": block.offering_id, "group_id": block.group_id,
            "classroom_id": block.classroom_id, "activity_type": block.activity_type,
            "weekday": block.weekday, "start_time": block.start_time, "end_time": block.end_time,
        }
        try:
            academic._validate_schedule_block(db, draft, values, block.id)
        except HTTPException as exc:
            validation_counts[str(exc.detail)] = validation_counts.get(str(exc.detail), 0) + 1
        relevant = _relevant_assignments(block, effective_from)
        coverage = _coverage_error(relevant, effective_from)
        if coverage:
            validation_counts[coverage] = validation_counts.get(coverage, 0) + 1
        for assignment in relevant:
            try:
                academic._ensure_teacher_availability(db, draft, block, assignment.teacher_ci)
                academic._ensure_assignment_available(
                    db, draft, block, assignment.teacher_ci,
                    assignment.effective_from, assignment.effective_to, {assignment.id},
                )
            except HTTPException as exc:
                validation_counts[str(exc.detail)] = validation_counts.get(str(exc.detail), 0) + 1
    coverage_messages = {
        "teacher_coverage_start": "Cada bloque debe tener exactamente un docente vigente en la fecha efectiva.",
        "teacher_coverage_overlap": "La cobertura docente contiene intervalos superpuestos.",
        "teacher_coverage_gap": "La cobertura docente contiene intervalos discontinuos.",
        "teacher_coverage_not_open_ended": "La asignación docente final debe quedar abierta.",
    }
    blockers.extend({
        "category": key if key in coverage_messages else "draft_validation",
        "count": count,
        "message": coverage_messages.get(key, key),
    } for key, count in sorted(validation_counts.items()))
    blockers.extend(_retroactive_blockers(db, draft, effective_from))
    content = _canonical_content(draft, effective_from, sequence)
    assignment_count = sum(len(block["assignments"]) for block in content["blocks"])
    return {
        "draft_id": draft.id,
        "program_id": draft.program_id,
        "academic_period": draft.academic_period,
        "effective_from": effective_from,
        "sequence": sequence,
        "digest": _digest(content),
        "can_publish": not blockers,
        "block_count": len(content["blocks"]),
        "assignment_count": assignment_count,
        "blockers": blockers,
        "warnings": OPERATIONAL_WARNINGS,
        "diff": _diff(db, draft, effective_from, content["blocks"]),
    }


def publish(
    db: Session,
    draft_id: int,
    effective_from: date,
    preview_digest: str,
    user_id: int,
    before_commit: Callable[[AcademicSchedulePublication], None] | None = None,
) -> AcademicSchedulePublication:
    preview = preview_publication(db, draft_id, effective_from, lock=True)
    if preview["blockers"]:
        raise HTTPException(409, detail={
            "message": "La publicación está bloqueada.", "blockers": preview["blockers"]
        })
    if preview["digest"] != preview_digest:
        raise HTTPException(
            409,
            detail="El borrador o la secuencia cambió desde la vista previa. Genere una nueva vista previa.",
        )
    draft = _draft_graph(db, draft_id, lock=False)
    publication = AcademicSchedulePublication(
        program_id=draft.program_id,
        academic_period=draft.academic_period,
        effective_from=effective_from,
        sequence=preview["sequence"],
        content_digest=preview["digest"],
        source_draft_id=draft.id,
        created_by=user_id,
    )
    try:
        db.add(publication)
        db.flush()
        for block in sorted(draft.blocks, key=lambda item: item.id):
            snapshot = AcademicSchedulePublishedBlock(
                publication_id=publication.id,
                source_block_id=block.id,
                source_offering_id=block.offering_id,
                source_subject_id=block.offering.subject_id,
                source_group_id=block.group_id,
                source_classroom_id=block.classroom_id,
                subject_code=block.offering.subject.code,
                subject_name=block.offering.subject.name,
                group_code=block.group.code,
                semester=block.group.semester,
                classroom_code=block.classroom.code,
                classroom_name=block.classroom.name,
                activity_type=block.activity_type,
                weekday=block.weekday,
                start_time=block.start_time,
                end_time=block.end_time,
                notes=None,
            )
            db.add(snapshot)
            db.flush()
            for assignment in _relevant_assignments(block, effective_from):
                db.add(AcademicSchedulePublishedAssignment(
                    publication_block_id=snapshot.id,
                    source_assignment_id=assignment.id,
                    teacher_ci=assignment.teacher_ci,
                    teacher_name=assignment.teacher.full_name,
                    effective_from=assignment.effective_from,
                    effective_to=assignment.effective_to,
                ))
        draft.status = "published"
        db.flush()
        if before_commit:
            before_commit(publication)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            detail="Otra publicación ganó la carrera o el borrador ya fue publicado. Genere una nueva vista previa.",
        ) from exc
    return get_publication(db, publication.id)


def list_publications(
    db: Session, program_id: int | None = None, academic_period: str | None = None
) -> list[AcademicSchedulePublication]:
    query = _publication_query(db)
    if program_id is not None:
        query = query.filter(AcademicSchedulePublication.program_id == program_id)
    if academic_period:
        query = query.filter(AcademicSchedulePublication.academic_period == academic_period.strip())
    return query.order_by(
        AcademicSchedulePublication.effective_from.desc(),
        AcademicSchedulePublication.sequence.desc(),
    ).limit(500).all()


def get_publication(db: Session, publication_id: int) -> AcademicSchedulePublication:
    publication = _publication_query(db).filter(
        AcademicSchedulePublication.id == publication_id
    ).first()
    if publication is None:
        raise HTTPException(404, detail="No se encontró la publicación de horario solicitada.")
    publication.blocks.sort(key=lambda block: (block.weekday, block.start_time, block.id))
    for block in publication.blocks:
        block.assignments.sort(key=lambda item: (item.effective_from, item.id))
    return publication


def clone_publication(
    db: Session,
    publication_id: int,
    name: str,
    before_commit: Callable[[AcademicScheduleDraft], None] | None = None,
) -> AcademicScheduleDraft:
    publication = get_publication(db, publication_id)
    normalized_name = academic._ensure_active_draft_name(
        db, publication.program_id, publication.academic_period, name
    )
    draft = AcademicScheduleDraft(
        program_id=publication.program_id,
        academic_period=publication.academic_period,
        name=name,
        normalized_name=normalized_name,
        status="draft",
    )
    try:
        db.add(draft)
        db.flush()
        for source in publication.blocks:
            block = AcademicScheduleBlock(
                draft_id=draft.id,
                offering_id=source.source_offering_id,
                group_id=source.source_group_id,
                classroom_id=source.source_classroom_id,
                activity_type=source.activity_type,
                weekday=source.weekday,
                start_time=source.start_time,
                end_time=source.end_time,
            )
            db.add(block)
            db.flush()
            for assignment in source.assignments:
                db.add(AcademicScheduleAssignment(
                    block_id=block.id,
                    teacher_ci=assignment.teacher_ci,
                    effective_from=assignment.effective_from,
                    effective_to=assignment.effective_to,
                ))
        if before_commit:
            before_commit(draft)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="No se pudo clonar la publicación como borrador.") from exc
    return db.query(AcademicScheduleDraft).options(
        joinedload(AcademicScheduleDraft.program)
    ).filter(AcademicScheduleDraft.id == draft.id).one()
