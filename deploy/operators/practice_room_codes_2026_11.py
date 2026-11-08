"""One-off operator: move three II/2026 practice blocks to their real classrooms.

What it does, in one controlled order (see the ODD task practice-room-codes, P1):

1. Preconditions (fail closed, nothing is written if any fails), including that each target room is
   free at the moved slot: no confirmed reservation from the effective date on, no class of another
   program's effective publication, and no other block of publication 5 overlapping it.
2. Clone academic schedule publication 5 into a draft named "Prácticas — aulas corregidas desde <date>".
3. Set ``classroom_id`` on exactly three draft blocks (wrong code -> real room, see ``MOVES``).
4. Prove the draft equals publication 5 block by block and assignment by assignment, except for
   the three classrooms. Any other difference aborts.
5. Publish the draft with the requested effective date.
6. Verify the new publication and that ``effective_schedule_slots`` resolves publication 5 the
   day before the effective date and the new publication from that date on.
7. Deactivate the three wrong classrooms through the same service path and audit entry as
   ``POST /api/admin/academic-management/classrooms/{id}/deactivate``.
8. Print a summary.

Usage (production, inside the backend container; no envelope or personal data is needed)::

    docker exec -i sipad-backend-1 python - fingerprint < deploy/operators/practice_room_codes_2026_11.py
    docker exec -i sipad-backend-1 python - preview --effective-from YYYY-MM-DD \\
        < deploy/operators/practice_room_codes_2026_11.py
    docker exec -i sipad-backend-1 python - apply --effective-from YYYY-MM-DD \\
        < deploy/operators/practice_room_codes_2026_11.py

``--effective-from`` is required for ``preview`` and ``apply`` and must be strictly after today in
Bolivia, so attendance already captured for today keeps publication 5. ``--admin-user-id N`` selects
the actor of the audit trail (default: the lowest-id active admin). ``fingerprint`` is read-only: it
hashes publication 5, the row counts of the published tables, the practice attendance logs, the
practice planillas and the billing publications, so a before/after comparison proves nothing else moved.

Transactions: every service commits internally, so the whole run happens on one connection inside an
outer transaction (the session joins it with ``create_savepoint``). ``preview`` rolls that transaction
back at the end; ``apply`` commits it once (all or nothing). Re-running ``apply`` detects the draft
(by name), the publication (draft + effective date) and the deactivated rooms, and changes nothing.
Nothing is retried. No SQL update is written against a published table: published rows are only
created by the publication service.

GUARD BYPASS (deliberate, authorized): publishing goes through ``_materialize_publication`` with the
sequence and digest computed by ``preview_publication`` (exactly what ``publish()`` does), instead of
``publish()`` itself. ``publish()`` refuses this draft because historical II/2026 teacher availability
was never recorded; publications 1-3 and 5 were created the same way (policy
``historical_availability_not_recorded``). The bypass is narrow: the only blocker tolerated is the
availability message, and its count must equal the number of draft assignments without an active
availability that covers their block, recomputed from the data. The date is in the future, so
retroactive blockers cannot appear; any other blocker or count aborts. The draft must contain only
practice blocks. For the same reason as in the precedent (``save_schedule_block`` refuses blocks that
have assignments) ``classroom_id`` is set directly on the three draft blocks, after validating the
move with the service's own block validator (capacity, overlap, active room).

SIDE EFFECTS: from the effective date the practice payroll sources and attendance keys come from the
new publication (new published assignment ids); the days before keep publication 5. Nothing in
October or earlier planillas, attendance or billing is touched: publications 1-3 and 5 stay immutable.
Deactivating a classroom has no cascade; existing reservations of those rooms are only reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_management import (
    AcademicGroup,
    AcademicScheduleBlock,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    Classroom,
    TeacherAvailability,
)
from app.models.classroom_reservation import ClassroomReservation
from app.models.user import User
from app.schemas.academic_management import ScheduleBlockUpdate
from app.services import academic_management_service as academic
from app.services import academic_schedule_publication_service as publication_service
from app.services import app_settings_service
from app.services.effective_schedule_service import effective_schedule_slots

PERIOD = "II/2026"
SOURCE_PUBLICATION_ID = 5
SOURCE_EFFECTIVE_FROM = date(2026, 9, 21)
EXPECTED_BLOCK_COUNT = 33
BOLIVIA = ZoneInfo("America/La_Paz")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
CATALOG_SYNC_HINT = (
    "Ejecute primero la sincronización del catálogo de aulas (administración → catálogo de aulas → aplicar) y repita."
)
AVAILABILITY_MESSAGE = "El docente no tiene una disponibilidad activa que cubra completamente este bloque."
ROOM_FIELDS = ("classroom_id", "classroom_code", "classroom_name")


@dataclass(frozen=True)
class RoomMove:
    """A source block of publication 5, identified by its content, and the room it must move to."""

    wrong_code: str
    subject_name: str
    group_code: str
    weekday: str
    start_time: time
    end_time: time
    target_code: str


MOVES = (
    RoomMove("COB-NUEVO-P3-A1", "Anatomía Humana I", "T-01", "thursday", time(15, 10), time(17, 25), "COB-ANTIGUO-P1-A1"),
    RoomMove("COB-ANTIGUO-P3-A20", "Introducción a la Cirugía I", "N-01", "wednesday", time(19, 10), time(22, 20), "COB-NUEVO-P3-A20"),
    RoomMove("COB-ANTIGUO-P4-A26", "Anatomía Humana I", "N-02", "friday", time(17, 30), time(19, 55), "COB-NUEVO-P4-A26"),
)


def say(line: str = "") -> None:
    print(line, flush=True)


class OperatorError(RuntimeError):
    """The operation cannot continue; the caller rolls everything back."""


class PreconditionError(OperatorError):
    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("; ".join(failures))


# ── Pure helpers ──────────────────────────────────────────────────────────────

def bolivia_today() -> date:
    return datetime.now(BOLIVIA).date()


def draft_name(effective_from: date) -> str:
    return f"Prácticas — aulas corregidas desde {effective_from.isoformat()}"


def block_key(item: dict[str, Any]) -> tuple[Any, ...]:
    """Identity of a canonical block dict inside one publication (the service's own block key)."""
    return publication_service._block_key(item)


def compare_blocks(
    old: list[dict[str, Any]], new: list[dict[str, Any]], moves: dict[tuple[Any, ...], tuple[str, str]],
) -> list[str]:
    """Differences between two canonical block lists; only the moves' room fields may differ.

    ``moves`` maps a block key to the (classroom code, classroom name) it must carry in ``new``.
    Every other field of every block, including each assignment, must be equal.
    """
    diffs: list[str] = []
    indexed: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}
    for label, items in (("origen", old), ("nuevo", new)):
        keyed: dict[tuple[Any, ...], dict[str, Any]] = {}
        for item in items:
            key = block_key(item)
            if key in keyed:
                diffs.append(f"{label}: bloque duplicado {key}")
            keyed[key] = item
        indexed[label] = keyed
    if len(old) != len(new):
        diffs.append(f"cantidad de bloques: origen {len(old)}, nuevo {len(new)}")
    for key in moves:
        if key not in indexed["origen"]:
            diffs.append(f"movimiento esperado sin bloque de origen: {key}")
    for key in sorted(set(indexed["origen"]) | set(indexed["nuevo"]), key=str):
        before, after = indexed["origen"].get(key), indexed["nuevo"].get(key)
        if before is None or after is None:
            diffs.append(f"bloque {key} solo existe en {'nuevo' if before is None else 'origen'}")
            continue
        for field in sorted((set(before) | set(after)) - set(ROOM_FIELDS)):
            if before.get(field) != after.get(field):
                diffs.append(f"bloque {key} difiere en {field}: {before.get(field)!r} -> {after.get(field)!r}")
        if key in moves:
            if (after["classroom_code"], after["classroom_name"]) != moves[key]:
                diffs.append(
                    f"bloque {key} difiere en aula: se esperaba {moves[key]!r}, "
                    f"tiene {(after['classroom_code'], after['classroom_name'])!r}"
                )
            if after["classroom_id"] == before["classroom_id"]:
                diffs.append(f"bloque {key} difiere en classroom_id: no cambió de aula")
        else:
            for field in ROOM_FIELDS:
                if before.get(field) != after.get(field):
                    diffs.append(f"bloque {key} difiere en {field}: {before.get(field)!r} -> {after.get(field)!r}")
    return diffs


