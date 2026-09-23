from __future__ import annotations

from datetime import date, time, timedelta
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload

from app.models.academic_management import (
    AcademicGroup,
    AcademicProgram,
    AcademicScheduleAssignment,
    AcademicScheduleBlock,
    AcademicScheduleDraft,
    AcademicSubject,
    Classroom,
    SubjectOffering,
    TeacherAvailability,
)
from app.models.teacher import Teacher

ModelT = TypeVar("ModelT")

ENTITY_LABELS = {
    AcademicProgram: "programa académico",
    AcademicSubject: "asignatura",
    SubjectOffering: "oferta académica",
    AcademicGroup: "grupo académico",
    Classroom: "aula",
    TeacherAvailability: "bloque de disponibilidad",
    AcademicScheduleDraft: "borrador de horario",
    AcademicScheduleBlock: "bloque de horario",
    AcademicScheduleAssignment: "asignación docente",
}


def list_catalog(db: Session, model: type[ModelT], search: str | None = None) -> list[ModelT]:
    query = db.query(model)
    if search and hasattr(model, "code") and hasattr(model, "name"):
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(model.code.ilike(pattern), model.name.ilike(pattern)))
    if model is SubjectOffering:
        query = query.options(joinedload(SubjectOffering.subject), joinedload(SubjectOffering.program))
    elif model is AcademicGroup:
        query = query.options(joinedload(AcademicGroup.program))
    return query.order_by(model.id.desc()).limit(500).all()


def get_or_404(db: Session, model: type[ModelT], entity_id: int) -> ModelT:
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"No se encontró el {ENTITY_LABELS[model]} solicitado.")
    return entity


def ensure_references(db: Session, values: dict[str, Any]) -> None:
    if "program_id" in values:
        program = db.get(AcademicProgram, values["program_id"])
        if program is None or not program.active:
            raise HTTPException(409, detail="El programa académico no existe o está inactivo.")
    if "subject_id" in values:
        subject = db.get(AcademicSubject, values["subject_id"])
        if subject is None or not subject.active:
            raise HTTPException(409, detail="La asignatura no existe o está inactiva.")
    if "teacher_ci" in values and db.get(Teacher, values["teacher_ci"]) is None:
        raise HTTPException(404, detail="No se encontró el docente seleccionado.")


def create_entity(
    db: Session,
    model: type[ModelT],
    values: dict[str, Any],
    before_commit: Callable[[ModelT], None] | None = None,
) -> ModelT:
    ensure_references(db, values)
    entity = model(**values)
    try:
        db.add(entity)
        db.flush()
        if before_commit:
            before_commit(entity)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un {ENTITY_LABELS[model]} con la misma identidad.",
        ) from exc
    db.refresh(entity)
    return entity


def update_entity(
    db: Session,
    entity: Any,
    values: dict[str, Any],
    before_commit: Callable[[Any], None] | None = None,
) -> Any:
    ensure_references(db, values)
    try:
        for key, value in values.items():
            setattr(entity, key, value)
        db.flush()
        if before_commit:
            before_commit(entity)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un {ENTITY_LABELS[type(entity)]} con la misma identidad.",
        ) from exc
    db.refresh(entity)
    return entity


def deactivate_entity(
    db: Session,
    entity: Any,
    before_commit: Callable[[Any], None] | None = None,
) -> Any:
    if isinstance(entity, AcademicProgram):
        has_dependencies = db.query(SubjectOffering.id).filter(
            SubjectOffering.program_id == entity.id, SubjectOffering.active.is_(True)
        ).first() or db.query(AcademicGroup.id).filter(
            AcademicGroup.program_id == entity.id, AcademicGroup.active.is_(True)
        ).first()
        if has_dependencies:
            raise HTTPException(409, detail="No se puede desactivar el programa porque tiene ofertas o grupos activos.")
    elif isinstance(entity, AcademicSubject):
        if db.query(SubjectOffering.id).filter(
            SubjectOffering.subject_id == entity.id, SubjectOffering.active.is_(True)
        ).first():
            raise HTTPException(409, detail="No se puede desactivar la asignatura porque tiene ofertas activas.")
    try:
        entity.active = False
        db.flush()
        if before_commit:
            before_commit(entity)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pudo desactivar el {ENTITY_LABELS[type(entity)]}.",
        ) from exc
    db.refresh(entity)
    return entity


