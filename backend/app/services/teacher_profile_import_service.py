"""Preview/confirm workflow for fill-empty-only teacher profile imports."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.domain.teacher_types import normalize_teacher_type
from app.models.teacher import Teacher


PERIOD_RE = re.compile(r"^(I|II)/\d{4}$")
CI_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 -]{0,19}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^[+0-9() .-]{5,30}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SUPPORTED_SCOPES = {"theory", "practice", "all"}
PROFILE_FIELDS = (
    "email",
    "phone",
    "gender",
    "external_permanent",
    "academic_level",
    "profession",
    "specialty",
    "bank",
    "account_number",
    "nit",
    "sap_code",
    "invoice_retention",
)
FIELD_MAX_LENGTHS = {
    "email": 200,
    "phone": 50,
    "gender": 20,
    "external_permanent": 50,
    "academic_level": 100,
    "profession": 200,
    "specialty": 2000,
    "bank": 100,
    "account_number": 50,
    "nit": 50,
    "sap_code": 50,
    "invoice_retention": 50,
}
GENDER_ALIASES = {
    "M": "M",
    "MASCULINO": "M",
    "F": "F",
    "FEMENINO": "F",
    "OTRO": "OTRO",
    "PREFIERO NO INDICAR": "PREFIERO NO INDICAR",
}


class TeacherProfileImportError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class CanonicalProfileRow:
    teacher_ci: str
    official_name: str
    profile: dict[str, str | None]


@dataclass
class FieldCoverage:
    creates: int = 0
    fills: int = 0
    noops: int = 0
    conflicts: int = 0
    missing: int = 0


@dataclass
class IdentityCoverage:
    matched: int = 0
    missing: int = 0
    duplicates: int = 0
    conflicts: int = 0


@dataclass
class TeacherProfileImportPlan:
    digest: str
    parsed_format: str
    academic_period: str
    scope: str
    policy: str
    total_rows: int
    rows_with_fills: int = 0
    identity: IdentityCoverage = field(default_factory=IdentityCoverage)
    fields: dict[str, FieldCoverage] = field(
        default_factory=lambda: {name: FieldCoverage() for name in PROFILE_FIELDS}
    )
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows: list[CanonicalProfileRow] = field(default_factory=list, repr=False)

    @property
    def can_apply(self) -> bool:
        return not self.errors and not (
            self.identity.missing
            or self.identity.duplicates
            or self.identity.conflicts
            or any(item.conflicts or item.creates for item in self.fields.values())
        )


def confirmation_digest(raw_bytes: bytes, academic_period: str) -> str:
    return hashlib.sha256(academic_period.encode("utf-8") + b"\0" + raw_bytes).hexdigest()


def _clean_text(value: Any, field_name: str, row_number: int, errors: list[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(f"Fila {row_number}: '{field_name}' debe ser texto o null.")
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    if len(cleaned) > FIELD_MAX_LENGTHS.get(field_name, 500):
        errors.append(f"Fila {row_number}: '{field_name}' supera la longitud permitida.")
        return None
    return cleaned


def _identity_text(value: Any, field_name: str, row_number: int, errors: list[str]) -> str:
    if not isinstance(value, str):
        errors.append(f"Fila {row_number}: '{field_name}' debe ser texto.")
        return ""
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        errors.append(f"Fila {row_number}: falta '{field_name}'.")
    return cleaned


def _identity_name(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return " ".join(normalized.upper().split())


def _canonical_profile(raw: dict[str, Any], row_number: int, errors: list[str]) -> dict[str, str | None]:
    unknown = sorted(set(raw) - set(PROFILE_FIELDS))
    if unknown:
        errors.append(
            f"Fila {row_number}: 'profile' contiene campos no soportados; use sólo el contrato documentado."
        )

    result = {name: _clean_text(raw.get(name), name, row_number, errors) for name in PROFILE_FIELDS}
    if result["email"]:
        result["email"] = result["email"].lower()
        if not EMAIL_RE.fullmatch(result["email"]):
            errors.append(f"Fila {row_number}: 'email' no tiene un formato válido.")
    if result["phone"] and not PHONE_RE.fullmatch(result["phone"]):
        errors.append(f"Fila {row_number}: 'phone' no tiene un formato válido.")
    if result["gender"]:
        gender = GENDER_ALIASES.get(result["gender"].upper())
        if gender is None:
            errors.append(f"Fila {row_number}: 'gender' no es un valor permitido.")
        result["gender"] = gender
    if result["external_permanent"]:
        try:
            result["external_permanent"] = normalize_teacher_type(result["external_permanent"])
        except ValueError:
            errors.append(f"Fila {row_number}: 'external_permanent' debe ser EXTERNO, PERMANENTE o TITULAR.")
            result["external_permanent"] = None
    if result["invoice_retention"]:
        retention = unicodedata.normalize("NFD", result["invoice_retention"].upper())
        retention = "".join(char for char in retention if unicodedata.category(char) != "Mn")
        if retention != "RETENCION":
            errors.append(f"Fila {row_number}: 'invoice_retention' sólo admite RETENCION o null.")
            result["invoice_retention"] = None
        else:
            result["invoice_retention"] = "RETENCION"
    return result


def _same(field_name: str, current: str, incoming: str) -> bool:
    if field_name == "email":
        return current.strip().lower() == incoming.strip().lower()
    if field_name in {"account_number", "nit", "sap_code", "phone"}:
        return current.strip() == incoming.strip()
    return _identity_name(current) == _identity_name(incoming)


class TeacherProfileImportService:
    def preview(self, db: Session, raw_bytes: bytes, academic_period: str) -> TeacherProfileImportPlan:
        digest = confirmation_digest(raw_bytes, academic_period)
        try:
            rows, scope, policy = self._parse(raw_bytes, academic_period)
            return self._build_plan(db, digest, academic_period, rows, scope, policy)
        except TeacherProfileImportError as exc:
            return TeacherProfileImportPlan(
                digest=digest,
                parsed_format="unknown",
                academic_period=academic_period,
                scope="unknown",
                policy="fill_empty_only",
                total_rows=0,
                errors=exc.errors,
            )

    def apply(
        self,
        db: Session,
        raw_bytes: bytes,
        academic_period: str,
        expected_digest: str,
    ) -> TeacherProfileImportPlan:
        actual_digest = confirmation_digest(raw_bytes, academic_period)
        if not hmac.compare_digest(actual_digest, expected_digest):
            raise TeacherProfileImportError(
                ["El archivo o el período cambiaron después de la vista previa. Generá una nueva vista previa."]
            )
        rows, scope, policy = self._parse(raw_bytes, academic_period)
        # Serialize the conflict check and fill-empty writes for these exact
        # identities. SQLite ignores this in unit tests; PostgreSQL enforces it.
        db.query(Teacher).filter(
            Teacher.ci.in_([row.teacher_ci for row in rows])
        ).with_for_update().all()
        plan = self._build_plan(db, actual_digest, academic_period, rows, scope, policy)
        if not plan.can_apply:
            raise TeacherProfileImportError(plan.errors or ["La importación contiene conflictos sin resolver."])

        teachers = {
            teacher.ci: teacher
            for teacher in db.query(Teacher).filter(Teacher.ci.in_([row.teacher_ci for row in rows])).all()
        }
        for row in rows:
            teacher = teachers[row.teacher_ci]
            for field_name, value in row.profile.items():
                if value is not None and not getattr(teacher, field_name):
                    setattr(teacher, field_name, value)
        db.flush()
        return plan

    def _parse(
        self,
        raw_bytes: bytes,
        academic_period: str,
    ) -> tuple[list[CanonicalProfileRow], str, str]:
        errors: list[str] = []
        if not PERIOD_RE.fullmatch(academic_period.strip()):
            errors.append("El período explícito debe usar I/AAAA o II/AAAA.")
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TeacherProfileImportError(["El archivo JSON no es válido."])
        if not isinstance(payload, dict):
            raise TeacherProfileImportError(["Use el formato audit_envelope de perfiles docentes."])
        unknown_envelope = sorted(set(payload) - {"academic_period", "scope", "contract", "rows"})
        if unknown_envelope:
            errors.append("El sobre contiene campos superiores no soportados.")
        envelope_period = payload.get("academic_period")
        if not isinstance(envelope_period, str) or envelope_period != academic_period:
            errors.append("El período del archivo no coincide con el período explícito seleccionado.")
        scope_payload = payload.get("scope")
        if not isinstance(scope_payload, dict):
            errors.append("El archivo requiere un objeto 'scope'.")
            scope = "unknown"
        else:
            unknown_scope = sorted(set(scope_payload) - {"population"})
            if unknown_scope:
                errors.append("El objeto 'scope' contiene campos no soportados.")
            scope = scope_payload.get("population")
            if not isinstance(scope, str) or not scope.strip():
                errors.append("El archivo requiere 'scope.population' como texto no vacío.")
                scope = "unknown"
            else:
                scope = scope.strip()
                if scope not in SUPPORTED_SCOPES:
                    errors.append("'scope.population' debe ser theory, practice o all.")
        contract = payload.get("contract")
        policy = contract.get("policy") if isinstance(contract, dict) else None
        if not isinstance(contract, dict):
            errors.append("El archivo requiere un objeto 'contract'.")
        elif sorted(set(contract) - {"policy", "source_revision"}):
            errors.append("El objeto 'contract' contiene campos no soportados.")
        elif contract.get("source_revision") is not None and not isinstance(contract.get("source_revision"), str):
            errors.append("'contract.source_revision' debe ser texto o null.")
        if policy != "fill_empty_only":
            errors.append("El contrato debe declarar policy='fill_empty_only'.")
            policy = "fill_empty_only"
        raw_rows = payload.get("rows")
        if not isinstance(raw_rows, list) or not raw_rows:
            errors.append("El archivo debe contener al menos una fila en 'rows'.")
            raw_rows = []

        rows: list[CanonicalProfileRow] = []
        for index, raw_row in enumerate(raw_rows, start=1):
            if not isinstance(raw_row, dict):
                errors.append(f"Fila {index}: la fila debe ser un objeto.")
                continue
            unknown_row = sorted(set(raw_row) - {"identity", "profile", "source"})
            if unknown_row:
                errors.append(f"Fila {index}: la fila contiene campos no soportados.")
            identity = raw_row.get("identity")
            profile = raw_row.get("profile")
            source = raw_row.get("source")
            if not isinstance(identity, dict):
                errors.append(f"Fila {index}: falta el objeto 'identity'.")
                continue
            unknown_identity = sorted(
                set(identity) - {"teacher_ci", "official_name_normalized"}
            )
            if unknown_identity:
                errors.append(f"Fila {index}: 'identity' contiene campos no soportados.")
            if not isinstance(profile, dict):
                errors.append(f"Fila {index}: falta el objeto 'profile'.")
                continue
            if not isinstance(source, dict):
                errors.append(f"Fila {index}: falta el objeto 'source'.")
            else:
                required_source = {"file", "sheet", "row", "sha256"}
                unknown_source = sorted(set(source) - required_source)
                if unknown_source:
                    errors.append(f"Fila {index}: 'source' contiene campos no soportados.")
                missing_source = sorted(required_source - set(source))
                if missing_source:
                    errors.append(
                        f"Fila {index}: faltan campos source obligatorios: {', '.join(missing_source)}."
                    )
                for source_name in ("file", "sheet"):
                    source_value = source.get(source_name)
                    if not isinstance(source_value, str) or not source_value.strip():
                        errors.append(
                            f"Fila {index}: 'source.{source_name}' debe ser texto no vacío."
                        )
                source_row = source.get("row")
                if isinstance(source_row, bool) or not isinstance(source_row, int) or source_row < 1:
                    errors.append(f"Fila {index}: 'source.row' debe ser un entero positivo.")
                source_sha = source.get("sha256")
                if not isinstance(source_sha, str) or not SHA256_RE.fullmatch(source_sha):
                    errors.append(
                        f"Fila {index}: 'source.sha256' debe contener 64 caracteres hexadecimales."
                    )
            ci = _identity_text(identity.get("teacher_ci"), "identity.teacher_ci", index, errors)
            name = _identity_text(
                identity.get("official_name_normalized"),
                "identity.official_name_normalized",
                index,
                errors,
            )
            if ci and (ci.upper().startswith("TEMP-") or not CI_RE.fullmatch(ci) or not any(c.isdigit() for c in ci)):
                errors.append(f"Fila {index}: el CI no es una identidad real válida.")
            rows.append(CanonicalProfileRow(ci, name, _canonical_profile(profile, index, errors)))
        if errors:
            raise TeacherProfileImportError(errors)
        return rows, scope, policy

    def _build_plan(
        self,
        db: Session,
        digest: str,
        academic_period: str,
        rows: list[CanonicalProfileRow],
        scope: str,
        policy: str,
    ) -> TeacherProfileImportPlan:
        plan = TeacherProfileImportPlan(
            digest=digest,
            parsed_format="audit_envelope",
            academic_period=academic_period,
            scope=scope,
            policy=policy,
            total_rows=len(rows),
            rows=rows,
        )
        teachers = {
            teacher.ci: teacher
            for teacher in db.query(Teacher).filter(Teacher.ci.in_([row.teacher_ci for row in rows])).all()
        }
        seen: set[str] = set()
        for row in rows:
            if row.teacher_ci in seen:
                plan.identity.duplicates += 1
                continue
            seen.add(row.teacher_ci)
            teacher = teachers.get(row.teacher_ci)
            if teacher is None:
                plan.identity.missing += 1
                for field_name, value in row.profile.items():
                    if value is not None:
                        plan.fields[field_name].creates += 1
                continue
            if _identity_name(teacher.full_name) != _identity_name(row.official_name):
                plan.identity.conflicts += 1
            else:
                plan.identity.matched += 1
            for field_name, incoming in row.profile.items():
                counts = plan.fields[field_name]
                if incoming is None:
                    counts.missing += 1
                    continue
                current = getattr(teacher, field_name)
                if current is None or (isinstance(current, str) and not current.strip()):
                    counts.fills += 1
                elif _same(field_name, current, incoming):
                    counts.noops += 1
                else:
                    counts.conflicts += 1
            if any(
                incoming is not None
                and (getattr(teacher, field_name) is None or not str(getattr(teacher, field_name)).strip())
                for field_name, incoming in row.profile.items()
            ):
                plan.rows_with_fills += 1
        if plan.identity.missing:
            plan.errors.append("Hay identidades que no existen en la base; este importador no crea docentes.")
        if plan.identity.duplicates:
            plan.errors.append("Hay CI duplicados en el archivo; cada docente debe aparecer una sola vez.")
        if plan.identity.conflicts:
            plan.errors.append("Hay CI cuyos nombres no coinciden con la identidad existente.")
        if any(item.conflicts for item in plan.fields.values()):
            plan.errors.append("Hay valores existentes distintos; fill_empty_only prohíbe sobrescribirlos.")
        return plan