# ── Preconditions ─────────────────────────────────────────────────────────────

@dataclass
class MovePlan:
    move: RoomMove
    source_block: dict[str, Any]
    wrong_room_id: int
    target_room_id: int
    target_code: str
    target_name: str

    @property
    def key(self) -> tuple[Any, ...]:
        return block_key(self.source_block)


@dataclass
class Facts:
    program_id: int
    old_blocks: list[dict[str, Any]]
    plans: list[MovePlan]
    effective_from: date
    draft: AcademicScheduleDraft | None
    publication: AcademicSchedulePublication | None

    @property
    def expected_moves(self) -> dict[tuple[Any, ...], tuple[str, str]]:
        return {plan.key: (plan.target_code, plan.target_name) for plan in self.plans}


def active_draft_references(db: Session, room_ids: set[int], exclude_draft_id: int | None = None) -> list[str]:
    query = (
        db.query(AcademicScheduleDraft.name, Classroom.code)
        .join(AcademicScheduleBlock, AcademicScheduleBlock.draft_id == AcademicScheduleDraft.id)
        .join(Classroom, Classroom.id == AcademicScheduleBlock.classroom_id)
        .filter(AcademicScheduleDraft.status == "draft", AcademicScheduleBlock.classroom_id.in_(room_ids))
    )
    if exclude_draft_id is not None:
        query = query.filter(AcademicScheduleDraft.id != exclude_draft_id)
    return sorted({f"el borrador activo «{name}» tiene bloques en el aula {code}" for name, code in query.all()})