def ensure_availability_no_overlap(
    db: Session, values: dict[str, Any], exclude_id: int | None = None
) -> None:
    db.query(Teacher).filter(Teacher.ci == values["teacher_ci"]).with_for_update().first()
    query = db.query(TeacherAvailability.id).filter(
        TeacherAvailability.teacher_ci == values["teacher_ci"],
        TeacherAvailability.academic_period == values["academic_period"],
        TeacherAvailability.weekday == values["weekday"],
        TeacherAvailability.active.is_(True),
        TeacherAvailability.start_time < values["end_time"],
        TeacherAvailability.end_time > values["start_time"],
    )
    if exclude_id is not None:
        query = query.filter(TeacherAvailability.id != exclude_id)
    if query.first():
        raise HTTPException(
            409,
            detail="El bloque se superpone con otra disponibilidad activa del docente. Los bloques adyacentes sí están permitidos.",
        )


def list_availability(db: Session, teacher_ci: str, academic_period: str) -> list[TeacherAvailability]:
    return db.query(TeacherAvailability).options(joinedload(TeacherAvailability.teacher)).filter(
        TeacherAvailability.teacher_ci == teacher_ci,
        TeacherAvailability.academic_period == academic_period,
    ).order_by(TeacherAvailability.weekday, TeacherAvailability.start_time).limit(500).all()


def compatible_teachers(
    db: Session, academic_period: str, weekday: str, start_time: time, end_time: time
) -> list[Teacher]:
    if start_time >= end_time:
        raise HTTPException(422, detail="La hora de inicio debe ser anterior a la hora de fin.")
    return db.query(Teacher).join(TeacherAvailability).filter(
        TeacherAvailability.academic_period == academic_period,
        TeacherAvailability.weekday == weekday,
        TeacherAvailability.start_time <= start_time,
        TeacherAvailability.end_time >= end_time,
        TeacherAvailability.active.is_(True),
    ).distinct().order_by(Teacher.full_name).limit(500).all()


