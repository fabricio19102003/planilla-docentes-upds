from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

MONEY_QUANTUM = Decimal("0.01")
MAX_OVERRIDE = Decimal("9999999999.99")


class PaymentOverrideError(ValueError):
    def __init__(self, code: str, message: str, keys: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.sample = [_opaque(key) for key in (keys or [])[:5]]

    def as_detail(self) -> dict[str, object]:
        return {"code": self.code, "message": str(self), "sample": self.sample}


def _opaque(key: str) -> str:
    return hashlib.sha256(f"payment-override:{key}".encode()).hexdigest()[:16]


def _key_parts(key: Any) -> tuple[str, int | None]:
    if not isinstance(key, str) or not key or key != key.strip() or key.count(":") > 1:
        raise PaymentOverrideError("payment_override_key_invalid", "Override key must be a teacher CI or teacher CI plus designation ID", [str(key)])
    if ":" not in key:
        return key, None
    teacher_ci, designation_text = key.split(":")
    if not teacher_ci or not designation_text.isdigit() or int(designation_text) <= 0:
        raise PaymentOverrideError("payment_override_key_invalid", "Designation override key must use <teacher_ci>:<positive_designation_id>", [key])
    return teacher_ci, int(designation_text)


def _amount(key: str, value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PaymentOverrideError("payment_override_not_finite", "Override amount must be finite", [key]) from exc
    if not amount.is_finite():
        raise PaymentOverrideError("payment_override_not_finite", "Override amount must be finite", [key])
    if amount < 0 or amount > MAX_OVERRIDE:
        raise PaymentOverrideError("payment_override_out_of_range", "Override amount must fit Numeric(12,2) and be non-negative", [key])
    if amount.as_tuple().exponent < -2:
        raise PaymentOverrideError("payment_override_precision", "Override amount cannot have more than two decimal places", [key])
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def normalize_payment_overrides(overrides: dict[str, Any] | None) -> dict[str, Decimal]:
    normalized: dict[str, Decimal] = {}
    for key in sorted((overrides or {}), key=str):
        _key_parts(key)
        normalized[key] = _amount(key, overrides[key])
    return normalized


def validate_payment_override_targets(rows: list[Any], overrides: dict[str, Decimal]) -> None:
    valid_teachers = {row.teacher_ci for row in rows}
    valid_rows = {f"{row.teacher_ci}:{row.designation_id}" for row in rows}
    unknown = [key for key in overrides if key not in valid_teachers and key not in valid_rows]
    if unknown:
        raise PaymentOverrideError("payment_override_unknown_key", "Override key does not match a calculated teacher or designation", unknown)
    row_totals: dict[str, Decimal] = {}
    for key, value in overrides.items():
        teacher_ci, designation_id = _key_parts(key)
        if designation_id is not None:
            row_totals[teacher_ci] = row_totals.get(teacher_ci, Decimal("0")) + value
    exceeded = [teacher for teacher, total in row_totals.items() if teacher in overrides and total > overrides[teacher]]
    if exceeded:
        raise PaymentOverrideError("payment_override_rows_exceed_teacher", "Designation overrides cannot exceed the teacher override", exceeded)


def get_teacher_override_allocations(teacher_rows: list[Any], overrides: dict[str, Decimal]) -> dict[int, Decimal] | None:
    teacher_ci = teacher_rows[0].teacher_ci
    teacher_override = overrides.get(teacher_ci)
    if teacher_override is None:
        return None
    allocations: dict[int, Decimal] = {}
    remaining_rows = []
    for row in sorted(teacher_rows, key=lambda item: item.designation_id):
        explicit = overrides.get(f"{teacher_ci}:{row.designation_id}")
        if explicit is None:
            remaining_rows.append(row)
        else:
            allocations[row.designation_id] = explicit
    remaining = teacher_override - sum(allocations.values(), Decimal("0"))
    if remaining < 0:
        raise PaymentOverrideError("payment_override_rows_exceed_teacher", "Designation overrides cannot exceed the teacher override", [teacher_ci])
    if not remaining_rows:
        if remaining != 0:
            raise PaymentOverrideError(
                "override_unallocated_amount", "Explicit designation overrides must fully allocate the teacher override", [teacher_ci],
            )
        return allocations
    weights = [Decimal(str(max(0, row.total_hours))) for row in remaining_rows]
    total_weight = sum(weights, Decimal("0"))
    if total_weight == 0:
        weights = [Decimal("1")] * len(remaining_rows)
        total_weight = Decimal(len(remaining_rows))
    allocated = Decimal("0")
    for row, weight in zip(remaining_rows[:-1], weights[:-1]):
        share = (remaining * weight / total_weight).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        allocations[row.designation_id] = share
        allocated += share
    allocations[remaining_rows[-1].designation_id] = remaining - allocated
    return allocations


def calculate_override_total(rows: list[Any], overrides: dict[str, Decimal]) -> Decimal:
    validate_payment_override_targets(rows, overrides)
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        grouped.setdefault(row.teacher_ci, []).append(row)
    allocations = {teacher: get_teacher_override_allocations(items, overrides) for teacher, items in grouped.items()}
    total = Decimal("0")
    for row in rows:
        value = (allocations[row.teacher_ci] or {}).get(row.designation_id)
        if value is None:
            value = overrides.get(f"{row.teacher_ci}:{row.designation_id}", Decimal(str(row.final_payment)))
        total += value
    return total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