def _overlaps(start: time, end: time, other_start: time, other_end: time) -> bool:
    """Half-open [start, end) overlap: back-to-back slots do not conflict."""
    return start < other_end and other_start < end


def target_room_conflicts(
    db: Session, move: RoomMove, target: Classroom, source_blocks: list[Any], program_id: int, effective_from: date,
) -> list[str]:
    """What would double-book ``target`` at the moved slot from ``effective_from`` on.

    The reservation service treats a published class as occupying its room by code, so the check
    looks at (a) confirmed reservations, (b) the effective class blocks of other programs and
    (c) the other blocks of the source publication that already use the room.
    """
    when = f"{move.weekday} {move.start_time:%H:%M}-{move.end_time:%H:%M}"
    weekday = list(WEEKDAYS).index(move.weekday)
    conflicts: list[str] = []
    for row in db.query(ClassroomReservation).filter(
        ClassroomReservation.classroom_id == target.id, ClassroomReservation.status == "confirmed",
        ClassroomReservation.reservation_date >= effective_from,
    ).order_by(ClassroomReservation.reservation_date, ClassroomReservation.start_time):
        if row.reservation_date.weekday() == weekday and _overlaps(
            move.start_time, move.end_time, row.start_time, row.end_time,
        ):
            conflicts.append(
                f"el aula {target.code} tiene una reserva confirmada el {row.reservation_date} "
                f"de {row.start_time:%H:%M} a {row.end_time:%H:%M} que se superpone con {when}"
            )
    effective = {}
    for publication in db.query(AcademicSchedulePublication).filter(
        AcademicSchedulePublication.academic_period == PERIOD, AcademicSchedulePublication.program_id != program_id,
        AcademicSchedulePublication.effective_from <= effective_from,
    ).order_by(
        AcademicSchedulePublication.effective_from.desc(), AcademicSchedulePublication.sequence.desc(),
        AcademicSchedulePublication.id.desc(),
    ):
        effective.setdefault(publication.program_id, publication)
    for publication in effective.values():
        for block in publication.blocks:
            if (block.classroom_code == target.code and block.weekday.lower() == move.weekday
                    and _overlaps(move.start_time, move.end_time, block.start_time, block.end_time)):
                conflicts.append(
                    f"el aula {target.code} tiene la clase «{block.subject_name}» {block.group_code} del programa "
                    f"{publication.program_id} (publicación {publication.id}) el {block.weekday} "
                    f"{block.start_time:%H:%M}-{block.end_time:%H:%M}, que se superpone con {when}"
                )
    for block in source_blocks:
        if (block.classroom_code == target.code and block.weekday.lower() == move.weekday
                and _overlaps(move.start_time, move.end_time, block.start_time, block.end_time)):
            conflicts.append(
                f"el aula {target.code} ya la usa «{block.subject_name}» {block.group_code} en la publicación "
                f"{SOURCE_PUBLICATION_ID} el {block.weekday} {block.start_time:%H:%M}-{block.end_time:%H:%M}, "
                f"que se superpone con {when}"
            )
    return conflicts