def _normalized_name(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _lock_row(db: Session, model: type[ModelT], entity_id: int) -> ModelT | None:
    return db.query(model).filter(model.id == entity_id).with_for_update().first()


def _lock_schedule_draft(
    db: Session,
    draft_id: int,
    additional_program_ids: set[int] | None = None,
) -> AcademicScheduleDraft | None:
    """Lock schedule mutations in the global lock order.

    The order is program(s) -> draft -> block(s) -> assignment(s) -> teacher(s).
    Draft creation and publication cloning lock the program before inserts.
    All update, archive, block, assignment, and publication paths enter here.
    A concurrent program move is rejected instead of acquiring a newly observed
    program after the draft lock, which would invert the global order.
    """
    observed_program_id = db.query(AcademicScheduleDraft.program_id).filter(
        AcademicScheduleDraft.id == draft_id
    ).scalar()
    if observed_program_id is None:
        return None
    program_ids = {observed_program_id, *(additional_program_ids or set())}
    db.query(AcademicProgram.id).filter(
        AcademicProgram.id.in_(program_ids)
    ).order_by(AcademicProgram.id).with_for_update().all()
    draft = _lock_row(db, AcademicScheduleDraft, draft_id)
    if draft is not None and draft.program_id != observed_program_id:
        db.rollback()
        raise HTTPException(
            409,
            detail="El programa del borrador cambió durante la operación. Vuelva a intentarlo.",
        )
    return draft


def _ensure_active_draft_name(
    db: Session,
    program_id: int,
    academic_period: str,
    name: str,
    exclude_id: int | None = None,
    lock_program: bool = True,
) -> str:
    if lock_program:
        _lock_row(db, AcademicProgram, program_id)
    normalized = _normalized_name(name)
    query = db.query(AcademicScheduleDraft.id).filter(
        AcademicScheduleDraft.program_id == program_id,
        AcademicScheduleDraft.academic_period == academic_period,
        AcademicScheduleDraft.normalized_name == normalized,
        AcademicScheduleDraft.status == "draft",
    )
    if exclude_id is not None:
        query = query.filter(AcademicScheduleDraft.id != exclude_id)
    if query.first():
        raise HTTPException(409, detail="Ya existe un borrador activo con el mismo nombre para el programa y período.")
    return normalized


def list_schedule_drafts(
    db: Session, program_id: int | None = None, academic_period: str | None = None
) -> list[AcademicScheduleDraft]:
    query = db.query(AcademicScheduleDraft).options(joinedload(AcademicScheduleDraft.program))
    if program_id is not None:
        query = query.filter(AcademicScheduleDraft.program_id == program_id)
    if academic_period:
        query = query.filter(AcademicScheduleDraft.academic_period == academic_period.strip())
    return query.order_by(AcademicScheduleDraft.updated_at.desc(), AcademicScheduleDraft.id.desc()).limit(500).all()


def create_schedule_draft(
    db: Session, values: dict[str, Any], before_commit: Callable[[AcademicScheduleDraft], None] | None = None
) -> AcademicScheduleDraft:
    ensure_references(db, values)
    values["normalized_name"] = _ensure_active_draft_name(
        db, values["program_id"], values["academic_period"], values["name"]
    )
    return create_entity(db, AcademicScheduleDraft, values, before_commit)


def update_schedule_draft(
    db: Session,
    draft_id: int,
    values: dict[str, Any],
    before_commit: Callable[[AcademicScheduleDraft], None] | None = None,
) -> AcademicScheduleDraft:
    draft = _lock_schedule_draft(db, draft_id, {values["program_id"]})
    if draft is None:
        raise HTTPException(404, detail="No se encontró el borrador de horario solicitado.")
    if draft.status != "draft":
        raise HTTPException(409, detail="Un borrador archivado no se puede modificar.")
    scope_changed = (
        draft.program_id != values["program_id"]
        or draft.academic_period != values["academic_period"]
    )
    if scope_changed and db.query(AcademicScheduleBlock.id).filter(
        AcademicScheduleBlock.draft_id == draft.id
    ).first():
        raise HTTPException(
            409, detail="No se puede cambiar el programa o período de un borrador que ya tiene bloques."
        )
    ensure_references(db, values)
    values["normalized_name"] = _ensure_active_draft_name(
        db,
        values["program_id"],
        values["academic_period"],
        values["name"],
        draft.id,
        lock_program=False,
    )
    return update_entity(db, draft, values, before_commit)


def archive_schedule_draft(
    db: Session,
    draft_id: int,
    before_commit: Callable[[AcademicScheduleDraft], None] | None = None,
) -> AcademicScheduleDraft:
    draft = _lock_schedule_draft(db, draft_id)
    if draft is None:
        raise HTTPException(404, detail="No se encontró el borrador de horario solicitado.")
    if draft.status == "archived":
        return draft
    if draft.status != "draft":
        raise HTTPException(409, detail="Un borrador publicado es inmutable y no se puede archivar.")
    try:
        draft.status = "archived"
        if before_commit:
            before_commit(draft)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="No se pudo archivar el borrador de horario.") from exc
    db.refresh(draft)
    return draft


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _schedule_block_query(db: Session):
    return db.query(AcademicScheduleBlock).options(
        joinedload(AcademicScheduleBlock.offering).joinedload(SubjectOffering.subject),
        joinedload(AcademicScheduleBlock.offering).joinedload(SubjectOffering.program),
        joinedload(AcademicScheduleBlock.group).joinedload(AcademicGroup.program),
        joinedload(AcademicScheduleBlock.classroom),
    )


def list_schedule_blocks(db: Session, draft_id: int) -> list[AcademicScheduleBlock]:
    get_or_404(db, AcademicScheduleDraft, draft_id)
    return _schedule_block_query(db).filter(
        AcademicScheduleBlock.draft_id == draft_id
    ).order_by(AcademicScheduleBlock.weekday, AcademicScheduleBlock.start_time).all()


