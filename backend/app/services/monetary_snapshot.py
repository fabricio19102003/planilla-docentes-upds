from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from types import SimpleNamespace
from typing import Any, Iterable

MONEY_QUANTUM = Decimal("0.01")
PAYROLL_PROFILE_FIELDS = (
    "phone", "email", "nit", "account_number", "bank", "sap_code", "invoice_retention",
)


class SnapshotReconciliationError(ValueError):
    def __init__(self, code: str, message: str, sample: Iterable[str] = ()):
        super().__init__(message)
        self.code = code
        self.sample = list(sample)[:5]

    def as_detail(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "sample": self.sample}


def _money(value: Any, sample: str = "snapshot") -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SnapshotReconciliationError("invalid_money", "Snapshot contains invalid money", [sample]) from exc
    if not amount.is_finite() or amount < 0:
        raise SnapshotReconciliationError("invalid_money", "Snapshot money must be finite and non-negative", [sample])
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _serialized_money(value: Any, sample: str = "snapshot") -> str:
    return format(_money(value, sample), ".2f")


def _nonnegative(value: Any, sample: str) -> Any:
    try:
        if not Decimal(str(value)).is_finite() or Decimal(str(value)) < 0:
            raise ValueError
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SnapshotReconciliationError("invalid_value", "Snapshot values must be finite and non-negative", [sample]) from exc
    return value


def _teacher_ref(ci: Any) -> str:
    return hashlib.sha256(f"payroll-teacher:{ci}".encode()).hexdigest()[:16]


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _profile_value(value: Any) -> str | None:
    return None if value is None else str(value)


def calculation_snapshot_digest(snapshot: dict[str, Any]) -> str:
    payload = {key: value for key, value in snapshot.items() if key != "digest"}
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_calculation_snapshot(
    *,
    rows: list[Any],
    row_amounts: list[Any],
    month: int,
    year: int,
    start_date: date | None,
    end_date: date | None,
    discount_mode: str,
    payment_overrides: dict[str, Any],
    excluded_days: list[Any],
) -> dict[str, Any]:
    if len(rows) != len(row_amounts):
        raise SnapshotReconciliationError("row_amount_count_mismatch", "Every designation requires one amount")
    period_start = start_date or date(year, month, 1)
    period_end = end_date or date(year, month, calendar.monthrange(year, month)[1])
    designations = []
    teacher_totals: dict[str, Decimal] = {}
    teacher_designations: dict[str, list[int]] = {}
    profiles: dict[str, dict[str, Any]] = {}
    for row, amount_value in zip(rows, row_amounts):
        opaque_ref = _teacher_ref(row.teacher_ci)
        amount = _money(amount_value, f"designation:{row.designation_id}")
        teacher_totals[opaque_ref] = teacher_totals.get(opaque_ref, Decimal("0")) + amount
        teacher_designations.setdefault(opaque_ref, []).append(row.designation_id)
        profile = {
            "teacher_ref": opaque_ref,
            **{field: _profile_value(getattr(row, field, None)) for field in PAYROLL_PROFILE_FIELDS},
        }
        if opaque_ref in profiles and profiles[opaque_ref] != profile:
            raise SnapshotReconciliationError("invalid_schema", "Teacher payroll profile differs across designations", [opaque_ref])
        profiles[opaque_ref] = profile
        designations.append({
            "designation_id": row.designation_id,
            "teacher_ref": opaque_ref,
            "teacher_ci": str(row.teacher_ci),
            "teacher_name": str(row.teacher_name),
            "has_biometric": bool(row.has_biometric),
            "has_retention": bool(row.has_retention),
            "subject": str(row.subject),
            "group": str(row.group_code),
            "semester": str(row.semester),
            "base_hours": _nonnegative(row.base_monthly_hours, opaque_ref),
            "absent_hours": _nonnegative(row.absent_hours, opaque_ref),
            "payable_hours": _nonnegative(row.payable_hours, opaque_ref),
            "rate": _serialized_money(row.rate_per_hour, f"designation:{row.designation_id}"),
            "gross": _serialized_money(row.calculated_payment, f"designation:{row.designation_id}"),
            "retention": _serialized_money(row.retention_amount, f"designation:{row.designation_id}"),
            "retention_rate": _serialized_money(row.retention_rate, f"designation:{row.designation_id}"),
            "amount": format(amount, ".2f"),
        })
    designations.sort(key=lambda item: item["designation_id"])
    teachers = [
        {"teacher_ref": ref, "designation_ids": sorted(teacher_designations[ref]), "total": format(total, ".2f")}
        for ref, total in sorted(teacher_totals.items())
    ]
    snapshot = {
        "schema_version": 1,
        "period": {"month": month, "year": year, "start": period_start.isoformat(), "end": period_end.isoformat()},
        "discount_mode": discount_mode,
        "rates": sorted({_serialized_money(row.rate_per_hour) for row in rows}),
        "excluded_days": sorted((_json_value(item) for item in excluded_days), key=lambda item: json.dumps(item, sort_keys=True)),
        "overrides": {key: _serialized_money(value, f"override:{key}") for key, value in sorted(payment_overrides.items())},
        "designations": designations,
        "teachers": teachers,
        # Limited to the admin-only salary XLSX columns and immutable payroll evidence.
        "profiles": [profiles[ref] for ref in sorted(profiles)],
        "total": format(sum(teacher_totals.values(), Decimal("0")), ".2f"),
        "metadata": {"designation_count": len(designations), "teacher_count": len(teachers), "source": "generated_rows_v1"},
    }
    snapshot["digest"] = calculation_snapshot_digest(snapshot)
    reconcile_calculation_snapshot(snapshot, Decimal(snapshot["total"]))
    return snapshot