def check_preconditions(db: Session, effective_from: date, today: date) -> Facts:
    """Read-only checks. Raises PreconditionError listing every failure."""
    failures: list[str] = []
    active = app_settings_service.get_active_academic_period(db)
    if active != PERIOD:
        failures.append(f"el período académico activo es {active}; se esperaba {PERIOD}")

    source = db.get(AcademicSchedulePublication, SOURCE_PUBLICATION_ID)
    if source is None:
        raise PreconditionError(failures + [f"la publicación {SOURCE_PUBLICATION_ID} no existe"])
    if source.academic_period != PERIOD or source.effective_from != SOURCE_EFFECTIVE_FROM:
        failures.append(
            f"la publicación {source.id} es de {source.academic_period} con fecha efectiva {source.effective_from}; "
            f"se esperaba {PERIOD} / {SOURCE_EFFECTIVE_FROM}"
        )
    elif source.effective_from > today:
        failures.append(f"la publicación {source.id} aún no está vigente (fecha efectiva {source.effective_from})")
    program_id = source.program_id

    name = draft_name(effective_from)
    drafts = db.query(AcademicScheduleDraft).filter(
        AcademicScheduleDraft.program_id == program_id, AcademicScheduleDraft.academic_period == PERIOD,
        AcademicScheduleDraft.name == name,
    ).all()
    draft = drafts[0] if len(drafts) == 1 else None
    if len(drafts) > 1:
        failures.append(f"hay {len(drafts)} borradores llamados «{name}»; revisar a mano")
    ours = None
    if draft is not None:
        ours = db.query(AcademicSchedulePublication).filter(AcademicSchedulePublication.source_draft_id == draft.id).first()
        if draft.status == "archived":
            failures.append(f"el borrador «{name}» está archivado; revisar a mano")
        elif draft.status == "published" and ours is None:
            failures.append(f"el borrador «{name}» está publicado pero su publicación no existe")

    latest = db.query(AcademicSchedulePublication).filter(
        AcademicSchedulePublication.program_id == program_id, AcademicSchedulePublication.academic_period == PERIOD,
        *([AcademicSchedulePublication.id != ours.id] if ours is not None else []),
    ).order_by(
        AcademicSchedulePublication.effective_from.desc(), AcademicSchedulePublication.sequence.desc(),
        AcademicSchedulePublication.id.desc(),
    ).first()
    if latest is None or latest.id != SOURCE_PUBLICATION_ID:
        failures.append(
            f"la publicación {SOURCE_PUBLICATION_ID} no es la última publicación del programa y período "
            f"(última que no proviene de este operador: id {latest.id if latest else None}, "
            f"fecha efectiva {latest.effective_from if latest else None})"
        )
    if ours is not None:
        if ours.effective_from != effective_from:
            failures.append(
                f"este operador ya publicó la publicación {ours.id} con fecha efectiva {ours.effective_from}, "
                f"distinta de la solicitada ({effective_from})"
            )
    elif effective_from <= today:
        failures.append(
            f"la fecha efectiva {effective_from} debe ser estrictamente posterior a hoy en Bolivia ({today})"
        )

    blocks = sorted(source.blocks, key=lambda item: item.id)
    if len(blocks) != EXPECTED_BLOCK_COUNT:
        failures.append(f"la publicación {source.id} tiene {len(blocks)} bloques; se esperaban {EXPECTED_BLOCK_COUNT}")
    if any(block.activity_type != "practice" for block in blocks):
        failures.append(f"la publicación {source.id} contiene bloques que no son de práctica")

    plans: list[MovePlan] = []
    for move in MOVES:
        label = f"{move.wrong_code} / {move.subject_name} {move.group_code} {move.weekday} {move.start_time:%H:%M}-{move.end_time:%H:%M}"
        matches = [
            block for block in blocks
            if (block.classroom_code, block.subject_name, block.group_code, block.weekday.lower(),
                block.start_time, block.end_time)
            == (move.wrong_code, move.subject_name, move.group_code, move.weekday, move.start_time, move.end_time)
        ]
        if len(matches) != 1:
            failures.append(f"bloque origen {label}: aparece {len(matches)} veces en la publicación; se esperaba exactamente 1")
            continue
        block = matches[0]
        if any(other.id != block.id and other.classroom_code == move.wrong_code for other in blocks):
            failures.append(f"el aula {move.wrong_code} es usada por otro bloque de la publicación {source.id}")
        wrong = db.query(Classroom).filter(Classroom.code == move.wrong_code).first()
        if wrong is None or wrong.id != block.source_classroom_id:
            failures.append(f"el aula {move.wrong_code} no existe o no es la del bloque publicado")
        target = db.query(Classroom).filter(Classroom.code == move.target_code).first()
        if target is None:
            failures.append(f"el aula {move.target_code} no existe en el catálogo. {CATALOG_SYNC_HINT}")
            continue
        if not target.active:
            failures.append(f"el aula {move.target_code} está inactiva")
        group = db.get(AcademicGroup, block.source_group_id)
        if (group is not None and group.expected_size is not None and target.capacity is not None
                and target.capacity < group.expected_size):
            failures.append(
                f"la capacidad del aula {move.target_code} ({target.capacity}) es menor que el tamaño "
                f"esperado del grupo {group.code} ({group.expected_size})"
            )
        failures.extend(target_room_conflicts(db, move, target, blocks, program_id, effective_from))
        if wrong is not None:
            plans.append(MovePlan(
                move, publication_service._publication_block_dict(block), wrong.id, target.id, target.code, target.name,
            ))

    if len(plans) == len(MOVES):
        failures.extend(active_draft_references(
            db, {plan.wrong_room_id for plan in plans}, draft.id if draft is not None else None,
        ))
    if failures:
        raise PreconditionError(failures)
    return Facts(program_id, [publication_service._publication_block_dict(block) for block in blocks],
                 plans, effective_from, draft, ours)


