"""Validated preview/apply workflow for designation imports.

The service intentionally separates parsing/planning from mutation.  A caller must
preview the exact file and academic period, then submit the same bytes together
with the returned digest before any database row is changed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.designation_loader import DesignationLoader, normalize_name
from app.utils.helpers import calc_academic_hours, normalize_group_code


PERIOD_RE = re.compile(r"^(I|II)/\d{4}$")
CI_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{0,19}$")
SUPPORTED_TYPES = {"regular", "practice"}
DAY_NAMES = {
    "lunes",
    "martes",
    "miercoles",
    "miércoles",
    "jueves",
    "viernes",
    "sabado",
    "sábado",
    "domingo",
}
MUTABLE_DESIGNATION_FIELDS = (
    "schedule_json",
    "semester_hours",
    "monthly_hours",
    "weekly_hours",
    "weekly_hours_calculated",
    "schedule_raw",
    "designation_type",
    "contract_start_date",
    "contract_end_date",
)
TEACHER_MUTABLE_FIELDS = (
    "email",
    "phone",
    "bank",
    "account_number",
    "nit",
    "invoice_retention",
)


class DesignationImportError(ValueError):
    """Actionable validation failure that must not be partially applied."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class CanonicalDesignationRow:
    teacher_ci: str | None
    teacher_name: str
    subject: str
    semester: str
    group_code: str
    academic_period: str
    schedule_json: list[dict[str, Any]]
    semester_hours: int | None = None
    monthly_hours: int | None = None
    weekly_hours: int | None = None
    weekly_hours_calculated: int | None = None
    schedule_raw: str | None = None
    designation_type: str = "regular"
    contract_start_date: Any = None
    contract_end_date: Any = None
    email: str | None = None
    phone: str | None = None
    bank: str | None = None
    account_number: str | None = None
    nit: str | None = None
    invoice_retention: str | None = None

    @property
    def business_key(self) -> tuple[str, str, str, str, str]:
        if self.teacher_ci is None:
            raise RuntimeError("Teacher identity has not been resolved")
        return (
            self.teacher_ci,
            self.subject,
            self.semester,
            self.group_code,
            self.academic_period,
        )


@dataclass
class ImportCounts:
    creates: int = 0
    updates: int = 0
    noops: int = 0
    conflicts: int = 0


@dataclass
class DesignationImportPlan:
    digest: str
    parsed_format: str
    academic_period: str
    total_rows: int
    teachers: ImportCounts = field(default_factory=ImportCounts)
    designations: ImportCounts = field(default_factory=ImportCounts)
    users: ImportCounts = field(default_factory=ImportCounts)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rows: list[CanonicalDesignationRow] = field(default_factory=list, repr=False)

    @property
    def can_apply(self) -> bool:
        return not self.errors and not (
            self.teachers.conflicts
            or self.designations.conflicts
            or self.users.conflicts
        )


def confirmation_digest(raw_bytes: bytes, academic_period: str) -> str:
    """Bind confirmation to the exact bytes and explicitly selected period."""
    payload = academic_period.encode("utf-8") + b"\0" + raw_bytes
    return hashlib.sha256(payload).hexdigest()


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _prepass_text(value: Any) -> str:
    """Read text during audit-envelope grouping without coercing nested JSON."""
    return _normalize_text(value) if isinstance(value, str) else ""


def _required_text(value: Any, field_name: str, row_number: int, errors: list[str]) -> str:
    if not isinstance(value, str):
        errors.append(f"Fila {row_number}: '{field_name}' debe ser texto.")
        return ""
    cleaned = _normalize_text(value)
    if not cleaned:
        errors.append(f"Fila {row_number}: falta el campo obligatorio '{field_name}'.")
    return cleaned


def _optional_text(
    value: Any,
    field_name: str,
    row_number: int,
    errors: list[str],
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"Fila {row_number}: '{field_name}' debe ser texto cuando está presente.")
        return None
    return _normalize_text(value) or None