def _validate_schedule_block(
    db: Session,
    draft: AcademicScheduleDraft,
    values: dict[str, Any],
    exclude_id: int | None = None,
) -> None:
    if draft.status != "draft":
        raise HTTPException(409, detail="Un borrador archivado no se puede modificar.")

    start = values["start_time"]
    end = values["end_time"]
    start_minutes, end_minutes = _minutes(start), _minutes(end)
    if start_minutes < 7 * 60 or end_minutes > 22 * 60:
        raise HTTPException(422, detail="El bloque debe estar entre las 07:00 y las 22:00.")
    if start.second or start.microsecond or end.second or end.microsecond or start_minutes % 30 or end_minutes % 30:
        raise HTTPException(422, detail="Las horas deben alinearse en intervalos de 30 minutos.")

    offering = db.get(SubjectOffering, values["offering_id"])
    group = db.get(AcademicGroup, values["group_id"])
    classroom = db.get(Classroom, values["classroom_id"])
    if offering is None or not offering.active:
        raise HTTPException(409, detail="La oferta académica no existe o está inactiva.")
    if group is None or not group.active:
        raise HTTPException(409, detail="El grupo académico no existe o está inactivo.")
    if classroom is None or not classroom.active:
        raise HTTPException(409, detail="El aula no existe o está inactiva.")
    if offering.program_id != draft.program_id or offering.academic_period != draft.academic_period:
        raise HTTPException(409, detail="La oferta no pertenece al programa y período del borrador.")
    if group.program_id != draft.program_id or group.academic_period != draft.academic_period:
        raise HTTPException(409, detail="El grupo no pertenece al programa y período del borrador.")
    if offering.semester != group.semester:
        raise HTTPException(409, detail="La oferta y el grupo deben pertenecer al mismo semestre.")
    if (
        group.expected_size is not None
        and classroom.capacity is not None
        and classroom.capacity < group.expected_size
    ):
        raise HTTPException(409, detail="La capacidad del aula es menor que el tamaño esperado del grupo.")

    configured_hours = offering.theory_hours if values["activity_type"] == "theory" else offering.practice_hours
    if configured_hours <= 0:
        raise HTTPException(409, detail="La oferta no tiene horas configuradas para este tipo de actividad.")
    existing = db.query(AcademicScheduleBlock).filter(
        AcademicScheduleBlock.draft_id == draft.id,
        AcademicScheduleBlock.offering_id == offering.id,
        AcademicScheduleBlock.group_id == group.id,
        AcademicScheduleBlock.activity_type == values["activity_type"],
    )
    if exclude_id is not None:
        existing = existing.filter(AcademicScheduleBlock.id != exclude_id)
    scheduled_minutes = sum(_minutes(item.end_time) - _minutes(item.start_time) for item in existing.all())
    if scheduled_minutes + end_minutes - start_minutes > configured_hours * 60:
        raise HTTPException(409, detail="El bloque excede las horas configuradas para la actividad.")

    overlap = db.query(AcademicScheduleBlock.id).filter(
        AcademicScheduleBlock.draft_id == draft.id,
        AcademicScheduleBlock.weekday == values["weekday"],
        AcademicScheduleBlock.start_time < end,
        AcademicScheduleBlock.end_time > start,
        or_(
            AcademicScheduleBlock.group_id == group.id,
            AcademicScheduleBlock.classroom_id == classroom.id,
        ),
    )
    if exclude_id is not None:
        overlap = overlap.filter(AcademicScheduleBlock.id != exclude_id)
    if overlap.first():
        raise HTTPException(409, detail="El grupo o el aula ya tiene un bloque superpuesto. Los bloques adyacentes sí están permitidos.")


