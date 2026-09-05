from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.schemas.planilla import PlanillaGenerateRequest
from app.schemas.practice_planilla import PracticePlanillaGenerateRequest
from app.services.payment_overrides import (
    PaymentOverrideError,
    calculate_override_total,
    get_teacher_override_allocations,
    normalize_payment_overrides,
    validate_payment_override_targets,
)
from app.services.planilla_generator import PlanillaGenerator
from app.services.practice_planilla_generator import PracticePlanillaGenerator


def _rows():
    return [
        SimpleNamespace(teacher_ci="teacher-a", designation_id=1, total_hours=1, final_payment=Decimal("100.00")),
        SimpleNamespace(teacher_ci="teacher-a", designation_id=2, total_hours=3, final_payment=Decimal("200.00")),
        SimpleNamespace(teacher_ci="teacher-b", designation_id=3, total_hours=2, final_payment=Decimal("300.00")),
    ]


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("-0.01", "payment_override_out_of_range"),
        ("NaN", "payment_override_not_finite"),
        ("Infinity", "payment_override_not_finite"),
        ("-Infinity", "payment_override_not_finite"),
        ("1e100", "payment_override_out_of_range"),
        ("100.005", "payment_override_precision"),
    ],
)
def test_normalization_rejects_audited_invalid_amounts(value, code):
    with pytest.raises(PaymentOverrideError) as exc_info:
        normalize_payment_overrides({"teacher-a": value})

    assert exc_info.value.code == code
    assert exc_info.value.sample
    assert "teacher-a" not in str(exc_info.value.as_detail())


@pytest.mark.parametrize("key", ["", " ", ":1", "teacher-a:", "teacher-a:not-an-id", "teacher-a:0"])
def test_normalization_rejects_malformed_keys(key):
    with pytest.raises(PaymentOverrideError) as exc_info:
        normalize_payment_overrides({key: "10.00"})

    assert exc_info.value.code == "payment_override_key_invalid"


@pytest.mark.parametrize("schema", [PlanillaGenerateRequest, PracticePlanillaGenerateRequest])
def test_api_schemas_preserve_override_money_as_decimal(schema):
    payload = schema(month=8, year=2026, payment_overrides={"teacher-a": "100.50"})

    assert payload.payment_overrides == {"teacher-a": Decimal("100.50")}
    non_finite = schema(month=8, year=2026, payment_overrides={"teacher-a": float("nan")})
    with pytest.raises(PaymentOverrideError) as exc_info:
        normalize_payment_overrides(non_finite.payment_overrides)
    assert exc_info.value.code == "payment_override_not_finite"


def test_normalization_is_deterministic_and_accepts_current_key_forms():
    normalized = normalize_payment_overrides({"teacher-b:3": "5", "teacher-a": 100})

    assert list(normalized) == ["teacher-a", "teacher-b:3"]
    assert normalized == {"teacher-a": Decimal("100.00"), "teacher-b:3": Decimal("5.00")}


def test_semantic_validation_rejects_unknown_teacher_or_designation_key():
    for key in ("unknown-teacher", "teacher-a:999", "teacher-b:1"):
        with pytest.raises(PaymentOverrideError) as exc_info:
            validate_payment_override_targets(_rows(), normalize_payment_overrides({key: "10"}))
        assert exc_info.value.code == "payment_override_unknown_key"
        assert key not in str(exc_info.value.as_detail())


def test_row_overrides_cannot_exceed_teacher_override():
    overrides = normalize_payment_overrides({"teacher-a": "100", "teacher-a:1": "60", "teacher-a:2": "50"})

    with pytest.raises(PaymentOverrideError) as exc_info:
        validate_payment_override_targets(_rows(), overrides)

    assert exc_info.value.code == "payment_override_rows_exceed_teacher"


def test_valid_teacher_and_row_overrides_have_predictable_precedence():
    rows = _rows()
    overrides = normalize_payment_overrides({"teacher-a": "1000", "teacher-a:1": "400", "teacher-b:3": "50"})
    validate_payment_override_targets(rows, overrides)

    allocations = get_teacher_override_allocations(rows[:2], overrides)

    assert allocations == {1: Decimal("400.00"), 2: Decimal("600.00")}
    assert calculate_override_total(rows, overrides) == Decimal("1050.00")


def test_all_explicit_rows_must_allocate_exact_teacher_override():
    rows = _rows()[:2]
    overrides = normalize_payment_overrides({"teacher-a": "100", "teacher-a:1": "30", "teacher-a:2": "40"})

    with pytest.raises(PaymentOverrideError) as exc_info:
        get_teacher_override_allocations(rows, overrides)

    assert exc_info.value.code == "override_unallocated_amount"


def test_all_explicit_rows_accept_exact_teacher_override():
    rows = _rows()[:2]
    overrides = normalize_payment_overrides({"teacher-a": "100", "teacher-a:1": "30", "teacher-a:2": "70"})
    assert get_teacher_override_allocations(rows, overrides) == {
        1: Decimal("30.00"), 2: Decimal("70.00"),
    }


def test_subset_override_distributes_remaining_amount():
    rows = _rows()[:2]
    overrides = normalize_payment_overrides({"teacher-a": "100", "teacher-a:1": "30"})
    assert get_teacher_override_allocations(rows, overrides) == {
        1: Decimal("30.00"), 2: Decimal("70.00"),
    }


def test_teacher_override_assigns_cent_residue_deterministically():
    rows = [
        SimpleNamespace(teacher_ci="teacher-a", designation_id=index, total_hours=1, final_payment=0)
        for index in (1, 2, 3)
    ]
    allocations = get_teacher_override_allocations(
        rows, normalize_payment_overrides({"teacher-a": "100"}),
    )
    assert allocations == {
        1: Decimal("33.33"), 2: Decimal("33.33"), 3: Decimal("33.34"),
    }


def test_override_allocation_error_maps_to_stable_422(client, monkeypatch):
    def fail(*args, **kwargs):
        raise PaymentOverrideError("override_unallocated_amount", "Teacher override is not fully allocated")

    monkeypatch.setattr(PlanillaGenerator, "generate", fail)
    response = client.post("/api/planilla/generate", json={"month": 5, "year": 2026})
    assert (response.status_code, response.json()["detail"]["code"]) == (422, "override_unallocated_amount")


@pytest.mark.parametrize("generator_class", [PlanillaGenerator, PracticePlanillaGenerator])
def test_generators_reject_invalid_money_before_building_rows(tmp_path, generator_class):
    generator = generator_class(output_dir=str(tmp_path))
    generator._build_planilla_data = lambda *args, **kwargs: pytest.fail("rows must not be built")

    with pytest.raises(PaymentOverrideError) as exc_info:
        generator.generate(None, month=8, year=2026, payment_overrides={"teacher-a": float("nan")})

    assert exc_info.value.code == "payment_override_not_finite"