def _optional_int(value: Any, field_name: str, row_number: int, errors: list[str]) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        errors.append(f"Fila {row_number}: '{field_name}' debe ser un número entero.")
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors.append(f"Fila {row_number}: '{field_name}' debe ser un número entero.")
        return None
    if parsed < 0:
        errors.append(f"Fila {row_number}: '{field_name}' no puede ser negativo.")
    return parsed


def _validate_ci(
    value: Any,
    row_number: int,
    errors: list[str],
    field_name: str = "teacher_ci",
) -> str:
    ci = _required_text(value, field_name, row_number, errors)
    if not ci:
        return ""
    elif (
        ci.upper().startswith("TEMP-")
        or not CI_RE.fullmatch(ci)
        or not any(character.isdigit() for character in ci)
    ):
        errors.append(f"Fila {row_number}: el CI no es una identidad real válida.")
    return ci


def _optional_date(value: Any, field_name: str, row_number: int, errors: list[str]) -> date | None:
    raw = _optional_text(value, field_name, row_number, errors)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors.append(f"Fila {row_number}: '{field_name}' debe usar el formato AAAA-MM-DD.")
        return None


def _canonical_schedule(value: Any, row_number: int, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        errors.append(f"Fila {row_number}: el horario debe contener al menos un bloque.")
        return []

    result: list[dict[str, Any]] = []
    for slot_number, slot in enumerate(value, start=1):
        if not isinstance(slot, dict):
            errors.append(f"Fila {row_number}, horario {slot_number}: el bloque debe ser un objeto.")
            continue
        day_value = slot.get("dia") if "dia" in slot else slot.get("day")
        start_value = slot.get("hora_inicio") if "hora_inicio" in slot else slot.get("start_time")
        end_value = slot.get("hora_fin") if "hora_fin" in slot else slot.get("end_time")
        day = _required_text(
            day_value,
            f"horario {slot_number}.dia",
            row_number,
            errors,
        ).lower()
        start = _required_text(
            start_value,
            f"horario {slot_number}.hora_inicio",
            row_number,
            errors,
        )
        end = _required_text(
            end_value,
            f"horario {slot_number}.hora_fin",
            row_number,
            errors,
        )
        if day not in DAY_NAMES:
            errors.append(f"Fila {row_number}, horario {slot_number}: día no soportado.")
        try:
            start_time = datetime.strptime(start, "%H:%M")
            end_time = datetime.strptime(end, "%H:%M")
            duration = int((end_time - start_time).total_seconds() / 60)
            if duration <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(
                f"Fila {row_number}, horario {slot_number}: las horas deben usar HH:MM y finalizar después del inicio."
            )
            duration = 0
        raw_hours = slot.get("horas_academicas", slot.get("hours_academicas"))
        hours = (
            calc_academic_hours(duration)
            if raw_hours in (None, "") and duration > 0
            else _optional_int(
                raw_hours,
                f"horario {slot_number}.horas_academicas",
                row_number,
                errors,
            )
        )
        if hours is None or hours <= 0:
            errors.append(f"Fila {row_number}, horario {slot_number}: las horas académicas deben ser mayores a cero.")
        result.append(
            {
                "dia": day.replace("á", "a").replace("é", "e"),
                "hora_inicio": start,
                "hora_fin": end,
                "duracion_minutos": duration,
                "horas_academicas": hours or 0,
            }
        )
    return result


class DesignationImportService:
    """Parse, preview and atomically stage designation imports."""

    def __init__(self) -> None:
        self.legacy_loader = DesignationLoader()
        self.auth_service = AuthService()

    def preview(
        self,
        db: Session,
        raw_bytes: bytes,
        academic_period: str,
        digest_bytes: bytes | None = None,
    ) -> DesignationImportPlan:
        digest = confirmation_digest(digest_bytes if digest_bytes is not None else raw_bytes, academic_period)
        try:
            parsed_format, rows, warnings = self._parse(raw_bytes, academic_period)
            plan = self._build_plan(db, digest, parsed_format, academic_period, rows, warnings)
        except DesignationImportError as exc:
            plan = DesignationImportPlan(
                digest=digest,
                parsed_format="unknown",
                academic_period=academic_period,
                total_rows=0,
                errors=exc.errors,
            )
        return plan

    def apply(
        self,
        db: Session,
        raw_bytes: bytes,
        academic_period: str,
        expected_digest: str,
        actor_id: int | None = None,
        digest_bytes: bytes | None = None,
    ) -> DesignationImportPlan:
        actual_digest = confirmation_digest(
            digest_bytes if digest_bytes is not None else raw_bytes,
            academic_period,
        )
        if not hmac.compare_digest(actual_digest, expected_digest):
            raise DesignationImportError(
                ["El archivo o el período cambiaron después de la vista previa. Generá una nueva vista previa."]
            )

        parsed_format, rows, warnings = self._parse(raw_bytes, academic_period)
        plan = self._build_plan(db, actual_digest, parsed_format, academic_period, rows, warnings)
        if not plan.can_apply:
            raise DesignationImportError(plan.errors or ["La importación contiene conflictos sin resolver."])

        teachers_by_ci = {teacher.ci: teacher for teacher in db.query(Teacher).all()}
        for row in self._unique_teacher_rows(plan.rows).values():
            assert row.teacher_ci is not None
            teacher = teachers_by_ci.get(row.teacher_ci)
            if teacher is None:
                teacher = Teacher(ci=row.teacher_ci, full_name=row.teacher_name)
                db.add(teacher)
                teachers_by_ci[row.teacher_ci] = teacher
            for field_name in TEACHER_MUTABLE_FIELDS:
                value = getattr(row, field_name)
                if value:
                    setattr(teacher, field_name, value)
        db.flush()

        existing_designations = {
            (
                item.teacher_ci,
                item.subject,
                item.semester,
                item.group_code,
                item.academic_period,
            ): item
            for item in db.query(Designation).filter(
                Designation.academic_period == academic_period
            )
        }
        for row in plan.rows:
            item = existing_designations.get(row.business_key)
            if item is None:
                item = Designation(
                    teacher_ci=row.teacher_ci,
                    subject=row.subject,
                    semester=row.semester,
                    group_code=row.group_code,
                    academic_period=row.academic_period,
                    schedule_json=row.schedule_json,
                    semester_hours=row.semester_hours,
                    monthly_hours=row.monthly_hours,
                    weekly_hours=row.weekly_hours,
                    weekly_hours_calculated=row.weekly_hours_calculated,
                    schedule_raw=row.schedule_raw,
                    designation_type=row.designation_type,
                    contract_start_date=row.contract_start_date,
                    contract_end_date=row.contract_end_date,
                )
                db.add(item)
                existing_designations[row.business_key] = item
            else:
                for field_name in MUTABLE_DESIGNATION_FIELDS:
                    setattr(item, field_name, getattr(row, field_name))
        db.flush()

        users_by_ci = {user.ci: user for user in db.query(User).all()}
        for row in self._unique_teacher_rows(plan.rows).values():
            assert row.teacher_ci is not None
            user = users_by_ci.get(row.teacher_ci)
            if user is None:
                user = User(
                    ci=row.teacher_ci,
                    full_name=row.teacher_name,
                    password_hash=self.auth_service.hash_password(settings.DOCENTE_DEFAULT_PASSWORD),
                    role="docente",
                    teacher_ci=row.teacher_ci,
                    is_active=True,
                    must_change_password=True,
                    created_by=actor_id,
                )
                db.add(user)
                users_by_ci[row.teacher_ci] = user
            elif user.teacher_ci is None:
                user.teacher_ci = row.teacher_ci
        db.flush()
        return plan

    def _parse(
        self,
        raw_bytes: bytes,
        academic_period: str,
    ) -> tuple[str, list[CanonicalDesignationRow], list[str]]:
        errors: list[str] = []
        if not PERIOD_RE.fullmatch(academic_period):
            errors.append("El período debe usar el formato I/AAAA o II/AAAA.")
        try:
            data = json.loads(raw_bytes.decode("utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise DesignationImportError(["El archivo JSON debe estar codificado en UTF-8."]) from exc
        except json.JSONDecodeError as exc:
            raise DesignationImportError([f"JSON inválido en la línea {exc.lineno}, columna {exc.colno}."]) from exc

        if isinstance(data, dict) and set(("academic_period", "contract", "rows")) <= set(data):
            parsed_format = "audit_envelope"
            rows = self._parse_audit_envelope(data, academic_period, errors)
        elif isinstance(data, dict) and "designaciones" in data:
            parsed_format = "legacy"
            entries = data.get("designaciones")
            rows = self._parse_legacy_entries(entries, academic_period, errors)
        elif isinstance(data, list):
            if not data:
                errors.append("El archivo no contiene designaciones.")
                parsed_format = "unknown"
                rows = []
            elif all(isinstance(entry, dict) and "CI" in entry and "NOMBRE COMPLETO" in entry for entry in data):
                parsed_format = "upds_official"
                rows = self._parse_official_entries(data, academic_period, errors)
            elif all(isinstance(entry, dict) and "docente" in entry and "horario_detalle" in entry for entry in data):
                parsed_format = "intermediate"
                rows = self._parse_intermediate_entries(data, academic_period, errors)
            else:
                parsed_format = "unknown"
                rows = []
                errors.append("El arreglo JSON no coincide con un formato de designaciones soportado.")
        else:
            parsed_format = "unknown"
            rows = []
            errors.append(
                "El objeto JSON no coincide con el sobre auditado ni con el formato legacy soportado."
            )

        if not rows and not errors:
            errors.append("El archivo no contiene designaciones.")
        if errors:
            raise DesignationImportError(errors)
        return parsed_format, rows, []

    def _parse_audit_envelope(
        self,
        data: dict[str, Any],
        selected_period: str,
        errors: list[str],
    ) -> list[CanonicalDesignationRow]:
        envelope_period = _required_text(
            data.get("academic_period"),
            "academic_period",
            0,
            errors,
        )
        if envelope_period != selected_period:
            errors.append(
                f"El período del archivo ({envelope_period or 'vacío'}) no coincide con el período seleccionado ({selected_period})."
            )
        if not isinstance(data.get("contract"), dict):
            errors.append("El sobre auditado requiere un objeto 'contract'.")
        raw_rows = data.get("rows")
        if not isinstance(raw_rows, list) or not raw_rows:
            errors.append("El sobre auditado requiere una lista 'rows' no vacía.")
            return []

        names_by_ci: dict[str, list[str]] = {}
        explicit_names_by_ci: dict[str, set[str]] = {}
        for raw_row in raw_rows:
            if not isinstance(raw_row, dict) or not isinstance(raw_row.get("identity"), dict):
                continue
            identity = raw_row["identity"]
            ci = _prepass_text(identity.get("teacher_ci"))
            official_name = _prepass_text(identity.get("official_name_normalized"))
            canonical_name = _prepass_text(identity.get("canonical_name"))
            if ci and official_name:
                names_by_ci.setdefault(ci, []).append(official_name.upper())
            if ci and canonical_name:
                explicit_names_by_ci.setdefault(ci, set()).add(canonical_name.upper())
        selected_names: dict[str, str] = {}
        for ci, names in names_by_ci.items():
            explicit_names = explicit_names_by_ci.get(ci, set())
            if len(explicit_names) > 1:
                errors.append("Un CI contiene más de un nombre canónico dentro del sobre auditado.")
            elif explicit_names:
                selected_names[ci] = next(iter(explicit_names))
            else:
                selected_names[ci] = Counter(names).most_common(1)[0][0]

        rows: list[CanonicalDesignationRow] = []
        for index, raw_row in enumerate(raw_rows, start=1):
            if not isinstance(raw_row, dict):
                errors.append(f"Fila {index}: cada fila auditada debe ser un objeto.")
                continue
            identity = raw_row.get("identity")
            designation = raw_row.get("designation")
            if not isinstance(identity, dict) or not isinstance(designation, dict):
                errors.append(f"Fila {index}: faltan los objetos 'identity' o 'designation'.")
                continue
            row_contract = raw_row.get("contract")
            if row_contract is not None and not isinstance(row_contract, dict):
                errors.append(f"Fila {index}: 'contract' debe ser un objeto.")
            elif isinstance(row_contract, dict):
                if "loaded" in row_contract and not isinstance(row_contract["loaded"], bool):
                    errors.append(f"Fila {index}: 'contract.loaded' debe ser booleano.")
                _optional_text(
                    row_contract.get("status"),
                    "contract.status",
                    index,
                    errors,
                )
            source = raw_row.get("source")
            if source is not None and not isinstance(source, dict):
                errors.append(f"Fila {index}: 'source' debe ser un objeto.")
            elif isinstance(source, dict):
                for source_field in ("file", "sheet", "sha256"):
                    _optional_text(
                        source.get(source_field),
                        f"source.{source_field}",
                        index,
                        errors,
                    )
            ci = _validate_ci(
                identity.get("teacher_ci"),
                index,
                errors,
                "identity.teacher_ci",
            )
            designation_ci = _validate_ci(
                designation.get("teacher_ci"),
                index,
                errors,
                "designation.teacher_ci",
            )
            if designation_ci != ci:
                errors.append(f"Fila {index}: el CI de identity y designation no coincide.")
            _required_text(
                identity.get("official_name_normalized"),
                "identity.official_name_normalized",
                index,
                errors,
            )
            _optional_text(
                identity.get("canonical_name"),
                "identity.canonical_name",
                index,
                errors,
            )
            _required_text(
                identity.get("match_method"),
                "identity.match_method",
                index,
                errors,
            )
            name = selected_names.get(ci, "")
            row_period = _required_text(
                designation.get("academic_period"), "designation.academic_period", index, errors
            )
            if row_period != selected_period:
                errors.append(f"Fila {index}: el período no coincide con el período seleccionado.")
            designation_type = _required_text(
                designation.get("designation_type"),
                "designation.designation_type",
                index,
                errors,
            )
            if designation_type not in SUPPORTED_TYPES:
                errors.append(f"Fila {index}: tipo de designación no soportado.")
            _optional_text(
                designation.get("load_basis"),
                "designation.load_basis",
                index,
                errors,
            )
            _optional_text(
                designation.get("schedule_raw_original"),
                "designation.schedule_raw_original",
                index,
                errors,
            )
            schedule = _canonical_schedule(designation.get("schedule_json"), index, errors)
            weekly = _optional_int(designation.get("weekly_hours"), "weekly_hours", index, errors)
            calculated = _optional_int(
                designation.get("weekly_hours_calculated"),
                "weekly_hours_calculated",
                index,
                errors,
            )
            slot_hours = sum(slot["horas_academicas"] for slot in schedule)
            if weekly is not None and weekly != slot_hours:
                errors.append(f"Fila {index}: weekly_hours no coincide con la suma del horario.")
            if calculated is not None and calculated != slot_hours:
                errors.append(f"Fila {index}: weekly_hours_calculated no coincide con la suma del horario.")
            rows.append(
                CanonicalDesignationRow(
                    teacher_ci=ci,
                    teacher_name=name,
                    subject=_required_text(designation.get("subject"), "designation.subject", index, errors),
                    semester=_required_text(designation.get("semester"), "designation.semester", index, errors),
                    group_code=normalize_group_code(
                        _required_text(designation.get("group_code"), "designation.group_code", index, errors)
                    ),
                    academic_period=row_period,
                    schedule_json=schedule,
                    semester_hours=_optional_int(
                        designation.get("semester_hours"), "semester_hours", index, errors
                    ),
                    monthly_hours=_optional_int(
                        designation.get("monthly_hours"), "monthly_hours", index, errors
                    ),
                    weekly_hours=weekly,
                    weekly_hours_calculated=calculated,
                    schedule_raw=_optional_text(
                        designation.get("schedule_raw"),
                        "designation.schedule_raw",
                        index,
                        errors,
                    ),
                    designation_type=designation_type,
                )
            )
        return rows

    def _parse_official_entries(
        self, entries: list[dict[str, Any]], academic_period: str, errors: list[str]
    ) -> list[CanonicalDesignationRow]:
        rows: list[CanonicalDesignationRow] = []
        for index, entry in enumerate(entries, start=1):
            ci = _validate_ci(entry.get("CI"), index, errors, "CI")
            name = _required_text(entry.get("NOMBRE COMPLETO"), "NOMBRE COMPLETO", index, errors).upper()
            subject = _required_text(entry.get("MATERIAS"), "MATERIAS", index, errors)
            schedule_raw = _required_text(entry.get("HORARIO"), "HORARIO", index, errors)
            schedule = _canonical_schedule(
                self.legacy_loader._parse_horario_string(schedule_raw), index, errors
            )
            contract_start = _optional_date(entry.get("FECHA INICIO"), "FECHA INICIO", index, errors)
            contract_end = _optional_date(entry.get("FECHA FIN"), "FECHA FIN", index, errors)
            if contract_start and contract_end and contract_end < contract_start:
                errors.append(f"Fila {index}: FECHA FIN no puede ser anterior a FECHA INICIO.")
            email = _optional_text(entry.get("CORREO"), "CORREO", index, errors)
            if email and "@" not in email:
                errors.append(f"Fila {index}: CORREO no contiene una dirección válida.")
            raw_nit = _optional_text(entry.get("NIT"), "NIT", index, errors)
            retention = None
            if raw_nit and normalize_name(raw_nit) in {"RETENCION", "RETENCIÓN"}:
                retention = "RETENCION"
                raw_nit = None
            rows.append(
                CanonicalDesignationRow(
                    teacher_ci=ci,
                    teacher_name=name,
                    subject=subject,
                    semester=_required_text(entry.get("SEMESTRE"), "SEMESTRE", index, errors),
                    group_code=normalize_group_code(
                        _required_text(entry.get("GRUPO"), "GRUPO", index, errors)
                    ),
                    academic_period=academic_period,
                    schedule_json=schedule,
                    semester_hours=_optional_int(entry.get("CARGA HORARIA SEMESTRAL"), "CARGA HORARIA SEMESTRAL", index, errors),
                    monthly_hours=_optional_int(entry.get("CARGA HORARIA MENSUAL"), "CARGA HORARIA MENSUAL", index, errors),
                    weekly_hours=_optional_int(entry.get("CARGA HORARIA SEMANAL"), "CARGA HORARIA SEMANAL", index, errors),
                    weekly_hours_calculated=sum(slot["horas_academicas"] for slot in schedule),
                    schedule_raw=schedule_raw,
                    designation_type=self.legacy_loader._detect_designation_type(subject),
                    contract_start_date=contract_start,
                    contract_end_date=contract_end,
                    email=email,
                    phone=_optional_text(
                        entry.get("NÚMERO DE TELÉFONO"),
                        "NÚMERO DE TELÉFONO",
                        index,
                        errors,
                    ),
                    bank=_optional_text(entry.get("BANCO"), "BANCO", index, errors),
                    account_number=_optional_text(
                        entry.get("NÚMERO CUENTA BANCARIA"),
                        "NÚMERO CUENTA BANCARIA",
                        index,
                        errors,
                    ),
                    nit=raw_nit,
                    invoice_retention=retention,
                )
            )
        return rows

    def _parse_intermediate_entries(
        self, entries: list[dict[str, Any]], academic_period: str, errors: list[str]
    ) -> list[CanonicalDesignationRow]:
        rows: list[CanonicalDesignationRow] = []
        for index, entry in enumerate(entries, start=1):
            schedule = _canonical_schedule(entry.get("horario_detalle"), index, errors)
            subject = _required_text(entry.get("materias"), "materias", index, errors)
            rows.append(
                CanonicalDesignationRow(
                    teacher_ci=None,
                    teacher_name=_required_text(entry.get("docente"), "docente", index, errors).upper(),
                    subject=subject,
                    semester=_required_text(entry.get("semestre"), "semestre", index, errors),
                    group_code=normalize_group_code(_required_text(entry.get("grupo"), "grupo", index, errors)),
                    academic_period=academic_period,
                    schedule_json=schedule,
                    semester_hours=_optional_int(entry.get("carga_horaria"), "carga_horaria", index, errors),
                    monthly_hours=_optional_int(entry.get("mes"), "mes", index, errors),
                    weekly_hours=_optional_int(entry.get("semana"), "semana", index, errors),
                    weekly_hours_calculated=sum(slot["horas_academicas"] for slot in schedule),
                    schedule_raw=_optional_text(
                        entry.get("horario"), "horario", index, errors
                    ),
                    designation_type=self.legacy_loader._detect_designation_type(subject),
                )
            )
        return rows

    def _parse_legacy_entries(
        self, entries: Any, academic_period: str, errors: list[str]
    ) -> list[CanonicalDesignationRow]:
        if not isinstance(entries, list) or not entries:
            errors.append("El formato legacy requiere una lista 'designaciones' no vacía.")
            return []
        rows: list[CanonicalDesignationRow] = []
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                errors.append(f"Fila {index}: cada designación legacy debe ser un objeto.")
                continue
            schedule = _canonical_schedule(entry.get("horario"), index, errors)
            subject = _required_text(entry.get("materia"), "materia", index, errors)
            rows.append(
                CanonicalDesignationRow(
                    teacher_ci=None,
                    teacher_name=_required_text(entry.get("docente"), "docente", index, errors).upper(),
                    subject=subject,
                    semester=_required_text(entry.get("semestre"), "semestre", index, errors),
                    group_code=normalize_group_code(_required_text(entry.get("grupo"), "grupo", index, errors)),
                    academic_period=academic_period,
                    schedule_json=schedule,
                    semester_hours=_optional_int(entry.get("carga_horaria_semestral"), "carga_horaria_semestral", index, errors),
                    monthly_hours=_optional_int(entry.get("carga_horaria_mensual"), "carga_horaria_mensual", index, errors),
                    weekly_hours=_optional_int(entry.get("carga_horaria_semanal"), "carga_horaria_semanal", index, errors),
                    weekly_hours_calculated=_optional_int(
                        entry.get("total_horas_academicas_semanal_calculado"),
                        "total_horas_academicas_semanal_calculado",
                        index,
                        errors,
                    ) or sum(slot["horas_academicas"] for slot in schedule),
                    schedule_raw=_optional_text(
                        entry.get("horario_raw"), "horario_raw", index, errors
                    ),
                    designation_type=self.legacy_loader._detect_designation_type(subject),
                )
            )
        return rows

    def _build_plan(
        self,
        db: Session,
        digest: str,
        parsed_format: str,
        academic_period: str,
        rows: list[CanonicalDesignationRow],
        warnings: list[str],
    ) -> DesignationImportPlan:
        plan = DesignationImportPlan(
            digest=digest,
            parsed_format=parsed_format,
            academic_period=academic_period,
            total_rows=len(rows),
            warnings=list(warnings),
        )
        teachers = db.query(Teacher).all()
        teachers_by_ci = {item.ci: item for item in teachers}
        teachers_by_name: dict[str, list[Teacher]] = {}
        for item in teachers:
            if not item.ci.upper().startswith("TEMP-"):
                teachers_by_name.setdefault(normalize_name(item.full_name), []).append(item)

        resolved_rows: list[CanonicalDesignationRow] = []
        for index, row in enumerate(rows, start=1):
            if row.teacher_ci is None:
                matches = teachers_by_name.get(normalize_name(row.teacher_name), [])
                if len(matches) != 1:
                    plan.errors.append(
                        f"Fila {index}: el formato sin CI requiere exactamente un docente real existente con ese nombre."
                    )
                    continue
                row = replace(row, teacher_ci=matches[0].ci)
            resolved_rows.append(row)
        plan.rows = resolved_rows

        errors_before_teacher_merge = len(plan.errors)
        unique_teachers = self._unique_teacher_rows(resolved_rows, plan.errors)
        plan.teachers.conflicts += len(plan.errors) - errors_before_teacher_merge
        input_names: dict[str, str] = {}
        for ci, row in unique_teachers.items():
            normalized_name = normalize_name(row.teacher_name)
            previous_ci = input_names.get(normalized_name)
            if previous_ci and previous_ci != ci:
                plan.errors.append("El archivo asigna el mismo nombre normalizado a CIs diferentes.")
                plan.teachers.conflicts += 1
            input_names[normalized_name] = ci

            existing = teachers_by_ci.get(ci)
            same_name_other_ci = [item for item in teachers_by_name.get(normalized_name, []) if item.ci != ci]
            if existing and normalize_name(existing.full_name) != normalized_name:
                plan.errors.append(f"El CI {ci} ya pertenece a otro nombre de docente.")
                plan.teachers.conflicts += 1
            elif same_name_other_ci:
                plan.errors.append(f"El nombre del docente asociado al CI {ci} ya pertenece a otro CI.")
                plan.teachers.conflicts += 1
            elif existing is None:
                plan.teachers.creates += 1
            elif any(
                getattr(row, field_name) and getattr(existing, field_name) != getattr(row, field_name)
                for field_name in TEACHER_MUTABLE_FIELDS
            ):
                plan.teachers.updates += 1
            else:
                plan.teachers.noops += 1

        duplicate_keys: set[tuple[str, str, str, str, str]] = set()
        seen_keys: set[tuple[str, str, str, str, str]] = set()
        for row in resolved_rows:
            if row.business_key in seen_keys:
                duplicate_keys.add(row.business_key)
            seen_keys.add(row.business_key)
        if duplicate_keys:
            plan.designations.conflicts += len(duplicate_keys)
            plan.errors.append(
                f"El archivo contiene {len(duplicate_keys)} clave(s) de designación duplicada(s)."
            )

        existing_designations = {
            (
                item.teacher_ci,
                item.subject,
                item.semester,
                item.group_code,
                item.academic_period,
            ): item
            for item in db.query(Designation).filter(Designation.academic_period == academic_period)
        }
        for row in resolved_rows:
            existing = existing_designations.get(row.business_key)
            if existing is None:
                plan.designations.creates += 1
            elif any(getattr(existing, field_name) != getattr(row, field_name) for field_name in MUTABLE_DESIGNATION_FIELDS):
                plan.designations.updates += 1
            else:
                plan.designations.noops += 1

        users = db.query(User).all()
        users_by_ci = {item.ci: item for item in users}
        docent_names: dict[str, list[User]] = {}
        for item in users:
            if item.role == "docente":
                docent_names.setdefault(normalize_name(item.full_name), []).append(item)
        for ci, row in unique_teachers.items():
            user = users_by_ci.get(ci)
            other_named_users = [item for item in docent_names.get(normalize_name(row.teacher_name), []) if item.ci != ci]
            if user and (
                user.role != "docente"
                or user.teacher_ci not in (None, ci)
                or normalize_name(user.full_name) != normalize_name(row.teacher_name)
            ):
                plan.users.conflicts += 1
                plan.errors.append(f"El CI {ci} ya tiene una cuenta incompatible.")
            elif other_named_users:
                plan.users.conflicts += 1
                plan.errors.append(f"El docente del CI {ci} ya tiene una cuenta con otro CI.")
            elif user is None:
                plan.users.creates += 1
            elif user.teacher_ci is None:
                plan.users.updates += 1
            else:
                plan.users.noops += 1
        return plan

    @staticmethod
    def _unique_teacher_rows(
        rows: list[CanonicalDesignationRow], errors: list[str] | None = None
    ) -> dict[str, CanonicalDesignationRow]:
        unique: dict[str, CanonicalDesignationRow] = {}
        for row in rows:
            if row.teacher_ci is None:
                continue
            existing = unique.get(row.teacher_ci)
            if existing and normalize_name(existing.teacher_name) != normalize_name(row.teacher_name):
                if errors is not None:
                    errors.append(f"El CI {row.teacher_ci} aparece con nombres diferentes dentro del archivo.")
                continue
            if existing is None:
                unique[row.teacher_ci] = row
                continue
            merged = existing
            for field_name in TEACHER_MUTABLE_FIELDS:
                previous_value = getattr(merged, field_name)
                current_value = getattr(row, field_name)
                if previous_value and current_value and previous_value != current_value:
                    if errors is not None:
                        errors.append(
                            f"El CI {row.teacher_ci} contiene valores diferentes para '{field_name}'."
                        )
                elif not previous_value and current_value:
                    merged = replace(merged, **{field_name: current_value})
            unique[row.teacher_ci] = merged
        return unique