def save_schedule_block(
    db: Session,
    draft_id: int,
    values: dict[str, Any],
    block_id: int | None = None,
    before_commit: Callable[[AcademicScheduleBlock], None] | None = None,
) -> AcademicScheduleBlock:
    draft = _lock_schedule_draft(db, draft_id)
    if draft is None:
        raise HTTPException(404, detail="No se encontró el borrador de horario solicitado.")
    block = None
    if block_id is not None:
        block = _lock_row(db, AcademicScheduleBlock, block_id)
        if block is None or block.draft_id != draft.id:
            raise HTTPException(404, detail="No se encontró el bloque de horario solicitado.")
        if db.query(AcademicScheduleAssignment.id).filter(
            AcademicScheduleAssignment.block_id == block.id
        ).first():
            raise HTTPException(
                409,
                detail="Quite explícitamente las asignaciones antes de modificar un bloque con historial docente.",
            )
    _validate_schedule_block(db, draft, values, block_id)
    if block is None:
        block = AcademicScheduleBlock(draft_id=draft.id, **values)
        db.add(block)
    else:
        for key, value in values.items():
            setattr(block, key, value)
    try:
        db.flush()
        if before_commit:
            before_commit(block)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="No se pudo guardar el bloque de horario.") from exc
    return _schedule_block_query(db).filter(AcademicScheduleBlock.id == block.id).one()


def delete_schedule_block(
    db: Session,
    draft_id: int,
    block_id: int,
    before_commit: Callable[[AcademicScheduleBlock], None] | None = None,
) -> None:
    draft = _lock_schedule_draft(db, draft_id)
    if draft is None:
        raise HTTPException(404, detail="No se encontró el borrador de horario solicitado.")
    if draft.status != "draft":
        raise HTTPException(409, detail="Un borrador archivado no se puede modificar.")
    block = _lock_row(db, AcademicScheduleBlock, block_id)
    if block is None or block.draft_id != draft.id:
        raise HTTPException(404, detail="No se encontró el bloque de horario solicitado.")
    if db.query(AcademicScheduleAssignment.id).filter(
        AcademicScheduleAssignment.block_id == block.id
    ).first():
        raise HTTPException(
            409,
            detail="Quite explícitamente el historial de asignaciones antes de eliminar el bloque.",
        )
    try:
        if before_commit:
            before_commit(block)
        db.delete(block)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="No se pudo eliminar el bloque de horario.") from exc


def _assignment_query(db: Session):
    return db.query(AcademicScheduleAssignment).options(
        joinedload(AcademicScheduleAssignment.teacher),
        joinedload(AcademicScheduleAssignment.block),
    )


def _assignment_response_ready(assignment: AcademicScheduleAssignment) -> AcademicScheduleAssignment:
    assignment.teacher_name = assignment.teacher.full_name
    return assignment


def _assignment_context(
    db: Session, draft_id: int, block_id: int, teacher_ci: str | None = None
) -> tuple[AcademicScheduleDraft, AcademicScheduleBlock, Teacher | None]:
    draft = _lock_schedule_draft(db, draft_id)
    if draft is None:
        raise HTTPException(404, detail="No se encontró el borrador de horario solicitado.")
    if draft.status != "draft":
        raise HTTPException(409, detail="Un borrador archivado no se puede modificar.")
    block = _lock_row(db, AcademicScheduleBlock, block_id)
    if block is None or block.draft_id != draft.id:
        raise HTTPException(404, detail="No se encontró el bloque de horario solicitado.")
    block = _schedule_block_query(db).filter(
        AcademicScheduleBlock.id == block_id,
        AcademicScheduleBlock.draft_id == draft.id,
    ).first()
    if not block.offering.active or not block.group.active or not block.classroom.active:
        raise HTTPException(409, detail="La oferta, el grupo y el aula del bloque deben permanecer activos.")
    teacher = None
    if teacher_ci is not None:
        teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci).with_for_update().first()
        if teacher is None:
            raise HTTPException(404, detail="No se encontró el docente seleccionado.")
    return draft, block, teacher


def _date_overlap_filters(
    model: type[AcademicScheduleAssignment], effective_from: date, effective_to: date | None
):
    filters = [or_(model.effective_to.is_(None), model.effective_to >= effective_from)]
    if effective_to is not None:
        filters.append(model.effective_from <= effective_to)
    return filters