def reconcile_calculation_snapshot(snapshot: Any, expected_total: Any) -> None:
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1:
        raise SnapshotReconciliationError("invalid_schema", "Unsupported or malformed snapshot schema")
    try:
        period = snapshot["period"]
        if snapshot["discount_mode"] not in {"attendance", "full"} or date.fromisoformat(period["start"]) > date.fromisoformat(period["end"]):
            raise ValueError
        designations = snapshot["designations"]
        teachers = snapshot["teachers"]
        metadata = snapshot["metadata"]
        profiles = snapshot.get("profiles")
        digest = snapshot["digest"]
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError
        if metadata["designation_count"] != len(designations) or metadata["teacher_count"] != len(teachers):
            raise ValueError
        if profiles is not None and not isinstance(profiles, list):
            raise ValueError
        total = _money(snapshot["total"])
        for value in snapshot.get("rates", []):
            _money(value, "rate")
        for key, value in snapshot.get("overrides", {}).items():
            _money(value, f"override:{key}")
    except SnapshotReconciliationError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotReconciliationError("invalid_schema", "Snapshot is missing required reconciliation data") from exc
    by_teacher: dict[str, Decimal] = {}
    for item in designations:
        ref = str(item.get("teacher_ref", "unknown"))
        for field in ("base_hours", "absent_hours", "payable_hours"):
            _nonnegative(item.get(field), ref)
        for field in ("rate", "gross", "retention", "retention_rate", "amount"):
            _money(item.get(field), ref)
        for field in ("teacher_ci", "teacher_name", "subject", "group", "semester"):
            if not isinstance(item.get(field), str):
                raise SnapshotReconciliationError("invalid_schema", "Snapshot is missing publication data", [ref])
        by_teacher[ref] = by_teacher.get(ref, Decimal("0")) + _money(item["amount"], ref)
    teacher_sum = Decimal("0")
    seen = set()
    for item in teachers:
        ref = str(item.get("teacher_ref", "unknown"))
        teacher_total = _money(item.get("total"), ref)
        if ref in seen or by_teacher.get(ref) != teacher_total:
            raise SnapshotReconciliationError("teacher_total_mismatch", "Designation sum does not match teacher total", [ref])
        seen.add(ref)
        teacher_sum += teacher_total
    if profiles is not None:
        profile_refs = set()
        for profile in profiles:
            ref = profile.get("teacher_ref") if isinstance(profile, dict) else None
            if ref in profile_refs or ref not in seen:
                raise SnapshotReconciliationError("invalid_schema", "Snapshot payroll profile has invalid teacher reference")
            if any(profile.get(field) is not None and not isinstance(profile.get(field), str) for field in PAYROLL_PROFILE_FIELDS):
                raise SnapshotReconciliationError("invalid_schema", "Snapshot payroll profile contains invalid data", [ref])
            profile_refs.add(ref)
        if profile_refs != seen:
            raise SnapshotReconciliationError("invalid_schema", "Snapshot payroll profile does not cover every teacher")
    missing = sorted(set(by_teacher) - seen)
    if missing:
        raise SnapshotReconciliationError("teacher_total_mismatch", "Designation has no matching teacher total", missing)
    if teacher_sum != total:
        raise SnapshotReconciliationError("planilla_total_mismatch", "Teacher sum does not match planilla total", sorted(seen))
    if total != _money(expected_total, "stored_total"):
        raise SnapshotReconciliationError("stored_total_mismatch", "Snapshot total does not match stored total", sorted(seen))
    if snapshot["digest"] != calculation_snapshot_digest(snapshot):
        raise SnapshotReconciliationError("snapshot_digest_mismatch", "Snapshot digest does not match its contents")


