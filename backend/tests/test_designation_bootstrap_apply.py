from __future__ import annotations

import json
from datetime import date, time

import pytest
from sqlalchemy import event, text, update, delete

from app.models.academic_management import (
    AcademicProgram,
    AcademicScheduleAssignment,
    AcademicScheduleBlock,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
)
from app.models.activity_log import ActivityLog
from app.models.designation_bootstrap import DesignationBootstrapReceipt
from app.models.user import User
from app.services import designation_bootstrap_apply as apply_service
from app.services.designation_bootstrap_apply import (
    DesignationBootstrapApplyError,
    _operation_key,
    _scope_lock_key,
    apply_designation_bootstrap,
)
from app.services.designation_bootstrap_preview import build_designation_bootstrap_preview
from tests.test_designation_bootstrap_preview import _alias, _official, _salary, _seed


EFFECTIVE_DATE = date(2026, 8, 21)
FORBIDDEN_TABLES = (
    "teachers",
    "users",
    "academic_programs",
    "academic_subjects",
    "subject_offerings",
    "academic_groups",
    "classrooms",
    "teacher_availability",
    "designations",
    "attendance_records",
    "planilla_outputs",
    "contract_documents",
    "billing_publications",
    "academic_schedule_publications",
    "app_settings",
)


def _admin(db_session) -> User:
    actor = User(
        ci="ADMIN-BOOTSTRAP-1",
        full_name="Bootstrap Admin",
        password_hash="not-used",
        role="admin",
        is_active=True,
    )
    db_session.add(actor)
    db_session.flush()
    return actor


def _valid_inputs(db_session):
    _seed(db_session)
    actor = _admin(db_session)
    official = _official(include_practice=False)
    salary = _salary(hours=())
    preview = build_designation_bootstrap_preview(
        db_session,
        official_content=official,
        salary_content=salary,
        academic_period="II/2026",
        effective_date=EFFECTIVE_DATE,
        program_identity="MED",
    )
    assert preview["can_apply"] is True
    return actor, official, salary, preview


def _apply(db_session, actor, official, salary, digest, alias=None, program_identity="MED"):
    return apply_designation_bootstrap(
        db_session,
        official_content=official,
        salary_content=salary,
        alias_content=alias,
        academic_period="II/2026",
        effective_date=EFFECTIVE_DATE,
        program_identity=program_identity,
        confirmation_digest=digest,
        actor=actor,
    )


def _counts(db_session) -> dict[str, int]:
    return {
        table: db_session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        for table in FORBIDDEN_TABLES
    }


def test_apply_creates_only_new_draft_graph_receipt_and_aggregate_log(db_session):
    actor, official, salary, preview = _valid_inputs(db_session)
    forbidden_before = _counts(db_session)

    result = _apply(db_session, actor, official, salary, preview["preview_digest"])

    assert result == {
        "status": "applied",
        "replayed": False,
        "draft_id": result["draft_id"],
        "theory_block_count": 1,
        "practice_block_count": 0,
        "theory_assignment_count": 1,
        "practice_assignment_count": 0,
        "preview_digest": preview["preview_digest"],
    }
    draft = db_session.get(AcademicScheduleDraft, result["draft_id"])
    assert draft.status == "draft"
    assert draft.academic_period == "II/2026"
    block = db_session.query(AcademicScheduleBlock).filter_by(draft_id=draft.id).one()
    assignment = db_session.query(AcademicScheduleAssignment).filter_by(block_id=block.id).one()
    assert block.activity_type == "theory"
    assert block.offering_id and block.group_id and block.classroom_id
    assert block.weekday == "monday"
    assert (block.start_time, block.end_time) == (time(8), time(9, 30))
    assert assignment.teacher_ci == "880001"
    assert assignment.effective_from == EFFECTIVE_DATE
    assert assignment.effective_to is None
    assert db_session.query(AcademicSchedulePublication).count() == 0
    assert _counts(db_session) == forbidden_before

    receipt = db_session.query(DesignationBootstrapReceipt).one()
    assert receipt.draft_id == draft.id
    assert receipt.plan_snapshot["source_plan"][0]["teacher_ci"] == "880001"
    assert receipt.plan_snapshot["source_plan"][0]["source"]["sheet"] == "DOCENTES TEORICOS"
    activity = db_session.query(ActivityLog).filter_by(action="apply_designation_bootstrap").one()
    assert activity.user_ci is None and activity.user_name is None
    public_text = json.dumps({"response": result, "activity": activity.details})
    assert "880001" not in public_text
    assert "Private Theory Name" not in public_text


