"""Group opening suggestions: how many groups to open per semester and shift (academic phase 3, S4)."""
from __future__ import annotations

import itertools
from datetime import datetime

import pytest

from app.models.academic_records import Student
from app.models.activity_log import ActivityLog
from app.models.student_portal import ReenrollmentRequest, ReenrollmentRequestItem
from app.services import app_settings_service, reenrollment
from tests.test_reenrollment_api import TODAY, _group, _student_token, _window
from tests.test_reenrollment_eligibility import I_2026, _load
from tests.test_student_accounts import _as

ADMIN = "/api/admin/group-opening"
_DOCUMENTS = itertools.count(900_000)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(reenrollment, "bolivia_today", lambda: TODAY)


@pytest.fixture(autouse=True)
def curriculum(db_session):
    # Importing one history creates the curriculum plan the groups hang from.
    _load(db_session, "PLAN-SEED", [("Anatomía Humana II MRF-0200", "Aprobado", 75, I_2026)])


def _student(db_session):
    number = str(next(_DOCUMENTS))
    student = Student(document_number=number, document_type="CI", first_names="Est", last_names=number,
                      is_foreign=False)
    db_session.add(student)
    db_session.flush()
    return student


def _request(db_session, window_id, main_group, status="pendiente", items=()):
    request = ReenrollmentRequest(
        student_id=_student(db_session).id, window_id=window_id, target_semester=main_group.semester,
        main_group_id=main_group.id, status=status, snapshot={}, submitted_at=datetime(2026, 12, 10, 9, 0),
    )
    db_session.add(request)
    db_session.flush()
    for number, (kind, group) in enumerate(items):
        db_session.add(ReenrollmentRequestItem(
            request_id=request.id, kind=kind, subject_code=f"SUB {number:04d}", subject_name=f"Materia {number}",
            semester=group.semester, group_id=group.id,
        ))
    db_session.flush()
    return request


def _requests(db_session, window_id, group, count, **kwargs):
    return [_request(db_session, window_id, group, **kwargs) for _ in range(count)]


def _set_size(client, size):
    response = client.put(f"{ADMIN}/settings", json={"group_size": size})
    assert response.status_code == 200, response.text


