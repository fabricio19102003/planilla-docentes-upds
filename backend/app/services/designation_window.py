"""Contract-window rule for payroll generation and its display note for published rows."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from sqlalchemy.orm import Session

from app.models.designation import Designation


def overlaps_cutoff(
    contract_start: date | None,
    contract_end: date | None,
    cut_start: date,
    cut_end: date,
) -> bool:
    """Whether a contract window intersects the cut-off window (inclusive).

    A ``None`` contract date means the contract is open-ended on that side.
    """
    if contract_end is not None and contract_end < cut_start:
        return False
    if contract_start is not None and contract_start > cut_end:
        return False
    return True


NO_CLASSES_NOTE = "Sin clases en este período"


def _as_date(value: date | str | None) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def is_zero_hours_row(base_hours: object, payable_hours: object) -> bool:
    """Snapshot rows with no assigned and no payable hours (absences keep base > 0)."""
    return base_hours is not None and payable_hours is not None and base_hours == 0 and payable_hours == 0


def contract_end_dates(db: Session, designation_ids: Iterable[int | None]) -> dict[int, date | None]:
    """Live ``contract_end_date`` per designation id (read-only display lookup)."""
    ids = {item for item in designation_ids if item is not None}
    if not ids:
        return {}
    rows = db.query(Designation.id, Designation.contract_end_date).filter(Designation.id.in_(ids)).all()
    return {row.id: row.contract_end_date for row in rows}


def period_note(
    base_hours: object,
    payable_hours: object,
    effective_from: date | str | None,
    contract_end: date | None,
) -> str | None:
    """Display note for an already-published row without hours; amounts are never altered."""
    if not is_zero_hours_row(base_hours, payable_hours):
        return None
    start = _as_date(effective_from)
    if contract_end is not None and start is not None and contract_end < start:
        return f"{NO_CLASSES_NOTE} (designación finalizada el {contract_end.strftime('%d/%m/%Y')})"
    return NO_CLASSES_NOTE
