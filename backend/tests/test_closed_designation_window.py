from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.database import Base
from app.models.app_setting import AppSetting
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services.designation_window import overlaps_cutoff
from app.services.planilla_generator import PlanillaGenerator
from app.services.practice_planilla_generator import PracticePlanillaGenerator

CUT_START = date(2026, 5, 21)
CUT_END = date(2026, 6, 20)


# --- overlaps_cutoff -------------------------------------------------------


def test_contract_end_on_cut_start_overlaps() -> None:
    assert overlaps_cutoff(date(2026, 4, 1), CUT_START, CUT_START, CUT_END) is True


def test_contract_end_one_day_before_cut_start_does_not_overlap() -> None:
    assert overlaps_cutoff(date(2026, 4, 1), date(2026, 5, 20), CUT_START, CUT_END) is False


def test_contract_start_on_cut_end_overlaps() -> None:
    assert overlaps_cutoff(CUT_END, date(2026, 12, 1), CUT_START, CUT_END) is True


def test_contract_start_after_cut_end_does_not_overlap() -> None:
    assert overlaps_cutoff(date(2026, 6, 21), date(2026, 12, 1), CUT_START, CUT_END) is False


def test_null_contract_dates_are_open_ended() -> None:
    assert overlaps_cutoff(None, None, CUT_START, CUT_END) is True
    assert overlaps_cutoff(None, date(2026, 5, 20), CUT_START, CUT_END) is False
    assert overlaps_cutoff(None, date(2026, 5, 21), CUT_START, CUT_END) is True
    assert overlaps_cutoff(date(2026, 6, 21), None, CUT_START, CUT_END) is False
    assert overlaps_cutoff(date(2026, 6, 20), None, CUT_START, CUT_END) is True


# --- generator level -------------------------------------------------------


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            AppSetting(key="HOURLY_RATE", value="70", description="test"),
            AppSetting(key="PRACTICE_HOURLY_RATE", value="50", description="test"),
            AppSetting(key="ACTIVE_ACADEMIC_PERIOD", value="II/2026", description="test"),
        ]
    )
    session.flush()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _designation(
    db: Session,
    ci: str,
    group: str,
    *,
    practice: bool,
    contract_start: date | None,
    contract_end: date | None,
) -> Designation:
    if db.get(Teacher, ci) is None:
        db.add(Teacher(ci=ci, full_name=f"DOCENTE {ci}", invoice_retention=None))
    designation = Designation(
        teacher_ci=ci,
        academic_period="II/2026",
        subject="Materia",
        semester="3",
        group_code=group,
        designation_type="practice" if practice else "regular",
        schedule_json=[
            {"dia": "jueves", "hora_inicio": "17:30", "hora_fin": "19:45", "horas_academicas": 3}
        ],
        monthly_hours=12,
        weekly_hours=3,
        contract_start_date=contract_start,
        contract_end_date=contract_end,
    )
    db.add(designation)
    db.flush()
    return designation


def _build(db: Session, practice: bool, **kwargs):
    generator = PracticePlanillaGenerator() if practice else PlanillaGenerator()
    return generator._build_planilla_data(db, 6, 2026, discount_mode="full", **kwargs)[0]


@pytest.mark.parametrize("practice", [False, True])
def test_cutoff_generation_skips_designation_closed_before_the_cut(
    db: Session, practice: bool
) -> None:
    closed = _designation(
        db, "CI1", "N-3", practice=practice,
        contract_start=date(2026, 4, 1), contract_end=date(2026, 5, 20),
    )
    touching = _designation(
        db, "CI1", "TOUCH", practice=practice,
        contract_start=date(2026, 4, 1), contract_end=CUT_START,
    )
    open_ended = _designation(
        db, "CI1", "OPEN", practice=practice,
        contract_start=None, contract_end=None,
    )
    future = _designation(
        db, "CI1", "FUTURE", practice=practice,
        contract_start=date(2026, 6, 21), contract_end=None,
    )

    rows = _build(db, practice, start_date=CUT_START, end_date=CUT_END)
    by_id = {row.designation_id: row for row in rows}

    assert closed.id not in by_id
    assert future.id not in by_id
    assert set(by_id) == {touching.id, open_ended.id}
    # Open-ended: Thursdays 2026-05-21, 05-28, 06-04, 06-11, 06-18 -> 5 x 3 h.
    rate = 50 if practice else 70
    assert by_id[open_ended.id].payable_hours == 15
    assert by_id[open_ended.id].final_payment == 15 * rate
    # Touching: only Thursday 2026-05-21 falls inside its contract -> 3 h.
    assert by_id[touching.id].payable_hours == 3
    assert by_id[touching.id].final_payment == 3 * rate


@pytest.mark.parametrize("practice", [False, True])
def test_nominal_month_generation_keeps_historical_zero_row(
    db: Session, practice: bool
) -> None:
    closed = _designation(
        db, "CI2", "N-3", practice=practice,
        contract_start=date(2026, 4, 1), contract_end=date(2026, 5, 20),
    )
    rows = _build(db, practice)
    assert [row.designation_id for row in rows] == [closed.id]
    assert rows[0].payable_hours == 0
