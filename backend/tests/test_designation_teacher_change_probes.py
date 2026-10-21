from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.activity_log import ActivityLog
from app.models.attendance import AttendanceRecord
from app.models.academic_management import AcademicSchedulePublication, AcademicScheduleDraft
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.services import designation_change_service as svc
from app.services.planilla_generator import PlanillaGenerator
from tests.test_designation_teacher_change import URL, PERIOD, _designation, _body, _snapshot, seeded  # noqa: F401
from tests.test_publication_payroll_simulation import _rates, _simulate
from tests.test_academic_schedule_publication import _seed, _assign, _preview, _publish


def _impact(data):
    return [(t["teacher_ci"], t["activity"], t["hours_before"], t["hours_after"], t["amount_after"])
            for t in data["impact"]["teachers"]]


def test_preview_does_not_leak_into_reused_session(client, seeded):
    old = _designation(seeded)
    count = seeded.query(Designation).count()
    assert client.post(f"{URL}/preview", json=_body(old.id)).status_code == 200
    # no expire_all: identity map state after savepoint rollback
    assert old.contract_end_date is None
    assert seeded.query(Designation).count() == count
    seeded.flush()
    seeded.expire_all()
    assert seeded.get(Designation, old.id).contract_end_date is None
    assert seeded.query(Designation).count() == count
    # preview twice then apply in same session
    assert client.post(f"{URL}/preview", json=_body(old.id)).json()["can_apply"] is True
    assert client.post(f"{URL}/apply", json=_body(old.id)).status_code == 201


def test_apply_twice_is_blocked(client, seeded):
    old = _designation(seeded)
    assert client.post(f"{URL}/apply", json=_body(old.id)).status_code == 201
    second = client.post(f"{URL}/apply", json=_body(old.id))
    assert second.status_code == 409
    codes = {b["code"] for b in second.json()["detail"]["blockers"]}
    assert "incoming_has_designation" in codes
    snap = _snapshot(seeded)
    assert len(snap) == 2
    body = _body(scope="teacher", outgoing_teacher_ci="CHG-T1")
    again = client.post(f"{URL}/apply", json=body)
    assert again.status_code == 404


def test_change_on_first_of_month(client, seeded):
    old = _designation(seeded)
    data = client.post(f"{URL}/preview", json=_body(old.id, effective_from="2026-05-01")).json()
    assert data["can_apply"] is True
    assert _impact(data) == [("CHG-T1", "theory", 8, 0, 0.0), ("CHG-T2", "theory", 0, 8, 560.0)]
    assert client.post(f"{URL}/apply", json=_body(old.id, effective_from="2026-05-01")).status_code == 201
    april = PlanillaGenerator()._build_planilla_data(seeded, 4, 2026, discount_mode="full")[0]
    # The incoming designation appears with 0 h before it starts, as for any later-starting designation.
    assert sorted((r.teacher_ci, r.payable_hours) for r in april) == [("CHG-T1", 8), ("CHG-T2", 0)]
    may = PlanillaGenerator()._build_planilla_data(seeded, 5, 2026, discount_mode="full")[0]
    assert sorted((r.teacher_ci, r.payable_hours) for r in may) == [("CHG-T1", 0), ("CHG-T2", 8)]


def test_change_with_contract_dates_in_month(client, seeded):
    old = _designation(seeded, start=date(2026, 5, 4), end=date(2026, 5, 31))
    data = client.post(f"{URL}/preview", json=_body(old.id)).json()
    assert data["can_apply"] is True, data
    assert data["items"][0]["incoming_until"] == "2026-05-31"
    before = [t["hours_before"] for t in data["impact"]["teachers"]]
    assert _impact(data)[0][3] == 4 and _impact(data)[1][3] == 4, (before, _impact(data))
    assert client.post(f"{URL}/apply", json=_body(old.id)).status_code == 201
    rows = PlanillaGenerator()._build_planilla_data(seeded, 5, 2026, discount_mode="full")[0]
    assert sorted((r.teacher_ci, r.payable_hours) for r in rows) == [("CHG-T1", 4), ("CHG-T2", 4)]


