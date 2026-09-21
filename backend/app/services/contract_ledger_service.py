from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.contract import ContractDocument, ContractLine
from app.models.academic_management import (
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
)
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services import app_settings_service
from app.services.payroll_schedule_source_service import (
    PayrollScheduleSource,
    payroll_schedule_sources,
)

TEMPLATE_VERSION = "contract-ledger-v1"


class ContractIssuanceError(ValueError):
    """Actionable refusal raised before any contract is issued."""


@dataclass(frozen=True)
class ContractSnapshotLine:
    activity_kind: Literal["theory", "practice"]
    rate_class: Literal["regular", "practice"]
    hourly_rate: str
    hours: str
    hour_basis: Literal["weekly", "payable"]
    subject_label: str
    group_label: str
    semester_label: str
    schedule_label: str
    effective_from: str
    effective_to: str
    source_kind: Literal["legacy", "published"]
    source_id: int
    designation_id: int | None
    publication_id: int | None
    publication_sequence: int | None
    publication_program_id: int | None
    authority_effective_from: str
    published_block_id: int | None
    published_assignment_id: int | None

    @property
    def source_key(self) -> str:
        return f"{self.source_kind}:{self.source_id}"


@dataclass(frozen=True)
class ContractSnapshot:
    teacher: dict[str, Any]
    academic_period: dict[str, str]
    department: str
    template_version: str
    lines: tuple[ContractSnapshotLine, ...]
    authority_transitions: tuple[dict[str, Any], ...] = ()

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "teacher": self.teacher,
            "academic_period": self.academic_period,
            "department": self.department,
            "template_version": self.template_version,
            "lines": [asdict(line) for line in self.lines],
        }

    def storage_payload(self) -> dict[str, Any]:
        return {
            **self.canonical_payload(),
            "authority_transitions": list(self.authority_transitions),
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def academic_period_bounds(academic_period: str) -> tuple[date, date]:
    match = re.fullmatch(r"\s*(I|II|1|2)\s*[/\-]\s*(\d{4})\s*", academic_period, re.IGNORECASE)
    if match is None:
        raise ContractIssuanceError(
            f"El período académico {academic_period!r} no permite determinar fechas. "
            "Usá el formato I/AAAA o II/AAAA."
        )
    semester, year_text = match.groups()
    year = int(year_text)
    if semester.upper() in {"I", "1"}:
        return date(year, 1, 1), date(year, 6, 30)
    return date(year, 7, 1), date(year, 12, 31)


def _decimal_text(value: Decimal | int | float) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def _schedule_label(source: PayrollScheduleSource) -> str:
    labels = [
        f"{item['dia']} {item['hora_inicio']}-{item['hora_fin']} ({item['horas_academicas']}h)"
        for item in source.schedule
    ]
    return "; ".join(labels)


def _snapshot_line(
    source: PayrollScheduleSource,
    rate: Decimal,
    publication: dict[str, Any] | None,
) -> ContractSnapshotLine:
    weekly_hours = sum(int(item.get("horas_academicas", 0) or 0) for item in source.schedule)
    if weekly_hours > 0:
        hours = weekly_hours
        basis: Literal["weekly", "payable"] = "weekly"
    else:
        hours = int(source.monthly_hours or 0)
        basis = "payable"
    if hours <= 0:
        raise ContractIssuanceError(
            f"La fuente {source.source_key} de {source.subject} no tiene carga horaria contractual."
        )
    schedule_label = _schedule_label(source)
    if not schedule_label:
        raise ContractIssuanceError(
            f"La fuente {source.source_key} de {source.subject} no tiene horario válido."
        )
    return ContractSnapshotLine(
        activity_kind=source.activity_kind,
        rate_class=source.rate_class,
        hourly_rate=_decimal_text(rate),
        hours=_decimal_text(hours),
        hour_basis=basis,
        subject_label=source.subject.strip(),
        group_label=source.group_code.strip(),
        semester_label=str(source.semester).strip(),
        schedule_label=schedule_label,
        effective_from=source.effective_from.isoformat(),
        effective_to=source.effective_to.isoformat(),
        source_kind=source.source_kind,
        source_id=source.source_id,
        designation_id=source.designation_id,
        publication_id=source.publication_id,
        publication_sequence=publication["sequence"] if publication else None,
        publication_program_id=publication["program_id"] if publication else None,
        authority_effective_from=(
            publication["effective_from"].isoformat()
            if publication else source.effective_from.isoformat()
        ),
        published_block_id=source.published_block_id,
        published_assignment_id=source.published_assignment_id,
    )


def build_contract_snapshot(
    db: Session,
    *,
    teacher_ci: str,
    academic_period: str,
    department: str,
    allow_empty: bool = False,
    tracked_program_ids: set[int] | None = None,
) -> ContractSnapshot:
    teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
    if teacher is None:
        raise ContractIssuanceError(f"Docente con CI {teacher_ci} no encontrado.")
    if teacher.ci.startswith("TEMP-"):
        raise ContractIssuanceError(
            "No se puede emitir un contrato para un docente TEMP; vinculalo primero a un CI real."
        )
    period_start, period_end = academic_period_bounds(academic_period)
    regular_rate = Decimal(str(app_settings_service.get_hourly_rate(db)))
    practice_rate = Decimal(str(app_settings_service.get_practice_hourly_rate(db)))
    if regular_rate <= 0 or practice_rate <= 0:
        raise ContractIssuanceError("Las tarifas de teoría y práctica deben ser mayores que cero.")

    sources: list[PayrollScheduleSource] = []
    for activity_kind in ("theory", "practice"):
        sources.extend(payroll_schedule_sources(
            db,
            academic_period=academic_period,
            period_start=period_start,
            period_end=period_end,
            activity_kind=activity_kind,
        ))
    teacher_sources = [
        source for source in sources
        if source.teacher_ci == teacher_ci and source.schedule
    ]
    if not teacher_sources and not allow_empty:
        raise ContractIssuanceError(
            f"El docente {teacher.full_name} no tiene carga efectiva en {academic_period}."
        )

    publication_ids = {
        source.publication_id for source in teacher_sources if source.publication_id is not None
    }
    publication_rows = (
        db.query(
            AcademicSchedulePublication.id,
            AcademicSchedulePublication.sequence,
            AcademicSchedulePublication.program_id,
            AcademicSchedulePublication.effective_from,
        )
        .filter(AcademicSchedulePublication.id.in_(publication_ids))
        .all()
    ) if publication_ids else []
    publications = {
        row.id: {
            "sequence": row.sequence,
            "program_id": row.program_id,
            "effective_from": row.effective_from,
        }
        for row in publication_rows
    }
    missing_publications = sorted(publication_ids - publications.keys())
    if missing_publications:
        raise ContractIssuanceError(
            f"Falta procedencia de revisión publicada para las publicaciones {missing_publications}."
        )

    lines = tuple(sorted(
        (
            _snapshot_line(
                source,
                practice_rate if source.rate_class == "practice" else regular_rate,
                publications.get(source.publication_id),
            )
            for source in teacher_sources
        ),
        key=lambda line: (
            line.activity_kind,
            line.subject_label.casefold(),
            line.group_label.casefold(),
            line.effective_from,
            line.source_key,
        ),
    ))
    source_keys = [line.source_key for line in lines]
    if len(source_keys) != len(set(source_keys)):
        raise ContractIssuanceError(
            "La cobertura de carga es ambigua: una fuente aparece más de una vez en el período."
        )
    for line in lines:
        if date.fromisoformat(line.effective_from) < period_start or date.fromisoformat(line.effective_to) > period_end:
            raise ContractIssuanceError(
                f"La fuente {line.source_key} tiene vigencia fuera de {academic_period}."
            )

    _validate_snapshot_provenance(db, teacher_ci, lines)
    program_ids = set(tracked_program_ids or ()) | {
        item["program_id"] for item in publications.values()
    }
    transition_rows = (
        db.query(
            AcademicSchedulePublication.id,
            AcademicSchedulePublication.program_id,
            AcademicSchedulePublication.sequence,
            AcademicSchedulePublication.effective_from,
        )
        .filter(
            AcademicSchedulePublication.academic_period == academic_period,
            AcademicSchedulePublication.program_id.in_(program_ids),
        )
        .order_by(
            AcademicSchedulePublication.effective_from,
            AcademicSchedulePublication.sequence,
            AcademicSchedulePublication.id,
        )
        .all()
    ) if program_ids else []

    return ContractSnapshot(
        teacher={
            "ci": teacher.ci,
            "full_name": teacher.full_name,
        },
        academic_period={
            "identity": academic_period,
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        department=department,
        template_version=TEMPLATE_VERSION,
        lines=lines,
        authority_transitions=tuple({
            "publication_id": row.id,
            "program_id": row.program_id,
            "sequence": row.sequence,
            "effective_from": row.effective_from.isoformat(),
        } for row in transition_rows),
    )


def _validate_snapshot_provenance(
    db: Session,
    teacher_ci: str,
    lines: tuple[ContractSnapshotLine, ...],
) -> None:
    legacy_ids = {line.designation_id for line in lines if line.source_kind == "legacy"}
    legacy_rows = (
        db.query(Designation.id, Designation.teacher_ci)
        .filter(Designation.id.in_(legacy_ids))
        .all()
    ) if legacy_ids else []
    legacy = {row.id: row.teacher_ci for row in legacy_rows}
    for line in (item for item in lines if item.source_kind == "legacy"):
        if line.source_id != line.designation_id or legacy.get(line.designation_id) != teacher_ci:
            raise ContractIssuanceError(
                f"La fuente {line.source_key} no pertenece coherentemente al docente del contrato."
            )

    assignment_ids = {
        line.published_assignment_id for line in lines if line.source_kind == "published"
    }
    published_rows = (
        db.query(
            AcademicSchedulePublishedAssignment.id,
            AcademicSchedulePublishedAssignment.teacher_ci,
            AcademicSchedulePublishedBlock.id.label("block_id"),
            AcademicSchedulePublication.id.label("publication_id"),
            AcademicSchedulePublication.sequence,
            AcademicSchedulePublication.program_id,
            AcademicSchedulePublication.effective_from,
        )
        .join(
            AcademicSchedulePublishedBlock,
            AcademicSchedulePublishedAssignment.publication_block_id
            == AcademicSchedulePublishedBlock.id,
        )
        .join(
            AcademicSchedulePublication,
            AcademicSchedulePublishedBlock.publication_id == AcademicSchedulePublication.id,
        )
        .filter(AcademicSchedulePublishedAssignment.id.in_(assignment_ids))
        .all()
    ) if assignment_ids else []
    published = {row.id: row for row in published_rows}
    for line in (item for item in lines if item.source_kind == "published"):
        row = published.get(line.published_assignment_id)
        coherent = row is not None and (
            line.source_id == row.id
            and row.teacher_ci == teacher_ci
            and line.published_block_id == row.block_id
            and line.publication_id == row.publication_id
            and line.publication_sequence == row.sequence
            and line.publication_program_id == row.program_id
            and line.authority_effective_from == row.effective_from.isoformat()
        )
        if not coherent:
            raise ContractIssuanceError(
                f"La fuente {line.source_key} no forma una procedencia publicada coherente."
            )


def _line_identity(line: dict[str, Any]) -> str:
    return f"{line['source_kind']}:{line['source_id']}"


def _line_scope(line: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(line["activity_kind"]),
        str(line["subject_label"]).casefold().strip(),
        str(line["group_label"]).casefold().strip(),
        str(line["semester_label"]).casefold().strip(),
    )


def _removal_effective_date(
    old: dict[str, Any],
    previous: dict[str, Any],
    current: ContractSnapshot,
) -> date:
    previous_ids = {
        item.get("publication_id")
        for item in previous.get("authority_transitions", [])
        if isinstance(item, dict)
    }
    candidates = [
        date.fromisoformat(line.authority_effective_from)
        for line in current.lines
        if line.source_kind == "published"
        and line.publication_id not in previous_ids
        and _line_scope(asdict(line)) == _line_scope(old)
    ]
    old_program_id = old.get("publication_program_id")
    if old_program_id is not None:
        candidates.extend(
            date.fromisoformat(item["effective_from"])
            for item in current.authority_transitions
            if item["program_id"] == old_program_id
            and item["publication_id"] not in previous_ids
        )
    if not candidates:
        raise ContractIssuanceError(
            f"No se puede determinar la fecha efectiva autoritativa del retiro de {_line_identity(old)}."
        )
    return min(candidates)


def _metadata_changes(
    previous: dict[str, Any], current: ContractSnapshot
) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    previous_teacher = previous.get("teacher") if isinstance(previous.get("teacher"), dict) else {}
    for field, label in (("full_name", "Nombre del docente"), ("ci", "CI del docente")):
        before = str(previous_teacher.get(field, ""))
        after = str(current.teacher.get(field, ""))
        if before != after:
            changes.append({"field": field, "label": label, "previous": before, "current": after})
    for field, label, before, after in (
        ("department", "Departamento del CI", previous.get("department"), current.department),
        (
            "template_version",
            "Versión de plantilla",
            previous.get("template_version"),
            current.template_version,
        ),
    ):
        if before != after:
            changes.append({
                "field": field,
                "label": label,
                "previous": str(before or ""),
                "current": str(after),
            })
    return changes


def _delta_lines(
    previous: dict[str, Any] | None,
    current: ContractSnapshot,
    *,
    issuance_date: date,
) -> tuple[list[dict[str, Any]], date, list[dict[str, str]]]:
    current_lines = [asdict(line) for line in current.lines]
    if previous is None:
        return (
            [dict(line, change_kind="full") for line in current_lines],
            min(date.fromisoformat(line["effective_from"]) for line in current_lines),
            [],
        )

    previous_lines = previous.get("lines")
    if not isinstance(previous_lines, list):
        raise ContractIssuanceError("El contrato anterior no contiene un snapshot de líneas válido.")
    before = {_line_identity(line): line for line in previous_lines}
    after = {_line_identity(line): line for line in current_lines}
    if len(before) != len(previous_lines) or len(after) != len(current_lines):
        raise ContractIssuanceError("La cobertura contractual contiene fuentes ambiguas.")

    delta: list[dict[str, Any]] = []
    effective_candidates: list[date] = []
    for key in sorted(before.keys() | after.keys()):
        old = before.get(key)
        new = after.get(key)
        if old is None and new is not None:
            delta.append(dict(new, change_kind="added"))
            effective_candidates.append(date.fromisoformat(new["effective_from"]))
        elif old is not None and new is None:
            removed = dict(old)
            removed.update(
                change_kind="removed",
                previous_hours=old["hours"],
                previous_hourly_rate=old["hourly_rate"],
                previous_source_key=key,
                hours="0.00",
            )
            delta.append(removed)
            effective_candidates.append(_removal_effective_date(old, previous, current))
        elif old != new and old is not None and new is not None:
            changed = dict(new)
            changed.update(
                change_kind="changed",
                previous_hours=old["hours"],
                previous_hourly_rate=old["hourly_rate"],
                previous_source_key=key,
            )
            delta.append(changed)
            old_end = date.fromisoformat(old["effective_to"])
            new_end = date.fromisoformat(new["effective_to"])
            candidate = new_end.fromordinal(new_end.toordinal() + 1) if new_end < old_end else date.fromisoformat(new["effective_from"])
            effective_candidates.append(candidate)
    metadata_changes = _metadata_changes(previous, current)
    if not delta and not metadata_changes:
        raise ContractIssuanceError("El digest cambió sin diferencias contractuales identificables.")
    period_start = date.fromisoformat(current.academic_period["start"])
    period_end = date.fromisoformat(current.academic_period["end"])
    effective_date = min(effective_candidates) if effective_candidates else issuance_date
    if effective_candidates and not period_start <= effective_date <= period_end:
        raise ContractIssuanceError("La fecha efectiva de la enmienda queda fuera del período académico.")
    return delta, effective_date, metadata_changes


def _load_history(db: Session, teacher_ci: str, academic_period: str) -> list[ContractDocument]:
    return (
        db.query(ContractDocument)
        .options(selectinload(ContractDocument.lines))
        .filter(
            ContractDocument.teacher_ci == teacher_ci,
            ContractDocument.academic_period == academic_period,
        )
        .order_by(ContractDocument.amendment_sequence)
        .all()
    )


def _validate_history(history: list[ContractDocument]) -> None:
    if not history:
        return
    original = history[0]
    if (
        original.document_kind != "original"
        or original.amendment_sequence != 0
        or original.root_contract_id is not None
        or original.predecessor_contract_id is not None
    ):
        raise ContractIssuanceError("El historial contractual no comienza con un original válido.")
    for sequence, document in enumerate(history[1:], start=1):
        predecessor = history[sequence - 1]
        if (
            document.document_kind != "amendment"
            or document.amendment_sequence != sequence
            or document.root_contract_id != original.id
            or document.predecessor_contract_id != predecessor.id
        ):
            raise ContractIssuanceError("El historial contractual tiene una cadena de enmiendas inválida.")


def issue_contract(
    db: Session,
    *,
    teacher_ci: str,
    academic_period: str,
    department: str,
) -> ContractDocument:
    """Issue once or append an amendment; unchanged snapshots are idempotent."""
    from app.services.contract_pdf import render_contract_document_pdf

    db.query(Teacher).filter(Teacher.ci == teacher_ci).with_for_update().first()
    history = _load_history(db, teacher_ci, academic_period)
    _validate_history(history)
    predecessor = history[-1] if history else None
    tracked_program_ids = {
        int(line["publication_program_id"])
        for line in (predecessor.full_snapshot.get("lines", []) if predecessor else [])
        if line.get("publication_program_id") is not None
    }
    snapshot = build_contract_snapshot(
        db,
        teacher_ci=teacher_ci,
        academic_period=academic_period,
        department=department,
        allow_empty=bool(history),
        tracked_program_ids=tracked_program_ids,
    )
    existing = db.query(ContractDocument).filter(
        ContractDocument.teacher_ci == teacher_ci,
        ContractDocument.academic_period == academic_period,
        ContractDocument.source_digest == snapshot.digest,
    ).first()
    if existing is not None:
        return existing

    issued_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    delta_lines, effective_date, metadata_changes = _delta_lines(
        predecessor.full_snapshot if predecessor is not None else None,
        snapshot,
        issuance_date=issued_at.date(),
    )
    sequence = 0 if predecessor is None else predecessor.amendment_sequence + 1
    kind = "original" if predecessor is None else "amendment"
    root = None if predecessor is None else (predecessor.root_contract_id or predecessor.id)
    public_id = str(uuid4())
    render_payload = {
        **snapshot.canonical_payload(),
        "public_id": public_id,
        "document_kind": kind,
        "amendment_sequence": sequence,
        "effective_date": effective_date.isoformat(),
        "issued_at": issued_at.isoformat(),
        "root_public_id": history[0].public_id if history else None,
        "lines": delta_lines,
        "metadata_changes": metadata_changes,
    }
    pdf_bytes = render_contract_document_pdf(render_payload)
    artifact_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    filename = f"Contrato_{teacher_ci}_{academic_period.replace('/', '-')}_v{sequence + 1}.pdf"
    document = ContractDocument(
        public_id=public_id,
        teacher_ci=teacher_ci,
        teacher_name=str(snapshot.teacher["full_name"]),
        teacher_snapshot=snapshot.teacher,
        academic_period=academic_period,
        period_snapshot=snapshot.academic_period,
        document_kind=kind,
        root_contract_id=root,
        predecessor_contract_id=predecessor.id if predecessor else None,
        amendment_sequence=sequence,
        effective_date=effective_date,
        issued_at=issued_at,
        source_digest=snapshot.digest,
        template_version=TEMPLATE_VERSION,
        status="issued",
        department=department,
        full_snapshot=snapshot.storage_payload(),
        artifact_filename=filename,
        artifact_media_type="application/pdf",
        artifact_sha256=artifact_sha256,
        artifact_size=len(pdf_bytes),
        artifact_content=pdf_bytes,
    )
    for number, line in enumerate(delta_lines, start=1):
        document.lines.append(ContractLine(
            line_number=number,
            activity_kind=line["activity_kind"],
            rate_class=line["rate_class"],
            hourly_rate=Decimal(line["hourly_rate"]),
            hours=Decimal(line["hours"]),
            hour_basis=line["hour_basis"],
            subject_label=line["subject_label"],
            group_label=line["group_label"],
            semester_label=line["semester_label"],
            schedule_label=line["schedule_label"],
            effective_from=date.fromisoformat(line["effective_from"]),
            effective_to=date.fromisoformat(line["effective_to"]),
            source_kind=line["source_kind"],
            source_id=line["source_id"],
            designation_id=line.get("designation_id"),
            publication_id=line.get("publication_id"),
            publication_sequence=line.get("publication_sequence"),
            publication_program_id=line.get("publication_program_id"),
            authority_effective_from=date.fromisoformat(line["authority_effective_from"]),
            published_block_id=line.get("published_block_id"),
            published_assignment_id=line.get("published_assignment_id"),
            change_kind=line["change_kind"],
            previous_hours=Decimal(line["previous_hours"]) if line.get("previous_hours") is not None else None,
            previous_hourly_rate=Decimal(line["previous_hourly_rate"]) if line.get("previous_hourly_rate") is not None else None,
            previous_source_key=line.get("previous_source_key"),
        ))
    db.add(document)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = db.query(ContractDocument).filter(
            ContractDocument.teacher_ci == teacher_ci,
            ContractDocument.academic_period == academic_period,
            ContractDocument.source_digest == snapshot.digest,
        ).first()
        if replay is not None:
            return replay
        raise ContractIssuanceError(
            "Otra emisión modificó simultáneamente el historial; reintentá para emitir la siguiente enmienda."
        )
    db.refresh(document)
    return document