# ── Steps ─────────────────────────────────────────────────────────────────────

def resolve_admin(db: Session, user_id: int | None) -> User:
    query = db.query(User).filter(User.role == "admin", User.is_active.is_(True))
    admin = query.filter(User.id == user_id).first() if user_id is not None else query.order_by(User.id).first()
    if admin is None:
        raise OperatorError("No hay un usuario administrador activo para el registro de auditoría.")
    return admin


def _audit(db: Session, admin: User, action: str, entity_type: str) -> Callable[[Any], None]:
    from app.routers.academic_management import _audit as router_audit  # same activity log as the UI
    return router_audit(db, None, admin, action, entity_type)


def draft_blocks(db: Session, draft: AcademicScheduleDraft) -> list[AcademicScheduleBlock]:
    return db.query(AcademicScheduleBlock).filter(AcademicScheduleBlock.draft_id == draft.id).order_by(
        AcademicScheduleBlock.id
    ).all()


def clone_step(db: Session, facts: Facts, admin: User) -> AcademicScheduleDraft:
    draft = publication_service.clone_publication(
        db, SOURCE_PUBLICATION_ID, draft_name(facts.effective_from),
        _audit(db, admin, "clone", "academic_schedule_draft"),
    )
    say(f"  cloned draft id={draft.id}")
    return draft


def move_step(db: Session, draft: AcademicScheduleDraft, facts: Facts, admin: User) -> None:
    blocks = draft_blocks(db, draft)
    if len(blocks) != EXPECTED_BLOCK_COUNT:
        raise OperatorError(f"El borrador tiene {len(blocks)} bloques; se esperaban {EXPECTED_BLOCK_COUNT}.")
    if any(block.activity_type != "practice" for block in blocks):
        raise OperatorError("El borrador contiene bloques que no son de práctica.")
    audit = _audit(db, admin, "update", "academic_schedule_block")
    for plan in facts.plans:
        source = plan.source_block
        matches = [
            block for block in blocks
            if (block.offering_id, block.group_id, block.weekday, block.start_time, block.end_time, block.activity_type)
            == (source["offering_id"], source["group_id"], source["weekday"], time.fromisoformat(source["start_time"]),
                time.fromisoformat(source["end_time"]), source["activity_type"])
        ]
        if len(matches) != 1:
            raise OperatorError(f"El bloque {plan.move.wrong_code} tiene {len(matches)} equivalentes en el borrador (se esperaba 1).")
        block = matches[0]
        label = f"{plan.move.subject_name} {plan.move.group_code} {plan.move.weekday}"
        if block.classroom_id == plan.target_room_id:
            say(f"  {label}: already in {plan.target_code}; skipped")
            continue
        if block.classroom_id != plan.wrong_room_id:
            raise OperatorError(f"El bloque {label} del borrador no está en el aula {plan.move.wrong_code} esperada.")
        values = {
            "offering_id": block.offering_id, "group_id": block.group_id, "classroom_id": plan.target_room_id,
            "activity_type": block.activity_type, "weekday": block.weekday,
            "start_time": block.start_time, "end_time": block.end_time,
        }
        try:
            ScheduleBlockUpdate(**values, academic_hours=block.academic_hours)
            academic._validate_schedule_block(db, draft, values, block.id)
        except HTTPException as exc:
            raise OperatorError(f"El bloque {label} no puede moverse a {plan.target_code}: {exc.detail}") from exc
        block.classroom_id = plan.target_room_id
        db.flush()
        audit(block)
        say(f"  {label}: {plan.move.wrong_code} -> {plan.target_code} ({plan.target_name})")
    db.commit()
    db.expire_all()