def _ensure_teacher_availability(
    db: Session, draft: AcademicScheduleDraft, block: AcademicScheduleBlock, teacher_ci: str
) -> None:
    if not db.query(TeacherAvailability.id).filter(
        TeacherAvailability.teacher_ci == teacher_ci,
        TeacherAvailability.academic_period == draft.academic_period,
        TeacherAvailability.weekday == block.weekday,
        TeacherAvailability.start_time <= block.start_time,
        TeacherAvailability.end_time >= block.end_time,
        TeacherAvailability.active.is_(True),
    ).first():
        raise HTTPException(
            409,
            detail="El docente no tiene una disponibilidad activa que cubra completamente este bloque.",
        )


def _ensure_assignment_available(
    db: Session,
    draft: AcademicScheduleDraft,
    block: AcademicScheduleBlock,
    teacher_ci: str,
    effective_from: date,
    effective_to: date | None,
    exclude_assignment_ids: set[int] | None = None,
) -> None:
    excluded = exclude_assignment_ids or set()
    same_block = db.query(AcademicScheduleAssignment.id).filter(
        AcademicScheduleAssignment.block_id == block.id,
        *_date_overlap_filters(AcademicScheduleAssignment, effective_from, effective_to),
    )
    if excluded:
        same_block = same_block.filter(~AcademicScheduleAssignment.id.in_(excluded))
    if same_block.first():
        raise HTTPException(409, detail="El bloque ya tiene una asignación docente en ese intervalo efectivo.")

    other_block = aliased(AcademicScheduleBlock)
    conflict = db.query(AcademicScheduleAssignment.id).join(
        other_block, AcademicScheduleAssignment.block_id == other_block.id
    ).filter(
        AcademicScheduleAssignment.teacher_ci == teacher_ci,
        other_block.draft_id == draft.id,
        other_block.id != block.id,
        other_block.weekday == block.weekday,
        other_block.start_time < block.end_time,
        other_block.end_time > block.start_time,
        *_date_overlap_filters(AcademicScheduleAssignment, effective_from, effective_to),
    )
    if excluded:
        conflict = conflict.filter(~AcademicScheduleAssignment.id.in_(excluded))
    if conflict.first():
        raise HTTPException(
            409,
            detail="El docente ya está asignado a otro bloque superpuesto de este borrador durante ese intervalo.",
        )


def _commit_assignment(
    db: Session,
    assignment: AcademicScheduleAssignment,
    before_commit: Callable[[AcademicScheduleAssignment], None] | None,
) -> AcademicScheduleAssignment:
    try:
        db.add(assignment)
        db.flush()
        if before_commit:
            before_commit(assignment)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="No se pudo guardar la asignación docente.") from exc
    loaded = _assignment_query(db).filter(AcademicScheduleAssignment.id == assignment.id).one()
    return _assignment_response_ready(loaded)


def list_schedule_assignments(
    db: Session, draft_id: int, block_id: int
) -> list[AcademicScheduleAssignment]:
    draft = db.get(AcademicScheduleDraft, draft_id)
    block = db.get(AcademicScheduleBlock, block_id)
    if draft is None or block is None or block.draft_id != draft.id:
        raise HTTPException(404, detail="No se encontró el bloque de horario solicitado.")
    rows = _assignment_query(db).filter(
        AcademicScheduleAssignment.block_id == block.id
    ).order_by(AcademicScheduleAssignment.effective_from.desc(), AcademicScheduleAssignment.id.desc()).all()
    return [_assignment_response_ready(row) for row in rows]


def create_schedule_assignment(
    db: Session,
    draft_id: int,
    block_id: int,
    values: dict[str, Any],
    before_commit: Callable[[AcademicScheduleAssignment], None] | None = None,
) -> AcademicScheduleAssignment:
    draft, block, _teacher = _assignment_context(db, draft_id, block_id, values["teacher_ci"])
    _ensure_teacher_availability(db, draft, block, values["teacher_ci"])
    _ensure_assignment_available(
        db, draft, block, values["teacher_ci"], values["effective_from"], values["effective_to"]
    )
    return _commit_assignment(
        db, AcademicScheduleAssignment(block_id=block.id, **values), before_commit
    )


