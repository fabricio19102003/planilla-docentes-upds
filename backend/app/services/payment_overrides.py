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


def _key_parts(key: Any) -> tuple[str, str | None, int | None]:
    if not isinstance(key, str) or not key or key != key.strip() or key.count(":") not in {0, 1, 2}:
        raise PaymentOverrideError("payment_override_key_invalid", "Override key must identify a teacher or an immutable schedule source", [str(key)])
    if ":" not in key:
        return key, None, None
    parts = key.split(":")
    if len(parts) == 2:
        teacher_ci, source_text = parts
        source_kind = "legacy"
    else:
        teacher_ci, source_kind, source_text = parts
        if source_kind not in {"legacy", "published"}:
            raise PaymentOverrideError("payment_override_key_invalid", "Typed override source must be legacy or published", [key])
    if not teacher_ci or not source_text.isdigit() or int(source_text) <= 0:
        raise PaymentOverrideError("payment_override_key_invalid", "Source override key must end with a positive source ID", [key])
    return teacher_ci, source_kind, int(source_text)


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
    valid_rows = {
        key
        for row in rows
        for key in (
            f"{row.teacher_ci}:{getattr(row, 'source_kind', 'legacy')}:{getattr(row, 'source_id', None) or row.designation_id}",
            *(
                (f"{row.teacher_ci}:{row.designation_id}",)
                if getattr(row, "source_kind", "legacy") == "legacy" else ()
            ),
        )
    }
    unknown = [key for key in overrides if key not in valid_teachers and key not in valid_rows]
    if unknown:
        raise PaymentOverrideError("payment_override_unknown_key", "Override key does not match a calculated teacher or designation", unknown)
    row_totals: dict[str, Decimal] = {}
    for key, value in overrides.items():
        teacher_ci, _source_kind, source_id = _key_parts(key)
        if source_id is not None:
            row_totals[teacher_ci] = row_totals.get(teacher_ci, Decimal("0")) + value
    exceeded = [teacher for teacher, total in row_totals.items() if teacher in overrides and total > overrides[teacher]]
    if exceeded:
        raise PaymentOverrideError("payment_override_rows_exceed_teacher", "Designation overrides cannot exceed the teacher override", exceeded)


def _allocation_key(row: Any) -> str | int:
    """Keep legacy callers keyed by designation ID while typed rows use source keys."""
    return getattr(row, "source_key", None) or row.designation_id


def get_teacher_override_allocations(teacher_rows: list[Any], overrides: dict[str, Decimal]) -> dict[str | int, Decimal] | None:
    teacher_ci = teacher_rows[0].teacher_ci
    teacher_override = overrides.get(teacher_ci)
    if teacher_override is None:
        return None
    allocations: dict[str | int, Decimal] = {}
    remaining_rows = []
    for row in sorted(teacher_rows, key=lambda item: str(_allocation_key(item))):
        source_key = getattr(row, "source_key", None) or f"legacy:{row.designation_id}"
        typed_key = f"{teacher_ci}:{source_key}"
        legacy_key = f"{teacher_ci}:{row.designation_id}" if source_key.startswith("legacy:") else None
        explicit = overrides.get(typed_key, overrides.get(legacy_key) if legacy_key else None)
        if explicit is None:
            remaining_rows.append(row)
        else:
            allocations[_allocation_key(row)] = explicit
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
        allocations[_allocation_key(row)] = share
        allocated += share
    final_row = remaining_rows[-1]
    allocations[_allocation_key(final_row)] = remaining - allocated
    return allocations


def resolve_row_override(
    row: Any,
    teacher_rows: list[Any],
    overrides: dict[str, Decimal],
    *,
    allocations: dict[str | int, Decimal] | None = None,
) -> Decimal | None:
    """Resolve one row using source-specific-over-teacher precedence."""
    if allocations is None:
        allocations = get_teacher_override_allocations(teacher_rows, overrides)
    if allocations is not None:
        allocated = allocations.get(_allocation_key(row))
        if allocated is not None:
            return allocated

    source_key = getattr(row, "source_key", None) or f"legacy:{row.designation_id}"
    typed_key = f"{row.teacher_ci}:{source_key}"
    if typed_key in overrides:
        return overrides[typed_key]
    if source_key.startswith("legacy:"):
        return overrides.get(f"{row.teacher_ci}:{row.designation_id}")
    return None


def calculate_override_total(rows: list[Any], overrides: dict[str, Decimal]) -> Decimal:
    validate_payment_override_targets(rows, overrides)
    grouped: dict[str, list[Any]] = {}
    for row in rows:
        grouped.setdefault(row.teacher_ci, []).append(row)
    allocations = {teacher: get_teacher_override_allocations(items, overrides) for teacher, items in grouped.items()}
    total = Decimal("0")
    for row in rows:
        value = resolve_row_override(
            row,
            grouped[row.teacher_ci],
            overrides,
            allocations=allocations[row.teacher_ci],
        )
        if value is None:
            value = Decimal(str(row.final_payment))
        total += value
    return total.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