def diff_step(db: Session, draft: AcademicScheduleDraft, facts: Facts) -> None:
    graph = publication_service._draft_graph(db, draft.id, lock=False)
    new = [publication_service._canonical_block(block, facts.effective_from) for block in graph.blocks]
    diffs = compare_blocks(facts.old_blocks, new, facts.expected_moves)
    if diffs:
        raise OperatorError(
            f"El borrador difiere de la publicación {SOURCE_PUBLICATION_ID} más allá de las tres aulas:\n  - "
            + "\n  - ".join(diffs)
        )
    for plan in facts.plans:
        say(f"  moved: {plan.move.subject_name} {plan.move.group_code} {plan.move.weekday}: "
            f"{plan.move.wrong_code} -> {plan.target_code}")
    assignments = sum(len(item["assignments"]) for item in new)
    say(f"  no other difference with publication {SOURCE_PUBLICATION_ID}: {len(new)} blocks and {assignments} assignments compared")


def expected_availability_blockers(
    db: Session, graph: AcademicScheduleDraft, effective_from: date,
) -> set[tuple[str, int, str]]:
    """The only tolerated blocker: assignments with no active availability covering their block."""
    missing = 0
    for block in graph.blocks:
        for assignment in publication_service._relevant_assignments(block, effective_from):
            covered = db.query(TeacherAvailability.id).filter(
                TeacherAvailability.teacher_ci == assignment.teacher_ci,
                TeacherAvailability.academic_period == graph.academic_period,
                TeacherAvailability.weekday == block.weekday,
                TeacherAvailability.start_time <= block.start_time,
                TeacherAvailability.end_time >= block.end_time,
                TeacherAvailability.active.is_(True),
            ).first()
            missing += covered is None
    return {("draft_validation", missing, AVAILABILITY_MESSAGE)} if missing else set()


def publish_step(db: Session, draft: AcademicScheduleDraft, facts: Facts, admin: User) -> AcademicSchedulePublication:
    preview = publication_service.preview_publication(db, draft.id, facts.effective_from, lock=True)
    graph = publication_service._draft_graph(db, draft.id, lock=False)
    expected = expected_availability_blockers(db, graph, facts.effective_from)
    observed = {(b["category"], b["count"], b["message"]) for b in preview["blockers"]}
    say(f"  preview: blocks={preview['block_count']} assignments={preview['assignment_count']} "
        f"sequence={preview['sequence']} digest={preview['digest']} can_publish={preview['can_publish']}")
    for blocker in preview["blockers"]:
        tolerated = (blocker["category"], blocker["count"], blocker["message"]) in expected
        say(f"  blocker [{'tolerated' if tolerated else 'UNEXPECTED'}] {blocker['category']} x{blocker['count']}: {blocker['message']}")
    if observed != expected or len(preview["blockers"]) != len(observed):
        raise OperatorError(
            "Los bloqueos de la vista previa no son exactamente los esperados. "
            f"Inesperados: {sorted(observed - expected)}; ausentes: {sorted(expected - observed)}"
        )
    if preview["block_count"] != EXPECTED_BLOCK_COUNT or any(b.activity_type != "practice" for b in graph.blocks):
        raise OperatorError("La vista previa no tiene exactamente los bloques de práctica esperados.")
    try:
        publication = publication_service._materialize_publication(
            db, graph, facts.effective_from, preview["sequence"], preview["digest"], admin.id,
        )
        graph.status = "published"
        db.flush()
        _audit(db, admin, "publish", "academic_schedule_publication")(publication)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise OperatorError("No se pudo publicar: conflicto de integridad (¿otra publicación ganó la carrera?)") from exc
    say(f"  published publication id={publication.id} sequence={publication.sequence} effective_from={publication.effective_from}")
    return publication


def published_slot_ids(db: Session, facts: Facts, day: date, program_publications: set[int]) -> list[int]:
    slots = effective_schedule_slots(db, PERIOD, day, include_practice=True)
    return [slot.publication_id for slot in slots
            if slot.source_type == "published" and slot.publication_id in program_publications]