def replace_schedule_assignment(
    db: Session,
    draft_id: int,
    block_id: int,
    values: dict[str, Any],
    before_commit: Callable[[AcademicScheduleAssignment], None] | None = None,
) -> AcademicScheduleAssignment:
    draft, block, _teacher = _assignment_context(db, draft_id, block_id)
    cutover = values["effective_from"]
    if cutover == date.min:
        raise HTTPException(422, detail="La fecha de reemplazo no admite un día anterior válido.")
    same_start = db.query(AcademicScheduleAssignment.id).filter(
        AcademicScheduleAssignment.block_id == block.id,
        AcademicScheduleAssignment.effective_from == cutover,
    ).first()
    if same_start:
        raise HTTPException(
            409,
            detail="La fecha de reemplazo debe ser posterior al inicio de la asignación vigente; corrija o elimine explícitamente la fila iniciada ese día.",
        )
    previous_day = cutover - timedelta(days=1)
    prior = db.query(AcademicScheduleAssignment).filter(
        AcademicScheduleAssignment.block_id == block.id,
        AcademicScheduleAssignment.effective_from <= previous_day,
        or_(
            AcademicScheduleAssignment.effective_to.is_(None),
            AcademicScheduleAssignment.effective_to >= previous_day,
        ),
    ).order_by(AcademicScheduleAssignment.effective_from.desc()).with_for_update().first()
    if prior is None:
        raise HTTPException(
            409, detail="No existe una asignación activa inmediatamente antes de la fecha de reemplazo."
        )
    teacher = db.query(Teacher).filter(
        Teacher.ci == values["teacher_ci"]
    ).with_for_update().first()
    if teacher is None:
        raise HTTPException(404, detail="No se encontró el docente seleccionado.")
    if prior.teacher_ci == values["teacher_ci"]:
        raise HTTPException(409, detail="El docente seleccionado ya es el docente vigente del bloque.")
    _ensure_teacher_availability(db, draft, block, values["teacher_ci"])
    _ensure_assignment_available(
        db,
        draft,
        block,
        values["teacher_ci"],
        values["effective_from"],
        values["effective_to"],
        {prior.id},
    )
    prior.effective_to = previous_day
    replacement = AcademicScheduleAssignment(block_id=block.id, **values)
    try:
        db.add(replacement)
        db.flush()
        if before_commit:
            before_commit(replacement)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="No se pudo reemplazar la asignación docente.") from exc
    loaded = _assignment_query(db).filter(AcademicScheduleAssignment.id == replacement.id).one()
    return _assignment_response_ready(loaded)


def correct_schedule_assignment(
    db: Session,
    draft_id: int,
    block_id: int,
    assignment_id: int,
    values: dict[str, Any],
    before_commit: Callable[[AcademicScheduleAssignment], None] | None = None,
) -> AcademicScheduleAssignment:
    draft, block, _teacher = _assignment_context(db, draft_id, block_id)
    assignment = db.query(AcademicScheduleAssignment).filter(
        AcademicScheduleAssignment.id == assignment_id,
        AcademicScheduleAssignment.block_id == block.id,
    ).with_for_update().first()
    if assignment is None:
        raise HTTPException(404, detail="No se encontró la asignación docente solicitada.")
    _ensure_teacher_availability(db, draft, block, assignment.teacher_ci)
    _ensure_assignment_available(
        db,
        draft,
        block,
        assignment.teacher_ci,
        values["effective_from"],
        values["effective_to"],
        {assignment.id},
    )
    assignment.effective_from = values["effective_from"]
    assignment.effective_to = values["effective_to"]
    return _commit_assignment(db, assignment, before_commit)


def delete_schedule_assignment(
    db: Session,
    draft_id: int,
    block_id: int,
    assignment_id: int,
    before_commit: Callable[[AcademicScheduleAssignment], None] | None = None,
) -> None:
    _draft, block, _teacher = _assignment_context(db, draft_id, block_id)
    assignment = db.query(AcademicScheduleAssignment).filter(
        AcademicScheduleAssignment.id == assignment_id,
        AcademicScheduleAssignment.block_id == block.id,
    ).with_for_update().first()
    if assignment is None:
        raise HTTPException(404, detail="No se encontró la asignación docente solicitada.")
    try:
        if before_commit:
            before_commit(assignment)
        db.delete(assignment)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="No se pudo eliminar la asignación docente.") from exc