def test_practice_split_uses_practice_rate(client, seeded):
    old = _designation(seeded, kind="practice")
    data = client.post(f"{URL}/preview", json=_body(old.id)).json()
    assert data["can_apply"] is True
    assert _impact(data) == [("CHG-T1", "practice", 8, 4, 200.0), ("CHG-T2", "practice", 0, 4, 200.0)]


def test_approved_payroll_later_month_blocks_open_ended_and_custom_window(client, seeded):
    old = _designation(seeded)
    seeded.add(PlanillaOutput(month=4, year=2026, file_path="a", total_teachers=1, total_hours=8,
                              total_payment=1, status="approved"))
    seeded.flush()
    assert client.post(f"{URL}/preview", json=_body(old.id)).json()["can_apply"] is True
    seeded.add(PlanillaOutput(month=6, year=2026, file_path="b", total_teachers=1, total_hours=8,
                              total_payment=1, status="approved"))
    seeded.flush()
    data = client.post(f"{URL}/preview", json=_body(old.id)).json()
    assert [b["code"] for b in data["blockers"]] == ["payroll_approved"]


def test_custom_window_payroll_overlap(client, seeded):
    old = _designation(seeded)
    seeded.add(PlanillaOutput(month=4, year=2026, file_path="a", total_teachers=1, total_hours=8,
                              total_payment=1, status="approved",
                              start_date=date(2026, 4, 21), end_date=date(2026, 5, 20)))
    seeded.flush()
    data = client.post(f"{URL}/preview", json=_body(old.id)).json()
    assert [b["code"] for b in data["blockers"]] == ["payroll_approved"]


def test_no_exit_on_change_day_blocks_teacher_scope(client, seeded):
    old = _designation(seeded)
    seeded.add(AttendanceRecord(
        teacher_ci="CHG-T1", designation_id=old.id, date=date(2026, 5, 18),
        scheduled_start=time(8, 0), scheduled_end=time(9, 30), actual_entry=time(8, 0), actual_exit=None,
        status="NO_EXIT", academic_hours=2, month=5, year=2026,
    ))
    seeded.flush()
    att_before = seeded.query(AttendanceRecord).count()
    body = _body(scope="teacher", outgoing_teacher_ci="CHG-T1")
    r = client.post(f"{URL}/apply", json=body)
    assert r.status_code == 409
    b = [x for x in r.json()["detail"]["blockers"] if x["code"] == "outgoing_attendance_after_change"]
    assert b[0]["dates"] == ["2026-05-18"]
    assert seeded.query(AttendanceRecord).count() == att_before
    assert _snapshot(seeded) == [("CHG-T1", "Anatomia", None, None)]


def test_concurrent_double_create_hits_unique_constraint(client, seeded, monkeypatch):
    old = _designation(seeded)
    plan = svc._resolve(seeded, svc.DesignationChangeRequest(**_body(old.id)))
    svc._mutate(seeded, plan)
    plan.designations[0].contract_end_date = None
    with pytest.raises(IntegrityError):
        svc._mutate(seeded, plan)


def test_simulation_then_publish_in_same_session(client, db_session):
    _rates(db_session)
    *_, draft, block, _t = _seed(client, db_session)
    _assign(client, draft["id"], block["id"])
    assert _simulate(client, draft["id"]).status_code == 200
    preview = _preview(client, draft["id"])
    published = _publish(client, draft["id"], preview)
    assert published.status_code in (200, 201), published.text
    db_session.expire_all()
    assert db_session.query(AcademicSchedulePublication).count() == 1


def test_apply_race_on_unique_key_returns_409(client, seeded, monkeypatch):
    old = _designation(seeded)

    def lost_race(_db, _plan):
        raise IntegrityError("INSERT", {}, Exception("uq_designation_teacher_subject_semester_group_period"))

    monkeypatch.setattr(svc, "_mutate", lost_race)
    response = client.post(f"{URL}/apply", json=_body(old.id))
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["blockers"] == [{
        "code": "concurrent_change", "designation_id": None, "dates": [],
        "message": "Otro cambio modificó estas designaciones al mismo tiempo. Generá una nueva vista previa.",
    }]
    # The route rolls the transaction back; in this harness that also discards the fixture rows,
    # so persistence is not asserted here (the refused-apply tests cover "nothing is written").