def test_concurrent_candidates_share_target_scope_lock_but_keep_unique_operations(
    db_session, monkeypatch,
):
    actor, first_official, salary, _preview = _valid_inputs(db_session)
    first_official = _official(include_practice=False)
    second_official = _official(
        theory_schedule="LUNES: 08:00 AM-10:00 AM", include_practice=False,
    )
    salary = _salary(hours=())
    program_id = db_session.query(AcademicProgram).filter_by(code="MED").one().id
    first_operation = _operation_key(
        first_official, salary, None, "II/2026", EFFECTIVE_DATE, program_id,
    )
    second_operation = _operation_key(
        second_official, salary, None, "II/2026", EFFECTIVE_DATE, program_id,
    )

    assert first_operation != second_operation
    lock_keys = []
    monkeypatch.setattr(apply_service, "_advisory_lock", lambda _db, key: lock_keys.append(key))
    for official in (first_official, second_official):
        with pytest.raises(DesignationBootstrapApplyError, match="preview_digest_drift"):
            _apply(db_session, actor, official, salary, "0" * 64)
    assert lock_keys == [
        _scope_lock_key("II/2026", EFFECTIVE_DATE, program_id),
        _scope_lock_key("II/2026", EFFECTIVE_DATE, program_id),
    ]


@pytest.mark.parametrize("drift", ["digest", "source", "alias", "state"])
def test_apply_rejects_digest_source_alias_and_database_drift_without_writes(db_session, drift):
    actor, official, salary, preview = _valid_inputs(db_session)
    alias = None
    digest = preview["preview_digest"]
    if drift == "digest":
        digest = "0" * 64
    elif drift == "source":
        official = _official(theory_schedule="LUNES: 08:00 AM-10:00 AM", include_practice=False)
    elif drift == "alias":
        first_alias = _alias(official, salary)
        preview = build_designation_bootstrap_preview(
            db_session,
            official_content=official,
            salary_content=salary,
            alias_content=first_alias,
            academic_period="II/2026",
            effective_date=EFFECTIVE_DATE,
            program_identity="MED",
        )
        digest = preview["preview_digest"]
        alias = json.dumps(json.loads(first_alias), separators=(",", ":")).encode()
    else:
        teacher = db_session.get(__import__("app.models.teacher", fromlist=["Teacher"]).Teacher, "880001")
        teacher.full_name = "Changed Name"
        db_session.flush()

    with pytest.raises(DesignationBootstrapApplyError, match="preview_digest_drift"):
        _apply(db_session, actor, official, salary, digest, alias)
    assert db_session.query(AcademicScheduleDraft).count() == 0
    assert db_session.query(DesignationBootstrapReceipt).count() == 0
    assert db_session.query(ActivityLog).filter_by(action="apply_designation_bootstrap").count() == 0


def test_blocked_preview_and_wrong_effective_date_write_nothing(db_session):
    _seed(db_session)
    actor = _admin(db_session)
    official = _official()
    salary = _salary()
    preview = build_designation_bootstrap_preview(
        db_session,
        official_content=official,
        salary_content=salary,
        academic_period="II/2026",
        effective_date=EFFECTIVE_DATE,
        program_identity="MED",
    )
    assert preview["can_apply"] is False
    with pytest.raises(DesignationBootstrapApplyError, match="preview_blocked"):
        _apply(db_session, actor, official, salary, preview["preview_digest"])
    with pytest.raises(DesignationBootstrapApplyError, match="invalid_effective_date"):
        apply_designation_bootstrap(
            db_session,
            official_content=official,
            salary_content=salary,
            academic_period="II/2026",
            effective_date=date(2026, 8, 20),
            program_identity="MED",
            confirmation_digest=preview["preview_digest"],
            actor=actor,
        )
    assert db_session.query(AcademicScheduleDraft).count() == 0


def test_empty_import_is_refused_before_draft_creation(db_session):
    _seed(db_session)
    actor = _admin(db_session)
    official = _official(include_theory=False, include_practice=False)
    salary = _salary(hours=())
    preview = build_designation_bootstrap_preview(
        db_session,
        official_content=official,
        salary_content=salary,
        academic_period="II/2026",
        effective_date=EFFECTIVE_DATE,
        program_identity="MED",
    )

    with pytest.raises(DesignationBootstrapApplyError, match="preview_blocked"):
        _apply(db_session, actor, official, salary, preview["preview_digest"])

    assert db_session.query(AcademicScheduleDraft).count() == 0
    assert db_session.query(DesignationBootstrapReceipt).count() == 0


def test_apply_revalidates_actor_after_locks(db_session, monkeypatch):
    actor, official, salary, preview = _valid_inputs(db_session)

    def revoke_actor_after_locks(db):
        db.execute(update(User).where(User.id == actor.id).values(is_active=False))

    monkeypatch.setattr(apply_service, "_lock_postgresql_tables", revoke_actor_after_locks)

    with pytest.raises(DesignationBootstrapApplyError, match="invalid_actor"):
        _apply(db_session, actor, official, salary, preview["preview_digest"])

    assert db_session.query(AcademicScheduleDraft).count() == 0
    assert db_session.query(DesignationBootstrapReceipt).count() == 0