def require_reconciled_snapshot(snapshot: Any, expected_total: Any) -> None:
    if snapshot is None:
        raise SnapshotReconciliationError("snapshot_missing", "Planilla has no immutable calculation snapshot")
    try:
        reconcile_calculation_snapshot(snapshot, expected_total)
    except SnapshotReconciliationError as exc:
        raise SnapshotReconciliationError("snapshot_mismatch", f"Snapshot reconciliation failed: {exc.code}", exc.sample) from exc


def calculation_snapshot_rows(
    snapshot: Any, expected_total: Any, *, require_profiles: bool = False,
) -> list[SimpleNamespace]:
    require_reconciled_snapshot(snapshot, expected_total)
    overrides = snapshot.get("overrides", {})
    profiles = snapshot.get("profiles")
    if require_profiles and not isinstance(profiles, list):
        raise SnapshotReconciliationError(
            "snapshot_profile_missing", "Snapshot has no immutable payroll profile",
        )
    profiles_by_ref = {item["teacher_ref"]: item for item in (profiles or [])}
    rows = []
    for item in snapshot["designations"]:
        profile = profiles_by_ref.get(item["teacher_ref"])
        if require_profiles and profile is None:
            raise SnapshotReconciliationError(
                "snapshot_profile_missing", "Snapshot payroll profile is incomplete", [item["teacher_ref"]],
            )
        row_key = f'{item["teacher_ci"]}:{item["designation_id"]}'
        rows.append(SimpleNamespace(
            designation_id=item["designation_id"], teacher_ci=item["teacher_ci"],
            teacher_name=item["teacher_name"], subject=item["subject"],
            group_code=item["group"], semester=item["semester"],
            has_biometric=item["has_biometric"], has_retention=item["has_retention"],
            base_monthly_hours=item["base_hours"], absent_hours=item["absent_hours"],
            payable_hours=item["payable_hours"], rate_per_hour=_money(item["rate"]),
            calculated_payment=_money(item["gross"]), retention_amount=_money(item["retention"]),
            retention_rate=_money(item["retention_rate"]), final_payment=_money(item["amount"]),
            has_admin_override=item["teacher_ci"] in overrides or row_key in overrides,
            late_count=0, absent_count=0, observations=[],
            **{field: (profile or {}).get(field) for field in PAYROLL_PROFILE_FIELDS},
        ))
    return rows