def _rows(client, **params):
    response = client.get(ADMIN, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _by_key(body):
    return {(row["semester"], row["shift"]): row for row in body["rows"]}


# ── Suggestions ──────────────────────────────────────────────────────────────

def test_the_default_size_is_forty_and_with_no_window_there_is_nothing_to_show(client):
    body = _rows(client)
    assert (body["window"], body["group_size"], body["rows"]) == (None, 40, [])
    assert body["totals"]["suggested_groups"] == 0


def test_the_suggestion_is_the_ceiling_of_requests_over_the_size(client, db_session):
    window = _window(client)
    _set_size(client, 10)
    one = _group(db_session, 1, "M-01")
    two = _group(db_session, 2, "M-01")
    three = _group(db_session, 3, "M-01")
    _group(db_session, 4, "M-01")
    _requests(db_session, window["id"], two, 10)
    _requests(db_session, window["id"], three, 11)

    body = _rows(client)
    rows = _by_key(body)

    assert [(r["requests"], r["suggested_groups"]) for r in (rows[(1, "M")], rows[(2, "M")], rows[(3, "M")])] == [
        (0, 0), (10, 1), (11, 2),
    ]
    assert (rows[(4, "M")]["requests"], rows[(4, "M")]["suggested_groups"]) == (0, 0)
    assert (body["window"]["term_code"], body["group_size"]) == ("I/2027", 10)
    assert one.semester == 1


def test_missing_leftover_and_correct_groups_are_labelled(client, db_session):
    window = _window(client)
    _set_size(client, 10)
    _group(db_session, 1, "M-01")                      # 0 requests, 1 group -> leftover
    correct = _group(db_session, 2, "M-01")            # 10 requests, 1 group -> correct
    two_missing = _group(db_session, 3, "M-01")        # 25 requests, 1 group -> 2 missing
    one_missing = _group(db_session, 4, "M-01")        # 11 requests, 1 group -> 1 missing
    three = _group(db_session, 5, "M-01")              # 10 requests, 3 groups -> 2 leftover
    _group(db_session, 5, "M-02")
    _group(db_session, 5, "M-03")
    _requests(db_session, window["id"], correct, 10)
    _requests(db_session, window["id"], two_missing, 25)
    _requests(db_session, window["id"], one_missing, 11)
    _requests(db_session, window["id"], three, 10)

    body = _rows(client)

    assert {key: (r["difference"], r["status"], r["label"]) for key, r in _by_key(body).items()} == {
        (1, "M"): (-1, "sobran", "Sobra 1 grupo"),
        (2, "M"): (0, "correcto", "Correcto"),
        (3, "M"): (2, "faltan", "Faltan 2 grupos"),
        (4, "M"): (1, "faltan", "Falta 1 grupo"),
        (5, "M"): (-2, "sobran", "Sobran 2 grupos"),
    }
    assert (body["totals"]["missing_groups"], body["totals"]["leftover_groups"]) == (3, 3)


def test_requests_for_a_deactivated_main_group_show_every_group_missing(client, db_session):
    window = _window(client)
    _set_size(client, 10)
    main = _group(db_session, 3, "T-01", shift="T")
    _requests(db_session, window["id"], main, 3)
    main.active = False
    db_session.flush()

    row = _by_key(_rows(client))[(3, "T")]

    assert (row["requests"], row["existing_groups"], row["difference"], row["label"]) == (3, 0, 1, "Falta 1 grupo")


def test_groups_without_requests_still_get_a_row_and_inactive_groups_do_not(client, db_session):
    _window(client)
    _group(db_session, 7, "N-01", shift="N", capacity=30)
    inactive = _group(db_session, 8, "N-01", shift="N", capacity=30)
    inactive.active = False
    _group(db_session, 9, "M-01", period="II/2026")
    db_session.flush()

    rows = _by_key(_rows(client))

    assert list(rows) == [(7, "N")]
    assert (rows[(7, "N")]["requests"], rows[(7, "N")]["suggested_groups"], rows[(7, "N")]["existing_groups"]) == (0, 0, 1)


def test_capacity_adds_up_known_sizes_and_counts_the_groups_without_one(client, db_session):
    _window(client)
    _group(db_session, 3, "M-01", capacity=35)
    _group(db_session, 3, "M-02", capacity=25)
    _group(db_session, 3, "M-03")
    _group(db_session, 3, "M-04")

    body = _rows(client)
    row = _by_key(body)[(3, "M")]

    assert (row["existing_groups"], row["existing_capacity"], row["groups_without_capacity"]) == (4, 60, 2)
    assert (body["totals"]["existing_groups"], body["totals"]["existing_capacity"],
            body["totals"]["groups_without_capacity"]) == (4, 60, 2)


def test_retakers_are_counted_apart_and_never_open_groups(client, db_session):
    window = _window(client)
    _set_size(client, 10)
    main = _group(db_session, 3, "M-01")
    same_shift = _group(db_session, 3, "M-02")
    first_t = _group(db_session, 1, "T-01", shift="T")
    second_t = _group(db_session, 1, "T-02", shift="T")
    night = _group(db_session, 2, "N-01", shift="N")
    # Two subjects in the same (semester, shift) count the student once; a subject in the student's own
    # main (semester, shift) is not a retaker there.
    _request(db_session, window["id"], main, items=[("recursado", first_t), ("pendiente", second_t),
                                                    ("recursado", same_shift)])
    _request(db_session, window["id"], main, items=[("pendiente", first_t), ("recursado", night)])

    body = _rows(client)
    rows = _by_key(body)

    assert (rows[(1, "T")]["retakers"], rows[(1, "T")]["requests"], rows[(1, "T")]["suggested_groups"]) == (2, 0, 0)
    assert (rows[(2, "N")]["retakers"], rows[(2, "N")]["requests"], rows[(2, "N")]["suggested_groups"]) == (1, 0, 0)
    assert (rows[(3, "M")]["retakers"], rows[(3, "M")]["requests"], rows[(3, "M")]["suggested_groups"]) == (0, 2, 1)
    assert (body["totals"]["requests"], body["totals"]["retakers"], body["totals"]["suggested_groups"]) == (2, 3, 1)


def test_a_retaker_row_without_groups_is_listed_too(client, db_session):
    window = _window(client)
    main = _group(db_session, 3, "M-01")
    old = _group(db_session, 1, "T-01", shift="T")
    _request(db_session, window["id"], main, items=[("recursado", old)])
    old.active = False
    db_session.flush()

    rows = _by_key(_rows(client))

    assert (rows[(1, "T")]["retakers"], rows[(1, "T")]["existing_groups"], rows[(1, "T")]["label"]) == (1, 0, "Correcto")


def test_only_pending_and_done_requests_count(client, db_session):
    window = _window(client)
    _set_size(client, 1)
    main = _group(db_session, 3, "M-01")
    other = _group(db_session, 1, "T-01", shift="T")
    _request(db_session, window["id"], main, status="pendiente", items=[("recursado", other)])
    _request(db_session, window["id"], main, status="realizada")
    _request(db_session, window["id"], main, status="observada", items=[("recursado", other)])

    rows = _by_key(_rows(client))

    assert (rows[(3, "M")]["requests"], rows[(3, "M")]["suggested_groups"]) == (2, 2)
    assert rows[(1, "T")]["retakers"] == 1


def test_requests_of_other_windows_do_not_count(client, db_session):
    first = _window(client)
    second = _window(client, term="II/2027", starts="2027-06-01", ends="2027-06-20")
    _set_size(client, 10)
    this_term = _group(db_session, 3, "M-01")
    next_term = _group(db_session, 3, "M-01", period="II/2027", capacity=40)
    _requests(db_session, first["id"], this_term, 4)
    _requests(db_session, second["id"], next_term, 15)

    current = _rows(client)
    chosen = _rows(client, window_id=second["id"])

    assert (current["window"]["id"], _by_key(current)[(3, "M")]["requests"]) == (first["id"], 4)
    assert (chosen["window"]["id"], _by_key(chosen)[(3, "M")]["requests"]) == (second["id"], 15)
    assert (_by_key(chosen)[(3, "M")]["existing_groups"], _by_key(chosen)[(3, "M")]["suggested_groups"]) == (1, 2)
    assert client.get(ADMIN, params={"window_id": 9999}).status_code == 404


def test_rows_are_sorted_by_semester_then_morning_afternoon_night_and_others(client, db_session):
    _window(client)
    for semester, code, shift in [(2, "X-01", "X"), (2, "N-01", "N"), (1, "T-01", "T"), (2, "T-01", "T"),
                                  (2, "M-01", "M"), (1, "A-01", "A"), (1, "M-01", "M")]:
        _group(db_session, semester, code, shift=shift)

    keys = [(row["semester"], row["shift"]) for row in _rows(client)["rows"]]

    assert keys == [(1, "M"), (1, "T"), (1, "A"), (2, "M"), (2, "T"), (2, "N"), (2, "X")]


# ── Default size setting ─────────────────────────────────────────────────────

def test_the_group_size_is_validated_saved_and_logged_with_before_and_after(client, db_session):
    _window(client)

    for bad in (0, -5, 201, "muchos", 40.5, None):
        rejected = client.put(f"{ADMIN}/settings", json={"group_size": bad})
        assert rejected.status_code == 422, bad
    assert client.put(f"{ADMIN}/settings", json={}).status_code == 422
    assert app_settings_service.get_default_group_size(db_session) == 40
    assert db_session.query(ActivityLog).filter(ActivityLog.category == "group_opening").count() == 0

    for edge in (1, 200):
        assert client.put(f"{ADMIN}/settings", json={"group_size": edge}).json() == {"group_size": edge}
    saved = client.put(f"{ADMIN}/settings", json={"group_size": 35})
    assert (saved.status_code, saved.json()) == (200, {"group_size": 35})
    assert _rows(client)["group_size"] == 35
    assert app_settings_service.get_default_group_size(db_session) == 35

    entries = db_session.query(ActivityLog).filter(ActivityLog.category == "group_opening").order_by(ActivityLog.id).all()
    assert [(e.action, e.details) for e in entries] == [
        ("update_group_opening_size", {"before": 40, "after": 1}),
        ("update_group_opening_size", {"before": 1, "after": 200}),
        ("update_group_opening_size", {"before": 200, "after": 35}),
    ]
    assert entries[-1].user_ci is not None


def test_an_invalid_stored_size_falls_back_to_the_default(db_session):
    app_settings_service.update_setting(db_session, app_settings_service.KEY_DEFAULT_GROUP_SIZE, "no")
    assert app_settings_service.get_default_group_size(db_session) == 40
    app_settings_service.update_setting(db_session, app_settings_service.KEY_DEFAULT_GROUP_SIZE, "500")
    assert app_settings_service.get_default_group_size(db_session) == 40


# ── Access ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("method,path", [("get", ""), ("put", "/settings")])
def test_group_opening_is_admin_only(client, db_session, method, path):
    from app.models.user import User
    from app.services.auth_service import auth_service

    authorization = client.headers.pop("Authorization")
    try:
        assert getattr(client, method)(f"{ADMIN}{path}").status_code == 401
        docente = User(ci="OPENING-DOCENTE", full_name="Docente", role="docente", is_active=True,
                       password_hash=auth_service.hash_password("testpass123"))
        db_session.add(docente)
        db_session.flush()
        client.headers["Authorization"] = "Bearer " + auth_service.create_access_token(
            {"sub": str(docente.id), "role": "docente"})
        assert getattr(client, method)(f"{ADMIN}{path}").status_code == 403
    finally:
        client.headers["Authorization"] = authorization
    assert app_settings_service.get_default_group_size(db_session) == 40


def test_a_student_token_never_opens_group_opening(client, db_session):
    _window(client)
    token = _student_token(client, _student(db_session))
    assert client.get(ADMIN, headers=_as(token)).status_code == 401
    assert client.put(f"{ADMIN}/settings", headers=_as(token), json={"group_size": 10}).status_code == 401
    assert app_settings_service.get_default_group_size(db_session) == 40