def test_exact_replay_returns_same_verified_draft_without_duplicate_log(db_session):
    actor, official, salary, preview = _valid_inputs(db_session)
    first = _apply(db_session, actor, official, salary, preview["preview_digest"])
    repeated_preview = build_designation_bootstrap_preview(
        db_session,
        official_content=official,
        salary_content=salary,
        academic_period="II/2026",
        effective_date=EFFECTIVE_DATE,
        program_identity="MED",
    )
    replay = _apply(db_session, actor, official, salary, preview["preview_digest"])

    assert repeated_preview["preview_digest"] == preview["preview_digest"]
    assert replay == {**first, "status": "replayed", "replayed": True}
    assert db_session.query(AcademicScheduleDraft).count() == 1
    assert db_session.query(DesignationBootstrapReceipt).count() == 1
    assert db_session.query(ActivityLog).filter_by(action="apply_designation_bootstrap").count() == 1


def test_program_code_and_name_share_preview_and_replay_identity(db_session):
    actor, official, salary, code_preview = _valid_inputs(db_session)
    name_preview = build_designation_bootstrap_preview(
        db_session,
        official_content=official,
        salary_content=salary,
        academic_period="II/2026",
        effective_date=EFFECTIVE_DATE,
        program_identity="Medicine",
    )

    first = _apply(db_session, actor, official, salary, code_preview["preview_digest"])
    replay = _apply(
        db_session,
        actor,
        official,
        salary,
        name_preview["preview_digest"],
        program_identity="Medicine",
    )

    assert name_preview["preview_digest"] == code_preview["preview_digest"]
    assert replay == {**first, "status": "replayed", "replayed": True}
    assert db_session.query(AcademicScheduleDraft).count() == 1
    assert db_session.query(DesignationBootstrapReceipt).count() == 1


def test_replay_fails_closed_when_persisted_graph_drifts(db_session):
    actor, official, salary, preview = _valid_inputs(db_session)
    result = _apply(db_session, actor, official, salary, preview["preview_digest"])
    block = db_session.query(AcademicScheduleBlock).filter_by(draft_id=result["draft_id"]).one()
    block.end_time = time(9, 45)
    db_session.flush()

    with pytest.raises(DesignationBootstrapApplyError, match="replay_graph_drift"):
        _apply(db_session, actor, official, salary, preview["preview_digest"])


def test_mid_graph_failure_rolls_back_every_apply_write(db_session):
    actor, official, salary, preview = _valid_inputs(db_session)
    db_session.commit()

    def fail_assignment(*_args):
        raise RuntimeError("synthetic mid-graph failure")

    event.listen(AcademicScheduleAssignment, "before_insert", fail_assignment)
    try:
        with pytest.raises(RuntimeError, match="synthetic mid-graph failure"):
            _apply(db_session, actor, official, salary, preview["preview_digest"])
        db_session.rollback()
    finally:
        event.remove(AcademicScheduleAssignment, "before_insert", fail_assignment)

    assert db_session.query(AcademicScheduleDraft).count() == 0
    assert db_session.query(AcademicScheduleBlock).count() == 0
    assert db_session.query(AcademicScheduleAssignment).count() == 0
    assert db_session.query(DesignationBootstrapReceipt).count() == 0
    assert db_session.query(ActivityLog).filter_by(action="apply_designation_bootstrap").count() == 0


def test_receipt_is_append_only_for_orm_and_bulk_mutations(db_session):
    actor, official, salary, preview = _valid_inputs(db_session)
    _apply(db_session, actor, official, salary, preview["preview_digest"])
    db_session.commit()
    receipt = db_session.query(DesignationBootstrapReceipt).one()

    receipt.content_digest = "0" * 64
    with pytest.raises(TypeError, match="append-only"):
        db_session.flush()
    db_session.rollback()

    with pytest.raises(TypeError, match="append-only"):
        db_session.execute(update(DesignationBootstrapReceipt).values(content_digest="0" * 64))
    db_session.rollback()
    with pytest.raises(TypeError, match="append-only"):
        db_session.execute(delete(DesignationBootstrapReceipt))
    db_session.rollback()

    receipt = db_session.query(DesignationBootstrapReceipt).one()
    db_session.delete(receipt)
    with pytest.raises(TypeError, match="append-only"):
        db_session.flush()
    db_session.rollback()


def test_apply_endpoint_reuses_upload_security_and_returns_aggregate_only(client, db_session):
    actor_program = _seed(db_session)
    official = _official(include_practice=False)
    salary = _salary(hours=())
    preview = build_designation_bootstrap_preview(
        db_session,
        official_content=official,
        salary_content=salary,
        academic_period="II/2026",
        effective_date=EFFECTIVE_DATE,
        program_identity=actor_program.code,
    )
    files = {
        "official_workbook": (
            "official.xlsx", official,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        "salary_workbook": (
            "salary.xlsx", salary,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }
    data = {
        "academic_period": "II/2026",
        "effective_date": "2026-08-21",
        "program_identity": "MED",
        "confirmation_digest": preview["preview_digest"],
    }

    response = client.post("/api/admin/academic-management/designation-bootstrap/apply", files=files, data=data)
    assert response.status_code == 200, response.text
    serialized = response.text
    assert "880001" not in serialized and "Private Theory Name" not in serialized

    token = client.headers.pop("Authorization")
    try:
        unauthorized = client.post(
            "/api/admin/academic-management/designation-bootstrap/apply", files=files, data=data,
        )
    finally:
        client.headers["Authorization"] = token
    assert unauthorized.status_code == 401