def verify_publication(db: Session, publication: AcademicSchedulePublication, facts: Facts) -> None:
    db.expire_all()
    publication = publication_service.get_publication(db, publication.id)
    if publication.effective_from != facts.effective_from:
        raise OperatorError(f"La publicación {publication.id} tiene fecha efectiva {publication.effective_from}.")
    if len(publication.blocks) != EXPECTED_BLOCK_COUNT:
        raise OperatorError(f"La publicación {publication.id} tiene {len(publication.blocks)} bloques; se esperaban {EXPECTED_BLOCK_COUNT}.")
    new = [publication_service._publication_block_dict(block) for block in publication.blocks]
    diffs = compare_blocks(facts.old_blocks, new, facts.expected_moves)
    if diffs:
        raise OperatorError("La publicación creada difiere de la publicación 5:\n  - " + "\n  - ".join(diffs))
    source = publication_service.get_publication(db, SOURCE_PUBLICATION_ID)
    if compare_blocks(facts.old_blocks, [publication_service._publication_block_dict(b) for b in source.blocks], {}):
        raise OperatorError(f"La publicación {SOURCE_PUBLICATION_ID} cambió durante la operación.")
    scope = {
        item.id for item in db.query(AcademicSchedulePublication).filter(
            AcademicSchedulePublication.program_id == facts.program_id, AcademicSchedulePublication.academic_period == PERIOD)
    }
    before = published_slot_ids(db, facts, facts.effective_from - timedelta(days=1), scope)
    after = published_slot_ids(db, facts, facts.effective_from, scope)
    if set(before) != {SOURCE_PUBLICATION_ID} or len(before) != EXPECTED_BLOCK_COUNT:
        raise OperatorError(f"El día anterior a {facts.effective_from} no resuelve solo la publicación {SOURCE_PUBLICATION_ID}.")
    if set(after) != {publication.id} or len(after) != EXPECTED_BLOCK_COUNT:
        raise OperatorError(f"Desde {facts.effective_from} no se resuelve solo la publicación {publication.id}.")
    say(f"  verified publication {publication.id}: {len(new)} blocks, only the three rooms differ from publication "
        f"{SOURCE_PUBLICATION_ID}; {facts.effective_from - timedelta(days=1)} resolves {SOURCE_PUBLICATION_ID}, "
        f"{facts.effective_from} resolves {publication.id}")


def deactivate_step(db: Session, facts: Facts, admin: User, today: date) -> list[str]:
    room_ids = {plan.wrong_room_id for plan in facts.plans}
    references = active_draft_references(db, room_ids)
    if references:
        raise OperatorError("No se desactivan las aulas: " + "; ".join(references))
    audit = _audit(db, admin, "deactivate", "classroom")
    deactivated: list[str] = []
    for plan in facts.plans:
        room = academic.get_or_404(db, Classroom, plan.wrong_room_id)
        reservations = db.query(ClassroomReservation.id).filter(
            ClassroomReservation.classroom_id == room.id, ClassroomReservation.status == "confirmed",
            ClassroomReservation.reservation_date >= today,
        ).count()
        if reservations:
            say(f"  WARNING {room.code} has {reservations} confirmed reservation(s) from today on (not touched)")
        if not room.active:
            say(f"  {room.code}: already inactive; skipped")
            continue
        academic.deactivate_entity(db, room, audit)
        deactivated.append(room.code)
        say(f"  deactivated {room.code}")
    return deactivated


# ── Orchestration ─────────────────────────────────────────────────────────────

def execute(db: Session, *, effective_from: date, admin_user_id: int | None) -> dict[str, Any]:
    try:
        return _execute(db, effective_from=effective_from, admin_user_id=admin_user_id)
    except HTTPException as exc:
        raise OperatorError(f"Un servicio rechazó la operación: {exc.detail}") from exc


def _execute(db: Session, *, effective_from: date, admin_user_id: int | None) -> dict[str, Any]:
    today = bolivia_today()
    say("[1/7] preconditions")
    facts = check_preconditions(db, effective_from, today)
    admin = resolve_admin(db, admin_user_id)
    say(f"  ok. publication {SOURCE_PUBLICATION_ID} (program {facts.program_id}) has {len(facts.old_blocks)} practice blocks; "
        f"effective from {effective_from} (Bolivia today {today}); actor admin user id={admin.id}")
    say(f"  state: draft={'id ' + str(facts.draft.id) if facts.draft else 'none'}, "
        f"publication={'id ' + str(facts.publication.id) if facts.publication else 'none'}")

    publication = facts.publication
    draft = facts.draft
    say("[2/7] clone publication into a draft")
    if draft is None:
        draft = clone_step(db, facts, admin)
    else:
        say(f"  draft id={draft.id} already exists ({draft.status}); skipped")

    say("[3/7] move the three blocks")
    if publication is None:
        move_step(db, draft, facts, admin)
    else:
        say("  publication already exists; skipped")

    say("[4/7] prove only the rooms differ from the published schedule")
    if publication is None:
        diff_step(db, draft, facts)
    else:
        say("  publication already exists; verified in step 6")

    say("[5/7] publish")
    if publication is None:
        publication = publish_step(db, draft, facts, admin)
    else:
        say(f"  publication id={publication.id} already published; skipped")

    say("[6/7] verify the publication")
    verify_publication(db, publication, facts)

    say("[7/7] deactivate the wrong classrooms")
    deactivated = deactivate_step(db, facts, admin, today)

    return {
        "draft_id": draft.id, "publication_id": publication.id, "publication_sequence": publication.sequence,
        "effective_from": str(publication.effective_from),
        "moves": [f"{plan.move.wrong_code} -> {plan.target_code}" for plan in facts.plans],
        "deactivated_rooms": deactivated,
    }


