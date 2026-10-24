"""One-off operator: correct the October 2026 practice (asistencial) planilla.

What it does, in one controlled order (see the ODD task practicas-octubre-2026, P1):

1. Preconditions (fail closed, nothing is written if any fails).
2. Clone academic schedule publication 3 into a draft.
3. Store the per-session ``academic_hours`` on the draft blocks (round half up of
   minutes / 45, the value the reviewed workbook uses).
4. Update the teachers through the same service paths as ``PUT /api/teachers/{ci}``.
5. Publish the draft with effective date 2026-09-21 (Spanish catalog subject names).
6. Regenerate practice planilla 10/2026 (same function as POST /api/practice-planilla/generate)
   with the two administrative payment overrides; it stays ``generated`` (pending approval).
7. Compare the regenerated rows with the reviewed workbook and print the mismatches.

Usage (production, inside the backend container)::

    docker exec -i -e PRACTICAS_ENVELOPE_B64="$(base64 -w0 envelope.json)" \\
        sipad-backend-1 python - preview < deploy/operators/practicas_octubre_2026.py
    docker exec -i -e PRACTICAS_ENVELOPE_B64="$(base64 -w0 envelope.json)" \\
        sipad-backend-1 python - apply < deploy/operators/practicas_octubre_2026.py

The script itself is the interpreter's stdin, so the envelope (personal data, never committed)
travels in the ``PRACTICAS_ENVELOPE_B64`` environment variable: the base64 of the envelope JSON.
Locally, ``--envelope PATH`` reads a file instead. Optional ``--admin-user-id N`` (or
``admin_user_id`` in the envelope) selects the actor of the audit trail; the default is the
lowest-id active admin. A third mode, ``fingerprint``, is read-only: it hashes everything that
must NOT change (other planillas regenerated from their stored parameters, billing snapshots)
so a before/after comparison proves the operation stayed inside October practice.

Transactions: every service commits internally, so the whole run happens on one connection
inside an outer transaction (the session joins it with ``create_savepoint``). ``preview`` rolls
that transaction back at the end; ``apply`` commits it once (all or nothing). The planilla
workbook is generated in a temporary directory and only moved over the live file after the
commit, so a failed run never touches planilla 3's current file. Re-running ``apply`` detects
the draft (by name), the publication (draft name + effective date), the changed CI and the
regenerated planilla, and continues instead of duplicating. Nothing is retried. The only delete
is the old teacher row removed by ``change_ci`` (the same as the UI path), which also repoints that
teacher's draft assignments and portal login. Publications 1-3, the theory planillas and the
billing publications are never touched.

GUARD BYPASS (deliberate, authorized): publishing goes through
``_materialize_publication`` with the sequence and digest computed by ``preview_publication``
(exactly what ``publish()`` does), instead of ``publish()`` itself. ``publish()`` refuses
this draft because (a) historical II/2026 teacher availability was never recorded and (b) the
effective date is retroactive over existing planillas and billing publications. Publications
1-3 were created the same way by ``historical_assistential_import`` (policy
``historical_availability_not_recorded``). The bypass is narrow: only the exact blockers in
``EXPECTED_BLOCKERS`` (category, count and message) are tolerated, any other blocker or count
aborts, and the draft must contain only practice blocks. For the same reason the hours are
set directly on the draft blocks (``save_schedule_block`` refuses blocks that already have
assignments); each value is validated with ``ScheduleBlockUpdate`` and logged.

KNOWN, ACCEPTED SIDE EFFECT (decision: "Septiembre ya está cerrado, seguir igual"): publications
1-3 are immutable and keep the corrected teacher's old CI in their published assignments, while
``TeacherIdentityService.change_ci`` (the UI path) deletes the old teacher row. Afterwards the
September practice planilla (id 1) cannot be regenerated: ``PayrollDataError``, "La fuente
práctica published:70 referencia al docente CI <old CI>, que no existe". Its stored rows and
snapshot are unchanged. The ``fingerprint`` mode reports this as NOT REGENERABLE; it is the only
expected difference between the before and after fingerprints. No workaround is attempted.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.academic_management import (
    AcademicScheduleBlock,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSchedulePublishedBlock,
    AcademicSubject,
)
from app.models.billing_publication import BillingPublication
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.academic_management import ScheduleBlockUpdate
from app.schemas.planilla import ExcludedDaySchema
from app.schemas.practice_planilla import PracticePlanillaGenerateRequest
from app.schemas.teacher import TeacherUpdate
from app.services import academic_schedule_publication_service as publication_service
from app.services.activity_logger import log_activity
from app.services.monetary_snapshot import calculation_snapshot_rows
from app.services.planilla_generator import PayrollDataError, PlanillaGenerator
from app.services.practice_planilla_generator import PracticePlanillaGenerator
from app.services.teacher_identity_service import TeacherIdentityConflict, TeacherIdentityService

ALEMBIC_HEAD = "c5e7a9b1d3f4"
ENVELOPE_ENV = "PRACTICAS_ENVELOPE_B64"
ACADEMIC_HOUR_MINUTES = 45
MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

AVAILABILITY_MESSAGE = "El docente no tiene una disponibilidad activa que cubra completamente este bloque."
# Pinned from the rehearsal on the restored production copy. Anything else aborts.
EXPECTED_BLOCKERS = {
    ("draft_validation", 33, AVAILABILITY_MESSAGE),
    ("regular_planilla", 1, "Existen 1 registros de planillas regulares en el rango afectado."),
    ("practice_planilla", 1, "Existen 1 registros de planillas de práctica en el rango afectado."),
    ("billing_publication", 2, "Existen 2 registros de publicaciones de facturación en el rango afectado."),
    ("billing_revision", 2, "Existen 2 registros de revisiones de facturación en el rango afectado."),
}


def say(line: str = "") -> None:
    print(line, flush=True)


class OperatorError(RuntimeError):
    """The operation cannot continue; the caller rolls everything back."""


class PreconditionError(OperatorError):
    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("; ".join(failures))


# ── Pure helpers ──────────────────────────────────────────────────────────────

def mask(ci: str) -> str:
    """Keep the output free of full identity numbers."""
    value = str(ci)
    return value if len(value) <= 4 else f"{value[:2]}***{value[-2:]}"


def academic_hours_for(minutes: int, length: int = ACADEMIC_HOUR_MINUTES) -> int:
    """Per-session academic hours: minutes / length rounded half up, at least 1."""
    return max(1, (2 * minutes + length) // (2 * length))


def override_key(teacher_ci: str, published_assignment_id: int) -> str:
    return f"{teacher_ci}:published:{published_assignment_id}"


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def block_key(block: Any) -> tuple[Any, ...]:
    """(offering, group, weekday, start, end) for draft or published blocks alike."""
    offering = getattr(block, "source_offering_id", None) or getattr(block, "offering_id", None)
    group = getattr(block, "source_group_id", None) or getattr(block, "group_id", None)
    return (offering, group, str(block.weekday).lower(), block.start_time, block.end_time)


def map_blocks(sources: list[Any], candidates: list[Any]) -> dict[int, Any]:
    """Map each source published block id to its single counterpart in ``candidates``."""
    index: dict[tuple[Any, ...], list[Any]] = {}
    for candidate in candidates:
        index.setdefault(block_key(candidate), []).append(candidate)
    mapped: dict[int, Any] = {}
    for source in sources:
        found = index.get(block_key(source), [])
        if len(found) != 1:
            raise OperatorError(
                f"El bloque publicado {source.id} tiene {len(found)} bloques equivalentes "
                "(se esperaba exactamente 1)."
            )
        mapped[source.id] = found[0]
    return mapped


@dataclass
class Comparison:
    ok: bool
    mismatches: list[str]
    totals: dict[str, Any]
    overridden: list[dict[str, Any]] = field(default_factory=list)


def _tuple_text(item: tuple[int, Decimal, Decimal, Decimal]) -> str:
    hours, gross, retention, net = item
    return f"hours={hours} gross={gross:.2f} ret={retention:.2f} net={net:.2f}"


def compare_rows(actual: list[dict[str, Any]], expected: dict[str, Any], ci_map: dict[str, str]) -> Comparison:
    """Compare regenerated rows with the reviewed workbook, per teacher CI.

    Rows are matched as multisets of (hours, gross, retention, net) after mapping the
    workbook CI through ``ci_map`` (old CI -> new CI). A row paid through an administrative
    override is counted for what it pays (net = the override, gross = net + retention) and may
    differ from the workbook in hours only: such rows are matched on the three amounts and
    reported separately in ``overridden`` instead of forcing a match.
    """
    pools: dict[str, list[tuple[int, Decimal, Decimal, Decimal]]] = {}
    for row in expected["rows_detail"]:
        ci = ci_map.get(row["ci"], row["ci"])
        pools.setdefault(ci, []).append(
            (int(row["hours"]), _money(row["gross"]), _money(row["retention"]), _money(row["net"]))
        )
    rows: list[tuple[str, tuple[int, Decimal, Decimal, Decimal], bool]] = []
    for row in actual:
        net, retention = _money(row["net"]), _money(row["retention"])
        gross = net + retention if row["overridden"] else _money(row["gross"])
        rows.append((row["teacher_ci"], (int(row["hours"]), gross, retention, net), bool(row["overridden"])))

    mismatches: list[str] = []
    unmatched_actual: list[tuple[str, tuple[int, Decimal, Decimal, Decimal], bool]] = []
    overridden: list[dict[str, Any]] = []
    for ci, item, is_overridden in sorted((r for r in rows if not r[2]), key=lambda r: (r[0], r[1])):
        pool = pools.setdefault(ci, [])
        if item in pool:
            pool.remove(item)
        else:
            unmatched_actual.append((ci, item, False))
    for ci, item, _flag in sorted((r for r in rows if r[2]), key=lambda r: (r[0], r[1])):
        pool = pools.setdefault(ci, [])
        same_amounts = [p for p in pool if p[1:] == item[1:]]
        match = item if item in pool else (same_amounts[0] if same_amounts else None)
        if match is None:
            unmatched_actual.append((ci, item, True))
            continue
        pool.remove(match)
        overridden.append({
            "teacher_ci": ci, "hours_actual": item[0], "hours_expected": match[0],
            "amount_actual": item[3], "amount_expected": match[3],
        })
    for ci, item, is_overridden in unmatched_actual:
        flag = " (override)" if is_overridden else ""
        mismatches.append(f"CI {mask(ci)}: SIPAD has {_tuple_text(item)}{flag}, workbook has no such row")
    for ci, pool in sorted(pools.items()):
        for item in pool:
            mismatches.append(f"CI {mask(ci)}: workbook has {_tuple_text(item)}, SIPAD has no such row")

    totals = {
        "rows": len(rows),
        "teachers": len({ci for ci, _item, _flag in rows}),
        "gross": sum((item[1] for _ci, item, _f in rows), Decimal("0.00")).quantize(Decimal("0.01")),
        "retention": sum((item[2] for _ci, item, _f in rows), Decimal("0.00")).quantize(Decimal("0.01")),
        "net": sum((item[3] for _ci, item, _f in rows), Decimal("0.00")).quantize(Decimal("0.01")),
    }
    for name in ("rows", "teachers"):
        if totals[name] != int(expected[name]):
            mismatches.append(f"{name}: SIPAD {totals[name]}, workbook {expected[name]}")
    for name in ("gross", "retention", "net"):
        if totals[name] != _money(expected[name]):
            mismatches.append(f"{name}: SIPAD {totals[name]:.2f}, workbook {_money(expected[name]):.2f}")
    return Comparison(not mismatches, mismatches, totals, overridden)


# ── Preconditions ─────────────────────────────────────────────────────────────

@dataclass
class Facts:
    publication: AcademicSchedulePublication
    published_blocks: list[AcademicSchedulePublishedBlock]
    planilla: PracticePlanillaOutput
    window: tuple[date, date]
    effective_from: date
    ci_changes_done: bool
    ci_alias: dict[str, str]
    ci_map: dict[str, str]


def _teacher_exists(db: Session, ci: str) -> bool:
    return db.query(Teacher.ci).filter(Teacher.ci == ci).first() is not None


def check_preconditions(db: Session, envelope: dict[str, Any], *, alembic_head: str = ALEMBIC_HEAD) -> Facts:
    """Read-only checks. Raises PreconditionError listing every failure."""
    failures: list[str] = []
    window = (date.fromisoformat(envelope["planilla"]["start_date"]), date.fromisoformat(envelope["planilla"]["end_date"]))
    month, year = envelope["planilla"]["month"], envelope["planilla"]["year"]
    effective_from = date.fromisoformat(envelope["new_publication_effective_from"])

    versions = db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    if versions != [alembic_head]:
        failures.append(f"alembic: la base está en {versions}, se esperaba {alembic_head}")

    publication = db.get(AcademicSchedulePublication, envelope["source_publication_id"])
    published_blocks: list[AcademicSchedulePublishedBlock] = []
    if publication is None:
        failures.append(f"publicación de horarios {envelope['source_publication_id']} no existe")
    else:
        if publication.program_id != envelope["program_id"] or publication.academic_period != envelope["academic_period"]:
            failures.append("publicación de horarios: programa o período distinto del sobre")
        wanted = {item["source_published_block_id"]: item for item in envelope["block_hours"]}
        published_blocks = (
            db.query(AcademicSchedulePublishedBlock)
            .filter(AcademicSchedulePublishedBlock.publication_id == publication.id)
            .order_by(AcademicSchedulePublishedBlock.id).all()
        )
        have = {block.id for block in published_blocks}
        if have != set(wanted):
            failures.append(
                f"bloques de la publicación: faltan {len(set(wanted) - have)}, sobran {len(have - set(wanted))} "
                f"respecto del sobre ({len(wanted)} esperados)"
            )
        for block in published_blocks:
            item = wanted.get(block.id)
            if item is None:
                continue
            subject = db.get(AcademicSubject, block.source_subject_id)
            problems = []
            if block.activity_type != "practice":
                problems.append("no es de práctica")
            if (block.group_code, block.weekday.lower(), block.start_time, block.end_time) != (
                item["group"], item["weekday"].lower(), time.fromisoformat(item["start"]), time.fromisoformat(item["end"]),
            ):
                problems.append("grupo, día u horario distinto del sobre")
            if subject is None or subject.name != item["subject_catalog"]:
                problems.append("materia del catálogo distinta del sobre")
            if problems:
                failures.append(f"bloques: el bloque publicado {block.id} " + ", ".join(problems))
            teachers = [assignment.teacher_ci for assignment in block.assignments]
            if teachers != [item["teacher_ci"]]:
                failures.append(
                    f"docente del bloque publicado {block.id}: CI {[mask(c) for c in teachers]} "
                    f"distinto del sobre ({mask(item['teacher_ci'])})"
                )

    planilla = (
        db.query(PracticePlanillaOutput)
        .filter(PracticePlanillaOutput.month == month, PracticePlanillaOutput.year == year).first()
    )
    expected_id = envelope["planilla"]["copy_params_from_practice_planilla_id"]
    if planilla is None or planilla.id != expected_id:
        failures.append(f"planilla de prácticas {expected_id} para {month:02d}/{year} no existe")
    else:
        if planilla.status in ("approved", "published"):
            failures.append(f"planilla de prácticas {planilla.id} está en estado {planilla.status}; debe seguir sin aprobar")
        if (planilla.start_date, planilla.end_date) != window:
            failures.append(f"planilla de prácticas {planilla.id}: ventana de corte distinta del sobre")

    if db.query(BillingPublication.id).filter(
        BillingPublication.planilla_type == "practice",
        BillingPublication.month == month, BillingPublication.year == year,
    ).first():
        failures.append(f"facturación: ya existe una publicación de prácticas {month:02d}/{year}")

    changes = [item for item in envelope["teacher_updates"] if item.get("new_ci")]
    done_flags: list[bool] = []
    ci_alias: dict[str, str] = {}
    for item in envelope["teacher_updates"]:
        old, new = item["ci"], item.get("new_ci")
        old_exists = _teacher_exists(db, old)
        if not new:
            if not old_exists:
                failures.append(f"docente CI {mask(old)} no existe")
            continue
        new_exists = _teacher_exists(db, new)
        if old_exists and not new_exists:
            done_flags.append(False)
        elif new_exists and not old_exists:
            done_flags.append(True)
            ci_alias[old] = new
        elif old_exists and new_exists:
            failures.append(f"CI {mask(new)} ya existe junto al CI {mask(old)} del docente a corregir")
        else:
            failures.append(f"docente: no existe ni el CI {mask(old)} ni el CI {mask(new)}")
    if done_flags and len(set(done_flags)) != 1:
        failures.append("CI: los cambios de CI del sobre están a medias")

    logs = db.query(PracticeAttendanceLog.id).filter(
        PracticeAttendanceLog.date >= window[0], PracticeAttendanceLog.date <= window[1]
    ).count()
    if logs:
        failures.append(f"asistencia de prácticas: {logs} registro(s) en la ventana {window[0]}..{window[1]}")

    if failures:
        raise PreconditionError(failures)
    return Facts(
        publication=publication, published_blocks=published_blocks, planilla=planilla, window=window,
        effective_from=effective_from, ci_changes_done=bool(done_flags) and all(done_flags),
        ci_alias=ci_alias, ci_map={item["ci"]: item["new_ci"] for item in changes},
    )


# ── State of a previous (partial or complete) run ─────────────────────────────

@dataclass
class Operation:
    draft: AcademicScheduleDraft | None
    publication: AcademicSchedulePublication | None


def find_operation(db: Session, envelope: dict[str, Any], facts: Facts) -> Operation:
    name = envelope["clone_draft_name"]
    scope = (envelope["program_id"], envelope["academic_period"])
    drafts = db.query(AcademicScheduleDraft).filter(
        AcademicScheduleDraft.program_id == scope[0], AcademicScheduleDraft.academic_period == scope[1],
        AcademicScheduleDraft.name == name,
    ).all()
    if len(drafts) > 1:
        raise OperatorError(f"Hay {len(drafts)} borradores llamados como el sobre; revisar a mano.")
    draft = drafts[0] if drafts else None
    same_day = db.query(AcademicSchedulePublication).filter(
        AcademicSchedulePublication.program_id == scope[0], AcademicSchedulePublication.academic_period == scope[1],
        AcademicSchedulePublication.effective_from == facts.effective_from,
    ).all()
    ours = [item for item in same_day if draft is not None and item.source_draft_id == draft.id]
    if len(same_day) != len(ours):
        raise OperatorError(
            f"Existe otra publicación con fecha efectiva {facts.effective_from} que no proviene del borrador del sobre."
        )
    publication = ours[0] if ours else None
    if draft is not None and draft.status == "archived":
        raise OperatorError("El borrador del sobre está archivado; revisar a mano.")
    if draft is not None and draft.status == "published" and publication is None:
        raise OperatorError("El borrador del sobre está publicado pero su publicación no existe en la fecha efectiva.")
    if facts.ci_changes_done and draft is None:
        raise OperatorError("El CI ya fue cambiado pero no hay borrador ni publicación del sobre; revisar a mano.")
    return Operation(draft, publication)


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


def clone_step(db: Session, envelope: dict[str, Any], admin: User) -> AcademicScheduleDraft:
    draft = publication_service.clone_publication(
        db, envelope["source_publication_id"], envelope["clone_draft_name"],
        _audit(db, admin, "clone", "academic_schedule_draft"),
    )
    say(f"  cloned draft id={draft.id}")
    return draft


def draft_blocks(db: Session, draft: AcademicScheduleDraft) -> list[AcademicScheduleBlock]:
    return db.query(AcademicScheduleBlock).filter(AcademicScheduleBlock.draft_id == draft.id).order_by(
        AcademicScheduleBlock.id
    ).all()


def hours_step(
    db: Session, envelope: dict[str, Any], facts: Facts, draft: AcademicScheduleDraft, admin: User,
) -> None:
    blocks = draft_blocks(db, draft)
    if len(blocks) != len(envelope["block_hours"]):
        raise OperatorError(f"El borrador tiene {len(blocks)} bloques; el sobre trae {len(envelope['block_hours'])}.")
    if any(block.activity_type != "practice" for block in blocks):
        raise OperatorError("El borrador contiene bloques que no son de práctica.")
    mapping = map_blocks(facts.published_blocks, blocks)
    audit = _audit(db, admin, "update", "academic_schedule_block")
    changed, rule_exceptions = 0, []
    for item in envelope["block_hours"]:
        block = mapping[item["source_published_block_id"]]
        minutes = (block.end_time.hour * 60 + block.end_time.minute) - (block.start_time.hour * 60 + block.start_time.minute)
        if minutes != item["minutes"]:
            raise OperatorError(f"El bloque publicado {item['source_published_block_id']} dura {minutes} min; el sobre dice {item['minutes']}.")
        target = int(item["academic_hours"])
        if target != academic_hours_for(minutes):
            rule_exceptions.append((item["source_published_block_id"], target, academic_hours_for(minutes)))
        try:
            ScheduleBlockUpdate(
                offering_id=block.offering_id, group_id=block.group_id, classroom_id=block.classroom_id,
                activity_type=block.activity_type, weekday=block.weekday, start_time=block.start_time,
                end_time=block.end_time, academic_hours=target,
            )
        except ValidationError as exc:
            raise OperatorError(f"Horas inválidas para el bloque publicado {item['source_published_block_id']}: {exc.errors()[0]['msg']}") from exc
        if block.academic_hours != target:
            block.academic_hours = target
            db.flush()
            audit(block)
            changed += 1
    db.commit()
    distribution = Counter(int(item["academic_hours"]) for item in envelope["block_hours"])
    say(f"  hours set on {changed} of {len(blocks)} draft blocks; per-session distribution {dict(sorted(distribution.items()))}")
    if rule_exceptions:
        say(f"  WARNING {len(rule_exceptions)} block(s) differ from the half-up rule (block, envelope, rule): {rule_exceptions}")
    else:
        say("  all envelope hours equal the half-up rule (minutes / 45)")


def teachers_step(db: Session, envelope: dict[str, Any], admin: User) -> None:
    for item in envelope["teacher_updates"]:
        old_ci, new_ci = item["ci"], item.get("new_ci")
        payload = TeacherUpdate(**{k: v for k, v in item.items() if k not in ("ci", "new_ci")}).model_dump(exclude_unset=True)
        changed: list[str] = []
        if new_ci and _teacher_exists(db, old_ci) and not _teacher_exists(db, new_ci):
            try:
                teacher = TeacherIdentityService(db).change_ci(old_ci, new_ci, corrected_by=admin.id)
            except TeacherIdentityConflict as exc:
                raise OperatorError(f"Cambio de CI rechazado: {exc}") from exc
            changed.append("ci")
        else:
            teacher = db.query(Teacher).filter(Teacher.ci == (new_ci or old_ci)).one()
        for name, value in payload.items():
            if getattr(teacher, name) != value:
                setattr(teacher, name, value)
                changed.append(name)
        if changed:
            ci_note = f" [CI cambiado: {old_ci} → {new_ci}]" if "ci" in changed else ""
            log_activity(
                db, "update_teacher", "teachers",
                f"Docente actualizado: {teacher.full_name} (CI: {teacher.ci})" + ci_note,
                user=admin,
                details={"old_ci": old_ci, "new_ci": new_ci or old_ci,
                         "fields_updated": [name for name in changed if name != "ci"] + (["ci"] if "ci" in changed else [])},
            )
        db.flush()
        label = f"CI {mask(old_ci)}" + (f" -> {mask(new_ci)}" if new_ci else "")
        say(f"  teacher {label}: " + (f"updated fields {changed}" if changed else "already up to date"))
    db.commit()


def blockers_text(blockers: list[dict[str, Any]]) -> list[str]:
    return [f"{b['category']} x{b['count']}: {b['message']}" for b in blockers]


def publish_step(
    db: Session, envelope: dict[str, Any], facts: Facts, draft: AcademicScheduleDraft, admin: User,
) -> AcademicSchedulePublication:
    preview = publication_service.preview_publication(db, draft.id, facts.effective_from, lock=True)
    observed = {(b["category"], b["count"], b["message"]) for b in preview["blockers"]}
    say(f"  preview: blocks={preview['block_count']} assignments={preview['assignment_count']} "
        f"sequence={preview['sequence']} digest={preview['digest']} can_publish={preview['can_publish']}")
    for line in blockers_text(preview["blockers"]):
        tolerated = "tolerated" if any(line.startswith(f"{c} x{n}:") for c, n, _m in EXPECTED_BLOCKERS) else "UNEXPECTED"
        say(f"  blocker [{tolerated}] {line}")
    if observed != EXPECTED_BLOCKERS:
        extra, missing = sorted(observed - EXPECTED_BLOCKERS), sorted(EXPECTED_BLOCKERS - observed)
        raise OperatorError(f"Los bloqueos de la vista previa no son exactamente los esperados. Inesperados: {extra}; ausentes: {missing}")
    blocks = draft_blocks(db, draft)
    mapping = map_blocks(facts.published_blocks, blocks)
    for item in envelope["block_hours"]:
        name = mapping[item["source_published_block_id"]].offering.subject.name
        if name != item["subject_catalog"]:
            raise OperatorError(f"Materia del catálogo inesperada en el bloque {item['source_published_block_id']}")
    names = Counter(block.offering.subject.name for block in blocks)
    say(f"  subject names (catalog, {len(names)}): " + "; ".join(f"{n} x{c}" for n, c in sorted(names.items())))
    try:
        graph = publication_service._draft_graph(db, draft.id, lock=False)
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


def verify_publication(
    db: Session, envelope: dict[str, Any], facts: Facts, publication: AcademicSchedulePublication,
) -> dict[int, AcademicSchedulePublishedBlock]:
    blocks = db.query(AcademicSchedulePublishedBlock).filter(
        AcademicSchedulePublishedBlock.publication_id == publication.id
    ).order_by(AcademicSchedulePublishedBlock.id).all()
    if len(blocks) != len(envelope["block_hours"]):
        raise OperatorError(f"La publicación {publication.id} tiene {len(blocks)} bloques; se esperaban {len(envelope['block_hours'])}.")
    mapping = map_blocks(facts.published_blocks, blocks)
    for item in envelope["block_hours"]:
        block = mapping[item["source_published_block_id"]]
        expected_ci = facts.ci_map.get(item["teacher_ci"], item["teacher_ci"])
        if block.subject_name != item["subject_catalog"] or block.academic_hours != item["academic_hours"]:
            raise OperatorError(f"El bloque {block.id} de la publicación no tiene el nombre del catálogo o las horas del sobre.")
        if [a.teacher_ci for a in block.assignments] != [expected_ci]:
            raise OperatorError(f"El bloque {block.id} de la publicación no tiene al docente esperado (CI {mask(expected_ci)}).")
    say(f"  verified publication {publication.id}: {len(blocks)} blocks, Spanish catalog names, hours stored, teachers as expected")
    return mapping


def regenerate_step(
    db: Session, envelope: dict[str, Any], facts: Facts, publication: AcademicSchedulePublication,
    mapping: dict[int, AcademicSchedulePublishedBlock], admin: User, work_dir: Path, final_dir: Path,
) -> tuple[PracticePlanillaOutput, list[tuple[Path, Path]]]:
    spec = envelope["planilla"]
    planilla = facts.planilla
    overrides: dict[str, Decimal] = {}
    for item in envelope["amount_overrides"]:
        block = mapping[item["source_published_block_id"]]
        ci = facts.ci_map.get(item["teacher_ci"], item["teacher_ci"])
        assignments = [a for a in block.assignments if a.teacher_ci == ci]
        if len(assignments) != 1:
            raise OperatorError(f"El bloque {block.id} no tiene exactamente una asignación del docente CI {mask(ci)}.")
        overrides[override_key(ci, assignments[0].id)] = Decimal(item["amount"])
    stored = {key: format(value, ".2f") for key, value in overrides.items()}
    snapshot = planilla.calculation_snapshot or {}
    already = (
        (planilla.payment_overrides_json or {}) == stored
        and planilla.status == "generated"
        and snapshot.get("designations")
        and all(row.get("publication_id") == publication.id for row in snapshot["designations"])
    )
    if already:
        say(f"  planilla {planilla.id} was already regenerated from publication {publication.id}; nothing to do")
        return planilla, []
    if planilla.payment_overrides_json:
        raise OperatorError("La planilla tiene ajustes de pago previos que no son los del sobre; revisar a mano.")
    discount_mode = planilla.discount_mode
    excluded = [ExcludedDaySchema.model_validate(item) for item in (planilla.excluded_days_json or [])]
    request = PracticePlanillaGenerateRequest(
        month=spec["month"], year=spec["year"], payment_overrides=overrides,
        start_date=date.fromisoformat(spec["start_date"]), end_date=date.fromisoformat(spec["end_date"]),
        discount_mode=discount_mode, excluded_days=excluded,
    )
    say(f"  planilla {planilla.id}: discount_mode={discount_mode} excluded_days={len(excluded)} "
        f"window={request.start_date}..{request.end_date} overrides on {len(overrides)} source(s)")
    result = PracticePlanillaGenerator(output_dir=str(work_dir)).generate(
        db=db, month=request.month, year=request.year, payment_overrides=request.payment_overrides,
        start_date=request.start_date, end_date=request.end_date,
        discount_mode=request.discount_mode, excluded_days=request.excluded_days,
    )
    if result.planilla_output_id != planilla.id:
        raise OperatorError("La regeneración no actualizó la planilla esperada.")
    output = db.get(PracticePlanillaOutput, result.planilla_output_id)
    generated = Path(result.file_path)
    final = final_dir / generated.name
    output.file_path = str(final)
    db.flush()
    log_activity(
        db, "generate_practice_planilla", "practice-planilla",
        f"Planilla prácticas generada: {MONTH_NAMES.get(request.month, str(request.month))} {request.year}",
        user=admin,
        details={"month": request.month, "year": request.year, "total_teachers": result.total_teachers,
                 "total_hours": result.total_hours, "total_payment": float(result.total_payment),
                 "discount_mode": request.discount_mode},
    )
    db.commit()
    for warning in result.warnings:
        say(f"  generator warning: {warning}")
    say(f"  regenerated planilla {output.id}: status={output.status} teachers={result.total_teachers} "
        f"hours={result.total_hours} total=Bs {_money(result.total_payment)}")
    return output, [(generated, final)]


def compare_step(db: Session, envelope: dict[str, Any], facts: Facts, planilla: PracticePlanillaOutput) -> Comparison:
    rows = calculation_snapshot_rows(planilla.calculation_snapshot, planilla.total_payment)
    actual = [
        {"teacher_ci": row.teacher_ci, "hours": row.payable_hours, "gross": row.calculated_payment,
         "retention": row.retention_amount, "net": row.final_payment, "overridden": row.has_admin_override}
        for row in rows
    ]
    comparison = compare_rows(actual, envelope["expected"], facts.ci_map)
    totals = comparison.totals
    say(f"  rows={totals['rows']} teachers={totals['teachers']} gross={totals['gross']:.2f} "
        f"retention={totals['retention']:.2f} net={totals['net']:.2f} "
        f"(workbook: {envelope['expected']['rows']} / {envelope['expected']['teachers']} / "
        f"{envelope['expected']['gross']} / {envelope['expected']['retention']} / {envelope['expected']['net']})")
    for item in comparison.overridden:
        verdict = "hours equal" if item["hours_actual"] == item["hours_expected"] else "hours differ"
        say(f"  overridden row CI {mask(item['teacher_ci'])}: hours SIPAD {item['hours_actual']} vs workbook "
            f"{item['hours_expected']} ({verdict}); amount SIPAD {item['amount_actual']:.2f} vs workbook {item['amount_expected']:.2f}")
    if comparison.mismatches:
        say("  MISMATCHES:")
        for line in comparison.mismatches:
            say(f"    - {line}")
    else:
        say("  MATCH: rows, teachers and totals equal the reviewed workbook"
            + (" (overridden rows matched on amounts, hours reported above)" if comparison.overridden else ""))
    return comparison


# ── Orchestration ─────────────────────────────────────────────────────────────

def execute(
    db: Session, envelope: dict[str, Any], *, apply: bool, admin_user_id: int | None,
    work_dir: Path, final_dir: Path,
) -> tuple[dict[str, Any], list[tuple[Path, Path]]]:
    say("[1/7] preconditions")
    facts = check_preconditions(db, envelope)
    operation = find_operation(db, envelope, facts)
    admin = resolve_admin(db, admin_user_id if admin_user_id is not None else envelope.get("admin_user_id"))
    say(f"  ok. publication {facts.publication.id} has {len(facts.published_blocks)} practice blocks; planilla {facts.planilla.id} "
        f"is {facts.planilla.status}; actor admin user id={admin.id}")
    say(f"  state: draft={'id ' + str(operation.draft.id) if operation.draft else 'none'}, "
        f"publication={'id ' + str(operation.publication.id) if operation.publication else 'none'}, "
        f"ci changes done={facts.ci_changes_done}")

    say("[2/7] clone publication into a draft")
    draft = operation.draft
    if draft is None:
        draft = clone_step(db, envelope, admin)
    else:
        say(f"  draft id={draft.id} already exists ({draft.status}); skipped")
    publication = operation.publication

    say("[3/7] academic hours on the draft blocks")
    if publication is None:
        hours_step(db, envelope, facts, draft, admin)
    else:
        say("  publication already exists; skipped")

    say("[4/7] teachers")
    teachers_step(db, envelope, admin)

    say("[5/7] publish")
    if publication is None:
        publication = publish_step(db, envelope, facts, draft, admin)
    else:
        say(f"  publication id={publication.id} already published; skipped")
    mapping = verify_publication(db, envelope, facts, publication)

    say("[6/7] regenerate practice planilla")
    planilla, moves = regenerate_step(db, envelope, facts, publication, mapping, admin, work_dir, final_dir)

    say("[7/7] compare with the reviewed workbook")
    comparison = compare_step(db, envelope, facts, planilla)
    summary = {
        "draft_id": draft.id, "publication_id": publication.id, "publication_sequence": publication.sequence,
        "effective_from": str(publication.effective_from), "planilla_id": planilla.id,
        "planilla_status": planilla.status, "planilla_total": str(_money(planilla.total_payment)),
        "comparison_ok": comparison.ok,
    }
    return summary, moves


# ── Read-only fingerprint of everything that must not change ──────────────────

def _digest(parts: list[Any]) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _row_part(row: Any) -> list[Any]:
    return [
        getattr(row, "source_key", None) or f"legacy:{row.designation_id}", row.teacher_ci, row.payable_hours,
        f"{Decimal(str(row.calculated_payment)):.2f}", f"{Decimal(str(row.retention_amount)):.2f}",
        f"{Decimal(str(row.final_payment)):.2f}",
    ]


def fingerprint(db: Session, *, exclude_practice_planilla_id: int | None = None) -> dict[str, tuple[int, str]]:
    """name -> (row count, sha256) for the data that October practice must not change."""
    result: dict[str, tuple[int, str]] = {}
    for model_name, generator, outputs in (
        ("practice", PracticePlanillaGenerator(), db.query(PracticePlanillaOutput).order_by(PracticePlanillaOutput.id).all()),
        ("theory", PlanillaGenerator(), db.execute(text("SELECT id FROM planilla_outputs ORDER BY id")).scalars().all()),
    ):
        for output in outputs:
            if model_name == "theory":
                from app.models.planilla import PlanillaOutput
                output = db.get(PlanillaOutput, output)
            if model_name == "practice" and output.id == exclude_practice_planilla_id:
                continue
            excluded = [ExcludedDaySchema.model_validate(item) for item in (output.excluded_days_json or [])]
            label = f"{model_name} planilla {output.id} ({output.month:02d}/{output.year}) rows regenerated read-only"
            try:
                built = generator._build_planilla_data(
                    db, output.month, output.year, start_date=output.start_date, end_date=output.end_date,
                    discount_mode=output.discount_mode, excluded_days=excluded,
                )
            except PayrollDataError as exc:
                result[label] = (0, f"NOT REGENERABLE: {exc}")
                continue
            rows = sorted((_row_part(row) for row in built[0]), key=lambda part: json.dumps(part))
            result[label] = (len(rows), _digest(rows))
    for name, query in (
        ("billing_publications (all columns as stored)", "SELECT * FROM billing_publications ORDER BY id"),
        ("billing_publication_revisions (all columns as stored)", "SELECT * FROM billing_publication_revisions ORDER BY id"),
        ("planilla_outputs (all columns as stored)", "SELECT * FROM planilla_outputs ORDER BY id"),
        ("academic_schedule_publications 1-3 and their blocks/assignments",
         "SELECT p.*, b.id AS bid, b.subject_name, b.academic_hours, a.id AS aid, a.teacher_ci "
         "FROM academic_schedule_publications p JOIN academic_schedule_published_blocks b ON b.publication_id = p.id "
         "JOIN academic_schedule_published_assignments a ON a.publication_block_id = b.id WHERE p.id <= 3 ORDER BY p.id, b.id, a.id"),
    ):
        rows = [dict(row._mapping) for row in db.execute(text(query))]
        result[name] = (len(rows), _digest(rows))
    stored = db.query(PracticePlanillaOutput).filter(PracticePlanillaOutput.id != (exclude_practice_planilla_id or -1)).all()
    parts = [[o.id, o.status, str(o.total_payment), o.calculation_snapshot, o.payment_overrides_json] for o in stored]
    result["practice_planilla_outputs other than the target (as stored)"] = (len(parts), _digest(parts))
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def load_envelope(path: str | None) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    encoded = os.environ.get(ENVELOPE_ENV)
    if not encoded:
        raise OperatorError(f"Falta el sobre: use --envelope PATH o la variable {ENVELOPE_ENV} (base64 del JSON).")
    return json.loads(base64.b64decode(encoded).decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="October 2026 practice planilla correction")
    parser.add_argument("mode", choices=["preview", "apply", "fingerprint"])
    parser.add_argument("--envelope", help="path to the envelope JSON (default: $PRACTICAS_ENVELOPE_B64)")
    parser.add_argument("--admin-user-id", type=int, help="actor for the audit trail (default: lowest-id active admin)")
    args = parser.parse_args(argv)

    from app.database import SessionLocal, engine
    from app.routers import practice_planilla as practice_router

    envelope = load_envelope(args.envelope)
    apply = args.mode == "apply"
    final_dir = Path(practice_router.__file__).resolve().parents[2] / "data" / "output"
    say(f"mode={args.mode} database={engine.url.render_as_string(hide_password=True)}")
    moves: list[tuple[Path, Path]] = []
    with tempfile.TemporaryDirectory(prefix="practicas-octubre-") as work, engine.connect() as connection:
        outer = connection.begin()
        db = SessionLocal(bind=connection, join_transaction_mode="create_savepoint")
        try:
            if args.mode == "fingerprint":
                target = envelope["planilla"]["copy_params_from_practice_planilla_id"]
                for name, (count, digest) in fingerprint(db, exclude_practice_planilla_id=target).items():
                    say(f"{digest}  rows={count:<5} {name}")
                outer.rollback()
                return 0
            summary, moves = execute(
                db, envelope, apply=apply, admin_user_id=args.admin_user_id, work_dir=Path(work), final_dir=final_dir,
            )
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
        if apply:
            for generated, final in moves:
                final.parent.mkdir(parents=True, exist_ok=True)
                staged = final.with_name(final.name + ".new")
                shutil.copyfile(generated, staged)
                os.replace(staged, final)
                say(f"workbook moved to {final}")
    say()
    say(("APPLIED" if apply else "PREVIEW ONLY (rolled back)") + ": " + json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