def compatible_schedule_teachers(
    db: Session,
    draft_id: int,
    block_id: int,
    effective_from: date,
    effective_to: date | None,
    search: str | None,
    page: int,
    per_page: int,
) -> dict[str, Any]:
    draft = db.get(AcademicScheduleDraft, draft_id)
    block = db.get(AcademicScheduleBlock, block_id)
    if draft is None or block is None or block.draft_id != draft.id:
        raise HTTPException(404, detail="No se encontró el bloque de horario solicitado.")
    availability = db.query(TeacherAvailability.teacher_ci).filter(
        TeacherAvailability.teacher_ci == Teacher.ci,
        TeacherAvailability.academic_period == draft.academic_period,
        TeacherAvailability.weekday == block.weekday,
        TeacherAvailability.start_time <= block.start_time,
        TeacherAvailability.end_time >= block.end_time,
        TeacherAvailability.active.is_(True),
    ).exists()
    other_block = aliased(AcademicScheduleBlock)
    conflict = db.query(AcademicScheduleAssignment.id).join(
        other_block, AcademicScheduleAssignment.block_id == other_block.id
    ).filter(
        AcademicScheduleAssignment.teacher_ci == Teacher.ci,
        other_block.draft_id == draft.id,
        other_block.id != block.id,
        other_block.weekday == block.weekday,
        other_block.start_time < block.end_time,
        other_block.end_time > block.start_time,
        *_date_overlap_filters(AcademicScheduleAssignment, effective_from, effective_to),
    ).exists()
    same_block_teacher = db.query(AcademicScheduleAssignment.id).filter(
        AcademicScheduleAssignment.teacher_ci == Teacher.ci,
        AcademicScheduleAssignment.block_id == block.id,
        *_date_overlap_filters(AcademicScheduleAssignment, effective_from, effective_to),
    ).exists()
    query = db.query(Teacher).filter(availability, ~conflict, ~same_block_teacher)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Teacher.full_name.ilike(pattern), Teacher.ci.ilike(pattern)))
    total = query.count()
    items = query.order_by(Teacher.full_name, Teacher.ci).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def schedule_workload_summary(
    db: Session, draft_id: int, reference_date: date
) -> dict[str, Any]:
    if db.get(AcademicScheduleDraft, draft_id) is None:
        raise HTTPException(404, detail="No se encontró el borrador de horario solicitado.")
    rows = db.query(AcademicScheduleAssignment, AcademicScheduleBlock, Teacher).join(
        AcademicScheduleBlock, AcademicScheduleAssignment.block_id == AcademicScheduleBlock.id
    ).join(Teacher, AcademicScheduleAssignment.teacher_ci == Teacher.ci).filter(
        AcademicScheduleBlock.draft_id == draft_id,
        AcademicScheduleAssignment.effective_from <= reference_date,
        or_(
            AcademicScheduleAssignment.effective_to.is_(None),
            AcademicScheduleAssignment.effective_to >= reference_date,
        ),
    ).all()
    totals: dict[str, dict[str, Any]] = {}
    for _assignment, block, teacher in rows:
        item = totals.setdefault(teacher.ci, {
            "teacher_ci": teacher.ci,
            "teacher_name": teacher.full_name,
            "theory_minutes_week": 0,
            "practice_minutes_week": 0,
            "total_minutes_week": 0,
        })
        minutes = _minutes(block.end_time) - _minutes(block.start_time)
        item[f"{block.activity_type}_minutes_week"] += minutes
        item["total_minutes_week"] += minutes
    return {
        "draft_id": draft_id,
        "reference_date": reference_date,
        "items": sorted(totals.values(), key=lambda item: (item["teacher_name"], item["teacher_ci"])),
    }