# ── Read-only fingerprint ─────────────────────────────────────────────────────

def _digest(parts: list[Any]) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def fingerprint(db: Session) -> list[tuple[str, int, str]]:
    """(name, row count, sha256 or '-') for what the operation must not change, plus counts of what it adds."""
    entries: list[tuple[str, int, str]] = []

    def hashed(name: str, query: str, params: dict[str, Any] | None = None) -> None:
        rows = [dict(row._mapping) for row in db.execute(text(query), params or {})]
        entries.append((name, len(rows), _digest(rows)))

    pub = {"p": SOURCE_PUBLICATION_ID}
    hashed(f"publication {SOURCE_PUBLICATION_ID} (row)", "SELECT * FROM academic_schedule_publications WHERE id = :p", pub)
    hashed(f"publication {SOURCE_PUBLICATION_ID} blocks (all columns)",
           "SELECT * FROM academic_schedule_published_blocks WHERE publication_id = :p ORDER BY id", pub)
    hashed(f"publication {SOURCE_PUBLICATION_ID} assignments (all columns)",
           "SELECT a.* FROM academic_schedule_published_assignments a JOIN academic_schedule_published_blocks b "
           "ON b.id = a.publication_block_id WHERE b.publication_id = :p ORDER BY a.id", pub)
    for table in ("academic_schedule_publications", "academic_schedule_published_blocks",
                  "academic_schedule_published_assignments", "academic_schedule_drafts",
                  "academic_schedule_blocks", "academic_schedule_assignments"):
        entries.append((table, db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar(), "-"))
    for table in ("practice_attendance_logs", "practice_planilla_outputs", "billing_publications",
                  "billing_publication_revisions"):
        hashed(f"{table} (all columns as stored)", f"SELECT * FROM {table} ORDER BY id")
    return entries


def room_state(db: Session) -> list[str]:
    codes = [move.wrong_code for move in MOVES] + [move.target_code for move in MOVES]
    rooms = {room.code: room for room in db.query(Classroom).filter(Classroom.code.in_(codes))}
    return [f"room {code}: " + (f"active={rooms[code].active}" if code in rooms else "missing") for code in codes]


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="II/2026 practice room codes correction")
    parser.add_argument("mode", choices=["preview", "apply", "fingerprint"])
    parser.add_argument("--effective-from", type=date.fromisoformat, metavar="YYYY-MM-DD",
                        help="effective date of the new publication; strictly after today in Bolivia")
    parser.add_argument("--admin-user-id", type=int, help="actor for the audit trail (default: lowest-id active admin)")
    args = parser.parse_args(argv)
    if args.mode != "fingerprint" and args.effective_from is None:
        parser.error("--effective-from is required for preview and apply")

    from app.database import SessionLocal, engine

    apply = args.mode == "apply"
    say(f"mode={args.mode} database={engine.url.render_as_string(hide_password=True)}")
    with engine.connect() as connection:
        outer = connection.begin()
        db = SessionLocal(bind=connection, join_transaction_mode="create_savepoint")
        try:
            if args.mode == "fingerprint":
                for name, count, digest in fingerprint(db):
                    say(f"{digest}  rows={count:<5} {name}")
                for line in room_state(db):
                    say(line)
                outer.rollback()
                return 0
            summary = execute(db, effective_from=args.effective_from, admin_user_id=args.admin_user_id)
            db.commit()
            if apply:
                outer.commit()
            else:
                outer.rollback()
        except Exception as exc:  # report, roll everything back, re-raise unexpected errors
            outer.rollback()
            if isinstance(exc, PreconditionError):
                say("PRECONDITIONS FAILED (nothing was written):")
                for failure in exc.failures:
                    say(f"  - {failure}")
            else:
                say(f"FAILED, everything rolled back: {type(exc).__name__}: {exc}")
                if not isinstance(exc, OperatorError):
                    raise
            return 1
        finally:
            db.close()
    say()
    say(("APPLIED" if apply else "PREVIEW ONLY (rolled back)") + ": " + json.dumps(summary, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
