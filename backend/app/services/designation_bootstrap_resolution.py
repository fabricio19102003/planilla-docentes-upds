"""Ephemeral, source-bound alias choices for designation bootstrap workbooks."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time as time_module
from datetime import date
from typing import Any

from app.services.designation_bootstrap_preview import (
    ALIAS_SCHEMA_VERSION,
    OfficialRow,
    SalaryRow,
    _parse_official,
    _parse_salary,
    _sha,
)

RESOLUTION_TOKEN_VERSION = "designation-resolution-v1"
RESOLUTION_TOKEN_TTL_SECONDS = 15 * 60


class DesignationBootstrapResolutionError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _sign(key: str, payload: bytes) -> str:
    return hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _binding_token(
    signing_key: str,
    official_sha256: str,
    salary_sha256: str,
    academic_period: str,
    effective_date: date,
    issued_at: int,
) -> str:
    payload = json.dumps({
        "v": RESOLUTION_TOKEN_VERSION,
        "official": official_sha256,
        "salary": salary_sha256,
        "period": academic_period,
        "date": effective_date.isoformat(),
        "iat": issued_at,
    }, sort_keys=True, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    return f"{encoded}.{_sign(signing_key, payload)}"


def _verify_binding_token(
    token: str,
    *,
    signing_key: str,
    official_sha256: str,
    salary_sha256: str,
    academic_period: str,
    effective_date: date,
    now: int,
) -> None:
    try:
        encoded, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if not hmac.compare_digest(signature, _sign(signing_key, payload)):
            raise ValueError
        claims = json.loads(payload)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise DesignationBootstrapResolutionError("invalid_resolution_token") from None
    if not isinstance(claims, dict) or claims.get("v") != RESOLUTION_TOKEN_VERSION:
        raise DesignationBootstrapResolutionError("invalid_resolution_token")
    issued_at = claims.get("iat")
    if isinstance(issued_at, bool) or not isinstance(issued_at, int):
        raise DesignationBootstrapResolutionError("invalid_resolution_token")
    if issued_at > now + 30 or now - issued_at > RESOLUTION_TOKEN_TTL_SECONDS:
        raise DesignationBootstrapResolutionError("expired_resolution_token")
    expected = {
        "official": official_sha256,
        "salary": salary_sha256,
        "period": academic_period,
        "date": effective_date.isoformat(),
    }
    if any(claims.get(name) != value for name, value in expected.items()):
        raise DesignationBootstrapResolutionError("stale_resolution_sources")


def _candidate_token(
    signing_key: str,
    *,
    official_sha256: str,
    salary_sha256: str,
    official_teacher_key: str,
    salary_teacher_key: str,
    salary_ci: str,
) -> str:
    payload = "\0".join((
        RESOLUTION_TOKEN_VERSION,
        official_sha256,
        salary_sha256,
        official_teacher_key,
        salary_teacher_key,
        salary_ci,
    )).encode()
    return _sign(signing_key, payload)[:32]


def _mask_ci(ci: str) -> str:
    if len(ci) <= 1:
        return "•"
    visible_count = min(4, len(ci) - 1)
    return f"{'•' * (len(ci) - visible_count)}{ci[-visible_count:]}"


def _parse_sources(official_content: bytes, salary_content: bytes) -> tuple[list[OfficialRow], list[SalaryRow]]:
    official, official_errors, _warnings, _activity_errors, _stats, _sheets = _parse_official(official_content)
    salary, salary_errors, _stats, _sheets = _parse_salary(salary_content)
    if official_errors or salary_errors:
        raise DesignationBootstrapResolutionError("invalid_resolution_sources")
    return official, salary


def _representative(rows: list[OfficialRow] | list[SalaryRow], raw_field: str) -> str:
    return min(
        (str(getattr(row, raw_field)).strip() for row in rows if str(getattr(row, raw_field)).strip()),
        key=lambda value: (value.casefold(), value),
    )


def _build_choices(
    official: list[OfficialRow],
    salary: list[SalaryRow],
    *,
    signing_key: str,
    official_sha256: str,
    salary_sha256: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, tuple[str, str]]]:
    practice = [row for row in official if row.activity == "practice" and row.semester is not None]
    salary = salary if practice else []
    official_by_teacher: dict[str, list[OfficialRow]] = {}
    for row in practice:
        official_by_teacher.setdefault(row.teacher_key, []).append(row)
    salary_by_identity: dict[tuple[str, str], list[SalaryRow]] = {}
    for row in salary:
        if row.teacher_key and row.ci_key and row.semester is not None:
            salary_by_identity.setdefault((row.teacher_key, row.ci_key), []).append(row)

    official_teacher_keys = set(official_by_teacher)
    direct_salary_identities = {
        identity for identity in salary_by_identity if identity[0] in official_teacher_keys
    }
    teacher_choices: list[dict[str, Any]] = []
    candidate_lookup: dict[str, tuple[str, str]] = {}
    salary_teacher_keys = {row.teacher_key for row in salary if row.teacher_key}
    for official_key in sorted(official_teacher_keys - salary_teacher_keys):
        official_rows = official_by_teacher[official_key]
        exact_signatures = {(row.subject_key, row.semester) for row in official_rows}
        semesters = {row.semester for row in official_rows}
        exact_candidates = {
            identity for identity, rows in salary_by_identity.items()
            if identity not in direct_salary_identities
            and any((row.subject_key, row.semester) in exact_signatures for row in rows)
        }
        candidate_identities = exact_candidates or {
            identity for identity, rows in salary_by_identity.items()
            if identity not in direct_salary_identities
            and any(row.semester in semesters for row in rows)
        }
        candidates: list[dict[str, str]] = []
        for salary_key, salary_ci in sorted(candidate_identities):
            token = _candidate_token(
                signing_key,
                official_sha256=official_sha256,
                salary_sha256=salary_sha256,
                official_teacher_key=official_key,
                salary_teacher_key=salary_key,
                salary_ci=salary_ci,
            )
            candidate_lookup[token] = (salary_key, salary_ci)
            candidates.append({
                "candidate_token": token,
                "salary_teacher_display": _representative(salary_by_identity[(salary_key, salary_ci)], "teacher_raw"),
                "salary_teacher_key": salary_key,
                "masked_ci": _mask_ci(salary_ci),
            })
        teacher_choices.append({
            "official_teacher_display": _representative(official_rows, "teacher_raw"),
            "official_teacher_key": official_key,
            "candidates": candidates,
        })

    official_subjects: dict[tuple[str, int], list[OfficialRow]] = {}
    salary_subjects: dict[tuple[str, int], list[SalaryRow]] = {}
    for row in practice:
        official_subjects.setdefault((row.subject_key, row.semester), []).append(row)
    for row in salary:
        if row.subject_key and row.semester is not None:
            salary_subjects.setdefault((row.subject_key, row.semester), []).append(row)
    direct_subjects = set(official_subjects) & set(salary_subjects)
    subject_choices: list[dict[str, Any]] = []
    for salary_key, semester in sorted(set(salary_subjects) - set(official_subjects), key=lambda item: (item[1], item[0])):
        candidates = [
            {
                "official_subject_display": _representative(rows, "subject_raw"),
                "official_subject_key": official_key,
            }
            for (official_key, official_semester), rows in sorted(official_subjects.items())
            if official_semester == semester and (official_key, semester) not in direct_subjects
        ]
        subject_choices.append({
            "salary_subject_display": _representative(salary_subjects[(salary_key, semester)], "subject_raw"),
            "salary_subject_key": salary_key,
            "semester": semester,
            "candidates": candidates,
        })
    return teacher_choices, subject_choices, candidate_lookup


def build_designation_bootstrap_resolution_context(
    *,
    official_content: bytes,
    salary_content: bytes,
    academic_period: str,
    effective_date: date,
    signing_key: str,
    now: int | None = None,
) -> dict[str, Any]:
    if academic_period != "II/2026" or effective_date != date(2026, 8, 21):
        raise DesignationBootstrapResolutionError("invalid_resolution_scope")
    official, salary = _parse_sources(official_content, salary_content)
    official_sha256, salary_sha256 = _sha(official_content), _sha(salary_content)
    teacher_choices, subject_choices, _lookup = _build_choices(
        official,
        salary,
        signing_key=signing_key,
        official_sha256=official_sha256,
        salary_sha256=salary_sha256,
    )
    issued_at = int(time_module.time()) if now is None else now
    return {
        "resolution_token": _binding_token(
            signing_key, official_sha256, salary_sha256,
            academic_period, effective_date, issued_at,
        ),
        "expires_in_seconds": RESOLUTION_TOKEN_TTL_SECONDS,
        "teacher_resolutions": teacher_choices,
        "subject_resolutions": subject_choices,
    }


def build_designation_bootstrap_alias_artifact(
    *,
    official_content: bytes,
    salary_content: bytes,
    academic_period: str,
    effective_date: date,
    resolution_token: str,
    teacher_selections: list[dict[str, str]],
    subject_selections: list[dict[str, Any]],
    signing_key: str,
    now: int | None = None,
) -> bytes:
    current_time = int(time_module.time()) if now is None else now
    official_sha256, salary_sha256 = _sha(official_content), _sha(salary_content)
    _verify_binding_token(
        resolution_token,
        signing_key=signing_key,
        official_sha256=official_sha256,
        salary_sha256=salary_sha256,
        academic_period=academic_period,
        effective_date=effective_date,
        now=current_time,
    )
    official, salary = _parse_sources(official_content, salary_content)
    teacher_choices, subject_choices, candidate_lookup = _build_choices(
        official,
        salary,
        signing_key=signing_key,
        official_sha256=official_sha256,
        salary_sha256=salary_sha256,
    )
    expected_teachers = {item["official_teacher_key"] for item in teacher_choices}
    expected_subjects = {
        (item["salary_subject_key"], item["semester"]) for item in subject_choices
    }
    selected_teacher_keys = [item.get("official_teacher_key") for item in teacher_selections]
    selected_subject_keys = [
        (item.get("salary_subject_key"), item.get("semester")) for item in subject_selections
    ]
    if (set(selected_teacher_keys) != expected_teachers
            or len(selected_teacher_keys) != len(set(selected_teacher_keys))
            or set(selected_subject_keys) != expected_subjects
            or len(selected_subject_keys) != len(set(selected_subject_keys))):
        raise DesignationBootstrapResolutionError("incomplete_alias_selections")

    allowed_teacher_tokens = {
        item["official_teacher_key"]: {
            candidate["candidate_token"] for candidate in item["candidates"]
        }
        for item in teacher_choices
    }
    teacher_aliases: dict[str, dict[str, str]] = {}
    used_identities: set[tuple[str, str]] = set()
    for selection in teacher_selections:
        official_key = selection["official_teacher_key"]
        candidate_token = selection["candidate_token"]
        if candidate_token not in allowed_teacher_tokens.get(official_key, set()):
            raise DesignationBootstrapResolutionError("invalid_alias_selection")
        identity = candidate_lookup[candidate_token]
        if identity in used_identities:
            raise DesignationBootstrapResolutionError("duplicate_alias_target")
        used_identities.add(identity)
        teacher_aliases[official_key] = {
            "salary_teacher_key": identity[0],
            "salary_ci": identity[1],
        }

    allowed_subjects = {
        (item["salary_subject_key"], item["semester"]): {
            candidate["official_subject_key"] for candidate in item["candidates"]
        }
        for item in subject_choices
    }
    subject_aliases: list[dict[str, Any]] = []
    used_subject_targets: set[tuple[str, int]] = set()
    for selection in subject_selections:
        source = (selection["salary_subject_key"], selection["semester"])
        target = (selection["official_subject_key"], selection["semester"])
        if selection["official_subject_key"] not in allowed_subjects.get(source, set()):
            raise DesignationBootstrapResolutionError("invalid_alias_selection")
        if target in used_subject_targets:
            raise DesignationBootstrapResolutionError("duplicate_alias_target")
        used_subject_targets.add(target)
        subject_aliases.append({
            "salary_subject_key": selection["salary_subject_key"],
            "official_subject_key": selection["official_subject_key"],
            "semester": selection["semester"],
            "activity_type": "practice",
        })
    subject_aliases.sort(key=lambda item: (item["semester"], item["salary_subject_key"]))

    artifact = {
        "schema_version": ALIAS_SCHEMA_VERSION,
        "official_sha256": official_sha256,
        "salary_sha256": salary_sha256,
        "academic_period": academic_period,
        "effective_date": effective_date.isoformat(),
        "teacher_aliases": teacher_aliases,
        "subject_aliases": subject_aliases,
    }
    return json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
